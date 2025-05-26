FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
# FFmpeg is crucial for librosa to handle a wide range of audio formats like M4A.
# Running apt-get update and install in a single RUN command and cleaning up
# helps to keep Docker image layers smaller.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first to leverage Docker layer caching for dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Run the preload script to download and cache the Hugging Face model
RUN python preload_model.py

# Define the command to run your FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]