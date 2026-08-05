import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

def get_database_url() -> str:
    """Busca la URL de la base de datos en st.secrets (Streamlit Cloud) y luego en os.environ."""
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if "DATABASE_URL" in st.secrets:
                return str(st.secrets["DATABASE_URL"]).strip()
            if "database_url" in st.secrets:
                return str(st.secrets["database_url"]).strip()
            if "postgres" in st.secrets and "url" in st.secrets["postgres"]:
                return str(st.secrets["postgres"]["url"]).strip()
            if "db" in st.secrets and "url" in st.secrets["db"]:
                return str(st.secrets["db"]["url"]).strip()
    except Exception:
        pass

    return os.environ.get("DATABASE_URL", "sqlite:///./estas_muerto.db").strip()


DATABASE_URL = get_database_url()

# Soporte para URLs de PostgreSQL en Heroku/Render/Supabase (que usan postgres:// en lugar de postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # Evita desconexiones por inactividad comprobando la conexión automáticamente
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Generador de sesiones de base de datos para context manager o FastAPI/Streamlit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Crea las tablas en la base de datos si no existen y auto-migra columnas faltantes."""
    import models  # Asegura la carga de los modelos
    Base.metadata.create_all(bind=engine)

    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        if "users" in tables:
            columns = [c["name"] for c in inspector.get_columns("users")]
            with engine.connect() as conn:
                if "recibir_correos" not in columns:
                    if engine.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS recibir_correos BOOLEAN DEFAULT TRUE;"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN recibir_correos BOOLEAN DEFAULT 1;"))

                if "reset_token" not in columns:
                    if engine.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(255);"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN reset_token VARCHAR(255);"))

                if "reset_token_expires" not in columns:
                    if engine.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMP;"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN reset_token_expires DATETIME;"))
                conn.commit()

        if "rooms" in tables:
            columns = [c["name"] for c in inspector.get_columns("rooms")]
            with engine.connect() as conn:
                if "modo_ciego" not in columns:
                    if engine.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS modo_ciego BOOLEAN DEFAULT FALSE;"))
                    else:
                        conn.execute(text("ALTER TABLE rooms ADD COLUMN modo_ciego BOOLEAN DEFAULT 0;"))
                conn.commit()

        if "players" in tables:
            columns = [c["name"] for c in inspector.get_columns("players")]
            with engine.connect() as conn:
                if "cambios_restantes" not in columns:
                    if engine.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE players ADD COLUMN IF NOT EXISTS cambios_restantes INTEGER DEFAULT 1;"))
                    else:
                        conn.execute(text("ALTER TABLE players ADD COLUMN cambios_restantes INTEGER DEFAULT 1;"))
                if "cambios_gratuitos" not in columns:
                    if engine.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE players ADD COLUMN IF NOT EXISTS cambios_gratuitos INTEGER DEFAULT 1;"))
                    else:
                        conn.execute(text("ALTER TABLE players ADD COLUMN cambios_gratuitos INTEGER DEFAULT 1;"))
                if "cambios_bonus" not in columns:
                    if engine.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE players ADD COLUMN IF NOT EXISTS cambios_bonus INTEGER DEFAULT 0;"))
                    else:
                        conn.execute(text("ALTER TABLE players ADD COLUMN cambios_bonus INTEGER DEFAULT 0;"))
                if "cambios_realizados" not in columns:
                    if engine.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE players ADD COLUMN IF NOT EXISTS cambios_realizados INTEGER DEFAULT 0;"))
                    else:
                        conn.execute(text("ALTER TABLE players ADD COLUMN cambios_realizados INTEGER DEFAULT 0;"))
                if "created_at" not in columns:
                    if engine.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE players ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
                    else:
                        conn.execute(text("ALTER TABLE players ADD COLUMN created_at DATETIME;"))
                
                # Saneamiento de datos preexistentes: ajustar cambios gratuitos al máximo de 1
                conn.execute(text("UPDATE players SET cambios_gratuitos = 1 WHERE cambios_gratuitos IS NULL OR cambios_gratuitos > 1;"))
                conn.execute(text("UPDATE players SET cambios_bonus = 0 WHERE cambios_bonus IS NULL;"))
                conn.execute(text("UPDATE players SET cambios_realizados = 0 WHERE cambios_realizados IS NULL;"))
                conn.execute(text("UPDATE players SET cambios_restantes = (COALESCE(cambios_gratuitos, 1) + COALESCE(cambios_bonus, 0));"))
                conn.commit()

    except Exception as e:
        print(f"Nota auto-migración de esquema: {e}")
