from datetime import datetime, timedelta
import hashlib
import secrets
from sqlalchemy.orm import Session
from models import User, Room, Player


def hash_password(password: str) -> str:
    """Genera un hash seguro usando PBKDF2-HMAC-SHA256 con un salt de 16 bytes."""
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"{salt.hex()}${key.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica si una contraseña en texto plano coincide con el hash guardado."""
    if not password_hash:
        return False
    # Coincidencia directa en texto plano (compatibilidad con cuentas antiguas o creadas manualmente)
    if password_hash == password:
        return True
    if "$" not in password_hash:
        return False
    try:
        salt_hex, key_hex = password_hash.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return secrets.compare_digest(key, new_key)
    except Exception:
        return False


def register_user(db: Session, nombre: str, email: str, password: str) -> User:
    """Registra un nuevo usuario en la base de datos con contraseña hasheada."""
    email_clean = email.strip().lower()
    if db.query(User).filter(User.email.ilike(email_clean)).first():
        raise ValueError(f"Ya existe un usuario registrado con el correo '{email_clean}'.")

    pwd_hash = hash_password(password)
    user = User(
        nombre=nombre.strip(),
        email=email_clean,
        password_hash=pwd_hash
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Autentica a un usuario verificando su correo (case-insensitive) y contraseña."""
    email_clean = email.strip().lower()
    user = db.query(User).filter(User.email.ilike(email_clean)).first()
    if not user:
        return None
    if verify_password(password, user.password_hash):
        # Auto-actualizar hash si la cuenta venía en texto plano
        if user.password_hash == password:
            user.password_hash = hash_password(password)
            db.commit()
        return user
    return None


def request_password_reset(db: Session, email: str) -> tuple[str, User]:
    """Genera un código OTP de 6 dígitos con expiración de 15 minutos para el usuario."""
    email_clean = email.strip().lower()
    user = db.query(User).filter_by(email=email_clean).first()
    if not user:
        raise ValueError(f"No existe ningún usuario registrado con el correo '{email_clean}'.")

    token = f"{secrets.randbelow(900000) + 100000}"
    user.reset_token = token
    user.reset_token_expires = datetime.utcnow() + timedelta(minutes=15)
    db.commit()
    db.refresh(user)
    return token, user


def reset_password_with_token(db: Session, email: str, token: str, new_password: str) -> bool:
    """Valida el código OTP e impone la nueva contraseña para el usuario."""
    email_clean = email.strip().lower()
    user = db.query(User).filter_by(email=email_clean).first()
    if not user or not user.reset_token or not user.reset_token_expires:
        raise ValueError("No hay ninguna solicitud de restablecimiento activa.")

    if user.reset_token != token.strip():
        raise ValueError("El código de recuperación introducido no es válido.")

    if user.reset_token_expires < datetime.utcnow():
        raise ValueError("El código de recuperación ha caducado. Por favor solicita uno nuevo.")

    user.password_hash = hash_password(new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    return True


def obtener_estadisticas_usuario(db: Session, user_id: int) -> dict:
    """Calcula las estadísticas globales acumuladas del usuario e insignias desbloqueadas."""
    from collections import Counter
    from models import HistoryLog

    players = db.query(Player).filter_by(user_id=user_id).all()

    partidas_jugadas = len(players)
    total_kills = sum(p.bajas for p in players)

    partidas_ganadas = 0
    has_renegado = False
    has_unlucky = False
    has_concentrado = False
    has_killing_spree = False
    has_ace = False
    has_relampago = False
    has_loser = False

    for p in players:
        room = db.query(Room).get(p.room_id)
        
        # 1. Ganador, Renegado, Concentrado y Ace
        if room and room.estado == "finalizada" and p.estado == "vivo":
            partidas_ganadas += 1
            if p.bajas == 1:
                has_renegado = True
            
            if p.cambios_restantes == 2 and getattr(p, "cambios_realizados", 0) == 0:
                has_concentrado = True
            
            total_in_room = db.query(Player).filter_by(room_id=p.room_id).count()
            if total_in_room >= 3 and p.bajas == (total_in_room - 1):
                has_ace = True

        # 2. Unlucky (jugador con más bajas de la sala pero fuera del top 3)
        room_players = db.query(Player).filter_by(room_id=p.room_id).order_by(Player.bajas.desc()).all()
        if room_players:
            max_k = max(rp.bajas for rp in room_players)
            if p.bajas == max_k and p.bajas > 0:
                rank = 1
                prev_b = None
                p_pos = 0
                for idx, rp in enumerate(room_players, start=1):
                    if rp.bajas != prev_b:
                        rank = idx
                        prev_b = rp.bajas
                    if rp.id == p.id:
                        p_pos = rank
                        break
                if p_pos > 3:
                    has_unlucky = True

        # 3. Killing Spree y Asesino Relámpago (baja en < 2h)
        logs = db.query(HistoryLog).filter_by(room_id=p.room_id, asesino_id=p.id).all()
        dates = [l.fecha.date() for l in logs if l.fecha]
        counts = Counter(dates)
        if any(c >= 2 for c in counts.values()):
            has_killing_spree = True

        if room and logs:
            ref_time = room.fecha_inicio or getattr(p, "created_at", None)
            for l in logs:
                if l.fecha and ref_time:
                    diff_sec = (l.fecha - ref_time).total_seconds()
                    if 0 <= diff_sec <= 7200: # 2 horas
                        has_relampago = True
                        break

        # 4. Looser (eliminado en menos de 24h desde que se unió a la sala)
        if p.estado == "muerto" and p.fecha_eliminacion:
            p_created = getattr(p, "created_at", None) or (room.created_at if room else None)
            if p_created:
                diff_sec = (p.fecha_eliminacion - p_created).total_seconds()
                if 0 <= diff_sec <= 86400: # 24 horas
                    has_loser = True

    insignias = [
        # Logros Base
        {
            "nombre": "🩸 Primera Sangre",
            "descripcion": "Consigue tu primer asesinato en cualquier partida.",
            "desbloqueado": total_kills >= 1
        },
        {
            "nombre": "🔪 Asesino en Serie",
            "descripcion": "Acumula 5 o más bajas en tu historial global.",
            "desbloqueado": total_kills >= 5
        },
        {
            "nombre": "👑 Superviviente Supremo",
            "descripcion": "Gana al menos 1 partida como único superviviente.",
            "desbloqueado": partidas_ganadas >= 1
        },
        {
            "nombre": "🏆 Leyenda del Juego",
            "descripcion": "Gana 3 o más partidas en la plataforma.",
            "desbloqueado": partidas_ganadas >= 3
        },
        {
            "nombre": "🛡️ Veterano de Guerra",
            "descripcion": "Participa en 5 o más salas de juego.",
            "desbloqueado": partidas_jugadas >= 5
        },
        {
            "nombre": "🎲 Estratega del Cambio",
            "descripcion": "Ejecuta al menos 1 cambio individual de arma.",
            "desbloqueado": any((p.cambios_restantes < 2 or getattr(p, "cambios_realizados", 0) > 0) for p in players)
        },

        # Logros Especiales Solicitados
        {
            "nombre": "👤 Renegado",
            "descripcion": "Gana una partida realizando únicamente la baja final del último jugador.",
            "desbloqueado": has_renegado
        },
        {
            "nombre": "🍀 Unlucky",
            "descripcion": "Sé el jugador con más bajas acumuladas de la sala pero queda fuera del podio (puesto 4º o inferior).",
            "desbloqueado": has_unlucky
        },
        {
            "nombre": "🧘 Concentrado",
            "descripcion": "Gana una partida sin utilizar ningún reroll de objeto en tu arma asignada.",
            "desbloqueado": has_concentrado
        },
        {
            "nombre": "🔥 Killing Spree",
            "descripcion": "Elimina a 2 o más jugadores en un mismo día en cualquier sala.",
            "desbloqueado": has_killing_spree
        },
        {
            "nombre": "⚔️ Doublekill",
            "descripcion": "Elimina a 2 jugadores en una misma partida.",
            "desbloqueado": any(p.bajas >= 2 for p in players)
        },
        {
            "nombre": "⚔️ Triplekill",
            "descripcion": "Elimina a 3 jugadores en una misma partida.",
            "desbloqueado": any(p.bajas >= 3 for p in players)
        },
        {
            "nombre": "⚔️ Quadrakill",
            "descripcion": "Elimina a 4 jugadores en una misma partida.",
            "desbloqueado": any(p.bajas >= 4 for p in players)
        },
        {
            "nombre": "🔥 Pentakill",
            "descripcion": "Elimina a 5 o más jugadores en una misma partida.",
            "desbloqueado": any(p.bajas >= 5 for p in players)
        },
        {
            "nombre": "💥 Ace",
            "descripcion": "Elimina a absolutamente todos los oponentes participantes de la partida.",
            "desbloqueado": has_ace
        },
        {
            "nombre": "🎲 Indeciso",
            "descripcion": "Haz reroll de arma 3 o más veces sobre el mismo jugador en una partida.",
            "desbloqueado": any(getattr(p, "cambios_realizados", 0) >= 3 for p in players)
        },
        {
            "nombre": "⚡ Asesino Relámpago",
            "descripcion": "Elimina a tu víctima en menos de 2 horas desde el inicio de la partida o asignación.",
            "desbloqueado": has_relampago
        },
        {
            "nombre": "💀 Looser",
            "descripcion": "Sé eliminado en menos de 24 horas desde que te uniste a la sala.",
            "desbloqueado": has_loser
        }
    ]

    return {
        "partidas_jugadas": partidas_jugadas,
        "partidas_ganadas": partidas_ganadas,
        "total_kills": total_kills,
        "insignias": insignias,
        "players": players
    }

