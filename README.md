# polizas-api-v0

Servicio de gestión de pólizas de la Aseguradora Santo Tomás. Registra pólizas
y los siniestros que se les declaran, resume la cartera y puntúa el riesgo de
cada póliza con un modelo, guardando cada predicción.

## Instalación

Requiere Python 3.11 o superior. Las versiones de todas las dependencias están
fijadas en `requirements.txt` (las directas se declaran en `requirements.in`).

```bash
python -m venv .venv
source .venv/bin/activate        # Windows (Git Bash): source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env             # y ajustar los secretos en .env
```

La configuración se lee de variables de entorno o de `.env` (ver `config.py`).
`.env` no se versiona; `.env.example` lleva valores con los que el servicio arranca.

## Puesta en marcha

La base de datos **no viene en el repositorio**: su esquema lo crean las
migraciones de Alembic, sobre la base que indique `DATABASE_URL`.

```bash
alembic upgrade head
uvicorn main:app --host 127.0.0.1 --port 8000
```

`GET /health` responde 200 cuando la base responde y tiene el esquema aplicado.
Para desarrollar puede añadirse `--reload`, que reinicia el servidor con cada
cambio; en producción no se usa.

Para cargar pólizas de ejemplo, con el servicio en marcha:

```bash
python sembrar_datos.py --polizas 12
```

Si traen un `app.db` de antes de las migraciones (creado por la versión
anterior con `create_all`), bórrenlo y ejecuten `alembic upgrade head`.

### En contenedor

```bash
docker build -t polizas-api .
docker run -p 8000:8000 polizas-api
```

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/polizas` | Crea una póliza, con sus siniestros si ya tiene |
| GET | `/polizas` | Lista las pólizas con sus siniestros |
| GET | `/polizas/{id}` | Consulta una póliza |
| PUT | `/polizas/{id}` | Actualiza una póliza |
| POST | `/polizas/{id}/siniestros` | Declara un siniestro |
| GET | `/siniestros` | Lista los siniestros con su póliza |
| GET | `/resumen` | Siniestros y monto total por póliza |
| POST | `/score` | Puntúa el riesgo de una póliza y guarda la predicción |
| GET | `/predicciones` | Histórico de predicciones |

### Ejemplo

```bash
curl -X POST localhost:8000/polizas \
  -H "Content-Type: application/json" \
  -d '{"numero": "POL-2026-09001", "asegurado": "Ana Rueda", "tipo": "auto", "prima": 1250000,
       "fecha_inicio": "2026-01-15", "fecha_fin": "2027-01-14"}'
```

```bash
curl -X POST localhost:8000/score -H "Content-Type: application/json" -d '{"numero": "POL-2026-09001"}'
```

## Pruebas

```bash
pytest tests/test_api.py
```

## Utilidades

- `sembrar_datos.py` crea pólizas de ejemplo a través de la API.
- `contar_consultas.py` cuenta las sentencias SQL que emite cada endpoint.

## Notas

- Los secretos se configuran en `.env` (o como variables de entorno), nunca en el código.
- Cambios en `modelos.py` → nueva migración: `alembic revision --autogenerate -m "..."`,
  revisarla y aplicarla con `alembic upgrade head`.
