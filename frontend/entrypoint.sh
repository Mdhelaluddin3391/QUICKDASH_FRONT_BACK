#!/bin/sh
set -e

echo "Starting Frontend..."

# 1. Create env.js dynamically based on environment variables
echo "Generating env.js..."
cat <<EOF > /usr/share/nginx/html/assets/js/env.js
window.env = {
  API_BASE_URL: "${API_BASE_URL:-https://quickdash-front-back.onrender.com/api/v1}"
};
EOF

# 2. Inject PORT into Nginx config (for Railway/Render support)
if [ -n "$PORT" ]; then
    sed -i "s/listen\s*80;/listen $PORT;/g" /etc/nginx/conf.d/default.conf
fi

echo "Starting Nginx..."
exec nginx -g "daemon off;"