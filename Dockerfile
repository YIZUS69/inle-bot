FROM node:20-slim

# Instalar Git, openssh-client (requerido por dependencias de Baileys), Python 3 y curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    openssh-client \
    python3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Forzar a git a usar HTTPS en lugar de SSH para GitHub
RUN git config --global url."https://github.com/".insteadOf "ssh://git@github.com/" && \
    git config --global url."https://github.com/".insteadOf "git@github.com:" && \
    git config --global url."https://".insteadOf "ssh://"

WORKDIR /app

# Instalar dependencias de Node
COPY package*.json ./
RUN npm install --omit=dev

# Copiar el resto del código
COPY . .

ENV PORT=10000
EXPOSE 10000

CMD ["node", "server.js"]
