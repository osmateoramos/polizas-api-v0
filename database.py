"""Conexión a la base de datos: engine, fábrica de sesiones y `get_db`."""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings


class Base(DeclarativeBase):
    pass


def crear_engine(url: str) -> Engine:
    """Engine para `url`. En SQLite activa las claves foráneas en CADA conexión:
    SQLite las trae apagadas y el PRAGMA vale solo para la conexión que lo ejecuta."""
    if not url.startswith("sqlite"):
        return create_engine(url)

    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _activar_claves_foraneas(conexion_dbapi, _registro):
        cursor = conexion_dbapi.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


engine = crear_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Una sesión por petición: se abre al entrar y se cierra al terminar, pase lo
    que pase. Un error en una petición ya no deja la sesión rota para las demás."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
