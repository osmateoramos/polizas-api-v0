"""Tablas del servicio."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Poliza(Base):
    __tablename__ = "polizas"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True)
    asegurado: Mapped[Optional[str]] = mapped_column(String(80))
    tipo: Mapped[Optional[str]] = mapped_column(String(10))
    prima: Mapped[float] = mapped_column(Float)
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[Optional[date]] = mapped_column(Date)
    token_firma: Mapped[str] = mapped_column(String(64))

    # Los siniestros y las predicciones no existen sin su póliza: si la póliza se
    # borra, se borran con ella (en el ORM y, con passive_deletes, en la propia base).
    siniestros: Mapped[list["Siniestro"]] = relationship(
        back_populates="poliza", cascade="all, delete-orphan", passive_deletes=True)
    predicciones: Mapped[list["Prediccion"]] = relationship(
        back_populates="poliza", cascade="all, delete-orphan", passive_deletes=True)


class Siniestro(Base):
    __tablename__ = "siniestros"

    id: Mapped[int] = mapped_column(primary_key=True)
    poliza_id: Mapped[int] = mapped_column(ForeignKey("polizas.id", ondelete="CASCADE"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    monto: Mapped[float] = mapped_column(Float)
    descripcion: Mapped[str] = mapped_column(String(200))
    estado: Mapped[str] = mapped_column(String(10), default="abierto")

    poliza: Mapped["Poliza"] = relationship(back_populates="siniestros")


class Prediccion(Base):
    __tablename__ = "predicciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    poliza_id: Mapped[int] = mapped_column(ForeignKey("polizas.id", ondelete="CASCADE"), index=True)
    puntaje: Mapped[float] = mapped_column(Float)
    alto_riesgo: Mapped[bool]
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    poliza: Mapped["Poliza"] = relationship(back_populates="predicciones")
