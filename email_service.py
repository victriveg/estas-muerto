import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st

def get_smtp_credentials():
    """
    Obtiene las credenciales de correo buscando en st.secrets (tanto [smtp] como nivel raíz)
    y en variables de entorno (os.environ).
    """
    sender_email = None
    sender_password = None
    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    # 1. Buscar en st.secrets["smtp"]
    try:
        if hasattr(st, "secrets") and "smtp" in st.secrets:
            smtp_sec = st.secrets["smtp"]
            sender_email = (
                smtp_sec.get("sender_email") or 
                smtp_sec.get("SMTP_EMAIL") or 
                smtp_sec.get("SMTP_USER") or 
                smtp_sec.get("email") or 
                smtp_sec.get("user")
            )
            sender_password = (
                smtp_sec.get("sender_password") or 
                smtp_sec.get("SMTP_PASSWORD") or 
                smtp_sec.get("SMTP_PASS") or 
                smtp_sec.get("password") or 
                smtp_sec.get("pass")
            )
            smtp_server = smtp_sec.get("smtp_server") or smtp_sec.get("SMTP_SERVER") or smtp_server
            if smtp_sec.get("smtp_port") or smtp_sec.get("SMTP_PORT"):
                smtp_port = int(smtp_sec.get("smtp_port") or smtp_sec.get("SMTP_PORT"))
    except Exception:
        pass

    # 2. Buscar en st.secrets nivel raíz
    try:
        if hasattr(st, "secrets"):
            sender_email = sender_email or (
                st.secrets.get("sender_email") or 
                st.secrets.get("SMTP_EMAIL") or 
                st.secrets.get("SMTP_USER") or 
                st.secrets.get("email")
            )
            sender_password = sender_password or (
                st.secrets.get("sender_password") or 
                st.secrets.get("SMTP_PASSWORD") or 
                st.secrets.get("SMTP_PASS") or 
                st.secrets.get("password")
            )
            smtp_server = st.secrets.get("smtp_server") or st.secrets.get("SMTP_SERVER") or smtp_server
            if st.secrets.get("smtp_port") or st.secrets.get("SMTP_PORT"):
                smtp_port = int(st.secrets.get("smtp_port") or st.secrets.get("SMTP_PORT"))
    except Exception:
        pass

    # 3. Buscar en os.environ
    sender_email = sender_email or os.environ.get("SENDER_EMAIL") or os.environ.get("SMTP_EMAIL") or os.environ.get("SMTP_USER")
    sender_password = sender_password or os.environ.get("SENDER_PASSWORD") or os.environ.get("SMTP_PASSWORD") or os.environ.get("SMTP_PASS")
    smtp_server = os.environ.get("SMTP_SERVER") or smtp_server
    if os.environ.get("SMTP_PORT"):
        smtp_port = int(os.environ.get("SMTP_PORT"))

    return sender_email, sender_password, smtp_server, smtp_port


def send_email(to_email, subject, body_html):
    """
    Envía un correo electrónico usando las credenciales SMTP configuradas.
    Si el usuario tiene desmarcada la opción de recibir correos, se omite el envío.
    """
    try:
        from database import SessionLocal
        from models import User
        tmp_db = SessionLocal()
        user_obj = tmp_db.query(User).filter_by(email=to_email).first()
        recibir = getattr(user_obj, "recibir_correos", True) if user_obj else True
        tmp_db.close()
        if recibir is False:
            # El usuario ha desactivado la recepción de correos de la partida
            return True
    except Exception:
        pass

    sender_email, sender_password, smtp_server, smtp_port = get_smtp_credentials()

    if not sender_email or not sender_password or sender_email == "tu_cuenta@gmail.com":
        st.info(f"📧 [Simulación de Correo] Para: {to_email}\nAsunto: {subject}\n\n⚠️ No se detectaron credenciales SMTP válidas en secrets.toml o Streamlit Secrets.")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"Estás Muerto 🔪 <{sender_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # Adjuntar cuerpo HTML
        msg.attach(MIMEText(body_html, "html"))

        # Conectar al servidor SMTP (Soporta Port 465 SSL y Port 587 STARTTLS)
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, to_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, to_email, msg.as_string())
        
        return True
    except smtplib.SMTPAuthenticationError as e:
        st.error(f"❌ Error de Autenticación SMTP ({sender_email}): {e}\n\n💡 **Solución para Gmail:** Google requiere una **Contraseña de Aplicación** de 16 caracteres (no tu contraseña habitual). Genera una en `Cuenta de Google -> Seguridad -> Verificación en 2 pasos -> Contraseñas de aplicaciones`.")
        return False
    except Exception as e:
        st.error(f"❌ Error al enviar correo a {to_email}: {e}")
        return False


