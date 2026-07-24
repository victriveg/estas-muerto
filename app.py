import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random
from datetime import datetime
import email_service

# Configuración de página adaptada a móviles
st.set_page_config(
    page_title="Estás Muerto 🔪 - Panel de Control",
    page_icon="🔪",
    layout="centered"
)

st.title("🔪 Estás Muerto")
st.caption("Panel de control para gestionar la partida desde tu móvil")

# ---------------------------------------------------------
# 1. CONEXIÓN Y LECTURA DE GOOGLE SHEETS
# ---------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos():
    try:
        df_j = conn.read(worksheet="Jugadores", ttl=0)
    except Exception:
        df_j = pd.DataFrame(columns=["Nombre", "Email", "Estado", "Bajas"])

    try:
        df_a = conn.read(worksheet="Asignaciones", ttl=0)
    except Exception:
        df_a = pd.DataFrame(columns=["Asesino", "Victima", "Objeto"])

    try:
        df_o = conn.read(worksheet="Objetos", ttl=0)
    except Exception:
        df_o = pd.DataFrame(columns=["Nombre_Objeto"])

    try:
        df_h = conn.read(worksheet="Historial", ttl=0)
    except Exception:
        df_h = pd.DataFrame(columns=["Fecha", "Asesino", "Victima", "Objeto"])

    # Normalizar columnas vacías
    if "Bajas" not in df_j.columns:
        df_j["Bajas"] = 0
    df_j["Bajas"] = pd.to_numeric(df_j["Bajas"], errors="coerce").fillna(0).astype(int)

    return df_j, df_a, df_o, df_h

df_jugadores, df_asignaciones, df_objetos, df_historial = cargar_datos()

# ---------------------------------------------------------
# HELPER: ALGORITMO CICLO CERRADO DE ASESINOS
# ---------------------------------------------------------
def generar_ciclo_cerrado(lista_vivos, lista_objetos):
    """
    Genera una permuta aleatoria donde P1 -> P2 -> ... -> Pn -> P1
    y asigna un objeto aleatorio a cada asesino.
    """
    vivos_shuffled = lista_vivos.copy()
    random.shuffle(vivos_shuffled)
    
    n = len(vivos_shuffled)
    nuevas_asignaciones = []
    
    # Asegurar que haya suficientes objetos
    objetos_pool = lista_objetos.copy()
    while len(objetos_pool) < n:
        objetos_pool.extend(lista_objetos)
    random.shuffle(objetos_pool)

    for i in range(n):
        asesino = vivos_shuffled[i]
        victima = vivos_shuffled[(i + 1) % n]  # El último tiene como víctima al primero
        objeto = objetos_pool[i]
        nuevas_asignaciones.append({
            "Asesino": asesino,
            "Victima": victima,
            "Objeto": objeto
        })
    
    return pd.DataFrame(nuevas_asignaciones)

# ---------------------------------------------------------
# DIÁLOGOS POP-UP DE CONFIRMACIÓN DE BORRADO
# ---------------------------------------------------------
if hasattr(st, "dialog"):
    @st.dialog("⚠️ Confirmar eliminación de jugador")
    def popup_eliminar_jugador(nombre):
        st.warning(f"¿Estás seguro de que deseas eliminar a **{nombre}** de la lista de jugadores?")
        st.caption("Esta acción eliminará al jugador de la partida y actualizará la hoja de cálculo.")
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Sí, Eliminar", type="primary", use_container_width=True, key="pop_btn_del_j_yes"):
            df_updated = df_jugadores[df_jugadores["Nombre"] != nombre]
            conn.update(worksheet="Jugadores", data=df_updated)
            st.success(f"Jugador '{nombre}' eliminado.")
            st.rerun()
        if c2.button("Cancelar", use_container_width=True, key="pop_btn_del_j_no"):
            st.rerun()

    @st.dialog("⚠️ Confirmar eliminación de objeto")
    def popup_eliminar_objeto(objeto):
        st.warning(f"¿Estás seguro de que deseas eliminar el objeto **{objeto}** del catálogo?")
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Sí, Eliminar", type="primary", use_container_width=True, key="pop_btn_del_o_yes"):
            df_updated = df_objetos[df_objetos["Nombre_Objeto"] != objeto]
            conn.update(worksheet="Objetos", data=df_updated)
            st.success(f"Objeto '{objeto}' eliminado.")
            st.rerun()
        if c2.button("Cancelar", use_container_width=True, key="pop_btn_del_o_no"):
            st.rerun()

    @st.dialog("🚀 Confirmar Inicio de Partida")
    def popup_iniciar_partida():
        st.warning("⚠️ **¿Estás seguro de que deseas iniciar una nueva partida?**")
        st.markdown("""
        * **Todos los jugadores pasarán a estar 'Vivos'** y sus bajas se reiniciarán a 0.
        * Se generará un nuevo ciclo cerrado de víctimas y armas.
        * Se enviará un correo secreto a cada participante con su objetivo.
        """)
        c1, c2 = st.columns(2)
        if c1.button("💥 Sí, Iniciar Partida", type="primary", use_container_width=True, key="pop_btn_start_yes"):
            ejecutar_inicio_partida()
        if c2.button("Cancelar", use_container_width=True, key="pop_btn_start_no"):
            st.rerun()

