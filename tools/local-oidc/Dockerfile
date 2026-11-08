FROM node:22-alpine
WORKDIR /app
COPY tools/local-oidc/package*.json ./
RUN npm ci --omit=dev
COPY tools/local-oidc/server.mjs ./
EXPOSE 5556
CMD ["node", "server.mjs"]
