FROM python:3.12-slim

# System deps for pyzbar (QR decoding)
RUN apt-get update && apt-get install -y \
    libzbar0 \
    libzbar-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
