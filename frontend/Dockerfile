# Use Nginx stable Alpine for lightweight image
FROM nginx:stable-alpine

# Install su-exec and libcap-utils for running as non-root
RUN apk add --no-cache su-exec libcap-utils

# Allow Nginx to bind to port 80 as non-root user
RUN setcap 'cap_net_bind_service=+ep' /usr/sbin/nginx

# Create non-root user with UID 1000 to match backend and host
RUN addgroup -g 1000 appgroup && adduser -D -u 1000 -G appgroup appuser

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy frontend assets
COPY . /usr/share/nginx/html

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 80

# Set entrypoint and default command
ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
