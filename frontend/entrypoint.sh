#!/bin/bash
# /frontend/entrypoint.sh

set -e

echo " Configuring API URL..."

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

echo " Starting Nginx..."
exec "$@"