def ejecutar_inicio_partida():
    global df_jugadores, df_asignaciones
    # 1. Pasar a TODOS los jugadores a "Vivo" y reiniciar bajas a 0
    df_jugadores["Estado"] = "Vivo"
    df_jugadores["Bajas"] = 0
    conn.update(worksheet="Jugadores", data=df_jugadores)

    lista_vivos = df_jugadores["Nombre"].tolist()
    lista_obj = df_objetos["Nombre_Objeto"].dropna().tolist()

    if len(lista_vivos) < 2:
        st.error("Se necesitan al menos 2 jugadores registrados para iniciar.")
        return
    if len(lista_obj) == 0:
        st.error("Agrega al menos 1 objeto en el catálogo de armas.")
        return

    # 2. Generar ciclo cerrado
    df_asignaciones = generar_ciclo_cerrado(lista_vivos, lista_obj)
    conn.update(worksheet="Asignaciones", data=df_asignaciones)

    st.success("✅ ¡Partida iniciada! Todos los jugadores están VIVOS y las asignaciones se han creado en Google Sheets.")
    
    # 3. Enviar correos
    progress = st.progress(0)
    for idx, row in df_asignaciones.iterrows():
        asesino = row["Asesino"]
        victima = row["Victima"]
        objeto = row["Objeto"]
        
        email_dest = df_jugadores[df_jugadores["Nombre"] == asesino]["Email"].iloc[0]
        
        html_msg = email_service.build_assignment_email_html(
            nombre_asesino=asesino,
            nombre_victima=victima,
            objeto=objeto,
            vivos_lista=lista_vivos,
            historial_bajas=[]
        )
        email_service.send_email(
            to_email=email_dest,
            subject="🔪 [INICIO DE PARTIDA] Tu objetivo ha sido asignado - Estás Muerto",
            body_html=html_msg
        )
        progress.progress((idx + 1) / len(df_asignaciones))

    st.balloons()
    st.success("📩 Todos los correos de inicio han sido enviados.")

# ---------------------------------------------------------
# INTERFAZ PRINCIPAL EN PESTAÑAS (MÓVIL)
# ---------------------------------------------------------
tab_estado, tab_gestion, tab_setup, tab_rotacion = st.tabs([
    "🏆 Estado", "🔪 Baja", "⚙️ Setup", "🔄 Rotación"
])

