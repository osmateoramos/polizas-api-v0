"""Pruebas propias del servicio, aisladas de la base de la aplicación.

    pytest tests/test_api.py

Cada corrida trabaja sobre una base SQLite nueva, en una carpeta temporal de
pytest fuera del repositorio: se le aplican las migraciones y se sustituye
`database.get_db` —la dependencia que las rutas piden con `Depends(get_db)`—
por una sesión sobre esa base. `app.db` no se abre nunca, así que la segunda
corrida encuentra lo mismo que la primera.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))

import database  # noqa: E402
from main import app  # noqa: E402

SINIESTRO = {"fecha": "2026-03-02", "monto": 850_000, "descripcion": "Choque leve", "estado": "abierto"}


def _poliza(numero: str, **extra) -> dict:
    """Cada test usa su propio número fijo: nada al azar ni compartido entre tests."""
    base = {
        "numero": numero,
        "asegurado": "Prueba Interna",
        "tipo": "auto",
        "prima": 1_000_000,
        "fecha_inicio": "2026-01-01",
        "fecha_fin": "2026-12-31",
    }
    base.update(extra)
    return base


@pytest.fixture(scope="module")
def cliente(tmp_path_factory):
    """Base temporal con el esquema de las migraciones y `get_db` sustituido.

    La llave del override es `database.get_db`, el mismo objeto que reciben las
    rutas: con una función propia de otro nombre el override no se activaría y
    los tests seguirían escribiendo en `app.db`.
    """
    url = f"sqlite:///{(tmp_path_factory.mktemp('bd') / 'pruebas.db').as_posix()}"
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=RAIZ,
                   env={**os.environ, "DATABASE_URL": url}, check=True)
    engine = database.crear_engine(url)  # con PRAGMA foreign_keys=ON, igual que la app
    Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _get_db():
        db = Sesion()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[database.get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.pop(database.get_db, None)
    engine.dispose()


def test_crear_poliza(cliente):
    datos = _poliza("POL-TEST-00001")
    r = cliente.post("/polizas", json=datos)
    assert r.status_code == 201
    assert r.json()["numero"] == datos["numero"]


def test_listar_polizas(cliente):
    datos = _poliza("POL-TEST-00002")
    assert cliente.post("/polizas", json=datos).status_code == 201
    r = cliente.get("/polizas")
    assert r.status_code == 200
    assert any(p["numero"] == datos["numero"] for p in r.json())


def test_siniestro_declarado_queda_en_su_poliza(cliente):
    poliza = cliente.post("/polizas", json=_poliza("POL-TEST-00003")).json()
    r = cliente.post(f"/polizas/{poliza['id']}/siniestros", json=SINIESTRO)
    assert r.status_code == 201
    siniestro = r.json()
    assert siniestro["numero_poliza"] == "POL-TEST-00003"
    # Se lee de vuelta en peticiones nuevas: si no se hubiera guardado, no estaría.
    guardada = cliente.get(f"/polizas/{poliza['id']}").json()
    assert [s["id"] for s in guardada["siniestros"]] == [siniestro["id"]]
    assert any(s["id"] == siniestro["id"] and s["numero_poliza"] == "POL-TEST-00003"
               for s in cliente.get("/siniestros").json())


def test_resumen_cuenta_y_suma_los_siniestros(cliente):
    montos = [850_000, 1_150_000.5]
    datos = _poliza("POL-TEST-00004", siniestros=[{**SINIESTRO, "monto": m} for m in montos])
    assert cliente.post("/polizas", json=datos).status_code == 201
    fila = next(f for f in cliente.get("/resumen").json() if f["numero"] == datos["numero"])
    assert fila["n_siniestros"] == 2
    assert fila["monto_total"] == pytest.approx(sum(montos))
