# Use a base image with Python
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy only necessary files to leverage Docker cache
COPY requirements.txt .

# Expose any required ports
EXPOSE 11434

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Run the polling script
CMD ["python", "script.py"]