#!/usr/bin/env python3
"""Run protocol migration."""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import DatabaseManager
from dotenv import load_dotenv

load_dotenv()


async def run_migration():
    """Execute protocol tables migration."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment")
        return False
    
    db = DatabaseManager(db_url)
    await db.initialize()
    
    try:
        async with db._pool.acquire() as conn:
            # Read migration file
            migration_path = Path(__file__).parent.parent / "database" / "migrations" / "add_protocol_tables.sql"
            with open(migration_path, 'r') as f:
                sql = f.read()
            
            # Execute migration
            await conn.execute(sql)
            
            print("✅ Migration executed successfully!")
            print("Created tables:")
            print("  - user_protocol_status")
            print("  - protocol_audit_log") 
            print("  - quarantine_messages")
            
            # Verify tables exist
            tables = await conn.fetch("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename IN ('user_protocol_status', 'protocol_audit_log', 'quarantine_messages')
                ORDER BY tablename
            """)
            
            print(f"\nVerified {len(tables)} tables created:")
            for table in tables:
                print(f"  ✓ {table['tablename']}")
            
            return True
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    finally:
        await db.close()


if __name__ == "__main__":
    success = asyncio.run(run_migration())
    sys.exit(0 if success else 1)