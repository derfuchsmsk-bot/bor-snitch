FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if needed (usually none for this stack)

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Port for Cloud Run (default is 8080)
ENV PORT=8080

# Command to run the application using uvicorn
# Assuming src/main.py contains the FastAPI app instance named 'app'
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
