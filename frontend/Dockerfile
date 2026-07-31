FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
EXPOSE 5199
CMD ["npm", "run", "dev"]
