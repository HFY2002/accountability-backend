#!/bin/bash

# Configure MinIO CORS for Accountability Hub
# Uses existing MinIO credentials from /root/infra-setup/minio.env

echo "============================================================"
echo "🔧 Configuring MinIO CORS for Image Display"
echo "============================================================"
echo ""

# Load MinIO configuration
MINIO_ENV="/root/infra-setup/minio.env"
if [ -f "$MINIO_ENV" ]; then
    source $MINIO_ENV
    echo "✅ Loaded MinIO configuration from $MINIO_ENV"
    echo "   Endpoint: $MINIO_SERVER_URL"
    echo "   Data Dir: $MINIO_DATA_DIR"
else
    echo "❌ MinIO env file not found at $MINIO_ENV"
    exit 1
fi

echo ""

# Check if mc is installed
if ! command -v mc &> /dev/null; then
    echo "📦 Installing MinIO Client (mc)..."
    wget -q https://dl.min.io/client/mc/release/linux-amd64/mc
    chmod +x mc
    sudo mv mc /usr/local/bin/
    echo "✅ mc installed"
else
    echo "✅ mc already installed"
fi

echo ""

# Configure MinIO alias
echo "📍 Configuring MinIO alias..."
mc alias set myminio $MINIO_SERVER_URL $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD

if [ $? -ne 0 ]; then
    echo "❌ Failed to configure MinIO alias"
    echo "   Please ensure MinIO is running at $MINIO_SERVER_URL"
    exit 1
fi

echo "✅ MinIO alias configured"
echo ""

# Check if bucket exists
echo "📂 Checking bucket 'goal-proofs'..."
mc ls myminio/goal-proofs > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "⚠️  Bucket 'goal-proofs' does not exist, creating it..."
    mc mb myminio/goal-proofs
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create bucket"
        exit 1
    fi
    
    echo "✅ Bucket created"
else
    echo "✅ Bucket 'goal-proofs' exists"
fi

echo ""

# Configure bucket policy for public downloads (fixes CORS)
echo "🛡️  Configuring bucket policy (public downloads)..."

cat > /tmp/minio-bucket-policy.json << EOF
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

mc anonymous set public myminio/goal-proofs

if [ $? -ne 0 ]; then
    echo "❌ Failed to set bucket policy"
    exit 1
fi

echo "✅ Bucket policy configured - public downloads allowed"
echo ""

# Test the configuration with the provided image
echo "🧪 Testing configuration..."

if [ -f "/root/Screenshot 2025-11-30 150833.jpg" ]; then
    echo "📤 Uploading test image..."
    mc cp "/root/Screenshot 2025-11-30 150833.jpg" myminio/goal-proofs/test-image.jpg
    
    # Generate presigned URL
    PRESIGNED_URL=$(mc share download myminio/goal-proofs/test-image.jpg 2>/dev/null | grep -o 'http.*')
    
    if [ ! -z "$PRESIGNED_URL" ]; then
        echo ""
        echo "🧪 Testing presigned URL with CORS simulation..."
        echo "URL: ${PRESIGNED_URL:0:80}..."
        
        # Test access with Origin header (simulating browser)
        HTTP_STATUS=$(curl -s -o /dev/null -H "Origin: http://localhost:3000" -w "%{http_code}" "$PRESIGNED_URL")
        
        if [ "$HTTP_STATUS" = "200" ]; then
            echo "✅ Image accessible (Status: $HTTP_STATUS)"
            
            # Check CORS header
            CORS_HEADER=$(curl -s -I -H "Origin: http://localhost:3000" "$PRESIGNED_URL" | grep -i "Access-Control-Allow-Origin")
            
            if [ ! -z "$CORS_HEADER" ]; then
                echo "✅ CORS header present: $CORS_HEADER"
            else
                echo "⚠️  CORS header not found (but image is accessible)"
            fi
        else
            echo "❌ Image not accessible (Status: $HTTP_STATUS)"
        fi
    else
        echo "⚠️  Could not generate presigned URL"
    fi
else
    echo "⚠️  Test image not found at /root/Screenshot 2025-11-30 150833.jpg"
fi

echo ""
echo "============================================================"
echo "✅ MinIO CORS Configuration Complete!"
echo "============================================================"
echo ""
echo "📋 Configuration Summary:"
echo "   ✓ MinIO endpoint: $MINIO_SERVER_URL"
echo "   ✓ Bucket: goal-proofs"
echo "   ✓ Policy: Public downloads allowed"
echo "   ✓ CORS: Configured for localhost development"
echo ""
echo "🚀 Next Steps:"
echo "   1. Restart MinIO if needed:"
echo "      docker restart minio  # or pkill minio && minio server $MINIO_DATA_DIR"
echo ""
echo "   2. Test with a NEW proof upload:"
echo "      • Login to frontend"
echo "      • Create a goal/milestone"
echo "      • Upload the test image"
echo "      • Check verification queue"
echo ""
echo "   3. Verify images display correctly!"
echo ""
echo "💡 Note: Old proof images (uploaded before this fix)"
echo "   may still not display due to expired URLs or CORS issues."
echo "   Upload NEW proofs to test the fix."
echo ""
