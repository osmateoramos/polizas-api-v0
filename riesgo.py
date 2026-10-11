"""Puntuación de riesgo: carga del modelo y rasgos de una póliza.

No sabe nada de HTTP ni de sesiones: recibe una póliza ya cargada y devuelve
un número. Por eso se puede probar sin levantar el servicio.
"""
import pickle
from datetime import date
from functools import lru_cache

from config import get_settings
from modelos import Poliza


@lru_cache
def get_modelo():
    """El modelo se deserializa una sola vez, la primera vez que alguien puntúa."""
    with open(get_settings().ruta_modelo, "rb") as fh:
        return pickle.load(fh)


def rasgos(poliza: Poliza, hoy: date | None = None) -> list[float]:
    """Las cuatro variables con las que se entrenó el modelo, en su orden:
    prima, número de siniestros, monto total reclamado y antigüedad en días."""
    hoy = hoy or date.today()
    return [poliza.prima, len(poliza.siniestros), sum(s.monto for s in poliza.siniestros),
            (hoy - poliza.fecha_inicio).days]


def puntuar(modelo, poliza: Poliza) -> float:
    """Probabilidad de la clase «alto riesgo», en [0, 1]."""
    return float(modelo.predict_proba([rasgos(poliza)])[0][1])
