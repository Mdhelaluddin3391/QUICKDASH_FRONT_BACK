#!/bin/bash
# /frontend/entrypoint.sh

set -e

echo "Configuring API URL..."

# Check if API_BASE_URL env var is set
if [ ! -z "$API_BASE_URL" ]; then
    echo "Injecting API URL: $API_BASE_URL"

    # Target config file
    CONFIG_FILE="/usr/share/nginx/html/assets/js/config.js"

    # We use sed to replace the logic in config.js with the hardcoded production URL
    # This matches the specific line in your provided config.js
    sed -i "s|const apiBase = .*|const apiBase = \"$API_BASE_URL\";|g" $CONFIG_FILE
else
    echo "WARNING: API_BASE_URL not set. Using default config."
fi

# Change ownership of named volumes to appuser
# This ensures Nginx can read static and media files
# Named volumes are shared with backend, so ownership must match
chown -R appuser:appgroup /usr/share/nginx/html/static /usr/share/nginx/html/media

echo "Starting Nginx..."
exec su-exec appuser "$@"