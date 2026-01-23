# /frontend/Dockerfile

# Use Nginx stable Alpine
FROM nginx:stable-alpine

# Install su-exec and libcap-utils
RUN apk add --no-cache su-exec libcap-utils

# Allow Nginx to bind to port 80 as non-root user
RUN setcap 'cap_net_bind_service=+ep' /usr/sbin/nginx

# Create non-root user with UID 1000
RUN addgroup -g 1000 appgroup && adduser -D -u 1000 -G appgroup appuser

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Fix permissions and nginx config for non-root
RUN chown -R appuser:appgroup /var/cache/nginx \
    && chown -R appuser:appgroup /var/log/nginx \
    && chown -R appuser:appgroup /etc/nginx/conf.d \
    && touch /var/run/nginx.pid \
    && chown -R appuser:appgroup /var/run/nginx.pid \
    && echo -e 'error_log /tmp/error.log warn;\npid /tmp/nginx.pid;\nevents {\n}\nhttp {\n  access_log off;\n  include /etc/nginx/modules/*.conf;\n  include /etc/nginx/conf.d/*.conf;\n}' > /etc/nginx/nginx.conf

# Copy frontend assets with correct ownership
COPY --chown=appuser:appgroup . /usr/share/nginx/html

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 80

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]