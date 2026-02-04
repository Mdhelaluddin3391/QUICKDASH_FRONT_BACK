FROM nginx:stable-alpine

# Install utilities
RUN apk add --no-cache bash

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy Custom Nginx Config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy Frontend Assets
COPY . /usr/share/nginx/html

# Entrypoint setup
COPY entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Ensure env.js exists and is writable
RUN touch /usr/share/nginx/html/assets/js/env.js && \
    chmod 777 /usr/share/nginx/html/assets/js/env.js

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]