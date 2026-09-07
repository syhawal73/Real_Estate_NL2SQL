FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package.json and package-lock.json (if exists)
COPY package.json package-lock.json* ./

# Copy the rest of the application code
COPY . .

# Expose Vite's default port
EXPOSE 5173

# Install dependencies at startup (not during build) to avoid
# network issues during docker build and because the volume mount
# overwrites the build-time node_modules anyway.
CMD ["sh", "-c", "npm install && npm run dev"]
