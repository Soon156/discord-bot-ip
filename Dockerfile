FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ip_watcher_bot.py .
ENV PYTHONUNBUFFERED=1
CMD ["python", "ip_watcher_bot.py"]