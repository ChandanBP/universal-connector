#!/usr/bin/env python3
"""
Fix DATABASE_URL format for Supabase

The current format has special characters that need URL encoding.
This script provides guidance on fixing the connection string.
"""

import sys

print("""
╔════════════════════════════════════════════════════════════════════════════╗
║           SUPABASE DATABASE URL FIX                                        ║
╚════════════════════════════════════════════════════════════════════════════╝

Your current DATABASE_URL has a parsing issue.
The password contains special characters (#) that need URL encoding.

STEPS TO FIX:

1. Go to Supabase Dashboard
2. Project → Settings → Database → Connection Pooling
3. Select "Session mode" (not Direct)
4. Copy the full connection string

The format should look like:
  postgresql://[user].[project]:[password]@[region].pooler.supabase.com:6543/postgres

Where:
  [user] = postgres (usually)
  [project] = Your project reference ID
  [password] = Your database password (URL encoded if special chars)
  [region] = Region code (e.g., ap-southeast-1)

EXAMPLE WITH URL ENCODING:
  If your password is: Newuserstartup123#
  URL encoded: Newuserstartup123%23

So the full URL becomes:
  postgresql://postgres.[project]:Newuserstartup123%23@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres

QUICK FIX:

1. Edit .env file
2. Replace the DATABASE_URL line with the correct connection string from Supabase
3. Make sure to URL-encode special characters:
   • # → %23
   • @ → %40
   • & → %26

Then run: python test_database.py

""")

# URL encode helper
import urllib.parse

password = "Newuserstartup123#"
encoded = urllib.parse.quote(password, safe='')
print(f"Your password URL-encoded: {encoded}")
print(f"\nThen use it in DATABASE_URL like:")
print(f"postgresql://postgres.PROJECT_REF:{encoded}@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres")
