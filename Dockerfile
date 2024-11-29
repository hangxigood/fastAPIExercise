FROM python:3.9

WORKDIR /app

# Added ENV PYTHONUNBUFFERED=1 for better logging in interactive mode
ENV PYTHONUNBUFFERED=1

# Install requirements and iptables
RUN apt-get update && \
    apt-get install -y iptables && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Start script with rate limiting
CMD ["sh", "-c", "iptables -A INPUT -p tcp --dport 8080 -m limit --limit 60/minute --limit-burst 100 -j ACCEPT && iptables -A INPUT -p tcp --dport 8080 -j DROP && uvicorn main:app --host 0.0.0.0 --port 8080"]