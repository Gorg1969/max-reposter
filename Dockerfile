FROM python:3.11-slim

WORKDIR /app

ENV TZ=Europe/Moscow
ENV PYTHONUNBUFFERED=1
ENV PORT=3000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 3000

CMD ["python", "app.py"]
