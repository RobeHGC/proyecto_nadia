#!/usr/bin/env python3
"""Test database connection and permissions."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import DatabaseManager
from dotenv import load_dotenv

load_dotenv()


async def test_connection():
    """Test database connection and permissions."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found")
        return
    
    print(f"Database URL: {db_url}")
    
    db = DatabaseManager(db_url)
    await db.initialize()
    
    try:
        async with db._pool.acquire() as conn:
            # Test connection
            version = await conn.fetchval("SELECT version()")
            print(f"✅ Connected to: {version}")
            
            # Check current user
            user = await conn.fetchval("SELECT current_user")
            print(f"Current user: {user}")
            
            # Check existing tables
            tables = await conn.fetch("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
            
            print(f"\nExisting tables ({len(tables)}):")
            for table in tables:
                print(f"  - {table['tablename']}")
            
            # Check if protocol tables already exist
            protocol_tables = await conn.fetch("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename IN ('user_protocol_status', 'protocol_audit_log', 'quarantine_messages')
            """)
            
            if protocol_tables:
                print(f"\n⚠️  Protocol tables already exist:")
                for table in protocol_tables:
                    print(f"  - {table['tablename']}")
            else:
                print(f"\n✅ Protocol tables do not exist yet")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(test_connection())