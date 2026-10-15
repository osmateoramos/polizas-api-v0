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

y desde el host:

```bash
curl localhost:8000/health        # {"estado":"ok","base_de_datos":"ok"}
```

Al arrancar, el contenedor aplica `alembic upgrade head` y después levanta
uvicorn en `0.0.0.0:8000`. No hace falta pasarle `.env`: `config.py` trae
valores de desarrollo, y la imagen no lleva ni `.env` ni ninguna base (ver
`.dockerignore`). Los secretos reales se pasan al correrlo, con
`docker run --env-file .env ...` o `-e SECRETO_FIRMA=...`; la ruta de la base ya
viene fijada en la imagen (`DATABASE_URL=sqlite:////app/datos/app.db`).

El servicio corre como el usuario `app`, sin privilegios, y `HEALTHCHECK`
consulta `/health`: `docker ps` muestra el contenedor como `healthy` cuando la
base responde y tiene el esquema aplicado.

**Dónde quedan los datos.** La base está en `/app/datos`, dentro del
contenedor:

- `docker restart` reinicia el **mismo** contenedor: los datos siguen ahí.
- Borrar el contenedor (`docker rm`) y levantar otro desde la misma imagen
  empieza con una base vacía: el contenedor nuevo no hereda la capa de escritura
  del anterior, y las migraciones crean el esquema de cero.
- Para que sobrevivan al contenedor, se monta un volumen con nombre:

  ```bash
  docker run -p 8000:8000 -v polizas-datos:/app/datos polizas-api
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
| GET | `/health` | 200 si la base responde y tiene el esquema; 503 si no |

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
pytest
```

Corre toda la batería de `tests/`. Ningún test toca `app.db`: cada archivo crea
su propia base SQLite, le aplica las migraciones y sustituye `database.get_db`
con `app.dependency_overrides` por una sesión sobre esa base. Por eso `pytest`
puede correrse dos veces seguidas con el mismo resultado.

- `tests/test_contrato.py`: el contrato del taller. **No se modifica.**
- `tests/test_api.py`: pruebas propias, sobre una base en una carpeta temporal
  de pytest.
- `tests/test_ia_corregido.py`: la batería de `ia_tests_propuesta.py` corregida
  (Parte D, ver `DICTAMEN_IA.md`).

`ia_tests_propuesta.py`, en la raíz, es la batería original de la IA y se deja
tal cual como objeto de la auditoría. `pytest` no la recoge porque su nombre no
empieza por `test_`. Si se corre a mano, escribe en `app.db`: ese es justo su
defecto 1.

## Utilidades

- `sembrar_datos.py` crea pólizas de ejemplo a través de la API.
- `contar_consultas.py` cuenta las sentencias SQL que emite cada endpoint.

## Notas

- Los secretos se configuran en `.env` (o como variables de entorno), nunca en el código.
- Cambios en `modelos.py` → nueva migración: `alembic revision --autogenerate -m "..."`,
  revisarla y aplicarla con `alembic upgrade head`.
