from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Text
)
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    """Modelo para representar a los usuarios registrados en el sistema."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)  # Hash para futuro inicio de sesión
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relación con las participaciones del usuario en salas
    players = relationship("Player", back_populates="user", cascade="all, delete-orphan")


class Room(Base):
    """Modelo para representar las salas o partidas de juego independientes."""
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    codigo = Column(String(10), unique=True, index=True, nullable=False)  # Código único de sala (ej. 'GAME12')
    nombre = Column(String(100), nullable=False)
    estado = Column(String(20), default="espera", nullable=False)  # 'espera', 'en_juego', 'finalizada'
    host_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones pertenecientes a esta sala
    host = relationship("User", foreign_keys=[host_id])
    players = relationship("Player", back_populates="room", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="room", cascade="all, delete-orphan")
    history_logs = relationship("HistoryLog", back_populates="room", cascade="all, delete-orphan")
    objects = relationship("GameObject", back_populates="room", cascade="all, delete-orphan")


class Player(Base):
    """Modelo para relacionar a un User con una Room concreta y almacenar su estado en dicha partida."""
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    estado = Column(String(20), default="vivo", nullable=False)  # 'vivo', 'muerto'
    bajas = Column(Integer, default=0, nullable=False)
    cambios_restantes = Column(Integer, default=2, nullable=False)
    fecha_eliminacion = Column(DateTime, nullable=True)

    # Restricción: Un usuario solo puede registrarse una vez en una misma sala
    __table_args__ = (
        UniqueConstraint("user_id", "room_id", name="uq_user_room"),
    )

    # Relaciones
    user = relationship("User", back_populates="players")
    room = relationship("Room", back_populates="players")

    # Asignaciones donde este jugador actúa como Asesino o como Víctima
    assignments_as_killer = relationship("Assignment", foreign_keys="Assignment.asesino_id", back_populates="asesino")
    assignments_as_victim = relationship("Assignment", foreign_keys="Assignment.victima_id", back_populates="victima")


class Assignment(Base):
    """Modelo para almacenar las asignaciones activas de objetivo y arma filtradas por room_id."""
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    asesino_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    victima_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    objeto = Column(String(255), nullable=False)

    # Restricción: Cada jugador (asesino) tiene una única asignación activa por sala
    __table_args__ = (
        UniqueConstraint("room_id", "asesino_id", name="uq_room_asesino"),
    )

    # Relaciones
    room = relationship("Room", back_populates="assignments")
    asesino = relationship("Player", foreign_keys=[asesino_id], back_populates="assignments_as_killer")
    victima = relationship("Player", foreign_keys=[victima_id], back_populates="assignments_as_victim")


class GameObject(Base):
    """Modelo para almacenar el catálogo de objetos/armas (globales o específicos por sala)."""
    __tablename__ = "objects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=True)  # Null = Objeto global
    nombre_objeto = Column(String(255), nullable=False)

    room = relationship("Room", back_populates="objects")


class HistoryLog(Base):
    """Modelo para almacenar el historial de muertes por sala."""
    __tablename__ = "history_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    asesino_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    victima_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    objeto = Column(String(255), nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow)

    room = relationship("Room", back_populates="history_logs")
    asesino = relationship("Player", foreign_keys=[asesino_id])
    victima = relationship("Player", foreign_keys=[victima_id])


class KillClaim(Base):
    """Modelo para almacenar las solicitudes pendientes de confirmación de asesinato entre jugadores."""
    __tablename__ = "kill_claims"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    asesino_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    victima_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    estado = Column(String(20), default="pendiente", nullable=False)  # 'pendiente', 'confirmado', 'rechazado'
    created_at = Column(DateTime, default=datetime.utcnow)

    room = relationship("Room")
    asesino = relationship("Player", foreign_keys=[asesino_id])
    victima = relationship("Player", foreign_keys=[victima_id])

