# Hallazgos — Parte A

**Grupo:** <número> · **Integrantes:** Oscar Mateo Ramos, Vanessa Acosta

> No borren la fila de ejemplo hasta haber comprobado que su tabla se parsea
> (`python verificar_entrega.py`). El formato es rígido: ocho columnas, en este
> orden. Una tabla torcida se rechaza indicando la línea, no se «entiende igual».
>
> **Tuberías dentro de una celda:** si su comando lleva `|` —y varios lo llevarán,
> por `grep`, `head` o `jq`— escríbanlo `\|`. Sin escapar, Markdown lo lee como
> separador de columna y su fila pasa a tener nueve.

| ID | Síntoma observable | Causa | Módulo · Sección | SHA donde se observa | Comando de evidencia | Salida obtenida | Corrección aplicada |
|----|--------------------|-------|------------------|----------------------|----------------------|-----------------|---------------------|
| H1 | `requirements.txt` no fija ninguna versión: cada instalación trae lo último que haya en PyPI y el entorno no se puede reproducir | Los paquetes se listan sin `==`; además `modelo.pkl` se serializó con una versión concreta de scikit-learn (1.9.1) que nada garantiza | M10 · 7. Reproducibilidad sin Docker | `v0-semilla` | `grep -c "==" requirements.txt` | `0` | Todas las dependencias fijadas con `==`, incluida `scikit-learn==1.9.1`, la versión con la que se serializó el modelo |
| H2 | La base de datos `app.db`, con datos, está versionada: cada commit arrastra el estado de la base y un `git checkout` pisa los datos locales | `.gitignore` solo cubre `*.pyc`: no excluye `*.db`, `.env` ni el entorno virtual | M9 · 9. Guía de evaluación: taller en parejas | `v0-semilla` | `git ls-files "*.db"` | `app.db` | `.gitignore` con `*.db`, `.env` y `.venv/`; `app.db` sale del índice con `git rm --cached` |
| H3 | La aplicación ignora `DATABASE_URL`: aunque se le indique otra base, siempre abre `app.db`. Los secretos (`SECRETO_FIRMA`, `CLAVE_API_REASEGURO`) están escritos en el código y versionados | `config.py` define constantes literales: nada se lee del entorno ni de un `.env` | M8 · 3. De lo duro a lo flexible: variables de entorno | `v0-semilla` | `DATABASE_URL=sqlite:///otra.db python -c "import database; print(database.engine.url)"` | `sqlite:///app.db` | `Settings(BaseSettings)` leído de `.env`, entregado por una función con `lru_cache` e inyectado con `Depends`; los secretos viven solo en `.env` (no versionado) y `.env.example` lleva valores de ejemplo |
| H4 | No hay migraciones: el esquema se crea como efecto secundario de importar `main.py`, así que un cambio en los modelos nunca llega a una base que ya existe | `Base.metadata.create_all(engine)` al nivel de módulo en `main.py`; no existe `alembic/` | M9 · 6. Modelado de BD y migraciones con Alembic | `v0-semilla` | `grep -n "create_all" main.py` | `17:Base.metadata.create_all(engine)` | `alembic/` con una revisión inicial; `alembic/env.py` toma la URL de `DATABASE_URL`; `create_all` sale del arranque |
| H5 | SQLite acepta filas huérfanas: se registra un siniestro con `poliza_id=999999` sin que exista la póliza, y desde ese momento `GET /siniestros` responde 500 | SQLite trae las claves foráneas desactivadas y el motor nunca ejecuta `PRAGMA foreign_keys=ON` al abrir cada conexión | M9 · 7. SQLite local e integración con FastAPI | `v0-semilla` | `python -c "from sqlalchemy import text; import database; print(database.engine.connect().execute(text('PRAGMA foreign_keys')).scalar())"` | `0` | Listener `connect` del engine que ejecuta `PRAGMA foreign_keys=ON` en cada conexión |
| H6 | Los tests que indica el README escriben en la base real: la primera corrida pasa y la segunda falla, porque la póliza de prueba ya quedó guardada en `app.db` | `tests/test_api.py` usa la aplicación con su sesión global sobre `app.db`: no hay `dependency_overrides` ni base temporal | M10 · 5. TestClient de FastAPI | `v0-semilla` | `python -m pytest -q -p no:cacheprovider tests/test_api.py >/dev/null 2>&1; a=$?; python -m pytest -q -p no:cacheprovider tests/test_api.py >/dev/null 2>&1; echo "$a $?"` | `0 1` | Tests propios que sustituyen `database.get_db` con `app.dependency_overrides` sobre una base temporal; `pytest` pasa dos veces seguidas sin tocar `app.db` |
| H7 | El contenedor no responde desde el host: `docker run -p 8000:8000` publica el puerto, pero uvicorn escucha solo en el loopback del contenedor, y en modo desarrollo (`--reload`), que el README además recomienda para producción | `CMD` con `--host 127.0.0.1` y `--reload`; `FROM python:latest` sin fijar, una sola etapa, sin `USER` ni `HEALTHCHECK` y sin `.dockerignore` (`COPY . .` mete `app.db` en la imagen) | M11 · 6. Estructura de un Dockerfile | `v0-semilla` | `grep -n "CMD" Dockerfile` | `8:CMD ["uvicorn", "main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"]` | Dockerfile multietapa sobre `python:3.11.9-slim-bookworm`, usuario no root, `HEALTHCHECK` contra `/health`, `CMD` con `--host 0.0.0.0` y sin `--reload`, y `.dockerignore` |
| H8 | Las respuestas exponen `token_firma`, un hash derivado del secreto de firma, a cualquier cliente que consulte una póliza | Ninguna ruta declara `response_model`: se devuelve el objeto ORM o un dict con todas sus columnas, internas incluidas | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s localhost:8000/polizas/1 \| grep -o '"token_firma":"[0-9a-f]*"'` | `"token_firma":"e0f37b88f9799aa7b9103f60a7346b831e588b62b421480649eb6a4fcfbc1102"` | Esquemas de salida con `from_attributes=True` y `response_model` en todas las rutas; `token_firma` no forma parte de la salida |
| H9 | El nombre del asegurado se pierde: se envía `"Carla Rueda"` y la póliza se guarda y se devuelve con `asegurado: null` (toda la cartera sembrada lo tiene así) | El `field_validator` `normalizar_asegurado` calcula el nombre normalizado pero no lo devuelve; sin `return`, Pydantic asigna `None` | M7 · 4. Validadores de campo | `v0-semilla` | `curl -s -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero": "POL-2026-90009", "asegurado": "Carla Rueda", "tipo": "auto", "prima": 1250000, "fecha_inicio": "2026-01-15", "fecha_fin": "2027-01-14"}' \| grep -o '"asegurado":[^,]*'` | `"asegurado":null` | El validador devuelve el valor normalizado |
| H10 | Un recurso inexistente responde 200 con `{"error": ...}` en lugar de 404, en `GET` y `PUT /polizas/{id}`, `POST /polizas/{id}/siniestros` y `POST /score` | Los handlers devuelven un dict de error en vez de lanzar `HTTPException(404)`; `declarar_siniestro` ni siquiera comprueba que la póliza exista | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code} " localhost:8000/polizas/999999; curl -s -o /dev/null -w "%{http_code} " -X PUT localhost:8000/polizas/999999 -H "Content-Type: application/json" -d '{"prima": 10}'; curl -s -o /dev/null -w "%{http_code} " -X POST localhost:8000/polizas/999999/siniestros -H "Content-Type: application/json" -d '{"fecha": "2026-03-02", "monto": 850000, "descripcion": "Choque leve"}'; curl -s -o /dev/null -w "%{http_code}" -X POST localhost:8000/score -H "Content-Type: application/json" -d '{"numero": "POL-NO-EXISTE"}'` | `200 200 200 200` | `HTTPException(status_code=404)` en las cuatro rutas; la existencia de la póliza se comprueba antes de crear el siniestro |
| H11 | Crear una póliza responde 200 en lugar de 201 Created (lo mismo al declarar un siniestro) | Los decoradores `@app.post` que crean recursos no declaran `status_code=201` | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero": "POL-2026-90011", "asegurado": "Ana Rueda", "tipo": "auto", "prima": 1250000, "fecha_inicio": "2026-01-15", "fecha_fin": "2027-01-14"}'` | `200` | `status_code=201` en `POST /polizas` y `POST /polizas/{id}/siniestros` |
| H12 | `PUT /polizas/{id}` no es parcial: enviar solo `prima` borra `asegurado`, `tipo` y `fecha_fin`, que quedan en `null` | `datos.model_dump()` incluye los campos no enviados con su valor por defecto `None`, y el handler los asigna todos | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -X PUT localhost:8000/polizas/3 -H "Content-Type: application/json" -d '{"prima": 1000000}' \| grep -o '"tipo":[^,]*'` | `"tipo":null` | `model_dump(exclude_unset=True)`: solo se actualiza lo que viene en el cuerpo |
| H13 | La entrada acepta datos incoherentes: un siniestro anidado con `monto: -50` y una póliza con `fecha_fin` anterior a `fecha_inicio` se guardan con 200 en lugar de 422 | `siniestros` se tipa como `list[dict]`, así que los siniestros anidados no pasan por `SiniestroEntrada` (`monto > 0`); no hay `model_validator` que compare las fechas | M7 · 5. Modelos anidados y topología jerárquica | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code} " -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero": "POL-2026-90131", "asegurado": "Ana Rueda", "tipo": "auto", "prima": 1250000, "fecha_inicio": "2026-01-15", "fecha_fin": "2027-01-14", "siniestros": [{"fecha": "2026-03-02", "monto": -50, "descripcion": "Choque leve"}]}'; curl -s -o /dev/null -w "%{http_code}" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero": "POL-2026-90132", "asegurado": "Ana Rueda", "tipo": "auto", "prima": 1250000, "fecha_inicio": "2027-01-14", "fecha_fin": "2026-01-15"}'` | `200 200` | `siniestros: list[SiniestroEntrada]` y un `model_validator(mode="after")` que exige `fecha_fin` posterior a `fecha_inicio` |
| H14 | Un número de póliza repetido responde 500 en lugar de 409, y a partir de ahí **todo** el servicio responde 500 hasta que se reinicia | El `IntegrityError` no se captura, y la única sesión del módulo (`database.sesion`) queda con la transacción rota (`PendingRollbackError`) para todas las peticiones siguientes | M9 · 7. SQLite local e integración con FastAPI | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code} " -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero": "POL-2026-00001", "asegurado": "Ana Rueda", "tipo": "auto", "prima": 1250000, "fecha_inicio": "2026-01-15", "fecha_fin": "2027-01-14"}'; curl -s -o /dev/null -w "%{http_code}" localhost:8000/polizas/1` | `500 500` | Sesión por petición: `database.get_db` con `yield` y cierre, inyectada con `Depends(get_db)` en cada ruta; el `IntegrityError` se convierte en `rollback` + `HTTPException(409)` |

