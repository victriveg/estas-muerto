import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

_engine = None
_SessionFactory = None


def get_database_url() -> str:
    """Busca la URL de la base de datos en st.secrets (Streamlit Cloud, incluso en secciones anidadas) y luego en os.environ."""
    try:
        import streamlit as st
        try:
            if hasattr(st, "secrets"):
                if "DATABASE_URL" in st.secrets:
                    url = str(st.secrets["DATABASE_URL"]).strip()
                    if url: return url
                if "database_url" in st.secrets:
                    url = str(st.secrets["database_url"]).strip()
                    if url: return url
                if "postgres" in st.secrets and "url" in st.secrets["postgres"]:
                    url = str(st.secrets["postgres"]["url"]).strip()
                    if url: return url
                if "db" in st.secrets and "url" in st.secrets["db"]:
                    url = str(st.secrets["db"]["url"]).strip()
                    if url: return url

                for k, v in st.secrets.items():
                    try:
                        if hasattr(v, "__getitem__"):
                            if "DATABASE_URL" in v:
                                url = str(v["DATABASE_URL"]).strip()
                                if url: return url
                            if "database_url" in v:
                                url = str(v["database_url"]).strip()
                                if url: return url
                            if "url" in v and "postgres" in str(v["url"]).lower():
                                url = str(v["url"]).strip()
                                if url: return url
                    except Exception:
                        pass
        except Exception:
            pass
    except Exception:
        pass

    return os.environ.get("DATABASE_URL", "sqlite:///./estas_muerto.db").strip()


import urllib.parse

def clean_database_url(raw_url: str) -> str:
    """Codifica caracteres especiales en la contraseña (como + o *) y ajusta prefijos de dialecto."""
    url = raw_url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    if url.startswith("postgresql://"):
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.password:
                encoded_password = urllib.parse.quote(parsed.password, safe="")
                user = parsed.username or ""
                host = parsed.hostname or ""
                port = f":{parsed.port}" if parsed.port else ""
                netloc = f"{user}:{encoded_password}@{host}{port}"
                url = urllib.parse.urlunparse((
                    parsed.scheme,
                    netloc,
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment
                ))
        except Exception:
            pass
    return url


def get_engine():
    """Retorna el motor de SQLAlchemy instanciado perezosamente (lazy) cuando st.secrets está disponible."""
    global _engine
    if _engine is None:
        url = clean_database_url(get_database_url())

        connect_args = {}
        if url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        _engine = create_engine(
            url,
            connect_args=connect_args,
            pool_pre_ping=True,
            echo=False
        )
    return _engine


class LazyEngineProxy:
    """Proxy para acceder al engine sin instanciarlo antes de que st.secrets esté listo."""
    @property
    def name(self):
        return get_engine().name

    def connect(self, *args, **kwargs):
        return get_engine().connect(*args, **kwargs)

    def execute(self, *args, **kwargs):
        return get_engine().execute(*args, **kwargs)


engine = LazyEngineProxy()


def SessionLocal():
    """Genera una sesión de base de datos conectando al motor lazy."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionFactory()


from contextlib import contextmanager

@contextmanager
def get_db_session():
    """Context manager para operaciones de base de datos con rollback automático y cierre garantizado."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    """Generador de sesiones de base de datos para context manager."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Crea las tablas en la base de datos si no existen y auto-migra columnas faltantes."""
    try:
        eng = get_engine()
        import models  # Asegura la carga de los modelos
        Base.metadata.create_all(bind=eng)

        inspector = inspect(eng)
        tables = inspector.get_table_names()

        if "users" in tables:
            columns = [c["name"] for c in inspector.get_columns("users")]
            with eng.connect() as conn:
                if "recibir_correos" not in columns:
                    if eng.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS recibir_correos BOOLEAN DEFAULT TRUE;"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN recibir_correos BOOLEAN DEFAULT 1;"))

                if "reset_token" not in columns:
                    if eng.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(255);"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN reset_token VARCHAR(255);"))

                if "reset_token_expires" not in columns:
                    if eng.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMP;"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN reset_token_expires DATETIME;"))
                conn.commit()

        if "rooms" in tables:
            columns = [c["name"] for c in inspector.get_columns("rooms")]
            with eng.connect() as conn:
                if "modo_ciego" not in columns:
                    if eng.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS modo_ciego BOOLEAN DEFAULT FALSE;"))
                    else:
                        conn.execute(text("ALTER TABLE rooms ADD COLUMN modo_ciego BOOLEAN DEFAULT 0;"))
                conn.commit()

        if "players" in tables:
            columns = [c["name"] for c in inspector.get_columns("players")]
            with eng.connect() as conn:
                if "cambios_restantes" not in columns:
                    if eng.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE players ADD COLUMN IF NOT EXISTS cambios_restantes INTEGER DEFAULT 1;"))
                    else:
                        conn.execute(text("ALTER TABLE players ADD COLUMN cambios_restantes INTEGER DEFAULT 1;"))
                if "cambios_gratuitos" not in columns:
                    if eng.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE players ADD COLUMN IF NOT EXISTS cambios_gratuitos INTEGER DEFAULT 1;"))
                    else:
                        conn.execute(text("ALTER TABLE players ADD COLUMN cambios_gratuitos INTEGER DEFAULT 1;"))
                if "cambios_bonus" not in columns:
                    if eng.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE players ADD COLUMN IF NOT EXISTS cambios_bonus INTEGER DEFAULT 0;"))
                    else:
                        conn.execute(text("ALTER TABLE players ADD COLUMN cambios_bonus INTEGER DEFAULT 0;"))
                if "cambios_realizados" not in columns:
                    if eng.dialect.name == "postgresql":
                        conn.execute(text("ALTER TABLE players ADD COLUMN IF NOT EXISTS cambios_realizados INTEGER DEFAULT 0;"))
                    else:
                        conn.execute(text("ALTER TABLE players ADD COLUMN cambios_realizados INTEGER DEFAULT 0;"))
                if "created_at" not in columns:
                    if eng.dialect.name == "postgresql":
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
