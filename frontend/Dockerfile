FROM node:20-slim

WORKDIR /app

# Install pnpm globally
RUN npm install -g pnpm

# Copy package files first
COPY frontend/package.json frontend/pnpm-lock.yaml ./

# Install all dependencies
RUN pnpm install --frozen-lockfile

# Copy the rest of the frontend files
COPY frontend/ .

EXPOSE 8080

# Start Vite dev server exposing it to all network interfaces
CMD ["pnpm", "run", "dev", "--host", "0.0.0.0", "--port", "8080"]
