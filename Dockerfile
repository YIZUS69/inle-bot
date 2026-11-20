FROM node:20-slim

# Instalar Git, Python 3 y curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias de Node
COPY package*.json ./
RUN npm install --omit=dev

# Copiar el resto del código
COPY . .

ENV PORT=10000
EXPOSE 10000

CMD ["node", "server.js"]
