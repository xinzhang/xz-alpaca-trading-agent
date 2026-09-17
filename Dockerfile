FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src

RUN uv sync --no-dev

EXPOSE 8000
CMD ["uv", "run", "python", "-m", "alphadesk.main"]
