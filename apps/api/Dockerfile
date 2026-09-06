FROM python:3.12-slim

WORKDIR /app

RUN groupadd --gid 10001 vivoo \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin vivoo \
    && mkdir -p /data/media \
    && chown -R vivoo:vivoo /app /data/media \
    && pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.34" \
    "pydantic>=2.10" \
    "psycopg[binary]>=3.2" \
    "boto3>=1.40" \
    "cryptography>=45.0"

COPY --chown=vivoo:vivoo apps/api/src ./src

ENV PYTHONPATH=/app/src
EXPOSE 8000
USER vivoo

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
