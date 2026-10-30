FROM node:22-slim

WORKDIR /app
COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

EXPOSE 8681
CMD ["npm", "start"]
