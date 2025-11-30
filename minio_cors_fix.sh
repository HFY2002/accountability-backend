#!/bin/bash

# MinIO CORS Fix Script
# This configures MinIO to allow CORS requests from the frontend

echo "============================================================"
echo "🔧 Configuring MinIO for CORS Support"
echo "============================================================"
echo ""

# Check if mc is installed
if ! command -v mc &> /dev/null; then
    echo "📦 Installing MinIO Client (mc)..."
    wget -q https://dl.min.io/client/mc/release/linux-amd64/mc
    chmod +x mc
    sudo mv mc /usr/local/bin/
    echo "✅ mc installed"
    echo ""
fi

# Configure MinIO alias
echo "📍 Configuring MinIO access..."
mc alias set myminio http://localhost:9000 minioadmin minioadmin

if [ $? -ne 0 ]; then
    echo "❌ Failed to configure MinIO"
    exit 1
fi

echo "✅ MinIO configured"
echo ""

# Create the bucket policy file
echo "📋 Creating bucket policy..."
cat > /tmp/minio-bucket-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::goal-proofs/*"]
    }
  ]
}
EOF

# Apply the bucket policy
echo "📝 Applying bucket policy..."
mc admin policy create myminio public-download /tmp/minio-bucket-policy.json
mc anonymous set public myminio/goal-proofs

if [ $? -ne 0 ]; then
    echo "❌ Failed to apply bucket policy"
    exit 1
fi

echo "✅ Bucket policy applied - bucket is now publicly readable"
echo ""

# Test the configuration
echo "🧪 Testing configuration..."

# Upload test image if it doesn't exist
if [ -f "/root/Screenshot 2025-11-30 150833.jpg" ]; then
    echo "📤 Uploading test image..."
    mc cp "/root/Screenshot 2025-11-30 150833.jpg" myminio/goal-proofs/test-image.jpg
fi

# Get presigned URL
PRESIGNED_URL=$(mc share download myminio/goal-proofs/test-image.jpg | grep -o 'http.*')

echo ""
echo "🧪 Presigned URL: ${PRESIGNED_URL:0:100}..."
echo ""

# Test access with curl
echo "🧪 Testing access..."
curl -s -o /dev/null -w "%{http_code}" "${PRESIGNED_URL}" | grep -q "200"

if [ $? -eq 0 ]; then
    echo "✅ Image accessible via presigned URL"
else
    echo "❌ Image not accessible"
fi

echo ""
echo "============================================================"
echo "✅ MinIO CORS Configuration Complete!"
echo "============================================================"
echo ""
echo "📋 Summary:"
echo "   • Bucket 'goal-proofs' is now publicly readable"
echo "   • Presigned URLs should work without CORS issues"
echo "   • Frontend should display images correctly"
echo ""
echo "💡 Next steps:"
echo "   1. Restart MinIO (if needed)"
echo "   2. Upload a new proof image"
echo "   3. Check if images display in frontend"
echo ""
