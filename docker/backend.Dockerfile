# Backend image (demo mode / API tier).
#
# NOTE ON PRODUCTION: the PowerShell provider needs the ActiveDirectory RSAT
# module and domain line-of-sight, which only exist on a domain-joined Windows
# host. The recommended production topology (docs/DEPLOYMENT.md) runs this
# container for the API tier in DEMO_MODE=false only when the PowerShell
# execution host is Windows; otherwise run the backend directly on a Windows
# member server. This image is fully sufficient for demo and evaluation.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --gid 10001 eio && useradd --uid 10001 --gid eio --create-home eio

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY powershell ./powershell

RUN mkdir -p /app/data /app/logs && chown -R eio:eio /app
USER eio

ENV EIO_DEMO_MODE=true \
    EIO_DATA_DIR=/app/data \
    EIO_LOGS_DIR=/app/logs \
    EIO_SCRIPTS_DIR=/app/powershell/scripts

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
