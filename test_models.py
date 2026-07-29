"""
Script de prueba integral para verificar todos los modelos, lógica multisala, autenticación, 
sistema dual de bajas y rotación automática en la rama v2.
"""
from database import engine, Base, SessionLocal
from models import User, Room, Player, GameObject, Assignment, HistoryLog, KillClaim
import game_logic
import auth


def run_tests():
    # 1. Crear tablas en memoria (SQLite)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("✅ 1. Tablas SQL creadas correctamente.")

    # 2. Probar Registro e Inicio de Sesión de Usuarios
    u1 = auth.register_user(db, "Alicia", "alicia@example.com", "pass1234")
    u2 = auth.register_user(db, "Bob", "bob@example.com", "pass1234")
    u3 = auth.register_user(db, "Carlos", "carlos@example.com", "pass1234")
    
    assert auth.authenticate_user(db, "alicia@example.com", "pass1234") is not None, "Autenticación fallida."
    assert auth.authenticate_user(db, "alicia@example.com", "pass_wrong") is None, "Autenticación incorrecta no rechazada."

    print("✅ 2. Registro y Autenticación de usuarios verificados.")

    # 3. Probar Restablecimiento de Contraseña (OTP)
    token, u_reset = auth.request_password_reset(db, "alicia@example.com")
    assert len(token) == 6, "El token OTP debe ser de 6 dígitos."
    assert auth.reset_password_with_token(db, "alicia@example.com", token, "newpass5678"), "Cambio de contraseña fallido."
    assert auth.authenticate_user(db, "alicia@example.com", "newpass5678") is not None, "Nueva contraseña no válida."

    print("✅ 3. Restablecimiento autónomo de contraseña (OTP) verificado.")

    # 4. Crear Sala con PIN automático y Host
    pin_code = game_logic.generar_codigo_pin(db)
    assert len(pin_code) == 6, "El código PIN debe ser de 6 caracteres."
    room1 = Room(codigo=pin_code, nombre="Partida de Prueba v2", host_id=u1.id, modo_ciego=True)
    db.add(room1)
    db.commit()

    print(f"✅ 4. Sala creada con PIN: {pin_code} y Modo Ciego activado.")

    # 5. Crear Objetos globales y de la sala
    o1 = GameObject(nombre_objeto="Cuchara de madera")
    o2 = GameObject(nombre_objeto="Taza roja")
    o3 = GameObject(nombre_objeto="Calcetín desparejado")
    db.add_all([o1, o2, o3])
    db.commit()

    # 6. Unir Usuarios a la Sala
    p1 = Player(user_id=u1.id, room_id=room1.id, cambios_restantes=2)
    p2 = Player(user_id=u2.id, room_id=room1.id, cambios_restantes=2)
    p3 = Player(user_id=u3.id, room_id=room1.id, cambios_restantes=2)
    db.add_all([p1, p2, p3])
    db.commit()

    print("✅ 5. Jugadores unidos a la Sala 1.")

    # 7. Probar inicio de partida (Ciclo Hamiltoniano)
    asignaciones = game_logic.generar_ciclo_cerrado(db, room1.id)
    assert len(asignaciones) == 3, "Deben crearse 3 asignaciones."
    assert room1.estado == "en_juego", "La sala debe pasar a 'en_juego'."

    print("✅ 6. Ciclo Hamiltoniano generado y partida iniciada.")

    # 8. Probar Solicitud y Confirmación de Asesinato (Sistema Dual)
    claim = game_logic.solicitar_baja(db, room1.id, p1.id)
    assert claim.estado == "pendiente", "La baja debe estar pendiente de confirmación."

    res = game_logic.confirmar_baja_claim(db, claim.id)
    assert res["vivos_restantes"] == 2, "Deben quedar 2 jugadores vivos tras la baja."
    assert claim.estado == "confirmado", "El estado de la baja debe ser 'confirmado'."

    print("✅ 7. Solicitud y Confirmación anónima de baja procesadas.")

    # 9. Probar cambio individual de arma
    nuevo_obj, cambios_left = game_logic.ejecutar_cambio_arma(db, room1.id, p1.id)
    assert cambios_left == 1, "Debe quedar 1 cambio restante."

    print(f"✅ 8. Reroll de arma realizado con éxito (Nueva arma: {nuevo_obj}).")

    # 10. Probar Estadísticas de Jugador e Insignias
    stats = auth.obtener_estadisticas_usuario(db, u1.id)
    assert stats["total_kills"] == 1, "Alicia debe tener 1 kill."
    primera_sangre = [b for b in stats["insignias"] if b["nombre"] == "🩸 Primera Sangre"][0]
    assert primera_sangre["desbloqueado"], "La insignia 'Primera Sangre' debe estar desbloqueada."

    print("✅ 9. Estadísticas e Insignias del Perfil de Usuario calculadas correctamente.")

    # 11. Probar Cálculo de Próxima Rotación
    proxima_rot = game_logic.calcular_proxima_rotacion(room1)
    assert proxima_rot is not None, "Debe existir fecha de próxima rotación programada."
    assert proxima_rot.hour == 8, "La hora de rotación debe ser las 8:00 AM."

    print(f"✅ 10. Próxima rotación calculada a las 8:00 AM ({proxima_rot.strftime('%Y-%m-%d %H:%M')}).")

    db.close()
    print("\n🎉 ¡TODAS LAS PRUEBAS INTEGRALES DE LA RAMA V2 PASARON EXITOSAMENTE SIN ERRORES!")


if __name__ == "__main__":
    run_tests()
