# --- Etapa 1: construcción -----------------------------------------------------
# Instala las dependencias fijadas en un entorno virtual aislado. Esta etapa
# (pip, su caché, requirements.txt) no llega a la imagen final: solo /opt/venv.
FROM python:3.11.9-slim-bookworm AS construccion

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Solo requirements.txt: mientras no cambie, Docker reutiliza esta capa aunque
# cambie el código.
COPY requirements.txt .
RUN pip install -r requirements.txt


# --- Etapa 2: ejecución ----------------------------------------------------------
FROM python:3.11.9-slim-bookworm

# La base vive en /app/datos, la única carpeta en la que el usuario del servicio
# puede escribir. No viene en la imagen: la crean las migraciones al arrancar.
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////app/datos/app.db

RUN useradd --create-home --uid 10001 app

WORKDIR /app
COPY --from=construccion /opt/venv /opt/venv
# El código queda de root y el servicio solo lo lee; .dockerignore deja fuera
# .env, las bases *.db, los entornos virtuales y .git.
COPY . .
RUN mkdir -p /app/datos && chown app:app /app/datos

USER app

EXPOSE 8000

# La imagen slim no trae curl: se consulta /health con Python. Un 503 (base sin
# migrar o sin respuesta) lanza HTTPError y marca el contenedor como unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

# Migra la base antes de servir; `exec` deja a uvicorn como el proceso que recibe
# las señales de `docker stop`. Sin --reload (es para desarrollo) y en 0.0.0.0 para
# que el puerto publicado con -p responda desde el host.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000"]
