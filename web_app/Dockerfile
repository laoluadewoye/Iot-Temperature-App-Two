FROM ubuntu:latest

# Add system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Add a non-root user and set home
RUN useradd -ms /bin/bash app
WORKDIR /app
RUN chown -R app:app /app

# Copy project files
COPY --chown=app:app . .

# Create and activate virtual environment
RUN python3 -m venv /app/venv

# Install Python dependencies inside the virtual environment
RUN /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Add virtualenv to path
ENV PATH="/app/venv/bin:$PATH"

# Switch to non-root user
USER app

# Run the web application
ENTRYPOINT ["bash", "-c", "python DataGen.py && exec streamlit run WebApp.py"]
