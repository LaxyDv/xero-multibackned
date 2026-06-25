# Start with a lightweight Python image
FROM python:3.9-slim

# Install System Dependencies (FFmpeg is mandatory for video/audio merging)
RUN apt-get update && \
    apt-get install -y ffmpeg curl git && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 8000
EXPOSE 8000

# Command to start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
