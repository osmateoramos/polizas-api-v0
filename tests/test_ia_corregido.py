"""
Corrección de `ia_tests_propuesta.py` (Parte D). El dictamen completo, con los
tres defectos y sus mutaciones, está en DICTAMEN_IA.md. En resumen:

  1. El `dependency_overrides` del archivo de la IA usa como llave su propia
     función local `get_db`, no `database.get_db` (la que de verdad usan las
     rutas): el override nunca se activa y los tests escriben en la base real.
     Aquí se aísla igual que `tests/test_contrato.py`: DATABASE_URL antes de
     importar la aplicación, migraciones sobre esa base, y el override sobre
     la dependencia real.
  2. Varios asserts aceptaban tanto el resultado correcto como el roto
     (`in (200, 201, 422)`, `in (200, 404)`, `< 500`). Aquí cada assert exige
     el único código correcto para ese caso.
  3. El número de póliza era aleatorio sin control de colisión; combinado con
     el defecto 1, una corrida podía fallar con 409 sin que ningún test lo
     esperara. Aquí el caso de número duplicado se prueba directo, sin dejarlo
     al azar (`test_numero_duplicado_da_409_y_el_servicio_sigue_vivo`).

    pytest tests/test_ia_corregido.py -v
"""
import os
import random
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

DB = RAIZ / ".test_ia_corregido.db"
DB.unlink(missing_ok=True)
URL = f"sqlite:///{DB}"
os.environ["DATABASE_URL"] = URL
if (RAIZ / "alembic.ini").exists():
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)

import database  # noqa: E402
from main import app  # noqa: E402

if hasattr(database, "get_db"):
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker

    _engine = create_engine(URL, connect_args={"check_same_thread": False})

    @event.listens_for(_engine, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    if not (RAIZ / "alembic.ini").exists():
        database.Base.metadata.create_all(_engine)
    _Sesion = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)

    def _get_db():
        db = _Sesion()
        try:
            yield db
        finally:
            db.close()

    @pytest.fixture(autouse=True)
    def _aislar():
        """La llave del override es `database.get_db`: la misma que reciben las
        rutas por `Depends(get_db)`. Así sí se activa (a diferencia del archivo
        de la IA, que la sustituía por una función local sin uso real)."""
        previo = app.dependency_overrides.get(database.get_db)
        app.dependency_overrides[database.get_db] = _get_db
        yield
        if previo is None:
            app.dependency_overrides.pop(database.get_db, None)
        else:
            app.dependency_overrides[database.get_db] = previo

cliente = TestClient(app, raise_server_exceptions=False)

random.seed(2026)


def _numero() -> str:
    return f"POL-IAC-{uuid.uuid4().hex[:6].upper()}"


def _poliza(**extra) -> dict:
    base = {
        "numero": _numero(),
        "asegurado": "Prueba Automática",
        "tipo": random.choice(["auto", "hogar", "vida"]),
        "prima": round(random.uniform(1, 5_000_000), 2),
        "fecha_inicio": "2026-01-01",
        "fecha_fin": "2026-12-31",
    }
    base.update(extra)
    return base


def test_crear_poliza_devuelve_201():
    r = cliente.post("/polizas", json=_poliza())
    assert r.status_code == 201, f"devolvió {r.status_code}"
    assert "id" in r.json() and "numero" in r.json()


def test_primas_variadas_son_realmente_aceptadas():
    """A diferencia del original: exige 201 en cada vuelta, no admite 422
    como resultado válido. Una primera variante aceptable debe crearse siempre."""
    for _ in range(5):
        r = cliente.post("/polizas", json=_poliza())
        assert r.status_code == 201, f"una prima válida devolvió {r.status_code}"


def test_prima_no_positiva_da_422():
    r = cliente.post("/polizas", json=_poliza(prima=0))
    assert r.status_code == 422, f"devolvió {r.status_code}"


def test_poliza_inexistente_da_404():
    assert cliente.get("/polizas/999999").status_code == 404


def test_listar_polizas_responde_200():
    r = cliente.get("/polizas")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_resumen_devuelve_lista():
    r = cliente.get("/resumen")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_score_de_poliza_recien_creada():
    datos = _poliza()
    cliente.post("/polizas", json=datos)
    r = cliente.post("/score", json={"numero": datos["numero"]})
    assert r.status_code == 200
    cuerpo = r.json()
    assert "puntaje" in cuerpo and 0.0 <= cuerpo["puntaje"] <= 1.0


# Va el último a propósito, igual que en test_contrato.py: si el conflicto
# dejara la sesión inservible, arrastraría a los tests siguientes.
def test_numero_duplicado_da_409_y_el_servicio_sigue_vivo():
    datos = _poliza()
    assert cliente.post("/polizas", json=datos).status_code == 201
    r = cliente.post("/polizas", json=datos)
    assert r.status_code == 409, f"devolvió {r.status_code}"
    assert cliente.get("/polizas").status_code == 200, "tras el conflicto el servicio dejó de responder"
