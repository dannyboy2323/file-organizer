# Use official Python image
FROM python:3.11

# Set working directory
WORKDIR /app

# Copy files
COPY requirements.txt .
COPY main.py .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Command to run the populate script
CMD ["python", "main.py"]
