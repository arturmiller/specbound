FROM node:22-alpine
WORKDIR /app
COPY services/web/package*.json ./
RUN npm ci
COPY services/web/ ./
EXPOSE 5173
CMD ["npm", "run", "dev"]
