#!/bin/bash

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Database Erase Utility (v2) ===${NC}"
echo "This script will remove ALL ROWS from ALL TABLES while preserving the schema."
echo "This version works WITHOUT requiring superuser privileges."
echo ""

# Function to extract values from .env file
get_env_value() {
    grep "^$1=" "/root/backend/.env" | cut -d'=' -f2- | tr -d '"'
}

# Read database configuration from .env
DB_HOST=$(get_env_value "POSTGRES_SERVER")
DB_USER=$(get_env_value "POSTGRES_USER")
DB_PASS=$(get_env_value "POSTGRES_PASSWORD")
DB_NAME=$(get_env_value "POSTGRES_DB")

# Validate configuration
if [ -z "$DB_HOST" ] || [ -z "$DB_USER" ] || [ -z "$DB_NAME" ]; then
    echo -e "${RED}Error: Could not read database configuration from .env file${NC}"
    exit 1
fi

# Set password for psql
export PGPASSWORD="$DB_PASS"

# Test connection
echo -e "${GREEN}Testing database connection...${NC}"
if ! psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${RED}Error: Cannot connect to database. Check credentials and connection.${NC}"
    exit 1
fi

# Count rows before deletion
echo -e "${GREEN}Counting rows in each table...${NC}"
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT schemaname, tablename, 
       (xpath('/row/cnt/text()', xml_count))[1]::text::int as row_count
FROM (
  SELECT schemaname, tablename, 
         query_to_xml(format('SELECT COUNT(*) as cnt FROM %I.%I', schemaname, tablename), false, true, '') as xml_count
  FROM pg_tables
  WHERE schemaname = 'public'
) AS sub;
"

# Prompt for confirmation
echo ""
echo -e "${YELLOW}WARNING: This will DELETE ALL DATA from ALL TABLES!${NC}"
echo -e "${YELLOW}The database schema will be preserved.${NC}"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${RED}Operation cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${GREEN}Proceeding with data deletion using TRUNCATE CASCADE...${NC}"

# Get list of tables in correct order (handle dependencies)
TABLES=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT tablename 
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY tablename;")

if [ -z "$TABLES" ]; then
    echo -e "${RED}No tables found in public schema.${NC}"
    exit 1
fi

# Start transaction and truncate all tables
# Generate dynamic list of tables to avoid hardcoding issues
TABLE_LIST=$(echo "$TABLES" | tr '\n' ',' | sed 's/,$//')

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" <<EOF
-- Start transaction to ensure atomic operation
BEGIN;

-- Truncate all tables with CASCADE to handle foreign key constraints
-- CASCADE will truncate child tables when parent tables are truncated
TRUNCATE TABLE $TABLE_LIST CASCADE;

-- Commit transaction
COMMIT;

\echo ''
\echo '=== Verification: Row counts after deletion ==='
SELECT schemaname, tablename, 
       (xpath('/row/cnt/text()', xml_count))[1]::text::int as row_count
FROM (
  SELECT schemaname, tablename, 
         query_to_xml(format('SELECT COUNT(*) as cnt FROM %I.%I', schemaname, tablename), false, true, '') as xml_count
  FROM pg_tables
  WHERE schemaname = 'public'
) AS sub;
EOF

# Check exit status
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ Successfully erased all rows from database '${DB_NAME}'${NC}"
    echo -e "${GREEN}✓ Schema remains intact${NC}"
else
    echo ""
    echo -e "${RED}✗ Error occurred during deletion. Transaction may have been rolled back.${NC}"
fi

# Clear the password from environment
unset PGPASSWORD

echo -e "${GREEN}Operation completed.${NC}"