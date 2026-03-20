FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY solutions/tripletex_bot_v2.py .

EXPOSE 8080

CMD ["uvicorn", "tripletex_bot_v2:app", "--host", "0.0.0.0", "--port", "8080"]
