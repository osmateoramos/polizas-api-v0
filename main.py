"""
polizas-api-v0 — Gestión de pólizas y siniestros.
Aseguradora Santo Tomás · prototipo interno.
"""
import hashlib
import pickle
from datetime import date
from functools import lru_cache

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config import Settings, get_settings
from database import get_db
from esquemas import PolizaActualizacion, PolizaEntrada, PuntuacionEntrada, Salud, SiniestroEntrada
from modelos import Poliza, Prediccion, Siniestro

# El esquema de la base lo crean las migraciones (`alembic upgrade head`), no el arranque.

app = FastAPI(title="Pólizas API", version="0.1.0")


@lru_cache
def get_modelo():
    """El modelo se deserializa una sola vez, la primera vez que alguien puntúa."""
    with open(get_settings().ruta_modelo, "rb") as fh:
        return pickle.load(fh)


def firmar(numero: str, secreto: str) -> str:
    return hashlib.sha256(f"{numero}:{secreto}".encode()).hexdigest()


def _siniestro(s: Siniestro) -> dict:
    return {"id": s.id, "poliza_id": s.poliza_id, "numero_poliza": s.poliza.numero,
            "fecha": s.fecha, "monto": s.monto, "descripcion": s.descripcion, "estado": s.estado}


def _poliza(p: Poliza) -> dict:
    return {
        "id": p.id, "numero": p.numero, "asegurado": p.asegurado, "tipo": p.tipo,
        "prima": p.prima, "fecha_inicio": p.fecha_inicio, "fecha_fin": p.fecha_fin,
        "token_firma": p.token_firma,
        "siniestros": [{"id": s.id, "fecha": s.fecha, "monto": s.monto,
                        "descripcion": s.descripcion, "estado": s.estado} for s in p.siniestros],
    }


@app.get("/health", response_model=Salud, responses={503: {"model": Salud}})
def health(db: Session = Depends(get_db)):
    """200 si la base responde y tiene el esquema aplicado; 503 si no.

    Se consulta una tabla del servicio y no un simple `SELECT 1`: una base a la que
    le faltan las migraciones «responde», pero el servicio no puede trabajar con ella.
    """
    try:
        db.execute(select(Poliza.id).limit(1))
    except SQLAlchemyError:
        return JSONResponse(status_code=503,
                            content={"estado": "degradado", "base_de_datos": "sin respuesta"})
    return {"estado": "ok", "base_de_datos": "ok"}


@app.post("/polizas")
def crear_poliza(datos: PolizaEntrada, db: Session = Depends(get_db),
                 settings: Settings = Depends(get_settings)):
    poliza = Poliza(numero=datos.numero, asegurado=datos.asegurado, tipo=datos.tipo,
                    prima=datos.prima, fecha_inicio=datos.fecha_inicio, fecha_fin=datos.fecha_fin,
                    token_firma=firmar(datos.numero, settings.secreto_firma))
    for s in datos.siniestros:
        poliza.siniestros.append(Siniestro(
            fecha=date.fromisoformat(str(s.get("fecha", date.today()))),
            monto=s.get("monto", 0), descripcion=s.get("descripcion", ""),
            estado=s.get("estado", "abierto")))
    db.add(poliza)
    db.commit()
    db.refresh(poliza)
    return poliza


@app.get("/polizas")
def listar_polizas(db: Session = Depends(get_db)):
    return [_poliza(p) for p in db.scalars(select(Poliza).order_by(Poliza.id))]


@app.get("/polizas/{id_poliza}")
def obtener_poliza(id_poliza: int, db: Session = Depends(get_db)):
    poliza = db.get(Poliza, id_poliza)
    if poliza is None:
        return {"error": f"no existe la póliza {id_poliza}"}
    return _poliza(poliza)


@app.put("/polizas/{id_poliza}")
def actualizar_poliza(id_poliza: int, datos: PolizaActualizacion, db: Session = Depends(get_db)):
    poliza = db.get(Poliza, id_poliza)
    if poliza is None:
        return {"error": f"no existe la póliza {id_poliza}"}
    for campo, valor in datos.model_dump().items():
        setattr(poliza, campo, valor)
    db.commit()
    db.refresh(poliza)
    return _poliza(poliza)


@app.post("/polizas/{id_poliza}/siniestros")
def declarar_siniestro(id_poliza: int, datos: SiniestroEntrada, db: Session = Depends(get_db)):
    siniestro = Siniestro(poliza_id=id_poliza, fecha=datos.fecha, monto=datos.monto,
                          descripcion=datos.descripcion, estado=datos.estado)
    db.add(siniestro)
    db.commit()
    db.refresh(siniestro)
    return {"id": siniestro.id, "poliza_id": siniestro.poliza_id, "fecha": siniestro.fecha,
            "monto": siniestro.monto, "descripcion": siniestro.descripcion, "estado": siniestro.estado}


@app.get("/siniestros")
def listar_siniestros(db: Session = Depends(get_db)):
    return [_siniestro(s) for s in db.scalars(select(Siniestro).order_by(Siniestro.id))]


@app.get("/resumen")
def resumen(db: Session = Depends(get_db)):
    filas = []
    for p in db.scalars(select(Poliza).order_by(Poliza.id)):
        filas.append({"numero": p.numero, "n_siniestros": len(p.siniestros),
                      "monto_total": round(sum(s.monto for s in p.siniestros), 2)})
    return filas


@app.post("/score")
def puntuar(datos: PuntuacionEntrada, db: Session = Depends(get_db),
            settings: Settings = Depends(get_settings), modelo=Depends(get_modelo)):
    poliza = db.scalar(select(Poliza).where(Poliza.numero == datos.numero))
    if poliza is None:
        return {"error": f"no existe la póliza {datos.numero}"}
    rasgos = [[poliza.prima, len(poliza.siniestros), sum(s.monto for s in poliza.siniestros),
               (date.today() - poliza.fecha_inicio).days]]
    puntaje = float(modelo.predict_proba(rasgos)[0][1])
    prediccion = Prediccion(poliza_id=poliza.id, puntaje=puntaje,
                            alto_riesgo=puntaje > settings.umbral_alto_riesgo)
    db.add(prediccion)
    db.commit()
    return {"numero": poliza.numero, "puntaje": round(puntaje, 4),
            "alto_riesgo": prediccion.alto_riesgo}


@app.get("/predicciones")
def listar_predicciones(db: Session = Depends(get_db)):
    return [{"id": pr.id, "poliza_id": pr.poliza_id, "puntaje": pr.puntaje,
             "alto_riesgo": pr.alto_riesgo, "creado_en": pr.creado_en}
            for pr in db.scalars(select(Prediccion).order_by(Prediccion.id))]
