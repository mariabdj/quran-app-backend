FROM python:3.9-slim

WORKDIR /app

# 1. Copy requirements.txt first to leverage Docker layer caching for dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Copy the rest of your application code into the container
# This step will copy your main.py, ai.py, and the 'scripts' directory
# (containing preload_model.py), and any other project files.
COPY . .

# 3. Run the preload script to download and cache the Hugging Face model
# This command executes during the Docker image build process.
# Ensure 'scripts/preload_model.py' exists in your project structure.
RUN python preload_model.py

# 4. Define the command to run your FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]