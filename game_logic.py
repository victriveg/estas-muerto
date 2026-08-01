import random
import string
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import Room, Player, Assignment, GameObject, HistoryLog, KillClaim


def generar_codigo_pin(db: Session) -> str:
    """Genera un código PIN aleatorio de 6 caracteres alfanuméricos único en la base de datos."""
    chars = string.ascii_uppercase + string.digits
    while True:
        pin = "".join(random.choices(chars, k=6))
        if not db.query(Room).filter_by(codigo=pin).first():
            return pin



def obtener_objetos_disponibles(db: Session, room_id: int) -> list[str]:
    """Obtiene la lista de objetos globales (room_id is Null) y específicos de la sala."""
    objetos_db = db.query(GameObject).filter(
        (GameObject.room_id == None) | (GameObject.room_id == room_id)
    ).all()
    return [obj.nombre_objeto for obj in objetos_db]


def generar_ciclo_cerrado(db: Session, room_id: int) -> list[Assignment]:
    """
    Genera un ciclo Hamiltoniano (P1 -> P2 -> ... -> Pn -> P1) 
    para todos los jugadores 'vivos' de la sala especificada (room_id).
    """
    # 1. Obtener jugadores vivos de la sala
    vivos = db.query(Player).filter_by(room_id=room_id, estado="vivo").all()
    if len(vivos) < 2:
        raise ValueError("Se necesitan al menos 2 jugadores vivos en la sala para iniciar.")

    # 2. Obtener catálogo de armas
    objetos = obtener_objetos_disponibles(db, room_id)
    if not objetos:
        raise ValueError("No hay objetos/armas registrados para esta sala.")

    # 3. Eliminar asignaciones previas de la sala
    db.query(Assignment).filter_by(room_id=room_id).delete()

    # 4. Barajar jugadores
    vivos_shuffled = vivos.copy()
    random.shuffle(vivos_shuffled)
    n = len(vivos_shuffled)

    # Pool de objetos
    objetos_pool = objetos.copy()
    while len(objetos_pool) < n:
        objetos_pool.extend(objetos)
    random.shuffle(objetos_pool)

    # 5. Crear asignaciones en ciclo
    nuevas_asignaciones = []
    for i in range(n):
        asesino = vivos_shuffled[i]
        victima = vivos_shuffled[(i + 1) % n]
        arma = objetos_pool[i]

        asig = Assignment(
            room_id=room_id,
            asesino_id=asesino.id,
            victima_id=victima.id,
            objeto=arma
        )
        db.add(asig)
        nuevas_asignaciones.append(asig)

    # Actualizar estado de la sala y restaurar 1 reroll gratuito a supervivientes (máximo 1)
    room = db.query(Room).get(room_id)
    if room:
        if room.estado == "en_juego":
            for p_v in vivos:
                if getattr(p_v, "cambios_gratuitos", 0) < 1:
                    p_v.cambios_gratuitos = 1
                p_v.cambios_restantes = (p_v.cambios_gratuitos or 0) + (getattr(p_v, "cambios_bonus", 0) or 0)
        else:
            room.estado = "en_juego"

        now = datetime.utcnow()
        if not room.fecha_inicio:
            room.fecha_inicio = now
        room.ultima_rotacion = now

    db.commit()
    return nuevas_asignaciones


def calcular_proxima_rotacion(room: Room) -> datetime | None:
    """
    Calcula la fecha y hora de la próxima rotación (cada 3 días a las 8:00 AM) 
    basada en la fecha de la última rotación o inicio de partida.
    """
    if room.estado != "en_juego":
        return None

    base_dt = room.ultima_rotacion or room.fecha_inicio or room.created_at
    if not base_dt:
        return None

    target_dt = base_dt + timedelta(days=3)
    proxima_8am = target_dt.replace(hour=8, minute=0, second=0, microsecond=0)
    
    if proxima_8am <= base_dt:
        proxima_8am += timedelta(days=1)
        
    return proxima_8am


def verificar_rotacion_automatica(db: Session, room_id: int) -> bool:
    """
    Comprueba si se debe ejecutar la rotación automática (cada 3 días a las 8:00 AM).
    Si corresponde, la ejecuta y devuelve True.
    """
    room = db.query(Room).get(room_id)
    if not room or room.estado != "en_juego":
        return False

    proxima_rot = calcular_proxima_rotacion(room)
    if not proxima_rot:
        return False

    now = datetime.utcnow()
    if now >= proxima_rot:
        generar_ciclo_cerrado(db, room_id)
        room.ultima_rotacion = now
        db.commit()
        return True

    return False



