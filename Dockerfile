FROM python:3.11-slim

WORKDIR /app

COPY . /app

EXPOSE 4173

CMD ["python", "backend/app.py"]
