FROM python:3.9-slim

# Install System Dependencies (ffmpeg for video, libvips for image processing)
RUN apt-get update && \
    apt-get install -y ffmpeg curl git libvips-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
