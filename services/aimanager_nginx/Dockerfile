# =============================================================================
# AI Manager Platform - Nginx Reverse Proxy Dockerfile
# =============================================================================
# Purpose: Nginx reverse proxy container for Business API with AI-optimized timeouts
# Base: Official nginx:alpine for minimal size
# =============================================================================

FROM nginx:1.25-alpine

# Remove default nginx configuration
RUN rm /etc/nginx/nginx.conf

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Create log directory with proper permissions
RUN mkdir -p /var/log/nginx && \
    chown -R nginx:nginx /var/log/nginx

# Expose port 8000
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8000/health || exit 1

# Start nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
