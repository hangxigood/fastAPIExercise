FROM python:3.9

WORKDIR /app

# Added ENV PYTHONUNBUFFERED=1 for better logging in interactive mode
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Changed to allow interactive mode
ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]