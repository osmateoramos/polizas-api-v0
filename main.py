"""
polizas-api-v0 — Gestión de pólizas y siniestros.
Aseguradora Santo Tomás · prototipo interno.

Este módulo es la capa HTTP: rutas, códigos de estado y esquemas de respuesta.
La lectura y escritura en la base vive en crud.py; la puntuación, en riesgo.py.
El esquema de la base lo crean las migraciones (`alembic upgrade head`), no el arranque.
"""
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import crud
import riesgo
from config import Settings, get_settings
from database import get_db
from esquemas import (Error, PolizaActualizacion, PolizaEntrada, PolizaSalida, PrediccionSalida,
                      PuntuacionEntrada, PuntuacionSalida, ResumenPoliza, Salud, SiniestroDetalle,
                      SiniestroEntrada)
from modelos import Poliza

app = FastAPI(title="Pólizas API", version="0.2.0")

NO_EXISTE = {404: {"model": Error, "description": "La póliza no existe"}}


def poliza_o_404(id_poliza: int, db: Session = Depends(get_db)) -> Poliza:
    """Dependencia de las rutas /polizas/{id_poliza}: entrega la póliza o corta con 404.
    Comparte la sesión con la ruta: FastAPI resuelve `get_db` una vez por petición."""
    poliza = crud.obtener_poliza(db, id_poliza)
    if poliza is None:
        raise HTTPException(status_code=404, detail=f"no existe la póliza {id_poliza}")
    return poliza


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


@app.post("/polizas", status_code=201, response_model=PolizaSalida,
          responses={409: {"model": Error, "description": "El número de póliza ya existe"}})
def crear_poliza(datos: PolizaEntrada, db: Session = Depends(get_db),
                 settings: Settings = Depends(get_settings)):
    try:
        return crud.crear_poliza(db, datos, settings.secreto_firma)
    except crud.NumeroDuplicado:
        raise HTTPException(status_code=409,
                            detail=f"ya existe una póliza con el número {datos.numero}") from None


@app.get("/polizas", response_model=list[PolizaSalida])
def listar_polizas(db: Session = Depends(get_db)):
    return crud.listar_polizas(db)


@app.get("/polizas/{id_poliza}", response_model=PolizaSalida, responses=NO_EXISTE)
def obtener_poliza(poliza: Poliza = Depends(poliza_o_404)):
    return poliza


@app.put("/polizas/{id_poliza}", response_model=PolizaSalida, responses=NO_EXISTE)
def actualizar_poliza(datos: PolizaActualizacion, poliza: Poliza = Depends(poliza_o_404),
                      db: Session = Depends(get_db)):
    # exclude_unset: solo lo que el cliente envió. Sin esto, cada campo omitido
    # llegaría como None y borraría el valor guardado.
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("fecha_fin", poliza.fecha_fin) <= poliza.fecha_inicio:
        raise HTTPException(status_code=422, detail="fecha_fin debe ser posterior a fecha_inicio")
    return crud.actualizar_poliza(db, poliza, cambios)


@app.post("/polizas/{id_poliza}/siniestros", status_code=201, response_model=SiniestroDetalle,
          responses=NO_EXISTE)
def declarar_siniestro(datos: SiniestroEntrada, poliza: Poliza = Depends(poliza_o_404),
                       db: Session = Depends(get_db)):
    return crud.declarar_siniestro(db, poliza, datos)


@app.get("/siniestros", response_model=list[SiniestroDetalle])
def listar_siniestros(db: Session = Depends(get_db)):
    return crud.listar_siniestros(db)


@app.get("/resumen", response_model=list[ResumenPoliza])
def resumen(db: Session = Depends(get_db)):
    return crud.resumen(db)


@app.post("/score", response_model=PuntuacionSalida, responses=NO_EXISTE)
def puntuar(datos: PuntuacionEntrada, db: Session = Depends(get_db),
            settings: Settings = Depends(get_settings), modelo=Depends(riesgo.get_modelo)):
    poliza = crud.obtener_poliza_por_numero(db, datos.numero)
    if poliza is None:
        raise HTTPException(status_code=404, detail=f"no existe la póliza {datos.numero}")
    puntaje = riesgo.puntuar(modelo, poliza)
    prediccion = crud.registrar_prediccion(db, poliza, puntaje,
                                           alto_riesgo=puntaje > settings.umbral_alto_riesgo)
    return {"numero": poliza.numero, "puntaje": round(puntaje, 4),
            "alto_riesgo": prediccion.alto_riesgo}


@app.get("/predicciones", response_model=list[PrediccionSalida])
def listar_predicciones(db: Session = Depends(get_db)):
    return crud.listar_predicciones(db)
