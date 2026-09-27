"""Esquemas de entrada."""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

TipoPoliza = Literal["auto", "hogar", "vida"]
EstadoSiniestro = Literal["abierto", "pagado", "rechazado"]


def _normalizar_nombre(nombre: str) -> str:
    """Quita espacios sobrantes y pone cada palabra con mayúscula inicial."""
    return " ".join(nombre.split()).title()


# --- Entrada ------------------------------------------------------------------

class SiniestroEntrada(BaseModel):
    fecha: date
    monto: float = Field(gt=0, description="Monto reclamado, en pesos")
    descripcion: str = Field(min_length=3, max_length=200)
    estado: EstadoSiniestro = "abierto"


class PolizaEntrada(BaseModel):
    numero: str = Field(min_length=8, max_length=20, description="Formato POL-AAAA-NNNNN")
    asegurado: str = Field(min_length=3, max_length=80)
    tipo: TipoPoliza = Field(description="auto, hogar o vida")
    prima: float = Field(gt=0, description="Prima anual, en pesos")
    fecha_inicio: date
    fecha_fin: date
    # Tipado con el submodelo: cada siniestro anidado pasa por las mismas
    # restricciones que uno declarado con POST /polizas/{id}/siniestros.
    siniestros: list[SiniestroEntrada] = Field(default_factory=list,
                                               description="Siniestros ya declarados")

    @field_validator("asegurado")
    @classmethod
    def normalizar_asegurado(cls, v: str) -> str:
        return _normalizar_nombre(v)

    @model_validator(mode="after")
    def fechas_coherentes(self) -> "PolizaEntrada":
        """Regla entre dos campos: por eso va en el modelo y no en un validador de campo."""
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio")
        return self


class PolizaActualizacion(BaseModel):
    """Cuerpo del PUT parcial: solo cambia lo que viene. Un campo omitido se
    conserva; un `null` explícito se rechaza, porque borraría un dato obligatorio."""

    asegurado: Optional[str] = Field(default=None, min_length=3, max_length=80)
    tipo: Optional[TipoPoliza] = None
    prima: Optional[float] = Field(default=None, gt=0)
    fecha_fin: Optional[date] = None

    @field_validator("asegurado", "tipo", "prima", "fecha_fin")
    @classmethod
    def no_nulo(cls, v):
        if v is None:
            raise ValueError("no puede ser null; para dejar el campo como está, omítalo")
        return v

    @field_validator("asegurado")
    @classmethod
    def normalizar_asegurado(cls, v: str) -> str:
        return _normalizar_nombre(v)


class PuntuacionEntrada(BaseModel):
    numero: str = Field(min_length=8, max_length=20)


class Salud(BaseModel):
    estado: str = Field(description="ok o degradado")
    base_de_datos: str = Field(description="ok o sin respuesta")

