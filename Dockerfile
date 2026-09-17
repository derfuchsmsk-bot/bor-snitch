FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (ffmpeg needed for audio streaming in voice calls)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Port for Cloud Run (default is 8080)
ENV PORT=8080

# Command to run the application using uvicorn
# Assuming src/main.py contains the FastAPI app instance named 'app'
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
