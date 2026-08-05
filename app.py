import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import time
from datetime import datetime
from sqlalchemy import text
import database
from database import SessionLocal, init_db, engine
from models import User, Room, Player, Assignment, GameObject, HistoryLog, KillClaim
import game_logic
import auth

# Configuración de página adaptada a móviles
st.set_page_config(
    page_title="Estás Muerto 🔪 - Panel de Control",
    page_icon="🔪",
    layout="centered"
)

print("[LOG SERVIDOR] TEST 1: App iniciada", flush=True)

# Refresco automático nativo cada 5 segundos en segundo plano
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=5000, limit=None, key="global_autorefresh_timer")
except Exception:
    pass

# ---------------------------------------------------------
# SCRIPT DE OCULTACIÓN Y PURGA DOM PARA STREAMLIT CLOUD (TOP & PARENT FRAME)
# ---------------------------------------------------------
if hasattr(st, "html"):
    st.html("""
    <script>
        function purgeCloudElements() {
            const docs = [];
            try { if (window.document) docs.push(window.document); } catch(e){}
            try { if (window.parent && window.parent.document) docs.push(window.parent.document); } catch(e){}
            try { if (window.top && window.top.document) docs.push(window.top.document); } catch(e){}

            const selectors = [
                '._container_gzau3_1',
                '._viewerBadge_aycw8_23',
                '._profilePreview_gzau3_63',
                '._profileImage_gzau3_78',
                '[class*="_viewerBadge_"]',
                '[class*="_container_gzau3_"]',
                '[class*="_profilePreview_"]',
                '[class*="_profileImage_"]',
                '[data-testid="appCreatorAvatar"]',
                'a[href*="streamlit.io/cloud"]',
                'a[href*="share.streamlit.io/user"]',
                'a[href*="share.streamlit.io"]',
                'a[href*="streamlit.io"]',
                'a[href*="github.com"]',
                '[data-testid="stToolbarActionButton"]',
                '[class*="stToolbarActionButton"]',
                'button[aria-label*="Fork"]',
                'button[aria-label*="GitHub"]',
                'button[aria-label*="git"]',
                'footer',
                '[data-testid="stFooter"]'
            ];

            docs.forEach(d => {
                if (!d) return;
                try {
                    if (!d.getElementById('purge-cloud-style')) {
                        const s = d.createElement('style');
                        s.id = 'purge-cloud-style';
                        s.innerHTML = selectors.join(', ') + ' { display: none !important; visibility: hidden !important; opacity: 0 !important; pointer-events: none !important; }';
                        d.head.appendChild(s);
                    }
                } catch(e){}

                selectors.forEach(sel => {
                    try {
                        const els = d.querySelectorAll(sel);
                        els.forEach(el => {
                            try { el.remove(); } catch(e) { el.style.display = 'none'; }
                        });
                    } catch(e){}
                });
            });
        }

        purgeCloudElements();
        setInterval(purgeCloudElements, 200);
    </script>
    """)

