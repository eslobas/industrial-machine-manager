# Imagem da API REST (FastAPI + SQLite).
# A aplicação de desktop (Tkinter) não faz parte da imagem.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MANUTENCAO_DB=/data/manutencao.db

WORKDIR /app

# Dependências primeiro, para aproveitar a cache de camadas
COPY requirements.txt .
RUN pip install -r requirements.txt

# Utilizador sem privilégios e pasta para a base de dados (montada como volume)
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown app:app /data

COPY repositorio.py .
COPY api/ api/

USER app
VOLUME ["/data"]
EXPOSE 8000

# A imagem slim não traz curl; usa-se o próprio Python
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
