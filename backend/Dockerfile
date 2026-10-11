# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -s /run/secrets/proxy_ca ]; then PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -r requirements.lock; else pip install --no-cache-dir -r requirements.lock; fi
COPY . .
RUN useradd --uid 10001 --create-home tavolo && mkdir -p /work && chown -R tavolo:tavolo /app /work && chmod -R a+rX /app
USER tavolo
# Only the private Compose network sees port 8000; host ingress is loopback nginx.
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--no-access-log"]
