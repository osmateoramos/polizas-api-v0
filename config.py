"""Configuración del servicio, leída del entorno y de `.env`."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cada campo se toma de la variable de entorno homónima (sin distinguir
    mayúsculas) o, si no está, de `.env`. Las variables de entorno mandan sobre
    `.env`: así la batería de tests y el calificador apuntan la aplicación a otra
    base con `DATABASE_URL=... uvicorn main:app`.

    Los valores por defecto sirven para desarrollo y para que el contenedor
    arranque sin `.env`; los secretos reales van solo en `.env`, que no se
    versiona (ver `.env.example`).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///app.db"
    secreto_firma: str = "solo-desarrollo-cambiar"
    clave_api_reaseguro: str = "solo-desarrollo-cambiar"
    ruta_modelo: str = "modelo.pkl"
    umbral_alto_riesgo: float = 0.6


@lru_cache
def get_settings() -> Settings:
    """Una sola instancia por proceso: `.env` se lee una vez, no en cada petición."""
    return Settings()
