FROM python:3.11-slim

WORKDIR /code

# Added libgomp1 (often needed for ML libraries)
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libpq-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt ./

# THE FIX: --no-cache-dir reduces size by ~500MB
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501 5678

CMD ["streamlit", "run", "src/AutoML.py", "--server.runOnSave", "false"]