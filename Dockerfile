# 1. Use an official Python runtime as a parent image
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy the requirements file and install dependencies
# Make sure you have a requirements.txt file in your repo!
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of your bot's code into the container
COPY . .

# 5. The command to run your bot (replace 'main.py' with your script name)
CMD ["python", "main.py"]
