import streamlit as st
import pandas as pd
import time
from datetime import datetime
import email_service
from database import SessionLocal, init_db
from models import User, Room, Player, Assignment, GameObject, HistoryLog, KillClaim
import game_logic
import auth

# Configuración de página adaptada a móviles
st.set_page_config(
    page_title="Estás Muerto 🔪 - Panel de Control",
    page_icon="🔪",
    layout="centered"
)

# ---------------------------------------------------------
# AJUSTES DE ESTILO CSS: OCULTAR GITHUB, FORK, BADGES DE STREAMLIT CLOUD Y FOOTER
# (Mantiene visible únicamente el menú nativo de 3 puntos #MainMenu para el cambio de tema)
# ---------------------------------------------------------
st.markdown("""
<style>
/* 1. Ocultar todos los enlaces y botones de GitHub, Fork, Streamlit Cloud y perfil */
header a,
[data-testid="stHeader"] a,
[data-testid="stToolbar"] a,
.viewerBadge_container__1QSob,
.styles_viewerBadge__1yB5_,
[class*="viewerBadge"],
[class*="stAppHeader"] a,
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
a[href*="github.com"],
a[href*="streamlit.io"],
a[href*="share.streamlit.io"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}

/* 2. Ocultar todo el pie de página inferior (footer) */
footer,
[data-testid="stFooter"] {
    display: none !important;
    visibility: hidden !important;
}

/* 3. Asegurar que SOLO el menú nativo de 3 puntos permanezca visible y funcional */
#MainMenu,
[data-testid="stMainMenu"],
button[aria-label="Main menu"],
button[aria-label="Menú principal"] {
    display: inline-flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
}
</style>
""", unsafe_allow_html=True)

# Inicializar tablas en la base de datos (PostgreSQL / SQLite)
init_db()

# Abrir sesión de base de datos
db = SessionLocal()

st.title("🔪 Estás Muerto")
st.caption("Panel de control relacional multisala (SQLAlchemy)")

# ---------------------------------------------------------
# DETECCIÓN DE PARÁMETROS EN URL (?sala=CODIGO)
# ---------------------------------------------------------
url_params = st.query_params
url_pin = url_params.get("sala") or url_params.get("pin")
if url_pin:
    url_pin = url_pin.strip().upper()

# ---------------------------------------------------------
# AUTENTICACIÓN Y GESTIÓN DE SESIÓN DE USUARIO
# ---------------------------------------------------------
current_user_id = st.session_state.get("user_id")
current_user = db.query(User).get(current_user_id) if current_user_id else None

