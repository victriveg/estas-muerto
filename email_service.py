import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st

def send_email(to_email, subject, body_html):
    """
    Envía un correo electrónico usando las credenciales SMTP configuradas en .streamlit/secrets.toml.
    Si no hay credenciales configuradas, muestra una advertencia sin romper la app.
    """
    try:
        smtp_secrets = st.secrets.get("smtp", {})
        sender_email = smtp_secrets.get("sender_email")
        sender_password = smtp_secrets.get("sender_password")
        smtp_server = smtp_secrets.get("smtp_server", "smtp.gmail.com")
        smtp_port = int(smtp_secrets.get("smtp_port", 587))
    except Exception as e:
        st.warning(f"No se pudieron leer las credenciales SMTP de secrets.toml: {e}")
        return False

    if not sender_email or not sender_password or sender_email == "tu_cuenta@gmail.com":
        st.info(f"📧 [Simulación de Correo] Para: {to_email}\nAsunto: {subject}\n\n(Configura la sección [smtp] en secrets.toml para enviar correos reales)")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"Estás Muerto 🔪 <{sender_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # Adjuntar cuerpo HTML
        msg.attach(MIMEText(body_html, "html"))

        # Conectar al servidor SMTP
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        
        return True
    except Exception as e:
        st.error(f"Error al enviar correo a {to_email}: {e}")
        return False


def build_assignment_email_html(nombre_asesino, nombre_victima, objeto, vivos_lista, historial_bajas=None):
    """
    Construye la plantilla HTML del correo para un jugador con su objetivo asignado.
    """
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
