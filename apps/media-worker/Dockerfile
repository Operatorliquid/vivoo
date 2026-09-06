FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 vivoo \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin vivoo \
    && mkdir -p /data/media \
    && chown -R vivoo:vivoo /app /data/media \
    && pip install --no-cache-dir "boto3>=1.40"

COPY --chown=vivoo:vivoo apps/media-worker/src ./src

ENV PYTHONPATH=/app/src
USER vivoo

CMD ["python", "-m", "main"]
