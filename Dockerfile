# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.11-slim

WORKDIR /code

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Install pip requirements
COPY ./requirements.txt ./
RUN pip install --upgrade -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port Streamlit runs on
EXPOSE 8501
# Expose the port the debugger will listen on
EXPOSE 5678

# Command to run the Streamlit app with the debugger
# --wait-for-client will pause the app until the debugger attaches
CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client", "-m", "streamlit", "run", "src/AutoML.py", "--server.runOnSave", "false"]