# =========================================================
# PESTAÑA 1: ESTADO Y RANKING
# =========================================================
with tab_estado:
    st.subheader("🟢 Supervivientes")
    vivos = df_jugadores[df_jugadores["Estado"] == "Vivo"]
    
    if len(vivos) > 0:
        st.dataframe(vivos[["Nombre", "Email", "Bajas"]], hide_index=True, use_container_width=True)
    else:
        st.info("No hay jugadores vivos cargados. Ve a la pestaña 'Setup' para configurar la partida.")

    st.markdown("---")
    st.subheader("🥇 Ranking de Asesinos")
    ranking = df_jugadores.sort_values(by="Bajas", ascending=False)
    if len(ranking) > 0:
        st.dataframe(ranking[["Nombre", "Estado", "Bajas"]], hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader("📜 Historial de Muertes")
    if len(df_historial) > 0:
        st.dataframe(df_historial, hide_index=True, use_container_width=True)
    else:
        st.caption("Aún no se ha registrado ninguna baja.")

# =========================================================
# PESTAÑA 2: REGISTRAR BAJA
# =========================================================
with tab_gestion:
    st.subheader("☠️ Registrar un 'Asesinato'")

    vivos_list = df_jugadores[df_jugadores["Estado"] == "Vivo"]["Nombre"].dropna().tolist()

    if len(vivos_list) < 2:
        st.warning("⚠️ Quedan menos de 2 jugadores vivos o la partida no ha comenzado.")
    else:
        asesino_sel = st.selectbox("¿Quién ha ejecutado la baja?", vivos_list)
        
        # Buscar la asignación actual de este asesino
        asig_actual = df_asignaciones[df_asignaciones["Asesino"] == asesino_sel]
        
        if len(asig_actual) > 0:
            victima_actual = asig_actual.iloc[0]["Victima"]
            objeto_actual = asig_actual.iloc[0]["Objeto"]
            
            st.info(f"**Víctima actual de {asesino_sel}:** {victima_actual}  \n**Arma:** {objeto_actual}")

            if st.button("🔴 Confirmar Asesinato", type="primary", use_container_width=True):
                # 1. Buscar la asignación de la víctima caída para heredar su objetivo y arma
                asig_victima = df_asignaciones[df_asignaciones["Asesino"] == victima_actual]
                
                if len(asig_victima) > 0:
                    siguiente_victima = asig_victima.iloc[0]["Victima"]
                    siguiente_objeto = asig_victima.iloc[0]["Objeto"]
                else:
                    siguiente_victima = "N/A"
                    siguiente_objeto = "N/A"

                # 2. Actualizar estado de la víctima a 'Muerto'
                df_jugadores.loc[df_jugadores["Nombre"] == victima_actual, "Estado"] = "Muerto"
                
                # 3. Incrementar bajas del asesino
                idx_asesino = df_jugadores[df_jugadores["Nombre"] == asesino_sel].index
                df_jugadores.loc[idx_asesino, "Bajas"] = df_jugadores.loc[idx_asesino, "Bajas"] + 1

                # 4. Eliminar la asignación de la víctima y actualizar la del asesino con la herencia
                df_asignaciones = df_asignaciones[df_asignaciones["Asesino"] != victima_actual]
                df_asignaciones.loc[df_asignaciones["Asesino"] == asesino_sel, "Victima"] = siguiente_victima
                df_asignaciones.loc[df_asignaciones["Asesino"] == asesino_sel, "Objeto"] = siguiente_objeto

                # 5. Registrar en Historial
                nueva_baja = pd.DataFrame([{
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Asesino": asesino_sel,
                    "Victima": victima_actual,
                    "Objeto": objeto_actual
                }])
                df_historial = pd.concat([df_historial, nueva_baja], ignore_index=True)

                # 6. Guardar cambios en Google Sheets
                conn.update(worksheet="Jugadores", data=df_jugadores)
                conn.update(worksheet="Asignaciones", data=df_asignaciones)
                try:
                    conn.update(worksheet="Historial", data=df_historial)
                except Exception:
                    pass  # Si la pestaña Historial no existe en Google Sheets, no rompe la app

                st.success(f"🎉 ¡Baja registrada! {victima_actual} ha sido eliminado/a.")
                st.info(f"Nueva víctima de **{asesino_sel}**: `{siguiente_victima}` con el arma `{siguiente_objeto}`.")

                # 7. Enviar correo al asesino con sus nuevas órdenes
                email_asesino = df_jugadores[df_jugadores["Nombre"] == asesino_sel]["Email"].iloc[0]
                nuevos_vivos = df_jugadores[df_jugadores["Estado"] == "Vivo"]["Nombre"].tolist()
                historial_dict = df_historial.to_dict(orient="records")

                html_msg = email_service.build_assignment_email_html(
                    nombre_asesino=asesino_sel,
                    nombre_victima=siguiente_victima,
                    objeto=siguiente_objeto,
                    vivos_lista=nuevos_vivos,
                    historial_bajas=historial_dict
                )
                email_service.send_email(
                    to_email=email_asesino,
                    subject="🔪 ¡NUEVA VÍCTIMA ASIGNADA! - Estás Muerto",
                    body_html=html_msg
                )
        else:
            st.error("No se encontró asignación para este jugador.")

# =========================================================
# PESTAÑA 3: CONFIGURACIÓN / SETUP
# =========================================================
with tab_setup:
    st.subheader("⚙️ Configuración de la Partida")

    # A. Agregar nuevo jugador
    with st.expander("👤 Añadir Jugadores", expanded=True):
        col1, col2 = st.columns(2)
        nuevo_nombre = col1.text_input("Nombre del Jugador")
        nuevo_email = col2.text_input("Correo Electrónico")
        
        if st.button("➕ Agregar Jugador", use_container_width=True):
            if nuevo_nombre and nuevo_email:
                nombre_clean = nuevo_nombre.strip()
                email_clean = nuevo_email.strip().lower()

                # Comprobar nombres y correos existentes (insensible a mayúsculas/minúsculas)
                nombres_existentes = df_jugadores["Nombre"].astype(str).str.strip().str.lower().tolist()
                emails_existentes = df_jugadores["Email"].astype(str).str.strip().str.lower().tolist()
                
                if nombre_clean.lower() in nombres_existentes:
                    st.error(f"❌ Ya existe un jugador registrado con el nombre '{nombre_clean}'. Utiliza un nombre o apodo único.")
                elif email_clean in emails_existentes:
                    st.error(f"❌ El correo '{email_clean}' ya pertenece a otro jugador registrado.")
                else:
                    nuevo_registro = pd.DataFrame([{
                        "Nombre": nombre_clean,
                        "Email": email_clean,
                        "Estado": "Vivo",
                        "Bajas": 0
                    }])
                    df_jugadores = pd.concat([df_jugadores, nuevo_registro], ignore_index=True)
                    conn.update(worksheet="Jugadores", data=df_jugadores)
                    st.success(f"Jugador '{nombre_clean}' agregado correctamente.")
                    st.rerun()
            else:
                st.warning("Por favor rellena ambos campos (Nombre y Email).")

        if len(df_jugadores) > 0:
            st.markdown("---")
            st.caption("📋 **Jugadores Registrados actualmente:**")
            st.dataframe(df_jugadores[["Nombre", "Email", "Estado"]], hide_index=True, use_container_width=True)

            st.caption("🗑️ **Eliminar un jugador:**")
            c_del1, c_del2 = st.columns([2, 1])
            j_a_borrar = c_del1.selectbox("Seleccionar jugador", df_jugadores["Nombre"].tolist(), key="sel_del_j")
            if c_del2.button("🗑️ Borrar", use_container_width=True, key="btn_trigger_del_j"):
                if hasattr(st, "dialog"):
                    popup_eliminar_jugador(j_a_borrar)
                else:
                    st.session_state["pending_del_j"] = j_a_borrar

            if st.session_state.get("pending_del_j") == j_a_borrar:
                st.error(f"⚠️ ¿Confirmar eliminación de **{j_a_borrar}**?")
                c_y, c_n = st.columns(2)
                if c_y.button("Sí, Eliminar", type="primary", key="fb_j_del_y", use_container_width=True):
                    df_updated = df_jugadores[df_jugadores["Nombre"] != j_a_borrar]
                    conn.update(worksheet="Jugadores", data=df_updated)
                    st.session_state.pop("pending_del_j", None)
                    st.success(f"Jugador '{j_a_borrar}' eliminado.")
                    st.rerun()
                if c_n.button("Cancelar", key="fb_j_del_n", use_container_width=True):
                    st.session_state.pop("pending_del_j", None)
                    st.rerun()

    # B. Agregar / Ver Objetos
    with st.expander("🛋️ Catálogo de Objetos / Armas", expanded=False):
        nuevo_obj = st.text_input("Nuevo Objeto")
        if st.button("➕ Agregar Objeto", use_container_width=True):
            if nuevo_obj:
                nuevo_o = pd.DataFrame([{"Nombre_Objeto": nuevo_obj.strip()}])
                df_objetos = pd.concat([df_objetos, nuevo_o], ignore_index=True)
                conn.update(worksheet="Objetos", data=df_objetos)
                st.success(f"Objeto '{nuevo_obj}' agregado.")
                st.rerun()
        
        st.dataframe(df_objetos, hide_index=True, use_container_width=True)

        if len(df_objetos) > 0:
            st.caption("🗑️ **Eliminar un objeto del catálogo:**")
            c_o1, c_o2 = st.columns([2, 1])
            o_a_borrar = c_o1.selectbox("Seleccionar objeto", df_objetos["Nombre_Objeto"].dropna().tolist(), key="sel_del_o")
            if c_o2.button("🗑️ Borrar", use_container_width=True, key="btn_trigger_del_o"):
                if hasattr(st, "dialog"):
                    popup_eliminar_objeto(o_a_borrar)
                else:
                    st.session_state["pending_del_o"] = o_a_borrar

            if st.session_state.get("pending_del_o") == o_a_borrar:
                st.error(f"⚠️ ¿Confirmar eliminación de **{o_a_borrar}**?")
                c_y, c_n = st.columns(2)
                if c_y.button("Sí, Eliminar", type="primary", key="fb_o_del_y", use_container_width=True):
                    df_updated = df_objetos[df_objetos["Nombre_Objeto"] != o_a_borrar]
                    conn.update(worksheet="Objetos", data=df_updated)
                    st.session_state.pop("pending_del_o", None)
                    st.success(f"Objeto '{o_a_borrar}' eliminado.")
                    st.rerun()
                if c_n.button("Cancelar", key="fb_o_del_n", use_container_width=True):
                    st.session_state.pop("pending_del_o", None)
                    st.rerun()

    st.markdown("---")
    # C. Botón para Iniciar Partida
    st.subheader("🚀 Iniciar Partida & Repartir Víctimas")
    st.caption("Al pulsar este botón se confirmará el inicio de la partida. Todos los jugadores pasarán a estar VIVOS, se reiniciarán las bajas a 0 y se enviará un correo secreto a cada participante.")

    if st.button("💥 INICIAR Y REPARTIR DÍAS INICIALES", type="primary", use_container_width=True, key="btn_trigger_start_game"):
        if hasattr(st, "dialog"):
            popup_iniciar_partida()
        else:
            st.session_state["pending_start_game"] = True

    if st.session_state.get("pending_start_game"):
        st.warning("⚠️ **¿Confirmar inicio de partida?** Todos los jugadores pasarán a estar 'Vivos' y se enviarán los correos iniciales.")
        c_y, c_n = st.columns(2)
        if c_y.button("💥 Sí, Iniciar Partida", type="primary", key="fb_start_yes", use_container_width=True):
            st.session_state.pop("pending_start_game", None)
            ejecutar_inicio_partida()
        if c_n.button("Cancelar", key="fb_start_no", use_container_width=True):
            st.session_state.pop("pending_start_game", None)
            st.rerun()

# =========================================================
# PESTAÑA 4: ROTACIÓN CADA 3 DÍAS
# =========================================================
with tab_rotacion:
    st.subheader("🔄 Rotación de 3 Días")
    st.write("""
    Para agilizar la partida o por si sospechan de alguien, puedes ejecutar una **rotación periódica**.
    Esto reorganiza los objetivos y redistribuye las armas entre los jugadores que siguen **vivos**, enviando un nuevo correo secreto a cada uno.
    """)

    if st.button("🔀 Ejecutar Rotación Ahora", type="primary", use_container_width=True):
        lista_vivos = df_jugadores[df_jugadores["Estado"] == "Vivo"]["Nombre"].tolist()
        lista_obj = df_objetos["Nombre_Objeto"].dropna().tolist()

        if len(lista_vivos) < 2:
            st.error("No hay suficientes supervivientes para rotar.")
        else:
            df_asignaciones = generar_ciclo_cerrado(lista_vivos, lista_obj)
            conn.update(worksheet="Asignaciones", data=df_asignaciones)
            st.success("✅ ¡Objetivos y armas reordenados!")

            historial_dict = df_historial.to_dict(orient="records")
            progress = st.progress(0)
            for idx, row in df_asignaciones.iterrows():
                asesino = row["Asesino"]
                victima = row["Victima"]
                objeto = row["Objeto"]
                
                email_dest = df_jugadores[df_jugadores["Nombre"] == asesino]["Email"].iloc[0]
                
                html_msg = email_service.build_assignment_email_html(
                    nombre_asesino=asesino,
                    nombre_victima=victima,
                    objeto=objeto,
                    vivos_lista=lista_vivos,
                    historial_bajas=historial_dict
                )
                email_service.send_email(
                    to_email=email_dest,
                    subject="🔄 [ROTACIÓN DE OBJETIVOS] Tu nueva víctima y arma - Estás Muerto",
                    body_html=html_msg
                )
                progress.progress((idx + 1) / len(df_asignaciones))

            st.success("📩 Notificaciones de rotación enviadas a todos los supervivientes.")
