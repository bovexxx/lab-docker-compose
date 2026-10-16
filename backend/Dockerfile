# Backend — REST API (FastAPI + PostgreSQL + интеграция с Open Library)
FROM python:3.12-slim

WORKDIR /app

# Копируем и устанавливаем зависимости отдельным слоем (кэш образа)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY main.py .

EXPOSE 8000

# Запуск через uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
