# Dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose the port your application runs on
EXPOSE 8080

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

