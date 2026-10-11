# Accomodo: demo Render gratuita, dati temporanei e nessun provider reale.
FROM node:22-bookworm-slim AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN --mount=type=secret,id=proxy_ca if [ -s /run/secrets/proxy_ca ]; then NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca npm ci; else npm ci; fi
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-15 postgresql-contrib-15 redis-server && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.lock ./
RUN --mount=type=secret,id=proxy_ca if [ -s /run/secrets/proxy_ca ]; then PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -r requirements.lock; else pip install --no-cache-dir -r requirements.lock; fi
COPY backend/ ./
COPY scripts/hosted_demo.py scripts/hosted_worker.py /app/hosting/
COPY --from=frontend /frontend/dist /app/public
RUN useradd --uid 10001 --create-home accomodo && mkdir -p /work && chown -R accomodo:accomodo /app /work
USER accomodo
ENV PYTHONPATH=/app HOSTED_DEMO=true FRONTEND_DIST=/app/public APP_ENV=demo DEMO_MODE=true SEND_REAL_MESSAGES=false
EXPOSE 10000
CMD ["python", "/app/hosting/hosted_demo.py"]
