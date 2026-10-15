# Bitácora de uso de IA

**Grupo:** <número> · **Integrantes:** Oscar Mateo Ramos, Vanessa Acosta, Brayan David Barreto
**Herramientas usadas:** Claude Code (Claude Opus 5.5)

> Las tres secciones son obligatorias. **`## Rechazado` es la que se califica.**
> Una bitácora que solo lista prompts aceptados vale la mitad.

## Prompts

| # | Parte | Quién | Prompt (resumido si es largo) |
|---|-------|-------|-------------------------------|
| 1 | — | Mateo | Leer el enunciado del taller y clonar el repositorio semilla en mi GitHub, sin hacer nada más |
| 2 | — | Mateo | Dar acceso a Vanessa y proponer cómo repartir el taller entre dos personas de forma secuencial (ramas o `main`, bitácora) |
| 3 | A | Mateo | Hacer la Parte A: encontrar los defectos de `polizas-api-v0` y documentarlos en `HALLAZGOS.md` con evidencia reproducible sobre `v0-semilla` |
| 4 | B | Mateo | Hacer el PR 2 (B1–B5 y B10): dependencias fijadas, `.env`, `BaseSettings`, sesión por petición, claves foráneas, Alembic y `/health` |
| 5 | B | Mateo | Hacer el PR 3 (B6–B7): `response_model`, 201/404/409, PUT parcial y validadores, hasta que `test_contrato.py` pase 12/12 |
| 6 | B | Brayan | Revisar el enunciado y lo que me corresponde (`entregableBrayan.md`: B8, B9, revisión del PR de la Parte D) y hacer un plan |
| 7 | B | Brayan | Ejecutar el plan: B8 (tests aislados), B9 (Docker), README y revisión del PR de la Parte D con mutaciones |
| 8 | — | Brayan | Declararme en `EQUIPO.md`, registrar mis entradas en la bitácora y subir la rama `parte-b-tests-docker` |
| 9 | — | Brayan | Preguntar qué hace falta para la entrega |
| 10 | D | Brayan | Hacer todo lo que falte y que yo pueda hacer sin los demás: reforzar la Parte D, integrar las ramas y dejar la entrega lista |

## Aceptado

| # | Qué propuso la IA | Por qué lo aceptamos | Qué cambiamos antes de usarlo |
|---|-------------------|----------------------|-------------------------------|
| 1 | B8: en `tests/test_api.py`, una fixture de módulo que crea la base en una carpeta temporal de pytest, le aplica `alembic upgrade head` y sustituye `database.get_db` con `app.dependency_overrides` (commit `df867ef`) | La llave del override es la misma dependencia que usan las rutas, así que el aislamiento es real; reutiliza `database.crear_engine`, que activa `PRAGMA foreign_keys=ON` | Nada en el código. Antes de aceptarlo lo comprobamos: `pytest` dos veces seguidas con el mismo SHA-256 de `app.db`, y con `database.get_db` saboteado `tests/test_api.py` siguió 4/4 |
| 2 | B9: Dockerfile en dos etapas sobre `python:3.11.9-slim-bookworm`, usuario no root, base en `/app/datos` y `CMD sh -c "alembic upgrade head && exec uvicorn ..."` (commit `3966f76`) | La base no viene en la imagen, así que hay que migrar al arrancar; `exec` deja a uvicorn recibir la señal de `docker stop` | Nada en el código. Lo comprobamos con `docker run -p 8000:8000`: `/health` 200 desde el host, estado `healthy`, uid 10001, imagen sin `.env` ni `*.db`, y el ensayo de la demo (restart, contenedor nuevo, volumen) |
| 3 | Parte D: reforzar `tests/test_ia_corregido.py` (leer de vuelta lo escrito, `/predicciones` tras `/score`, los 422 de los validadores, 404 en PUT y en siniestros) y rehacer la mutación del defecto 1 con la forma pedida (commits `9ea6343` y `98c52f9`) | La corregida seguía en verde con cuatro mutaciones del tipo que pide el enunciado, y la mutación del defecto 1 dejaba la original en rojo, al revés de lo pedido | Nada en el código. Antes del commit se verificó con ocho mutaciones: la corregida falla con todas y la original solo detecta una. Esa verificación obligó a corregir una frase del dictamen que decía que la original no detectaba ninguna |

## Rechazado

| # | Qué propuso la IA | Por qué lo rechazamos | Qué hicimos en su lugar |
|---|-------------------|-----------------------|-------------------------|
| 1 | Clonar el repositorio fuera de OneDrive (`C:\Users\bdbar\dev`) para que OneDrive no sincronizara el `.venv` ni bloqueara los `.db` de SQLite durante `pytest` (Brayan) | Preferí tener el repositorio en la carpeta del curso, junto a `entregableBrayan.md` | Lo cloné en la carpeta del curso y dejé fuera de OneDrive solo el entorno virtual (`C:\Users\bdbar\.venvs\polizas-api`) |
