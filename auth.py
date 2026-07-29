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
    if not password_hash or "$" not in password_hash:
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
    if db.query(User).filter_by(email=email_clean).first():
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
    """Autentica a un usuario verificando su correo y contraseña."""
    email_clean = email.strip().lower()
    user = db.query(User).filter_by(email=email_clean).first()
    if not user:
        return None
    if verify_password(password, user.password_hash):
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


from models import User, Room, Player

...
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
    players = db.query(Player).filter_by(user_id=user_id).all()

    partidas_jugadas = len(players)
    total_kills = sum(p.bajas for p in players)

    partidas_ganadas = 0
    for p in players:
        room = db.query(Room).get(p.room_id)
        if room and room.estado == "finalizada" and p.estado == "vivo":
            partidas_ganadas += 1

    insignias = [
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
            "desbloqueado": any(p.cambios_restantes < 2 for p in players)
        }
    ]

    return {
        "partidas_jugadas": partidas_jugadas,
        "partidas_ganadas": partidas_ganadas,
        "total_kills": total_kills,
        "insignias": insignias,
        "players": players
    }

