FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir "boto3>=1.40"

COPY apps/media-worker/src ./src

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "main"]
