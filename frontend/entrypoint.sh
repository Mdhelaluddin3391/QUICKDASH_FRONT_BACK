#!/bin/sh
# /frontend/entrypoint.sh

set -e

echo "Configuring API URL..."

# Check if API_BASE_URL env var is set
if [ ! -z "$API_BASE_URL" ]; then
    echo "Injecting API URL: $API_BASE_URL"

    # Target config file
    CONFIG_FILE="/usr/share/nginx/html/assets/js/config.js"

    # Replace the placeholder in config.js with the actual URL
    sed -i "s|const apiBase = .*|const apiBase = \"$API_BASE_URL\";|g" $CONFIG_FILE
else
    echo "WARNING: API_BASE_URL not set. Using default config."
fi

# FIX: Removed the chown commands for static/media folders
# because they are proxied to the backend and don't exist here.

echo "Starting Nginx..."
exec su-exec appuser "$@"