FROM node:20-slim

# Instalar Python 3 para el motor del bot (bot_motor.py y generador_estados.py)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias de Node
COPY package*.json ./
RUN npm install --production

# Copiar el resto del código
COPY . .

ENV PORT=10000
EXPOSE 10000

CMD ["node", "server.js"]
