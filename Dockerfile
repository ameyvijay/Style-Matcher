FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# Opt out of Next.js telemetry
ENV NEXT_TELEMETRY_DISABLED 1

# Generate the production build
RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]
