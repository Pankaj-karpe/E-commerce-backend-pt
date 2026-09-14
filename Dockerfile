# ==========================================
# STAGE 1: BUILDER (Python 3.13)
# ==========================================
FROM python:3.13-slim AS BUILDER

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --user -r requirements.txt

# ==========================================
# STAGE 2: RUNTIME (Distroless Python 3.13)
# ==========================================
FROM gcr.io/distroless/python3:nonroot

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/home/nonroot/.local/lib/python3.13/site-packages:/app \
    PATH=/home/nonroot/.local/bin:$PATH

WORKDIR /app

# Copy compiled shared library from stage 1
COPY --from=BUILDER /usr/lib/*-linux-gnu/libpq.so* /usr/lib/

# Copy installed site-packages and binaries from stage 1
COPY --from=BUILDER /root/.local /home/nonroot/.local

# Copy application source code
COPY --chown=nonroot:nonroot . /app/

USER nonroot

EXPOSE 8080

CMD ["/home/nonroot/.local/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]