FROM python:3.11

WORKDIR /app/

RUN pip install uv

COPY . /app/

RUN uv pip install --system --no-cache-dir .

ENV PYTHONPATH=/app

CMD ["fastapi", "run", "--workers", "4", "app/main.py"]
