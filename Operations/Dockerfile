FROM node:22-bookworm-slim AS graphiques
WORKDIR /build
COPY Frontend/package.json Frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY Frontend/charts/ ./charts/
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY Backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && groupadd -g 10001 amblueo \
 && useradd -u 10001 -g 10001 -M amblueo \
 && mkdir -p /data/private /data/static \
 && chown -R amblueo:amblueo /data
COPY Backend/ /app/Backend/
COPY Frontend/templates/ /app/Frontend/templates/
COPY Frontend/static/ /app/Frontend/static/
COPY --from=graphiques /build/static/pilot/ /app/Frontend/static/pilot/
COPY Frontend/Logo/ /app/Frontend/Logo/
WORKDIR /app/Backend
USER 10001:10001
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--error-logfile", "-"]
