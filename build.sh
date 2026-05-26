#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Install Tesseract OCR
apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-kor || true

# Ensure data directories exist
mkdir -p data/uploads data/outputs data/review
