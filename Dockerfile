FROM python:3.11-slim

# 1. Set the working directory
WORKDIR /app

# 2. Copy requirements and install (Modified for speed)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3.  Copy your code before the volumes are mounted
COPY . .

# 4. Create the data directory so the volume mount doesn't error out
RUN mkdir -p /app/data /app/config

# 5. Run the bot
CMD ["python", "main.py"]