if not current_user:
    st.info("👋 Por favor inicia sesión o regístrate para acceder al panel del juego.")

    tab_login, tab_register = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])

    with tab_login:
        st.subheader("🔑 Iniciar Sesión")
        with st.form("form_login", clear_on_submit=False):
            email_in = st.text_input("Correo Electrónico", key="login_email")
            pass_in = st.text_input("Contraseña", type="password", key="login_pass")
            btn_login = st.form_submit_button("🚀 Entrar", type="primary", use_container_width=True)

        if btn_login:
            e_clean = email_in.strip() if email_in else ""
            p_clean = pass_in.strip() if pass_in else ""
            if e_clean and p_clean:
                u = auth.authenticate_user(db, e_clean, p_clean)
                if u:
                    st.session_state["user_id"] = u.id
                    st.success(f"¡Bienvenido/a de nuevo, **{u.nombre}**!")
                    st.rerun()
                else:
                    st.error("❌ Correo electrónico o contraseña incorrectos.")
            else:
                st.warning("Rellena todos los campos.")

        st.markdown("---")
        with st.expander("🔑 ¿Olvidaste tu contraseña?", expanded=False):
            st.caption("Solicita un código de recuperación de 6 dígitos que enviaremos a tu correo electrónico.")
            with st.form("form_request_reset", clear_on_submit=False):
                reset_email = st.text_input("Ingresa tu Correo Electrónico", key="reset_email_input")
                btn_send_reset = st.form_submit_button("📩 Enviar Código de Recuperación", use_container_width=True)
            
            if btn_send_reset:
                re_clean = reset_email.strip() if reset_email else ""
                if re_clean:
                    try:
                        token, u_reset = auth.request_password_reset(db, re_clean)
                        email_service.send_password_reset_email(u_reset.email, u_reset.nombre, token)
                        st.success(f"📩 Código de 6 dígitos enviado a **{u_reset.email}**. Revisa tu bandeja de entrada.")
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Escribe tu correo electrónico.")

            st.markdown("---")
            st.caption("Ingresa el código OTP recibido para cambiar tu contraseña:")
            with st.form("form_confirm_reset", clear_on_submit=False):
                col_r1, col_r2 = st.columns(2)
                reset_code_in = col_r1.text_input("Código de 6 dígitos", key="reset_code_in")
                new_pass_in = col_r2.text_input("Nueva Contraseña", type="password", key="new_pass_in")
                btn_confirm_reset = st.form_submit_button("🔒 Restablecer Contraseña", type="primary", use_container_width=True)

            if btn_confirm_reset:
                re_clean = reset_email.strip() if reset_email else ""
                rc_clean = reset_code_in.strip() if reset_code_in else ""
                np_clean = new_pass_in.strip() if new_pass_in else ""
                if re_clean and rc_clean and np_clean:
                    try:
                        auth.reset_password_with_token(db, re_clean, rc_clean, np_clean)
                        st.success("🎉 ¡Contraseña restablecida con éxito! Ya puedes iniciar sesión con tu nueva clave.")
                    except Exception as e:
                        st.error(f"Error al restablecer: {e}")
                else:
                    st.warning("Completa todos los campos para restablecer la contraseña.")

    with tab_register:
        st.subheader("📝 Crear Cuenta")
        with st.form("form_register", clear_on_submit=False):
            name_reg = st.text_input("Tu Nombre / Apodo", key="reg_name")
            email_reg = st.text_input("Correo Electrónico", key="reg_email")
            pass_reg = st.text_input("Contraseña", type="password", key="reg_pass")
            pass_reg_conf = st.text_input("Confirmar Contraseña", type="password", key="reg_pass_conf")
            btn_reg = st.form_submit_button("➕ Crear Cuenta", type="primary", use_container_width=True)

        if btn_reg:
            name_clean = name_reg.strip() if name_reg else ""
            email_clean = email_reg.strip() if email_reg else ""
            pass_clean = pass_reg.strip() if pass_reg else ""
            conf_clean = pass_reg_conf.strip() if pass_reg_conf else ""

            if not (name_clean and email_clean and pass_clean and conf_clean):
                st.warning("Por favor completa todos los campos.")
            elif pass_clean != conf_clean:
                st.error("❌ Las contraseñas no coinciden.")
            elif len(pass_clean) < 4:
                st.error("❌ La contraseña debe tener al menos 4 caracteres.")
            else:
                try:
                    u = auth.register_user(db, name_clean, email_clean, pass_clean)
                    st.session_state["user_id"] = u.id
                    st.success(f"¡Cuenta creada con éxito! Bienvenido/a, **{u.nombre}**.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar: {e}")

    db.close()
    st.stop()  # Detener ejecución si no hay usuario autenticado

# ---------------------------------------------------------
# USUARIO AUTENTICADO
# ---------------------------------------------------------
st.sidebar.markdown(f"👤 **Usuario:** `{current_user.nombre}`\n\n📧 `{current_user.email}`")
if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
    st.session_state.pop("user_id", None)
    st.session_state.pop("active_room_id", None)
    st.rerun()

st.sidebar.markdown("---")

# ---------------------------------------------------------
# UNIRSE A SALA CON CÓDIGO PIN (SIDEBAR)
# ---------------------------------------------------------
st.sidebar.header("🎮 Unirse a una Sala por PIN")
with st.sidebar.expander("🔑 Introducir Código PIN", expanded=bool(url_pin)):
    pin_input_val = url_pin if url_pin else ""
    pin_entered = st.text_input("Código PIN de 6 caracteres", value=pin_input_val, key="sidebar_pin_input")
    if st.button("🚀 Unirme a la Sala", use_container_width=True, key="btn_join_pin"):
        if pin_entered:
            pin_clean = pin_entered.strip().upper()
            room_found = db.query(Room).filter_by(codigo=pin_clean).first()
            if room_found:
                player_existing = db.query(Player).filter_by(user_id=current_user.id, room_id=room_found.id).first()
                if not player_existing:
                    p_new = Player(user_id=current_user.id, room_id=room_found.id, estado="vivo", bajas=0, cambios_restantes=2)
                    db.add(p_new)
                    db.commit()
                    st.success(f"¡Te has inscrito en **{room_found.nombre}**!")
                else:
                    st.info(f"Ya formas parte de **{room_found.nombre}**.")
                
                st.session_state["active_room_id"] = room_found.id
                st.rerun()
            else:
                st.error("❌ Código PIN no válido o sala inexistente.")
        else:
            st.warning("Escribe el código PIN.")