> **Orden de ejecución.** Las evidencias se capturaron en este orden, una sola vez, sobre
> `v0-semilla` recién clonado (con su `app.db` original) y con el servicio recién levantado.
> H10 deja un siniestro huérfano y H14 deja la sesión global inservible: por eso van al final
> y ninguna fila anterior depende de lo que ellas rompen.

**Reglas que se verifican automáticamente:**

- `Módulo · Sección` debe citar una lección que exista en los módulos 6 a 11, con el
  título tal como aparece en el menú lateral del material.
- **`SHA donde se observa`** es el commit donde el defecto todavía está: normalmente
  `v0-semilla`, la etiqueta del repositorio tal como se les entregó. El calificador hace
  *checkout* de ese commit para reproducir la evidencia. Si lo dejan en el commit final
  —donde ya está corregido— el comando no reproducirá nada y la fila no cuenta.
- `Comando de evidencia` se ejecuta ahí, con el servicio levantado. Escríbanlo contra
  `localhost:8000`; el calificador sustituye el puerto por el que use. Un comando `docker`
  también vale: se reproduce si hay Docker en la máquina que califica.
- `Salida obtenida` es literal, copiada de su terminal. **Se compara con lo que salga de
  verdad**, así que una salida inventada se detecta.
- Entre 8 y 14 hallazgos. Una fila que no corresponda a un defecto real resta la mitad de
  lo que suma una correcta: el máximo se alcanza con precisión, no con volumen.

