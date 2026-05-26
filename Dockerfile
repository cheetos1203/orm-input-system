FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY app /code/app
COPY data /code/data
COPY run_web.py /code/run_web.py
COPY .env.example /code/.env.example

EXPOSE 8000

CMD ["python", "run_web.py"]