st.sidebar.markdown("---")

# ---------------------------------------------------------
# GESTIÓN Y SELECCIÓN DE SALA ACTIVA
# ---------------------------------------------------------
salas = db.query(Room).all()
if not salas:
    def_room = Room(codigo="SALA01", nombre="Sala Principal", estado="espera", host_id=current_user.id, modo_ciego=False)
    db.add(def_room)
    db.commit()
    db.refresh(def_room)
    salas = [def_room]

# Determinar índice por defecto de la sala activa
opciones_salas = {f"{r.nombre} [{r.codigo}] ({r.estado.upper()})": r.id for r in salas}
id_lista = list(opciones_salas.values())

active_room_id_session = st.session_state.get("active_room_id")
default_idx = 0
if active_room_id_session and active_room_id_session in id_lista:
    default_idx = id_lista.index(active_room_id_session)

st.sidebar.header("🏠 Tus Salas")
sala_sel_key = st.sidebar.selectbox("Seleccionar Sala Activa:", list(opciones_salas.keys()), index=default_idx)
room_id = opciones_salas[sala_sel_key]
st.session_state["active_room_id"] = room_id
room_actual = db.query(Room).get(room_id)

if not room_actual:
    st.session_state.pop("active_room_id", None)
    st.rerun()

if not room_actual.host_id:
    room_actual.host_id = current_user.id
    db.commit()

# ---------------------------------------------------------
# VERIFICACIÓN DE ROTACIÓN AUTOMÁTICA CADA 3 DÍAS A LAS 8:00 AM
# ---------------------------------------------------------
auto_rotated = game_logic.verificar_rotacion_automatica(db, room_id)
if auto_rotated:
    st.success("🔄 **¡ROTACIÓN AUTOMÁTICA EJECUTADA!** Al cumplirse 3 días (8:00 AM), se han reordenado los objetivos y armas de esta sala.")

host_nombre = room_actual.host.nombre if room_actual.host else "Sin Host"
proxima_rot = game_logic.calcular_proxima_rotacion(room_actual)
proxima_rot_str = proxima_rot.strftime("%Y-%m-%d %H:%M") if proxima_rot else "No programada"
modo_ciego_txt = "🎭 **Activado**" if room_actual.modo_ciego else "👁️ **Desactivado**"

# Info de la sala en Sidebar
st.sidebar.info(f"**Sala Activa:** {room_actual.nombre}\n\n🔑 **PIN:** `{room_actual.codigo}`\n\n👑 **Host:** {host_nombre}\n\n🎭 **Asesino Ciego:** {modo_ciego_txt}\n\n📌 **Estado:** `{room_actual.estado}`\n\n⏱️ **Próxima Rotación (8am):** `{proxima_rot_str}`")

is_host = (current_user.id == room_actual.host_id)
player_active = db.query(Player).filter_by(user_id=current_user.id, room_id=room_id).first()

# ---------------------------------------------------------
# TARJETA DESTACADA: MI MISIÓN SECRETA
# ---------------------------------------------------------
if player_active and player_active.estado == "vivo" and room_actual.estado == "en_juego":
    asig_secret = db.query(Assignment).filter_by(room_id=room_id, asesino_id=player_active.id).first()
    if asig_secret:
        victima_secret = db.query(Player).get(asig_secret.victima_id)
        with st.expander("🕵️ **MI MISIÓN SECRETA** (Pulsa para ver/ocultar tu objetivo)", expanded=False):
            st.markdown(f"""
            <div style="background: #2a2a2a; padding: 15px; border-radius: 10px; border-left: 5px solid #e74c3c;">
                <p style="margin: 5px 0; font-size: 16px;">🎯 <b>Tu Víctima:</b> <span style="color: #ff6b6b; font-size: 22px; font-weight: bold;">{victima_secret.user.nombre}</span></p>
                <p style="margin: 5px 0; font-size: 16px;">🛋️ <b>Tu Arma / Objeto:</b> <span style="color: #fca311; font-size: 22px; font-weight: bold;">{asig_secret.objeto}</span></p>
                <p style="margin: 5px 0; font-size: 14px; color: #4cc9f0;">🔄 <b>Cambios restantes de arma:</b> {player_active.cambios_restantes}</p>
            </div>
            """, unsafe_allow_html=True)
            st.caption("🔒 Mantén esta pantalla oculta de miradas curiosas.")

