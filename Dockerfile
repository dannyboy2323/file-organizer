FROM amazonlinux:2023

# Install runtime dependencies
RUN yum update -y && \
    yum install -y python3.9 postgresql15 && \
    python3.9 -m pip install --upgrade pip

# Set application environment
ENV PYTHONUNBUFFERED=1 \
    COPILOT_APPLICATION_NAME=file-organizer \
    COPILOT_ENVIRONMENT_NAME=test

# Install application dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# Copy application code
COPY app/ .

# Configure entrypoint
CMD ["python3.9", "-u", "file_organizer.py"]
