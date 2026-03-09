FROM nginx:stable-alpine

# 1. Install utilities (bash aur dos2unix add kiya hai line-endings fix karne ke liye)
RUN apk add --no-cache bash dos2unix

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy Custom Nginx Config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy Frontend Assets
COPY . /usr/share/nginx/html

# Entrypoint setup
COPY entrypoint.sh /docker-entrypoint.sh

# 2. IMPORTANT FIX: Convert script to Unix format & Make executable
RUN dos2unix /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

# Ensure env.js exists and is writable
RUN touch /usr/share/nginx/html/assets/js/env.js && \
    chmod 777 /usr/share/nginx/html/assets/js/env.js

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]