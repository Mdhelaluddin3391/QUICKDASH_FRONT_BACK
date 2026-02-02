#!/bin/sh
set -e

echo "Starting Frontend with PORT=$PORT"

# Inject Railway PORT into nginx config
envsubst '$PORT' < /etc/nginx/conf.d/default.conf > /tmp/default.conf
mv /tmp/default.conf /etc/nginx/conf.d/default.conf

echo "Configuring API URL..."

if [ -n "$API_BASE_URL" ]; then
    echo "Injecting API URL: $API_BASE_URL"
    CONFIG_FILE="/usr/share/nginx/html/assets/js/config.js"
    sed -i "s|const apiBase = .*|const apiBase = \"$API_BASE_URL\";|g" $CONFIG_FILE
else
    echo "WARNING: API_BASE_URL not set"
fi

echo "Starting Nginx..."
exec su-exec appuser "$@"
