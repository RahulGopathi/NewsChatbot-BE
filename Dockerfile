FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install poetry==1.8.2

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1

COPY pyproject.toml poetry.lock ./

RUN poetry install --no-root


FROM python:3.11-slim AS runtime

RUN apt-get update && \
    apt-get install -y libmagic1 gettext-base && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY --from=builder /app/.venv ${VIRTUAL_ENV}

COPY . .

# Create necessary directories
RUN mkdir -p data/raw_articles data/processed logs

# Expose the API port
EXPOSE 8000

# Command to run the application with python directly to avoid path issues
CMD ["python", "run.py"] 