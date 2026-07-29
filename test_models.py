"""
Script de prueba para verificar los modelos SQLAlchemy y la lógica de juego multisala en rama v2.
"""
from database import engine, Base, SessionLocal
from models import User, Room, Player, GameObject, Assignment, HistoryLog
from game_logic import generar_ciclo_cerrado, registrar_baja, ejecutar_cambio_arma


def run_tests():
    # 1. Crear tablas en memoria (SQLite)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("✅ 1. Tablas creadas correctamente.")

    # 2. Crear Usuarios
    u1 = User(nombre="Alicia", email="alicia@example.com")
    u2 = User(nombre="Bob", email="bob@example.com")
    u3 = User(nombre="Carlos", email="carlos@example.com")
    db.add_all([u1, u2, u3])
    db.commit()

    print("✅ 2. Usuarios creados.")

    # 3. Crear Sala (Room)
    room1 = Room(codigo="SALA01", nombre="Partida de Prueba")
    db.add(room1)
    db.commit()

    # 4. Crear Objetos globales
    o1 = GameObject(nombre_objeto="Cuchara de madera")
    o2 = GameObject(nombre_objeto="Taza roja")
    o3 = GameObject(nombre_objeto="Calcetín desparejado")
    db.add_all([o1, o2, o3])
    db.commit()

    # 5. Unir Usuarios a la Sala (Crear Players)
    p1 = Player(user_id=u1.id, room_id=room1.id, cambios_restantes=2)
    p2 = Player(user_id=u2.id, room_id=room1.id, cambios_restantes=2)
    p3 = Player(user_id=u3.id, room_id=room1.id, cambios_restantes=2)
    db.add_all([p1, p2, p3])
    db.commit()

    print("✅ 3. Jugadores unidos a la Sala 1.")

    # 6. Probar inicio de partida (Ciclo Hamiltoniano)
    asignaciones = generar_ciclo_cerrado(db, room1.id)
    assert len(asignaciones) == 3, "Deben crearse 3 asignaciones."

    # Verificar que el ciclo se cierra (P1 -> P2 -> P3 -> P1)
    asesinos_set = {a.asesino_id for a in asignaciones}
    victimas_set = {a.victima_id for a in asignaciones}
    assert len(asesinos_set) == 3 and len(victimas_set) == 3, "Todos los jugadores deben tener objetivo."

    print("✅ 4. Ciclo Hamiltoniano generado correctamente.")

    # 7. Probar cambio individual de arma
    nuevo_obj, cambios_left = ejecutar_cambio_arma(db, room1.id, p1.id)
    assert cambios_left == 1, "Debe quedar 1 cambio restante."
    print(f"✅ 5. Reroll realizado. Nueva arma de P1: {nuevo_obj} (Cambios restantes: {cambios_left})")

    # 8. Probar registro de baja y herencia en la sala
    res = registrar_baja(db, room1.id, p1.id)
    assert res["vivos_restantes"] == 2, "Deben quedar 2 vivos."
    assert not res["partida_finalizada"], "La partida aún no finaliza."

    print("✅ 6. Baja y herencia de víctima procesadas correctamente.")

    db.close()
    print("\n🎉 ¡TODAS LAS PRUEBAS DE MODELOS Y LÓGICA PASARON EXITOSAMENTE!")


if __name__ == "__main__":
    run_tests()
