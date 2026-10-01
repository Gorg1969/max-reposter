FROM python:3.11-slim

WORKDIR /app

ENV TZ=Europe/Moscow
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN mkdir -p /app/data/webhooks

EXPOSE 3000

CMD ["python", "app.py"]
