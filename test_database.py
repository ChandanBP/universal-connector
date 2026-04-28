"""
DATABASE INTEGRATION TEST
Check connection and provide debugging info
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("\n" + "="*80)
print("DATABASE CONNECTION TEST")
print("="*80)

db_url = os.getenv("DATABASE_URL")

if not db_url:
    print("\n❌ ERROR: DATABASE_URL not set in .env file")
    print("\nTo set up your database:")
    print("  1. Create a Supabase project at https://supabase.com")
    print("  2. Go to Project Settings → Database → Connection Pooler")
    print("  3. Copy the 'Session' mode connection string")
    print("  4. Paste it in .env as DATABASE_URL")
    sys.exit(1)

print(f"\n✓ DATABASE_URL is set")

# Parse connection details
try:
    from urllib.parse import urlparse
    parsed = urlparse(db_url)
    
    print(f"\nConnection Details:")
    print(f"  User: {parsed.username}")
    print(f"  Host: {parsed.hostname}")
    print(f"  Port: {parsed.port}")
    print(f"  Database: {parsed.path.strip('/')}")
    
except Exception as e:
    print(f"\n⚠️  Could not parse DATABASE_URL: {e}")

# Try to connect
print("\n" + "-"*80)
print("Attempting connection...")
print("-"*80)

try:
    import psycopg2
    from psycopg2.extensions import connection
    
    conn = psycopg2.connect(db_url)
    print("✅ Connection successful!")
    
    # Check tables
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = cur.fetchall()
    
    if tables:
        print(f"\n✓ Found {len(tables)} tables:")
        for (table,) in tables:
            print(f"    • {table}")
    else:
        print("\n⚠️  No tables found. Schema may not be created yet.")
        print("\nTo create schema:")
        print("  1. Open Supabase Dashboard → SQL Editor")
        print("  2. Paste contents of db/schema.sql")
        print("  3. Click 'Run'")
    
    cur.close()
    conn.close()
    
except psycopg2.OperationalError as e:
    print(f"\n❌ Connection Error: {e}")
    print("\nPossible solutions:")
    print("  1. Verify DATABASE_URL is correct (copy from Supabase Dashboard)")
    print("  2. Check if Supabase project is active")
    print("  3. Try Session mode (Pooler) instead of direct connection")
    print("  4. Check firewall/network settings")
    
except Exception as e:
    print(f"\n❌ Error: {e}")

print("\n" + "="*80 + "\n")
