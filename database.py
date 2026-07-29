import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# URL de conexión: por defecto usa SQLite local para pruebas, o la variable DATABASE_URL (PostgreSQL) en producción
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./estas_muerto.db")

# Soporte para URLs de PostgreSQL en Heroku/Render/Supabase (que usan postgres:// en lugar de postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
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
    """Crea las tablas en la base de datos si no existen."""
    import models  # Asegura la carga de los modelos
    Base.metadata.create_all(bind=engine)
