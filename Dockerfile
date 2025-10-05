FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.4

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# Copy only dependency files first for caching
COPY pyproject.toml poetry.lock* /app/

# Configure Poetry to not create virtualenvs
RUN poetry config virtualenvs.create false \
 && poetry install --only main --no-interaction --no-ansi

# Copy project
COPY . /app

# Collect static in image build for WhiteNoise
RUN python manage.py collectstatic --noinput || true

# Ensure entrypoint is executable
RUN chmod +x /app/docker-entrypoint.sh

# Create non-root user
RUN useradd -m appuser
USER appuser

# Expose the app port
EXPOSE 8000

# Gunicorn config and entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
