FROM python:3.11

WORKDIR /app/

RUN pip install uv

COPY pyproject.toml /app/

RUN uv pip install --system --no-cache-dir .

COPY . /app/

ENV PYTHONPATH=/app

CMD ["fastapi", "run", "--workers", "4", "app/main.py"]