# ---------------------------------------------------------
# INTERFAZ PRINCIPAL EN PESTAÑAS
# ---------------------------------------------------------
tab_estado, tab_gestion, tab_setup, tab_rotacion, tab_perfil = st.tabs([
    "🏆 Estado", "🔪 Baja", "⚙️ Setup", "🔄 Rotación/Cambio", "👤 Mi Perfil"
])

# =========================================================
# PESTAÑA 1: ESTADO Y RANKING
# =========================================================
with tab_estado:
    st.subheader(f"🟢 Supervivientes - {room_actual.nombre}")
    
    # Comprobar Modo Asesino Ciego en partida activa
    if room_actual.modo_ciego and room_actual.estado == "en_juego" and not is_host:
        st.warning("🎭 **MODO ASESINO CIEGO ACTIVADO**")
        st.markdown("""
        *Las identidades de los supervivientes y la lista de jugadores vivos permanecen ocultas en las sombras.* 
        ¡Solo sabrás quién sigue con vida cuando aparezcan las bajas en el historial!
        """)
    else:
        if room_actual.modo_ciego and is_host:
            st.caption("👑 *(Visión exclusiva de Host en Modo Asesino Ciego)*")

        vivos_players = db.query(Player).filter_by(room_id=room_id, estado="vivo").all()
        
        if vivos_players:
            tabla_vivos = []
            for p in vivos_players:
                tabla_vivos.append({
                    "Nombre": p.user.nombre,
                    "Email": p.user.email,
                    "Bajas": p.bajas,
                    "Cambios Restantes": p.cambios_restantes
                })
            st.dataframe(pd.DataFrame(tabla_vivos), hide_index=True, use_container_width=True)
        else:
            st.info("No hay jugadores vivos actualmente en esta sala.")

    st.markdown("---")
    st.subheader("🥇 Ranking de Asesinos")
    
    all_players = db.query(Player).filter_by(room_id=room_id).order_by(Player.bajas.desc()).all()
    if all_players:
        ranking_list = []
        for idx, p in enumerate(all_players, start=1):
            tiempo_str = "¡Sobrevivió hasta el final! 👑" if p.estado == "vivo" else (
                p.fecha_eliminacion.strftime("%Y-%m-%d %H:%M") if p.fecha_eliminacion else "Eliminado"
            )
            ranking_list.append({
                "Posición": f"{idx}º",
                "Nombre": p.user.nombre,
                "Bajas": p.bajas,
                "Estado": p.estado.capitalize(),
                "Supervivencia": tiempo_str
            })
        st.dataframe(pd.DataFrame(ranking_list), hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader("📜 Historial de Muertes")
    logs = db.query(HistoryLog).filter_by(room_id=room_id).order_by(HistoryLog.fecha.desc()).all()
    if logs:
        historial_data = []
        for l in logs:
            historial_data.append({
                "Fecha": l.fecha.strftime("%Y-%m-%d %H:%M"),
                "Asesino": l.asesino.user.nombre if l.asesino else "Desconocido",
                "Víctima": l.victima.user.nombre if l.victima else "Desconocido",
                "Objeto": l.objeto
            })
        st.dataframe(pd.DataFrame(historial_data), hide_index=True, use_container_width=True)
    else:
        st.caption("Aún no se ha registrado ninguna baja en esta sala.")

# =========================================================
# PESTAÑA 2: REGISTRAR / CONFIRMAR BAJA
# =========================================================
with tab_gestion:
    st.subheader("☠️ Registro y Confirmación de Asesinatos")

    # 1. NOTIFICACIÓN ANÓNIMA PARA LA VÍCTIMA
    if player_active:
        claims_pendientes = db.query(KillClaim).filter_by(
            room_id=room_id, victima_id=player_active.id, estado="pendiente"
        ).all()

        if claims_pendientes:
            for claim in claims_pendientes:
                st.error("⚠️ **¡SOLICITUD DE CONFIRMACIÓN DE MUERTE!**")
                st.markdown("""
                Alguien ha marcado haberte eliminado cumpliendo el objetivo de su misión. 
                *(Por privacidad del juego, no se muestra la identidad del asesino)*.
                """)
                c1, c2 = st.columns(2)
                if c1.button("☠️ Confirmar mi Muerte", type="primary", key=f"btn_confirm_death_{claim.id}", use_container_width=True):
                    res = game_logic.confirmar_baja_claim(db, claim.id)
                    st.success("Has sido marcado/a como eliminado/a.")
                    if res.get("partida_finalizada"):
                        st.balloons()
                        st.success(f"🏆 ¡PARTIDA FINALIZADA! Ganador/a: **{res['ganador'].user.nombre}**")
                    st.rerun()
                if c2.button("❌ Rechazar (Fue un error)", key=f"btn_reject_death_{claim.id}", use_container_width=True):
                    game_logic.rechazar_baja_claim(db, claim.id)
                    st.info("Solicitud rechazada.")
                    st.rerun()
            st.markdown("---")

    # 2. OPCIÓN JUGADOR: MARCAR ASESINATO A SU VÍCTIMA
    if player_active and player_active.estado == "vivo":
        asig_mi = db.query(Assignment).filter_by(room_id=room_id, asesino_id=player_active.id).first()
        if asig_mi:
            victima_p = db.query(Player).get(asig_mi.victima_id)
            st.subheader("🎯 Tu Misión Actual")
            st.info(f"🎯 **Tu Víctima:** {victima_p.user.nombre}\n\n🛋️ **Tu Arma:** {asig_mi.objeto}")

            claim_existente = db.query(KillClaim).filter_by(
                room_id=room_id, asesino_id=player_active.id, victima_id=victima_p.id, estado="pendiente"
            ).first()

            if claim_existente:
                st.warning("⏳ **Solicitud enviada.** Esperando que tu víctima confirme la baja en su pantalla.")
            else:
                if st.button("🔴 He eliminado a mi víctima", type="primary", use_container_width=True, key="btn_claim_kill"):
                    game_logic.solicitar_baja(db, room_id, player_active.id)
                    st.success("📩 Solicitud enviada. Le ha aparecido una notificación a tu víctima para que la confirme.")
                    st.rerun()
            st.markdown("---")
        elif room_actual.estado == "espera":
            st.info("⏳ La partida aún no ha comenzado. Espera a que el Host inicie el juego para recibir tu objetivo.")
    elif player_active and player_active.estado == "muerto":
        st.error("☠️ Has sido eliminado/a de esta partida. Puedes consultar el ranking y el historial de bajas.")

    # 3. OPCIÓN ADMINISTRADOR (HOST): REGISTRO DIRECTO DE ASESINATO
    if is_host:
        st.subheader("👑 Registro Directo de Asesinato (Solo Administrador / Host)")
        st.caption("Como Host de la sala, puedes confirmar directamente la baja de cualquier jugador sin esperar la confirmación de la víctima.")

        vivos_players = db.query(Player).filter_by(room_id=room_id, estado="vivo").all()

        if len(vivos_players) < 2:
            st.warning("⚠️ Quedan menos de 2 jugadores vivos o la partida no ha comenzado.")
        else:
            dict_vivos = {f"{p.user.nombre} ({p.user.email})": p.id for p in vivos_players}
            asesino_sel_key = st.selectbox("Seleccionar Asesino que realizó la baja:", list(dict_vivos.keys()), key="host_sel_asesino")
            asesino_player_id = dict_vivos[asesino_sel_key]

            asig_host = db.query(Assignment).filter_by(room_id=room_id, asesino_id=asesino_player_id).first()

            if asig_host:
                victima_host = db.query(Player).get(asig_host.victima_id)
                st.write(f"Víctima actual: **{victima_host.user.nombre}** | Arma: **{asig_host.objeto}**")

                if st.button("⚡ Confirmar Asesinato Directo (Host)", type="primary", use_container_width=True, key="btn_host_direct_kill"):
                    res = game_logic.registrar_baja(db, room_id, asesino_player_id)
                    st.success(f"🎉 ¡Baja registrada! **{victima_host.user.nombre}** ha sido eliminado/a.")

                    if res["partida_finalizada"]:
                        st.balloons()
                        st.success(f"🏆 ¡PARTIDA FINALIZADA! Ganador/a: **{res['ganador'].user.nombre}**")
                    st.rerun()

# =========================================================
# PESTAÑA 3: CONFIGURACIÓN / SETUP
# =========================================================
with tab_setup:
    st.subheader("⚙️ Configuración de la Partida y Sala")

    if is_host:
        st.success(f"👑 **Eres el Host (Creador) de la sala {room_actual.nombre}.** Tienes permisos completos de administración.")
    else:
        st.warning(f"ℹ️ El creador y administrador de esta sala es **{host_nombre}**. Tu rol actual es participante.")

    st.info(f"📢 **Comparte esta sala con tus amigos:**\n\n🔑 **Código PIN:** `{room_actual.codigo}`\n\n⏱️ **Rotación Programada:** Cada 3 días a las 8:00 AM (Próxima: `{proxima_rot_str}`)")

    # Ajuste del Modo Asesino Ciego para el Host
    if is_host:
        new_ciego = st.checkbox("🎭 **Activar modo 'Asesino Ciego'** (Oculta la lista de supervivientes vivos a los jugadores)", value=room_actual.modo_ciego, key="chk_modo_ciego_setup")
        if new_ciego != room_actual.modo_ciego:
            room_actual.modo_ciego = new_ciego
            db.commit()
            st.success(f"Modo Asesino Ciego {'activado' if new_ciego else 'desactivado'}.")
            st.rerun()

    # Botón directo para que el usuario autenticado se una a esta sala
    if not player_active:
        st.info(f"💡 No estás inscrito en la sala **{room_actual.nombre}**.")
        if st.button("🎮 Unirme a esta Sala", type="primary", use_container_width=True):
            p_new = Player(user_id=current_user.id, room_id=room_id, estado="vivo", bajas=0, cambios_restantes=2)
            db.add(p_new)
            db.commit()
            st.success(f"¡Te has unido a {room_actual.nombre}!")
            st.rerun()

    # A. Crear Nueva Sala con Generación Automática de PIN y Modo Ciego
    with st.expander("🏠 Crear Nueva Sala", expanded=False):
        c_n1, c_n2 = st.columns(2)
        n_nombre = c_n1.text_input("Nombre de la Sala")
        n_codigo = c_n2.text_input("Código PIN personalizado (opcional - 6 caracteres)")
        n_ciego_opt = st.checkbox("🎭 Activar modo 'Asesino Ciego' en esta nueva sala", key="chk_ciego_create")

        if st.button("➕ Crear Sala", use_container_width=True):
            if n_nombre:
                if n_codigo.strip():
                    c_clean = n_codigo.strip().upper()
                else:
                    c_clean = game_logic.generar_codigo_pin(db)

                if db.query(Room).filter_by(codigo=c_clean).first():
                    st.error(f"❌ Ya existe una sala con el código PIN '{c_clean}'.")
                else:
                    n_room = Room(codigo=c_clean, nombre=n_nombre.strip(), estado="espera", host_id=current_user.id, modo_ciego=n_ciego_opt)
                    db.add(n_room)
                    db.commit()
                    db.refresh(n_room)
                    p_creator = Player(user_id=current_user.id, room_id=n_room.id, estado="vivo", bajas=0, cambios_restantes=2)
                    db.add(p_creator)
                    db.commit()
                    st.session_state["active_room_id"] = n_room.id
                    st.success(f"🎉 Sala '{n_nombre}' creada con éxito. Código PIN: **{c_clean}**.")
                    st.rerun()
            else:
                st.warning("Por favor completa el nombre de la sala.")

    # B. Agregar / Unir Otro Jugador a la Sala Activa
    with st.expander("👤 Añadir Otro Jugador a esta Sala (Manual)", expanded=False):
        col1, col2 = st.columns(2)
        nuevo_nombre = col1.text_input("Nombre del Jugador")
        nuevo_email = col2.text_input("Correo Electrónico")

        if st.button("➕ Registrar e Inscribir", use_container_width=True):
            if nuevo_nombre and nuevo_email:
                name_clean = nuevo_nombre.strip()
                email_clean = nuevo_email.strip().lower()

                user = db.query(User).filter_by(email=email_clean).first()
                if not user:
                    user = User(nombre=name_clean, email=email_clean, password_hash=auth.hash_password("1234"))
                    db.add(user)
                    db.commit()
                    db.refresh(user)

                player_existing = db.query(Player).filter_by(user_id=user.id, room_id=room_id).first()
                if player_existing:
                    st.error(f"❌ El usuario '{email_clean}' ya forma parte de esta sala.")
                else:
                    player_new = Player(user_id=user.id, room_id=room_id, estado="vivo", bajas=0, cambios_restantes=2)
                    db.add(player_new)
                    db.commit()
                    st.success(f"Jugador '{name_clean}' inscrito en {room_actual.nombre}.")
                    st.rerun()
            else:
                st.warning("Rellena ambos campos (Nombre y Email).")

        inscritos = db.query(Player).filter_by(room_id=room_id).all()
        if inscritos:
            st.markdown("---")
            st.caption("📋 **Jugadores en esta sala:**")
            st.dataframe(pd.DataFrame([{
                "Nombre": p.user.nombre,
                "Email": p.user.email,
                "Estado": p.estado,
                "Cambios Restantes": p.cambios_restantes
            } for p in inscritos]), hide_index=True, use_container_width=True)

    # C. Catálogo de Objetos / Armas
    with st.expander("🛋️ Catálogo de Objetos / Armas", expanded=False):
        if is_host:
            nuevo_obj = st.text_input("Nuevo Objeto para esta sala")
            if st.button("➕ Agregar Objeto", use_container_width=True):
                if nuevo_obj:
                    o_clean = nuevo_obj.strip()
                    obj_exist = db.query(GameObject).filter(
                        (GameObject.nombre_objeto == o_clean) & 
                        ((GameObject.room_id == None) | (GameObject.room_id == room_id))
                    ).first()
                    if obj_exist:
                        st.error("El objeto ya existe en el catálogo.")
                    else:
                        o_new = GameObject(nombre_objeto=o_clean, room_id=room_id)
                        db.add(o_new)
                        db.commit()
                        st.success(f"Objeto '{o_clean}' añadido al catálogo.")
                        st.rerun()
        else:
            st.caption("🔒 Solo el Host de la sala puede agregar nuevos objetos al catálogo.")

        objs_disponibles = game_logic.obtener_objetos_disponibles(db, room_id)
        st.dataframe(pd.DataFrame([{"Objeto": o} for o in objs_disponibles]), hide_index=True, use_container_width=True)

    st.markdown("---")
    # D. Iniciar Partida (Restringido al Host)
    st.subheader("🚀 Iniciar Partida & Repartir Víctimas")
    st.caption("Al pulsar este botón se iniciará el ciclo cerrado de asesinatos para los jugadores vivos de esta sala.")

    if is_host:
        if st.button("💥 INICIAR PARTIDA Y ENVIAR CORREOS", type="primary", use_container_width=True):
            try:
                asignaciones = game_logic.generar_ciclo_cerrado(db, room_id)
                st.success("✅ ¡Partida iniciada! Se han generado los ciclos de asignación.")

                vivos_nombres = [p.user.nombre for p in db.query(Player).filter_by(room_id=room_id, estado="vivo").all()]
                progress = st.progress(0)
                for idx, asig in enumerate(asignaciones):
                    if idx > 0:
                        time.sleep(1)
                    asesino_p = db.query(Player).get(asig.asesino_id)
                    victima_p = db.query(Player).get(asig.victima_id)
                    
                    html_msg = email_service.build_assignment_email_html(
                        nombre_asesino=asesino_p.user.nombre,
                        nombre_victima=victima_p.user.nombre,
                        objeto=asig.objeto,
                        vivos_lista=vivos_nombres,
                        historial_bajas=[],
                        modo_ciego=room_actual.modo_ciego
                    )
                    email_service.send_email(
                        to_email=asesino_p.user.email,
                        subject="🔪 [INICIO DE PARTIDA] Tu objetivo ha sido asignado - Estás Muerto",
                        body_html=html_msg
                    )
                    progress.progress((idx + 1) / len(asignaciones))
                
                st.balloons()
                st.success("📩 Correos secretos de inicio enviados.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al iniciar partida: {e}")
    else:
        st.warning(f"🔒 El inicio de la partida requiere permisos de Host. Contacta a **{host_nombre}** para iniciar la partida.")

# =========================================================
# PESTAÑA 4: ROTACIÓN / CAMBIO DE ARMA
# =========================================================
with tab_rotacion:
    st.subheader("🎲 Cambio Individual de Arma")
    st.caption("Cambia el arma de un jugador específico si dispone de cambios en `cambios_restantes`.")

    players_con_cambios = db.query(Player).filter(
        (Player.room_id == room_id) & (Player.cambios_restantes > 0) & (Player.estado == "vivo")
    ).all()

    if not players_con_cambios:
        st.info("No hay ningún jugador vivo con cambios disponibles en esta sala.")
    else:
        dict_cambios = {f"{p.user.nombre} ({p.cambios_restantes} cambios)": p.id for p in players_con_cambios}
        player_sel_key = st.selectbox("Selecciona un jugador para el cambio:", list(dict_cambios.keys()))
        player_sel_id = dict_cambios[player_sel_key]

        if st.button("🎲 Ejecutar Cambio", type="primary", use_container_width=True):
            try:
                nuevo_objeto, cambios_left = game_logic.ejecutar_cambio_arma(db, room_id, player_sel_id)
                player_obj = db.query(Player).get(player_sel_id)
                asig_obj = db.query(Assignment).filter_by(room_id=room_id, asesino_id=player_sel_id).first()
                victima_obj = db.query(Player).get(asig_obj.victima_id) if asig_obj else None

                exito_email = email_service.send_item_change_email(
                    to_email=player_obj.user.email,
                    nombre_jugador=player_obj.user.nombre,
                    nuevo_objeto=nuevo_objeto,
                    cambios_restantes=cambios_left,
                    nombre_victima=victima_obj.user.nombre if victima_obj else None
                )

                st.success(f"✅ ¡Cambio realizado! La nueva arma de **{player_obj.user.nombre}** es **{nuevo_objeto}**. Le quedan {cambios_left} cambios.")
                if exito_email:
                    st.info(f"📩 Correo enviado a {player_obj.user.email}.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al ejecutar el cambio: {e}")

    st.markdown("---")
    st.subheader("🔄 Rotación Periódica General")
    st.write("Reorganiza los objetivos y armas entre todos los supervivientes de esta sala.")
    st.info(f"⏱️ **Próxima rotación automática programada:** `{proxima_rot_str}` (Cada 3 días a las 8:00 AM).")

    if is_host:
        if st.button("🔀 Ejecutar Rotación Manual de Sala", type="primary", use_container_width=True):
            try:
                asignaciones = game_logic.generar_ciclo_cerrado(db, room_id)
                st.success("✅ ¡Rotación realizada correctamente!")

                vivos_nombres = [p.user.nombre for p in db.query(Player).filter_by(room_id=room_id, estado="vivo").all()]
                progress = st.progress(0)
                for idx, asig in enumerate(asignaciones):
                    if idx > 0:
                        time.sleep(1)
                    asesino_p = db.query(Player).get(asig.asesino_id)
                    victima_p = db.query(Player).get(asig.victima_id)

                    html_msg = email_service.build_assignment_email_html(
                        nombre_asesino=asesino_p.user.nombre,
                        nombre_victima=victima_p.user.nombre,
                        objeto=asig.objeto,
                        vivos_lista=vivos_nombres,
                        historial_bajas=[],
                        modo_ciego=room_actual.modo_ciego
                    )
                    email_service.send_email(
                        to_email=asesino_p.user.email,
                        subject="🔄 [ROTACIÓN DE OBJETIVOS] Tu nueva víctima y arma - Estás Muerto",
                        body_html=html_msg
                    )
                    progress.progress((idx + 1) / len(asignaciones))

                st.success("📩 Notificaciones de rotación enviadas a todos los supervivientes.")
            except Exception as e:
                st.error(f"Error al rotar sala: {e}")
    else:
        st.warning(f"🔒 La rotación periódica manual solo puede ser ejecutada por el Host (**{host_nombre}**).")

# =========================================================
# PESTAÑA 5: PERFIL DE USUARIO Y INSIGNIAS (PLAYER BADGES)
# =========================================================
with tab_perfil:
    st.subheader(f"👤 Perfil de {current_user.nombre}")
    fecha_reg = current_user.created_at.strftime('%Y-%m-%d') if current_user.created_at else "Reciente"
    st.caption(f"📧 Correo: `{current_user.email}` | 📅 Registrado el: {fecha_reg}")

    stats = auth.obtener_estadisticas_usuario(db, current_user.id)

    # Métricas Globales
    m1, m2, m3 = st.columns(3)
    m1.metric("🎮 Partidas Jugadas", stats["partidas_jugadas"])
    m2.metric("🏆 Partidas Ganadas", stats["partidas_ganadas"])
    m3.metric("🔪 Kills Totales", stats["total_kills"])

    st.markdown("---")
    st.subheader("🎖️ Insignias y Logros")

    cols = st.columns(2)
    for idx, badge in enumerate(stats["insignias"]):
        col = cols[idx % 2]
        with col:
            if badge["desbloqueado"]:
                st.success(f"**{badge['nombre']}**\n\n{badge['descripcion']}\n\n✅ *¡Desbloqueado!*")
            else:
                st.info(f"**{badge['nombre']}** (Bloqueado)\n\n{badge['descripcion']}\n\n🔒 *En progreso...*")

    st.markdown("---")
    st.subheader("📋 Historial de Salas del Jugador")
    if stats["players"]:
        historial_salas = []
        for p in stats["players"]:
            r = db.query(Room).get(p.room_id)
            if r:
                historial_salas.append({
                    "Sala": r.nombre,
                    "Código PIN": r.codigo,
                    "Estado Sala": r.estado.upper(),
                    "Tu Estado": p.estado.capitalize(),
                    "Tus Kills": p.bajas,
                    "Cambios Restantes": p.cambios_restantes
                })
        st.dataframe(pd.DataFrame(historial_salas), hide_index=True, use_container_width=True)
    else:
        st.caption("Aún no te has inscrito en ninguna sala.")

# Cerrar sesión DB al final de la ejecución
db.close()