def registrar_baja(db: Session, room_id: int, asesino_player_id: int) -> dict:
    """
    Procesa el asesinato en una sala concreta:
    - La víctima pasa a estado 'muerto'.
    - El asesino hereda la víctima y el arma que tenía la víctima caída.
    - Se elimina la asignación de la víctima y se registra en el Historial de la sala.
    """
    # 1. Buscar la asignación activa del asesino en esta sala
    asig_asesino = db.query(Assignment).filter_by(room_id=room_id, asesino_id=asesino_player_id).first()
    if not asig_asesino:
        raise ValueError("No se encontró la asignación activa del asesino en esta sala.")

    victima_player_id = asig_asesino.victima_id
    objeto_usado = asig_asesino.objeto

    # 2. Buscar la asignación de la víctima en esta sala para heredar su objetivo
    asig_victima = db.query(Assignment).filter_by(room_id=room_id, asesino_id=victima_player_id).first()
    if not asig_victima:
        raise ValueError("No se encontró la asignación de la víctima en esta sala.")

    siguiente_victima_id = asig_victima.victima_id
    siguiente_objeto = asig_victima.objeto

    # 3. Marcar a la víctima como muerta
    victima_player = db.query(Player).get(victima_player_id)
    victima_player.estado = "muerto"
    victima_player.fecha_eliminacion = datetime.utcnow()

    # 4. Incrementar bajas del asesino y otorgar +1 cambio de arma bonus por baja
    asesino_player = db.query(Player).get(asesino_player_id)
    asesino_player.bajas += 1
    if hasattr(asesino_player, "cambios_bonus"):
        asesino_player.cambios_bonus = (asesino_player.cambios_bonus or 0) + 1
    asesino_player.cambios_restantes = (getattr(asesino_player, "cambios_gratuitos", 1) or 0) + (getattr(asesino_player, "cambios_bonus", 0) or 0)

    # 5. Herencia: actualizar la asignación del asesino con la víctima y arma heredadas
    asig_asesino.victima_id = siguiente_victima_id
    asig_asesino.objeto = siguiente_objeto

    # 6. Eliminar la asignación de la víctima caída
    db.delete(asig_victima)

    # 7. Registrar en el historial de la sala
    log = HistoryLog(
        room_id=room_id,
        asesino_id=asesino_player_id,
        victima_id=victima_player_id,
        objeto=objeto_usado,
        fecha=datetime.utcnow()
    )
    db.add(log)

    # 8. Comprobar si la partida ha finalizado (queda 1 superviviente)
    vivos_restantes = db.query(Player).filter_by(room_id=room_id, estado="vivo").all()
    partida_finalizada = False
    ganador = None

    if len(vivos_restantes) == 1:
        partida_finalizada = True
        ganador = vivos_restantes[0]
        db.delete(asig_asesino)
        room = db.query(Room).get(room_id)
        if room:
            room.estado = "finalizada"

    db.commit()

    return {
        "partida_finalizada": partida_finalizada,
        "ganador": ganador,
        "siguiente_victima_id": siguiente_victima_id,
        "siguiente_objeto": siguiente_objeto,
        "vivos_restantes": len(vivos_restantes)
    }


def ejecutar_cambio_arma(db: Session, room_id: int, player_id: int, es_host: bool = False) -> tuple[str, int]:
    """
    Ejecuta el cambio de arma individual para un jugador en una sala.
    Consume primero el cambio gratuito (si disponible) y luego los cambios bonus por bajas.
    """
    player = db.query(Player).filter_by(id=player_id, room_id=room_id).first()
    if not player:
        raise ValueError("El jugador no existe en esta sala.")

    gratuitos = getattr(player, "cambios_gratuitos", 1) or 0
    bonus = getattr(player, "cambios_bonus", 0) or 0
    total_disponibles = gratuitos + bonus

    if not es_host and total_disponibles <= 0:
        raise ValueError("El jugador no tiene cambios de arma disponibles en esta sala.")

    asig = db.query(Assignment).filter_by(room_id=room_id, asesino_id=player_id).first()
    if not asig:
        raise ValueError("El jugador no tiene una asignación activa en esta sala.")

    objetos = obtener_objetos_disponibles(db, room_id)
    if not objetos:
        raise ValueError("No hay objetos disponibles en el catálogo.")

    # Excluir objeto actual
    disponibles = [o for o in objetos if o != asig.objeto]
    nuevo_objeto = random.choice(disponibles) if disponibles else random.choice(objetos)

    # Actualizar asignación y descontar primero el cambio gratuito, luego bonus
    asig.objeto = nuevo_objeto
    if not es_host:
        if getattr(player, "cambios_gratuitos", 0) > 0:
            player.cambios_gratuitos -= 1
        elif getattr(player, "cambios_bonus", 0) > 0:
            player.cambios_bonus -= 1

    if hasattr(player, "cambios_realizados"):
        player.cambios_realizados = (player.cambios_realizados or 0) + 1

    # Sincronizar total de cambios restantes
    player.cambios_restantes = (getattr(player, "cambios_gratuitos", 0) or 0) + (getattr(player, "cambios_bonus", 0) or 0)

    db.commit()
    return nuevo_objeto, player.cambios_restantes


def solicitar_baja(db: Session, room_id: int, asesino_player_id: int) -> KillClaim:
    """Crea una solicitud de baja pendiente para que la víctima la confirme."""
    asig = db.query(Assignment).filter_by(room_id=room_id, asesino_id=asesino_player_id).first()
    if not asig:
        raise ValueError("No tienes una asignación activa en esta sala.")

    # Verificar si ya existe una solicitud pendiente
    existente = db.query(KillClaim).filter_by(
        room_id=room_id,
        asesino_id=asesino_player_id,
        victima_id=asig.victima_id,
        estado="pendiente"
    ).first()
    if existente:
        return existente

    claim = KillClaim(
        room_id=room_id,
        asesino_id=asesino_player_id,
        victima_id=asig.victima_id,
        estado="pendiente"
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def confirmar_baja_claim(db: Session, claim_id: int) -> dict:
    """Procesa la baja tras la confirmación explícita de la víctima."""
    claim = db.query(KillClaim).get(claim_id)
    if not claim or claim.estado != "pendiente":
        raise ValueError("Solicitud no válida o ya procesada.")

    res = registrar_baja(db, claim.room_id, claim.asesino_id)
    claim.estado = "confirmado"
    db.commit()
    return res


def rechazar_baja_claim(db: Session, claim_id: int):
    """Rechaza la solicitud de baja pendiente."""
    claim = db.query(KillClaim).get(claim_id)
    if claim:
        claim.estado = "rechazado"
        db.commit()

