# Purpose: Production-optimized multi-stage build for the React dashboard.
# Responsibilities:
# - Stage 1 (builder): Install dependencies and compile the Vite/React app.
# - Stage 2 (runtime): Serve the static bundle via nginx with SPA routing support.
#
# This replaces the previous `npm run dev` approach which was dev-server only
# and NOT suitable for production use.

# ==========================================
# STAGE 1: Builder
# ==========================================
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (leverages Docker layer caching — only re-runs if
# package.json changes, not on every source code change)
COPY package.json ./
RUN npm install

# Copy source code
COPY . .

# Build the production bundle — Vite outputs to /app/dist
# VITE_API_BASE_URL is injected at build time from the environment.
# When building via docker-compose, pass it via the `environment:` block or `--build-arg`.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build


# ==========================================
# STAGE 2: Runtime (nginx)
# ==========================================
FROM nginx:1.27-alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our custom SPA-aware nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the compiled React bundle from the builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx runs as root by default to bind port 80, which is acceptable in a
# containerized environment. For extra hardness, nginx drops to www-data 
# internally after binding.

EXPOSE 80

# Health check — verify nginx is serving the index page
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/health || exit 1

CMD ["nginx", "-g", "daemon off;"]