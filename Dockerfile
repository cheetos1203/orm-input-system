FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

# Install Tesseract OCR with Korean language support
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-kor && \
    rm -rf /var/lib/apt/lists/*

ENV TESSERACT_CMD=/usr/bin/tesseract

COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY app /code/app
COPY data /code/data
COPY run_web.py /code/run_web.py
COPY .env.example /code/.env.example

RUN mkdir -p /code/data/uploads /code/data/outputs /code/data/review

EXPOSE 8000

# Use PORT env var for Render compatibility, default to 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
