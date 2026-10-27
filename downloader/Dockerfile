FROM python:3.12-slim

# ffmpeg es necesario para unir el audio y el video en un solo .mp4
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Aqui se instala yt-dlp (viene en requirements.txt) desde PyPI
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Para que los logs de yt-dlp salgan en tiempo real
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["python", "app.py"]
