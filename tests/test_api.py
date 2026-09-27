"""Pruebas del servicio.

    pytest tests/test_api.py
"""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app  # noqa: E402

cliente = TestClient(app)

POLIZA = {
    "numero": "POL-TEST-00001",
    "asegurado": "Prueba Interna",
    "tipo": "auto",
    "prima": 1_000_000,
    "fecha_inicio": "2026-01-01",
    "fecha_fin": "2026-12-31",
}


def test_crear_poliza():
    r = cliente.post("/polizas", json=POLIZA)
    assert r.status_code == 201
    assert r.json()["numero"] == POLIZA["numero"]


def test_listar_polizas():
    r = cliente.get("/polizas")
    assert r.status_code == 200
    assert any(p["numero"] == POLIZA["numero"] for p in r.json())
