FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for secp256k1
RUN apt-get update && apt-get install -y \
    pkg-config \
    build-essential \
    libsecp256k1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "main.py"]
