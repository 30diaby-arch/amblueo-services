FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && groupadd -g 10001 amblueo \
 && useradd -u 10001 -g 10001 -M amblueo \
 && mkdir -p /data/private /data/static \
 && chown -R amblueo:amblueo /data
COPY . .
USER 10001:10001
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--error-logfile", "-"]