# ---------------------------------------------------------
# AJUSTES DE ESTILO CSS: OCULTAR GITHUB, FORK, BADGES DE STREAMLIT CLOUD Y FOOTER
# (Mantiene visible únicamente el menú nativo de 3 puntos #MainMenu para el cambio de tema)
# ---------------------------------------------------------
st.markdown("""
<style>
/* 1. Ocultar avatar de creador, badge Hosted with Streamlit y botones de toolbar */
[data-testid="appCreatorAvatar"],
[class*="_profilePreview_"],
[class*="_profileImage_"],
[class*="_viewerBadge_"],
[class*="_container_gzau3_"],
a[href*="streamlit.io/cloud"],
a[href*="share.streamlit.io/user"],
[data-testid="stToolbarActionButton"],
[class*="stToolbarActionButton"],
button[aria-label*="Fork"],
button[aria-label*="GitHub"],
button[aria-label*="git"],
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

print("[LOG SERVIDOR] TEST 2: Intentando conectar a la base de datos...", flush=True)

# Inicializar tablas en la base de datos (PostgreSQL / SQLite)
init_db()

# Abrir sesión de base de datos
db = SessionLocal()

print("[LOG SERVIDOR] TEST 3: BBDD conectada correctamente", flush=True)

st.title("🔪 Estás Muerto")

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
print("[LOG SERVIDOR] TEST 4: Entrando a la lógica de autenticación", flush=True)
current_user_id = st.session_state.get("user_id")

# Intentar recuperar sesión persistente desde parámetro URL si no hay sesión en memoria
if not current_user_id and "u" in url_params:
    param_u = url_params.get("u")
    if param_u and str(param_u).isdigit():
        try:
            u_cand = db.query(User).get(int(param_u))
            if u_cand:
                st.session_state["user_id"] = u_cand.id
                current_user_id = u_cand.id
        except Exception:
            pass

current_user = db.query(User).get(current_user_id) if current_user_id else None
print("[LOG SERVIDOR] TEST 5: Consulta a base de datos finalizada", flush=True)

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
                    if st.session_state.get("user_id") != u.id:
                        st.session_state["user_id"] = u.id
                        st.query_params["u"] = str(u.id)
                        if "logout" in st.query_params:
                            st.query_params.pop("logout", None)
                        st.success(f"¡Bienvenido/a de nuevo, **{u.nombre}**!")
                        st.rerun()
                else:
                    st.error("❌ Correo electrónico o contraseña incorrectos.")
            else:
                st.warning("Rellena todos los campos.")

        st.markdown("---")


    st.markdown("---")
    with st.expander("🔍 Diagnóstico de Conexión a Base de Datos", expanded=False):
        db_engine = engine.name
        st.write(f"**Motor de base de datos en uso:** `{db_engine}`")
        try:
            db.execute(text("SELECT 1"))
            user_count = db.query(User).count()
            st.success(f"✅ Conexión exitosa a la base de datos. Hay **{user_count}** usuario(s) registrados.")
            if db_engine == "sqlite":
                st.warning("⚠️ La app está funcionando sobre **SQLite local (efímero)**.")
                keys_found = []
                try:
                    if hasattr(st, "secrets"):
                        keys_found = list(st.secrets.keys())
                except Exception:
                    pass
                st.info(f"🔑 **Claves detectadas actualmente en Secrets de Streamlit Cloud:** `{keys_found}`\n\nSi no ves `DATABASE_URL` en la lista superior, debes ir a `Settings -> Secrets` en Streamlit Cloud y guardar:\n```toml\nDATABASE_URL = \"postgresql://postgres:TU_CLAVE@db.wkqvukcszqayawzylyel.supabase.co:5432/postgres\"\n```")
        except Exception as ex:
            st.error(f"❌ Error al conectar con la base de datos: `{ex}`")
            err_str = str(ex)
            if "could not translate host name" in err_str or "No address associated with hostname" in err_str or "supabase.co" in err_str:
                st.warning("""
                ⚠️ **Causa detectada: La URL Directa de Supabase (`db.xxx.supabase.co`) es solo IPv6 y Streamlit Cloud opera en una red IPv4.**
                
                👉 **Solución rápida (Usar Supabase Connection Pooler en puerto 6543):**
                1. Entra a tu proyecto en **[app.supabase.com](https://app.supabase.com)**.
                2. Ve a **Project Settings** ➔ **Database** ➔ **Connection String**.
                3. Cambia la opción a **Session** o **Transaction Pooler** (en formato URI).
                4. Copia la URL que usa el servidor pooler y puerto `6543` (tendrá un formato como `postgresql://postgres.wkqvukcszqayawzylyel:TU_CLAVE@aws-0-eu-central-1.pooler.supabase.com:6543/postgres`).
                5. Reemplaza `DATABASE_URL` en `Settings ➔ Secrets` de Streamlit Cloud con esa nueva URL.
                """)

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
                    if st.session_state.get("user_id") != u.id:
                        st.session_state["user_id"] = u.id
                        st.query_params["u"] = str(u.id)
                        if "logout" in st.query_params:
                            st.query_params.pop("logout", None)
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
    st.query_params.pop("u", None)
    st.query_params["logout"] = "true"
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
                    p_new = Player(user_id=current_user.id, room_id=room_found.id, estado="vivo", bajas=0, cambios_restantes=1, cambios_gratuitos=1, cambios_bonus=0)
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
proxima_rot_str = proxima_rot.strftime("%d-%m-%Y %H:%M") if proxima_rot else "No programada"

# Info de la sala en Sidebar
st.sidebar.info(f"**Sala Activa:** {room_actual.nombre}\n\n🔑 **PIN:** `{room_actual.codigo}`\n\n⏱️ **Próxima Rotación (8am):** `{proxima_rot_str}`")

is_host = (current_user.id == room_actual.host_id)
player_active = db.query(Player).filter_by(user_id=current_user.id, room_id=room_id).first()
if player_active:
    needs_update = False
    if getattr(player_active, "cambios_gratuitos", 1) is None or player_active.cambios_gratuitos > 1:
        player_active.cambios_gratuitos = 1
        needs_update = True
    if getattr(player_active, "cambios_bonus", 0) is None:
        player_active.cambios_bonus = 0
        needs_update = True
    if player_active.cambios_restantes != (player_active.cambios_gratuitos + player_active.cambios_bonus):
        player_active.cambios_restantes = player_active.cambios_gratuitos + player_active.cambios_bonus
        needs_update = True
    if needs_update:
        db.commit()



# ---------------------------------------------------------
# INTERFAZ PRINCIPAL EN PESTAÑAS
# ---------------------------------------------------------
if is_host:
    tab_estado, tab_gestion, tab_setup, tab_perfil = st.tabs([
        "🏆 Estado", "🎯 Misión", "⚙️ Setup", "👤 Mi Perfil"
    ])
else:
    tab_estado, tab_gestion, tab_perfil = st.tabs([
        "🏆 Estado", "🎯 Misión", "👤 Mi Perfil"
    ])
    tab_setup = None

# =========================================================
# PESTAÑA 1: ESTADO Y RANKING
# =========================================================
with tab_estado:
    st.subheader("🟢 Supervivientes")
    
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

        vivos = db.query(Player).filter_by(room_id=room_id, estado="vivo").all()
        muertos = db.query(Player).filter_by(room_id=room_id, estado="muerto").order_by(Player.fecha_eliminacion.desc()).all()
        todos_supervivientes = vivos + muertos
        
        if todos_supervivientes:
            tabla_vivos = []
            for p in todos_supervivientes:
                tiempo_str = "¡Sobreviviendo! 👑" if p.estado == "vivo" else (
                    p.fecha_eliminacion.strftime("%d-%m-%Y %H:%M") if p.fecha_eliminacion else "Eliminado"
                )
                tabla_vivos.append({
                    "Nombre": p.user.nombre,
                    "Estado": p.estado.capitalize(),
                    "Bajas": p.bajas,
                    "Cambios Restantes": p.cambios_restantes,
                    "Supervivencia": tiempo_str
                })
            st.dataframe(pd.DataFrame(tabla_vivos), hide_index=True, use_container_width=True)
        else:
            st.info("No hay jugadores en esta sala.")

    st.markdown("---")
    st.subheader("🥇 Ranking de Asesinos")
    
    all_players = db.query(Player).filter_by(room_id=room_id).order_by(Player.bajas.desc()).all()
    if all_players:
        ranking_list = []
        prev_bajas = None
        prev_pos = 0
        for idx, p in enumerate(all_players, start=1):
            if p.bajas == prev_bajas:
                pos_str = f"{prev_pos}º"
            else:
                pos_str = f"{idx}º"
                prev_pos = idx
                prev_bajas = p.bajas

            ranking_list.append({
                "Posición": pos_str,
                "Nombre": p.user.nombre,
                "Bajas": p.bajas
            })
        st.dataframe(pd.DataFrame(ranking_list), hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader("📜 Historial de Muertes")
    logs = db.query(HistoryLog).filter_by(room_id=room_id).order_by(HistoryLog.fecha.desc()).all()
    if logs:
        historial_data = []
        for l in logs:
            historial_data.append({
                "Fecha": l.fecha.strftime("%d-%m-%Y %H:%M"),
                "Asesino": l.asesino.user.nombre if l.asesino else "Desconocido",
                "Víctima": l.victima.user.nombre if l.victima else "Desconocido",
                "Objeto": l.objeto
            })
        st.dataframe(pd.DataFrame(historial_data), hide_index=True, use_container_width=True)
    else:
        st.caption("Aún no se ha registrado ninguna baja en esta sala.")

# =========================================================
# PESTAÑA 2: BAJA & ROTACIÓN
# =========================================================
with tab_gestion:
    # Mensajes de feedback persistentes
    if "msg_feedback_baja" in st.session_state:
        st.success(st.session_state.pop("msg_feedback_baja"))
    if "msg_feedback_arma" in st.session_state:
        st.success(st.session_state.pop("msg_feedback_arma"))

    st.subheader("☠️ Registro y Confirmación de Asesinatos")

    # 1. NOTIFICACIÓN ANÓNIMA PARA LA VÍCTIMA (CONFIRMAR MI MUERTE CON POPUP)
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
                if c1.button("☠️ Confirmar mi Muerte", type="primary", key=f"btn_confirm_death_trg_{claim.id}", use_container_width=True):
                    st.session_state[f"dialog_confirm_death_{claim.id}"] = True

                if c2.button("❌ Rechazar (Fue un error)", key=f"btn_reject_death_{claim.id}", use_container_width=True):
                    game_logic.rechazar_baja_claim(db, claim.id)
                    st.info("Solicitud rechazada.")
                    st.rerun()

                # MODAL CONFIRMAR MI MUERTE
                if st.session_state.get(f"dialog_confirm_death_{claim.id}"):
                    if hasattr(st, "dialog"):
                        @st.dialog("❓ Confirmar Tu Eliminación")
                        def modal_confirmar_muerte():
                            st.write("¿Estás seguro/a de que deseas confirmar tu eliminación?")
                            st.warning("⚠️ Quedarás eliminado/a de esta partida y tu asesino avanzará al siguiente objetivo.")
                            mc1, mc2 = st.columns(2)
                            if mc1.button("✅ Sí, Confirmar mi Muerte", type="primary", use_container_width=True, key=f"dlg_yes_death_{claim.id}"):
                                st.session_state[f"dialog_confirm_death_{claim.id}"] = False
                                res = game_logic.confirmar_baja_claim(db, claim.id)
                                msg = "Has sido marcado/a como eliminado/a de la partida."
                                if res.get("partida_finalizada"):
                                    msg += f" 🏆 ¡PARTIDA FINALIZADA! Ganador/a: **{res['ganador'].user.nombre}**"
                                st.session_state["msg_feedback_baja"] = msg
                                st.rerun()
                            if mc2.button("❌ Cancelar", use_container_width=True, key=f"dlg_no_death_{claim.id}"):
                                st.session_state[f"dialog_confirm_death_{claim.id}"] = False
                                st.rerun()
                        modal_confirmar_muerte()
                    else:
                        with st.container(border=True):
                            st.subheader("❓ Confirmar Tu Eliminación")
                            st.write("¿Estás seguro/a de que deseas confirmar tu eliminación?")
                            st.warning("⚠️ Quedarás eliminado/a de esta partida.")
                            mc1, mc2 = st.columns(2)
                            if mc1.button("✅ Sí, Confirmar mi Muerte", type="primary", use_container_width=True, key=f"fb_yes_death_{claim.id}"):
                                st.session_state[f"dialog_confirm_death_{claim.id}"] = False
                                res = game_logic.confirmar_baja_claim(db, claim.id)
                                st.session_state["msg_feedback_baja"] = "Has sido marcado/a como eliminado/a."
                                st.rerun()
                            if mc2.button("❌ Cancelar", use_container_width=True, key=f"fb_no_death_{claim.id}"):
                                st.session_state[f"dialog_confirm_death_{claim.id}"] = False
                                st.rerun()

            st.markdown("---")

    # 2. OPCIÓN JUGADOR: MARCAR ASESINATO A SU VÍCTIMA (CON POPUP)
    if player_active and player_active.estado == "vivo":
        asig_mi = db.query(Assignment).filter_by(room_id=room_id, asesino_id=player_active.id).first()
        if asig_mi:
            victima_p = db.query(Player).get(asig_mi.victima_id)
            st.subheader("🎯 Tu Misión Actual")
            with st.expander("🕵️ **MI MISIÓN SECRETA** (Pulsa para ver/ocultar tu objetivo)", expanded=False):
                st.markdown(f"""
                <div style="background: #2a2a2a; padding: 15px; border-radius: 10px; border-left: 5px solid #e74c3c;">
                    <p style="margin: 5px 0; font-size: 16px;">🎯 <b>Tu Víctima:</b> <span style="color: #ff6b6b; font-size: 22px; font-weight: bold;">{victima_p.user.nombre}</span></p>
                    <p style="margin: 5px 0; font-size: 16px;">🛋️ <b>Tu Arma / Objeto:</b> <span style="color: #fca311; font-size: 22px; font-weight: bold;">{asig_mi.objeto}</span></p>
                    <p style="margin: 5px 0; font-size: 14px; color: #4cc9f0;">🔄 <b>Cambios restantes de arma:</b> {player_active.cambios_restantes}</p>
                </div>
                """, unsafe_allow_html=True)
                st.caption("🔒 Mantén esta pantalla oculta de miradas curiosas.")

            claim_existente = db.query(KillClaim).filter_by(
                room_id=room_id, asesino_id=player_active.id, victima_id=victima_p.id, estado="pendiente"
            ).first()

            if claim_existente:
                st.warning("⏳ **Solicitud enviada.** Esperando que tu víctima confirme la baja en su pantalla.")
            else:
                if st.button("🔴 He eliminado a mi víctima", type="primary", use_container_width=True, key="btn_claim_kill_trigger"):
                    st.session_state["dialog_claim_kill"] = True

                # MODAL MARCAR ASESINATO
                if st.session_state.get("dialog_claim_kill"):
                    if hasattr(st, "dialog"):
                        @st.dialog("❓ Confirmar Notificación de Asesinato")
                        def modal_marcar_asesinato():
                            st.write(f"¿Estás seguro/a de que has eliminado a **{victima_p.user.nombre}** con el objeto **{asig_mi.objeto}**?")
                            st.warning("⚠️ Se enviará una solicitud inmediata a tu víctima para que la confirme en su pantalla.")
                            kc1, kc2 = st.columns(2)
                            if kc1.button("✅ Sí, Notificar Asesinato", type="primary", use_container_width=True, key="dlg_yes_claim"):
                                st.session_state["dialog_claim_kill"] = False
                                game_logic.solicitar_baja(db, room_id, player_active.id)
                                st.session_state["msg_feedback_baja"] = "📩 Solicitud enviada con éxito. Le ha aparecido una notificación a tu víctima para que la confirme."
                                st.rerun()
                            if kc2.button("❌ Cancelar", use_container_width=True, key="dlg_no_claim"):
                                st.session_state["dialog_claim_kill"] = False
                                st.rerun()
                        modal_marcar_asesinato()
                    else:
                        with st.container(border=True):
                            st.subheader("❓ Confirmar Notificación de Asesinato")
                            st.write(f"¿Estás seguro/a de que has eliminado a **{victima_p.user.nombre}**?")
                            kc1, kc2 = st.columns(2)
                            if kc1.button("✅ Sí, Notificar Asesinato", type="primary", use_container_width=True, key="fb_yes_claim"):
                                st.session_state["dialog_claim_kill"] = False
                                game_logic.solicitar_baja(db, room_id, player_active.id)
                                st.session_state["msg_feedback_baja"] = "📩 Solicitud enviada."
                                st.rerun()
                            if kc2.button("❌ Cancelar", use_container_width=True, key="fb_no_claim"):
                                st.session_state["dialog_claim_kill"] = False
                                st.rerun()

        elif room_actual.estado == "espera":
            st.info("⏳ La partida aún no ha comenzado. Espera a que el Host inicie el juego para recibir tu objetivo.")
    elif player_active and player_active.estado == "muerto":
        st.error("☠️ Has sido eliminado/a de esta partida. Puedes consultar el ranking y el historial de bajas.")

    # 3. OPCIÓN ADMINISTRADOR (HOST): REGISTRO DIRECTO DE ASESINATO (CON POPUP)
    if is_host:
        st.markdown("---")
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

                if st.button("⚡ Confirmar Asesinato Directo (Host)", type="primary", use_container_width=True, key="btn_host_direct_kill_trigger"):
                    st.session_state["dialog_host_direct_kill"] = True

                if st.session_state.get("dialog_host_direct_kill"):
                    if hasattr(st, "dialog"):
                        @st.dialog("❓ Confirmar Asesinato Directo (Host)")
                        def modal_host_direct():
                            st.write(f"¿Estás seguro/a de registrar directamente la eliminación de **{victima_host.user.nombre}** por parte de **{asig_host.asesino.user.nombre}**?")
                            st.warning("⚠️ Esta acción es irreversible y actualizará la asignación inmediatamente.")
                            hc1, hc2 = st.columns(2)
                            if hc1.button("✅ Sí, Registrar Baja Directa", type="primary", use_container_width=True, key="dlg_yes_host_kill"):
                                st.session_state["dialog_host_direct_kill"] = False
                                res = game_logic.registrar_baja(db, room_id, asesino_player_id)
                                msg = f"🎉 ¡Baja registrada! **{victima_host.user.nombre}** ha sido eliminado/a."
                                if res["partida_finalizada"]:
                                    msg += f" 🏆 ¡PARTIDA FINALIZADA! Ganador/a: **{res['ganador'].user.nombre}**"
                                st.session_state["msg_feedback_baja"] = msg
                                st.rerun()
                            if hc2.button("❌ Cancelar", use_container_width=True, key="dlg_no_host_kill"):
                                st.session_state["dialog_host_direct_kill"] = False
                                st.rerun()
                        modal_host_direct()
                    else:
                        with st.container(border=True):
                            st.subheader("❓ Confirmar Asesinato Directo (Host)")
                            hc1, hc2 = st.columns(2)
                            if hc1.button("✅ Sí, Registrar Baja Directa", type="primary", use_container_width=True, key="fb_yes_host_kill"):
                                st.session_state["dialog_host_direct_kill"] = False
                                res = game_logic.registrar_baja(db, room_id, asesino_player_id)
                                st.session_state["msg_feedback_baja"] = f"🎉 ¡Baja registrada! **{victima_host.user.nombre}** ha sido eliminado/a."
                                st.rerun()
                            if hc2.button("❌ Cancelar", use_container_width=True, key="fb_no_host_kill"):
                                st.session_state["dialog_host_direct_kill"] = False
                                st.rerun()

    # =========================================================
    # SECCIÓN: CAMBIO INDIVIDUAL DE ARMA
    # =========================================================
    st.markdown("---")
    st.subheader("🎲 Cambio Individual de Arma")

    # 1. CAMBIO DE ARMA PROPIA PARA JUGADORES
    if player_active and player_active.estado == "vivo":
        cg = getattr(player_active, "cambios_gratuitos", 1) or 0
        cb = getattr(player_active, "cambios_bonus", 0) or 0
        total_disp = cg + cb

        if total_disp > 0:
            st.info(f"🔄 **Cambios disponibles de arma:** {total_disp} (`{cg}` gratuito + `{cb}` acumulados por bajas)")
            
            if st.button("🎲 Cambiar Mi Arma", type="primary", use_container_width=True, key="btn_change_my_weapon"):
                st.session_state["confirmar_cambio_arma_dialog"] = True

            if st.session_state.get("confirmar_cambio_arma_dialog"):
                if hasattr(st, "dialog"):
                    @st.dialog("❓ Confirmar Cambio de Arma")
                    def modal_confirmar_arma():
                        st.write("¿Estás seguro/a de que deseas cambiar tu arma actual por una nueva?")
                        st.warning(f"⚠️ Consumirá 1 de tus cambios disponibles (te quedarán {total_disp - 1}). Se prioriza el uso del cambio gratuito.")
                        col_c1, col_c2 = st.columns(2)
                        if col_c1.button("✅ Sí, Cambiar Arma", type="primary", use_container_width=True, key="btn_confirm_dialog"):
                            st.session_state["confirmar_cambio_arma_dialog"] = False
                            try:
                                nuevo_objeto, cambios_left = game_logic.ejecutar_cambio_arma(db, room_id, player_active.id)
                                st.session_state["msg_feedback_arma"] = f"🎉 ¡Arma cambiada con éxito! Tu nueva arma secreta es **{nuevo_objeto}**. Te quedan {cambios_left} cambios de arma."
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al cambiar arma: {e}")

                        if col_c2.button("❌ Cancelar", use_container_width=True, key="btn_cancel_dialog"):
                            st.session_state["confirmar_cambio_arma_dialog"] = False
                            st.rerun()
                    modal_confirmar_arma()
                else:
                    with st.container(border=True):
                        st.subheader("❓ Confirmar Cambio de Arma")
                        st.write("¿Estás seguro/a de que deseas cambiar tu arma actual por una nueva?")
                        st.warning("⚠️ Consumirá 1 de tus 2 cambios disponibles.")
                        col_c1, col_c2 = st.columns(2)
                        if col_c1.button("✅ Sí, Cambiar Arma", type="primary", use_container_width=True, key="btn_confirm_fallback"):
                            st.session_state["confirmar_cambio_arma_dialog"] = False
                            try:
                                nuevo_objeto, cambios_left = game_logic.ejecutar_cambio_arma(db, room_id, player_active.id)
                                st.session_state["msg_feedback_arma"] = f"🎉 ¡Arma cambiada con éxito! Tu nueva arma secreta es **{nuevo_objeto}**. Te quedan {cambios_left} cambios de arma."
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al cambiar arma: {e}")

                        if col_c2.button("❌ Cancelar", use_container_width=True, key="btn_cancel_fallback"):
                            st.session_state["confirmar_cambio_arma_dialog"] = False
                            st.rerun()
        else:
            st.warning("⚠️ Has agotado tus 2 cambios individuales de arma en esta partida.")
    elif player_active and player_active.estado == "muerto":
        st.caption("☠️ Estás eliminado/a de esta sala.")

    # 2. CAMBIO DE ARMA PARA OTRO JUGADOR (EXCLUSIVO DEL HOST)
    if is_host:
        st.markdown("---")
        st.subheader("👑 Cambio de Arma para Jugadores (Solo Host)")
        all_vivos = db.query(Player).filter(
            (Player.room_id == room_id) & (Player.estado == "vivo")
        ).all()

        if all_vivos:
            dict_cambios = {f"{p.user.nombre} (Cambios restantes: {p.cambios_restantes})": p.id for p in all_vivos}
            player_sel_key = st.selectbox("Seleccionar jugador a quien cambiar el arma:", list(dict_cambios.keys()), key="host_weapon_change_sel")
            player_sel_id = dict_cambios[player_sel_key]

            if st.button("🎲 Ejecutar Cambio a este Jugador (Host)", use_container_width=True, key="btn_host_change_player_weapon"):
                try:
                    nuevo_objeto, cambios_left = game_logic.ejecutar_cambio_arma(db, room_id, player_sel_id, es_host=True)
                    player_obj = db.query(Player).get(player_sel_id)
                    st.success(f"✅ ¡Cambio realizado por el Host! La nueva arma de **{player_obj.user.nombre}** es **{nuevo_objeto}**.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al ejecutar el cambio: {e}")
        else:
            st.caption("No hay jugadores vivos actualmente en esta sala.")

    # =========================================================
    # SECCIÓN: ROTACIÓN PERIÓDICA GENERAL
    # =========================================================
    st.markdown("---")
    st.subheader("🔄 Rotación Periódica General")
    st.info(f"⏱️ **Próxima rotación automática programada:** `{proxima_rot_str}` (Cada 3 días a las 8:00 AM).")

    if is_host:
        if st.button("🔀 Ejecutar Rotación Manual de Sala", type="primary", use_container_width=True):
            try:
                asignaciones = game_logic.generar_ciclo_cerrado(db, room_id)
                st.success("✅ ¡Rotación realizada correctamente!")
                st.rerun()
            except Exception as e:
                st.error(f"Error en la rotación: {e}")

                st.success("📩 Notificaciones de rotación enviadas a todos los supervivientes.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al rotar sala: {e}")

# =========================================================
# PESTAÑA 3: CONFIGURACIÓN / SETUP
# =========================================================
if is_host and tab_setup:
    with tab_setup:
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
                p_new = Player(user_id=current_user.id, room_id=room_id, estado="vivo", bajas=0, cambios_restantes=1, cambios_gratuitos=1, cambios_bonus=0)
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
                        p_creator = Player(user_id=current_user.id, room_id=n_room.id, estado="vivo", bajas=0, cambios_restantes=1, cambios_gratuitos=1, cambios_bonus=0)
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
                        player_new = Player(user_id=user.id, room_id=room_id, estado="vivo", bajas=0, cambios_restantes=1, cambios_gratuitos=1, cambios_bonus=0)
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
        # E. Iniciar Partida (Restringido al Host)
        st.subheader("🚀 Iniciar Partida & Repartir Víctimas")
        st.caption("Al pulsar este botón se iniciará el ciclo cerrado de asesinatos para los jugadores vivos de esta sala.")

        if is_host:
            if st.button("💥 INICIAR PARTIDA", type="primary", use_container_width=True):
                try:
                    asignaciones = game_logic.generar_ciclo_cerrado(db, room_id)
                    st.success("✅ ¡Partida iniciada! Se han generado los ciclos de asignación.")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al iniciar partida: {e}")
        else:
            st.warning(f"🔒 El inicio de la partida requiere permisos de Host. Contacta a **{host_nombre}** para iniciar la partida.")



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

    # st.markdown("---")
    # st.subheader("⚙️ Configuración de Notificaciones")
    # val_recibir = getattr(current_user, "recibir_correos", True)
    # if val_recibir is None:
    #     val_recibir = True
    # opt_recibir = st.checkbox(
    #     "📬 Recibir correos electrónicos con información de la partida",
    #     value=bool(val_recibir),
    #     key="chk_recibir_correos"
    # )
    # if opt_recibir != val_recibir:
    #     current_user.recibir_correos = opt_recibir
    #     db.commit()
    #     st.toast("✅ Preferencias de correo actualizadas con éxito.")
    #     st.rerun()

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

print("[LOG SERVIDOR] TEST 6: Fin del script", flush=True)

# Cerrar sesión DB al final de la ejecución
db.close()