def build_assignment_email_html(nombre_asesino, nombre_victima, objeto, vivos_lista, historial_bajas=None, modo_ciego=False):
    """
    Construye la plantilla HTML del correo para un jugador con su objetivo asignado.
    """
    if modo_ciego:
        vivos_html = "<li>🎭 <i>Modo Asesino Ciego Activado: Las identidades de los supervivientes permanecen en las sombras.</i></li>"
    else:
        vivos_html = "".join([f"<li>{v}</li>" for v in vivos_lista])
    
    bajas_html = ""
    if historial_bajas:
        bajas_items = "".join([f"<li>☠️ <b>{b.get('Asesino')}</b> eliminó a <b>{b.get('Victima')}</b></li>" for b in historial_bajas])
        bajas_html = f"""
        <hr style="border: 0; border-top: 1px solid #444; margin: 20px 0;">
        <h4 style="color: #e74c3c;">📜 Historial de Bajas</h4>
        <ul>{bajas_items}</ul>
        """

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #121212; color: #ffffff; padding: 20px;">
        <div style="max-width: 500px; margin: 0 auto; background: #1e1e1e; padding: 25px; border-radius: 12px; border: 1px solid #333;">
            <h2 style="color: #e74c3c; text-align: center; margin-bottom: 5px;">🔪 ESTÁS MUERTO 🔪</h2>
            <p style="text-align: center; color: #888; font-size: 14px;">Instrucciones secretas de la partida</p>
            <hr style="border: 0; border-top: 1px solid #444; margin: 20px 0;">
            
            <p>Hola <b>{nombre_asesino}</b>,</p>
            <p>Tus órdenes para el juego son las siguientes:</p>
            
            <div style="background: #2a2a2a; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #e74c3c;">
                <p style="margin: 5px 0;">🎯 <b>Tu Víctima:</b> <span style="color: #ff6b6b; font-size: 18px; font-weight: bold;">{nombre_victima}</span></p>
                <p style="margin: 5px 0;">🛋️ <b>Tu Arma / Objeto:</b> <span style="color: #fca311; font-size: 18px; font-weight: bold;">{objeto}</span></p>
            </div>
            
            <p style="font-size: 13px; color: #aaa;">
                💡 <i>Debes provocar la situación para que {nombre_victima} interactúe con el arma "{objeto}" sin que sospeche. Cuando lo logres, avisa al organizador para registrar la baja.</i>
            </p>
            
            <hr style="border: 0; border-top: 1px solid #444; margin: 20px 0;">
            <h4 style="color: #4cc9f0;">🟢 Supervivientes en la Partida ({len(vivos_lista)})</h4>
            <ul style="line-height: 1.6;">
                {vivos_html}
            </ul>
            
            {bajas_html}
            
            <hr style="border: 0; border-top: 1px solid #333; margin: 20px 0;">
            <p style="text-align: center; font-size: 11px; color: #666;">Juego "Estás Muerto" - Panel de Control</p>
        </div>
    </body>
    </html>
    """
    return html


def build_game_over_email_html(nombre_ganador, ranking_lista, historial_bajas=None):
    """
    Construye la plantilla HTML del correo de FIN DE PARTIDA con el podio,
    duración de supervivencia y ranking completo con empates compartidos.
    """
    rows_html = ""
    for r in ranking_lista:
        pos = r.get("Posicion")
        nombre = r.get("Nombre")
        kills = r.get("Bajas")
        tiempo = r.get("Tiempo_Supervivencia")
        
        # Icono según posición
        if pos == 1:
            icon = "🥇 1º"
            badge_color = "#fca311"
        elif pos == 2:
            icon = "🥈 2º"
            badge_color = "#e0e0e0"
        elif pos == 3:
            icon = "🥉 3º"
            badge_color = "#cd7f32"
        else:
            icon = f"{pos}º"
            badge_color = "#888888"

        rows_html += f"""
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 12px 8px; text-align: center; font-weight: bold; font-size: 15px; color: {badge_color};">{icon}</td>
            <td style="padding: 12px 8px; font-weight: bold; color: #ffffff; font-size: 15px;">{nombre}</td>
            <td style="padding: 12px 8px; text-align: center; color: #ff6b6b; font-weight: bold; font-size: 14px;">{kills} kills</td>
            <td style="padding: 12px 8px; font-size: 13px; color: #aaaaaa;">{tiempo}</td>
        </tr>
        """

    bajas_html = ""
    if historial_bajas:
        bajas_items = "".join([f"<li>☠️ <b>{b.get('Asesino')}</b> eliminó a <b>{b.get('Victima')}</b> ({b.get('Objeto')}) el {b.get('Fecha')}</li>" for b in historial_bajas])
        bajas_html = f"""
        <hr style="border: 0; border-top: 1px solid #444; margin: 25px 0;">
        <h4 style="color: #e74c3c;">📜 Historial Completo de Bajas</h4>
        <ul style="line-height: 1.6; color: #ccc; font-size: 13px;">{bajas_items}</ul>
        """

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #121212; color: #ffffff; padding: 20px;">
        <div style="max-width: 580px; margin: 0 auto; background: #1e1e1e; padding: 30px; border-radius: 14px; border: 2px solid #fca311;">
            <h1 style="color: #fca311; text-align: center; margin-bottom: 5px; font-size: 26px;">🏆 ¡PARTIDA FINALIZADA! 🏆</h1>
            <p style="text-align: center; color: #888; font-size: 15px;">Juego "Estás Muerto"</p>
            <hr style="border: 0; border-top: 1px solid #444; margin: 20px 0;">
            
            <div style="background: linear-gradient(135deg, #2a2a2a 0%, #1a1a1a 100%); padding: 20px; border-radius: 10px; text-align: center; border: 1px solid #fca311; margin-bottom: 25px;">
                <p style="color: #aaaaaa; margin: 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">👑 ÚLTIMO SUPERVIVIENTE & GANADOR/A 👑</p>
                <h2 style="color: #fca311; font-size: 30px; margin: 10px 0;">{nombre_ganador}</h2>
                <p style="color: #4cc9f0; margin: 0; font-size: 14px;">¡Ha logrado eliminar a todos sus oponentes y alzarse con la victoria!</p>
            </div>
            
            <h3 style="color: #ffffff; margin-bottom: 15px;">📊 Clasificación & Ranking Final</h3>
            <table style="width: 100%; border-collapse: collapse; background: #252525; border-radius: 8px; overflow: hidden;">
                <thead>
                    <tr style="background: #333333; color: #aaaaaa; font-size: 12px; text-align: left;">
                        <th style="padding: 10px 8px; text-align: center;">POS</th>
                        <th style="padding: 10px 8px;">JUGADOR</th>
                        <th style="padding: 10px 8px; text-align: center;">KILLS</th>
                        <th style="padding: 10px 8px;">SUPERVIVENCIA</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
            
            {bajas_html}
            
            <hr style="border: 0; border-top: 1px solid #333; margin: 25px 0;">
            <p style="text-align: center; font-size: 11px; color: #666;">Gracias por jugar a "Estás Muerto" 🔪</p>
        </div>
    </body>
    </html>
    """
    return html


