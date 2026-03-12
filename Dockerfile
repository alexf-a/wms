FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install Poetry (version from .tool-versions via --build-arg)
ARG POETRY_VERSION
RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# Copy only dependency files first for caching
COPY pyproject.toml poetry.lock* /app/

# Configure Poetry to not create virtualenvs
RUN poetry config virtualenvs.create false \
 && poetry install --only main --no-interaction --no-ansi

# Copy project
COPY . /app

# Download Tailwind standalone CLI and build CSS
# TARGETARCH is set automatically by Docker BuildKit (amd64 or arm64)
ARG TW_VERSION
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "arm64" ]; then TW_ARCH="linux-arm64"; else TW_ARCH="linux-x64"; fi \
 && curl -sL https://github.com/tailwindlabs/tailwindcss/releases/download/${TW_VERSION}/tailwindcss-${TW_ARCH} -o /usr/local/bin/tailwindcss \
 && chmod +x /usr/local/bin/tailwindcss \
 && tailwindcss -i core/tailwind/input.css -o core/static/core/css/tailwind.css --minify

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
