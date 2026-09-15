FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests
COPY create_tables.py .

EXPOSE 8000

CMD ["sh", "-c", "python create_tables.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]