def build_item_change_email_html(nombre_jugador, nuevo_objeto, cambios_restantes, nombre_victima=None):
    """
    Construye la plantilla HTML del correo tras un cambio/rotación individual de arma.
    """
    victima_html = ""
    if nombre_victima:
        victima_html = f'<p style="margin: 5px 0;">🎯 <b>Tu Víctima Sigue Siendo:</b> <span style="color: #ff6b6b; font-size: 18px; font-weight: bold;">{nombre_victima}</span></p>'

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #121212; color: #ffffff; padding: 20px;">
        <div style="max-width: 500px; margin: 0 auto; background: #1e1e1e; padding: 25px; border-radius: 12px; border: 1px solid #333;">
            <h2 style="color: #e74c3c; text-align: center; margin-bottom: 5px;">🔪 ESTÁS MUERTO 🔪</h2>
            <p style="text-align: center; color: #888; font-size: 14px;">🔄 CAMBIO DE ARMA / ROTACIÓN INDIVIDUAL</p>
            <hr style="border: 0; border-top: 1px solid #444; margin: 20px 0;">
            
            <p>Hola <b>{nombre_jugador}</b>,</p>
            <p>Se ha ejecutado un cambio de arma para ti. A partir de ahora tu armamento ha sido actualizado:</p>
            
            <div style="background: #2a2a2a; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #fca311;">
                {victima_html}
                <p style="margin: 5px 0;">🛋️ <b>Tu Nueva Arma / Objeto:</b> <span style="color: #fca311; font-size: 18px; font-weight: bold;">{nuevo_objeto}</span></p>
                <p style="margin: 5px 0;">🔄 <b>Cambios Restantes:</b> <span style="color: #4cc9f0; font-size: 16px; font-weight: bold;">{cambios_restantes}</span></p>
            </div>
            
            <p style="font-size: 13px; color: #aaa;">
                💡 <i>Recuerda eliminar a tu víctima utilizando únicamente tu nueva arma "{nuevo_objeto}".</i>
            </p>
            
            <hr style="border: 0; border-top: 1px solid #333; margin: 20px 0;">
            <p style="text-align: center; font-size: 11px; color: #666;">Juego "Estás Muerto" - Panel de Control</p>
        </div>
    </body>
    </html>
    """
    return html


def send_item_change_email(to_email, nombre_jugador, nuevo_objeto, cambios_restantes, nombre_victima=None):
    """
    Envía un correo electrónico al jugador notificando su nueva arma y cambios restantes.
    """
    html_msg = build_item_change_email_html(
        nombre_jugador=nombre_jugador,
        nuevo_objeto=nuevo_objeto,
        cambios_restantes=cambios_restantes,
        nombre_victima=nombre_victima
    )
    subject = "🔄 [CAMBIO DE ARMA] Tu nueva arma ha sido asignada - Estás Muerto"
    return send_email(to_email=to_email, subject=subject, body_html=html_msg)


def build_password_reset_email_html(nombre_usuario, token):
    """
    Construye la plantilla HTML del correo para el restablecimiento de contraseña.
    """
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #121212; color: #ffffff; padding: 20px;">
        <div style="max-width: 500px; margin: 0 auto; background: #1e1e1e; padding: 25px; border-radius: 12px; border: 1px solid #333;">
            <h2 style="color: #e74c3c; text-align: center; margin-bottom: 5px;">🔪 ESTÁS MUERTO 🔪</h2>
            <p style="text-align: center; color: #888; font-size: 14px;">🔑 RECUPERACIÓN DE CONTRASEÑA</p>
            <hr style="border: 0; border-top: 1px solid #444; margin: 20px 0;">
            
            <p>Hola <b>{nombre_usuario}</b>,</p>
            <p>Hemos recibido una solicitud para restablecer la contraseña de tu cuenta.</p>
            
            <div style="background: #2a2a2a; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center; border: 1px solid #4cc9f0;">
                <p style="margin: 0; color: #aaa; font-size: 13px;">TU CÓDIGO DE RECUPERACIÓN (OTP)</p>
                <h1 style="color: #4cc9f0; font-size: 36px; letter-spacing: 5px; margin: 10px 0;">{token}</h1>
                <p style="margin: 0; color: #888; font-size: 12px;">Este código caducará en 15 minutos.</p>
            </div>
            
            <p style="font-size: 13px; color: #aaa;">
                💡 <i>Si no has sido tú quien solicitó este cambio, puedes ignorar este correo de forma segura.</i>
            </p>
            
            <hr style="border: 0; border-top: 1px solid #333; margin: 20px 0;">
            <p style="text-align: center; font-size: 11px; color: #666;">Juego "Estás Muerto" - Panel de Control</p>
        </div>
    </body>
    </html>
    """
    return html


def send_password_reset_email(to_email, nombre_usuario, token):
    """
    Envía el correo electrónico con el código OTP para restablecer la contraseña.
    """
    html_msg = build_password_reset_email_html(nombre_usuario, token)
    subject = "🔑 [RESTABLECER CONTRASEÑA] Tu código de recuperación - Estás Muerto"
    return send_email(to_email=to_email, subject=subject, body_html=html_msg)
