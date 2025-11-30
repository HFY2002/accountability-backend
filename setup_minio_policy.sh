#!/bin/bash

# Quick MinIO policy setup

# Kill hanging configure script
pkill -f configure_minio_cors.sh

# Install mc if needed
if ! command -v mc &> /dev/null; then
    echo "Installing mc..."
    wget -q https://dl.min.io/client/mc/release/linux-amd64/mc
    chmod +x mc
    sudo mv mc /usr/local/bin/
fi

# Configure MinIO
mc alias set myminio http://127.0.0.1:9000 admin 12345678

# Make bucket publicly readable for downloads
mc anonymous set download myminio/goal-proofs

echo "✅ MinIO configured for public downloads"
echo ""
echo "Test it:"
echo "1. Upload a new proof image"
echo "2. Check if it displays in frontend"