---

# Parte C — Interpretación de las consultas

> Un párrafo por endpoint. Expliquen **los conteos que ustedes obtuvieron** con
> `contar_consultas.py`: por qué ese número, por qué cambia o no entre 10 y 2000
> pólizas, y qué estrategia dejaron en el código. Si un resultado los sorprendió,
> díganlo: eso se premia.

## `/polizas`

Con el código original (`lazy`) daba 1+N consultas: 11 a 10 pólizas, 2001 a 2000 —
la ruta pedía las pólizas y, al serializar cada una, disparaba una consulta
aparte por sus siniestros. Con `selectinload(Poliza.siniestros)` esperaba un
número fijo de 2 consultas sin importar N, pero a 2000 pólizas dio **5**, no 2.
Revisé el código de SQLAlchemy (`orm/strategies.py:2999`) y la explicación es
que `selectinload` agrupa los IDs de los padres en lotes de `chunksize=500` para
no armar un `WHERE poliza_id IN (...)` arbitrariamente largo: con 2000 pólizas
son `ceil(2000/500) = 4` lotes más la consulta inicial de pólizas, 5 en total.
Sigue siendo un cambio enorme frente al N+1 (2001 → 5), pero no es estrictamente
constante: crece a saltos de 500, no de 1 en 1. Probé además la alternativa
`joinedload(Poliza.siniestros)`: baja a **1** sola consulta (sin el lotaje), pero
tarda más —362.8 ms frente a 336.1 ms a 2000 pólizas— porque el JOIN repite las
columnas de cada póliza una vez por cada siniestro (2000×3 = 6000 filas con datos
de póliza duplicados) y SQLAlchemy obliga a llamar `.unique()` para deduplicar
los padres antes de poder usar la colección. Menos consultas no es sinónimo de
más rápido: me quedé con `selectinload`.

