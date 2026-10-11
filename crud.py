"""Operaciones de base de datos: consultas y escrituras, sin nada de HTTP.

Las rutas de main.py deciden los códigos de estado; aquí solo se lee y se
escribe. Cada función recibe la sesión de la petición (la de `get_db`).
"""
import hashlib

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from esquemas import PolizaEntrada, SiniestroEntrada
from modelos import Poliza, Prediccion, Siniestro


class NumeroDuplicado(Exception):
    """Ya existe una póliza con ese número (restricción UNIQUE de `polizas.numero`)."""


def firmar(numero: str, secreto: str) -> str:
    return hashlib.sha256(f"{numero}:{secreto}".encode()).hexdigest()


# --- Pólizas ------------------------------------------------------------------

def crear_poliza(db: Session, datos: PolizaEntrada, secreto_firma: str) -> Poliza:
    poliza = Poliza(**datos.model_dump(exclude={"siniestros"}),
                    token_firma=firmar(datos.numero, secreto_firma),
                    siniestros=[Siniestro(**s.model_dump()) for s in datos.siniestros])
    db.add(poliza)
    try:
        db.commit()
    except IntegrityError as error:
        # Sin rollback la sesión queda inservible; es de esta petición, pero se
        # deja limpia de todos modos antes de avisar del conflicto.
        db.rollback()
        raise NumeroDuplicado(datos.numero) from error
    db.refresh(poliza)
    return poliza


def listar_polizas(db: Session) -> list[Poliza]:
    # estrategia: selectinload. Trae todas las pólizas y, en una segunda consulta,
    # todos sus siniestros con un solo `WHERE poliza_id IN (...)`: 2 consultas sin
    # importar cuántas pólizas haya. joinedload también baja a 1 consulta, pero
    # con un JOIN que repite las columnas de la póliza por cada siniestro; con
    # 2000 pólizas x 3 siniestros ese fan-out pesa más que la segunda consulta.
    return list(db.scalars(
        select(Poliza).options(selectinload(Poliza.siniestros)).order_by(Poliza.id)))


def obtener_poliza(db: Session, id_poliza: int) -> Poliza | None:
    # estrategia: lazy. Aquí N=1 (una sola póliza): la carga diferida de sus
    # siniestros ya cuesta 1 sola consulta extra, así que selectinload mediría
    # exactamente las mismas 2 consultas. No hay N+1 que resolver.
    return db.get(Poliza, id_poliza)


def obtener_poliza_por_numero(db: Session, numero: str) -> Poliza | None:
    return db.scalar(select(Poliza).where(Poliza.numero == numero))


def actualizar_poliza(db: Session, poliza: Poliza, cambios: dict) -> Poliza:
    """Aplica solo los campos de `cambios` (el PUT parcial ya filtró lo no enviado)."""
    for campo, valor in cambios.items():
        setattr(poliza, campo, valor)
    db.commit()
    db.refresh(poliza)
    return poliza


def resumen(db: Session) -> list[dict]:
    """Por póliza: número de siniestros y monto total."""
    return [{"numero": p.numero, "n_siniestros": len(p.siniestros),
             "monto_total": round(sum(s.monto for s in p.siniestros), 2)}
            for p in db.scalars(select(Poliza).order_by(Poliza.id))]


# --- Siniestros ---------------------------------------------------------------

def declarar_siniestro(db: Session, poliza: Poliza, datos: SiniestroEntrada) -> Siniestro:
    siniestro = Siniestro(**datos.model_dump(), poliza=poliza)
    db.add(siniestro)
    db.commit()
    db.refresh(siniestro)
    return siniestro


def listar_siniestros(db: Session) -> list[Siniestro]:
    # estrategia: joinedload. Cada siniestro tiene exactamente una póliza (relación
    # a-uno): el JOIN no duplica filas de siniestro, así que baja a 1 sola consulta
    # sin el costo de fan-out que sí tiene joinedload sobre una relación a-muchos.
    return list(db.scalars(
        select(Siniestro).options(joinedload(Siniestro.poliza)).order_by(Siniestro.id)))


# --- Predicciones -------------------------------------------------------------

def registrar_prediccion(db: Session, poliza: Poliza, puntaje: float, alto_riesgo: bool) -> Prediccion:
    prediccion = Prediccion(poliza=poliza, puntaje=puntaje, alto_riesgo=alto_riesgo)
    db.add(prediccion)
    db.commit()
    return prediccion


def listar_predicciones(db: Session) -> list[Prediccion]:
    return list(db.scalars(select(Prediccion).order_by(Prediccion.id)))
