FROM python:3.9-slim

# Instala python-dotenv para carregar variáveis de ambiente
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o .env para dentro da imagem (opcional, para desenvolvimento)
COPY .env .env

WORKDIR /app
COPY src/ .

CMD ["python", "pump_producer.py"]