## `/polizas/{id}`

Da 2 consultas tanto a 10 como a 2000 pólizas: una para `db.get(Poliza, id)` y
otra, diferida, cuando se serializa `.siniestros`. No cambia con el tamaño de la
tabla porque la ruta solo toca **una** póliza —el costo depende de cuántos
siniestros tiene esa póliza (3, fijo en la siembra), no de cuántas pólizas haya
en total. Probé forzar `selectinload` aquí también, y dio exactamente las mismas
2 consultas en ambos tamaños: con N=1 no hay N+1 que arreglar, así que "cargar
todo de una vez" no gana nada. Por eso lo dejé en `lazy`, sin tocar el código:
es la estrategia más simple que mide igual que la alternativa "eager".

## `/siniestros`

Pasó de 1+N consultas (11 a 10, 2001 a 2000: una por listar los siniestros y una
por cada acceso diferido a `siniestro.poliza` dentro de `numero_poliza`) a **1
sola consulta fija**, con `joinedload(Siniestro.poliza)`. A diferencia de
`/polizas`, aquí el JOIN no tiene costo de fan-out: la relación de `Siniestro` a
`Poliza` es a-uno, así que cada fila del JOIN corresponde a exactamente un
siniestro —no hay filas duplicadas que deduplicar ni columnas repetidas de más.
Por eso para esta relación `joinedload` es estrictamente mejor que
`selectinload` (que aquí también bajaría a 2 consultas: todos los siniestros +
un `SELECT ... WHERE id IN (...)` con los IDs de póliza distintos).

## `/resumen`

Pasó de 1+N consultas (11 a 10, 2001 a 2000: una por listar las pólizas y una
por cada `len(p.siniestros)`/`sum(...)` al recorrerlas en Python) a **1 sola
consulta agregada**, calculando `COUNT`/`SUM` y `GROUP BY` directamente en la
base de datos con un `outerjoin` entre `Poliza` y `Siniestro` (el `outerjoin`
es necesario para que una póliza sin siniestros siga apareciendo con 0 y 0.0, en
vez de desaparecer del resultado). No cambia entre 10 y 2000 porque el cálculo
nunca trae las filas de siniestro a Python: lo único que viaja por la red es una
fila resumen por póliza. De las cuatro, es la única donde ni `lazy` ni
`selectinload`/`joinedload` tenían sentido: no se necesitan los siniestros
completos, solo dos agregados por póliza.
