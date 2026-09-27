FROM python:3.11-slim

# Prevent Python bytecode files and limit glibc malloc arenas to keep RAM low on Render & Koyeb
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MALLOC_ARENA_MAX=2 \
    MEDIA_POOL_SIZE=6 \
    RAM_CACHE_MAX_MB=40 \
    WZGRAM_MAX_READ_AHEAD=24

WORKDIR /app

# Install FFmpeg with minimal footprint
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app/

CMD ["python3", "bot.py"]
