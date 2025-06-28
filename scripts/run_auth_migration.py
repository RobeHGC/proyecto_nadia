#!/usr/bin/env python3
"""Run authentication tables migration for Epic 53 Session 1."""
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
    """Execute authentication tables migration."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment")
        return False
    
    db = DatabaseManager(db_url)
    await db.initialize()
    
    try:
        async with db._pool.acquire() as conn:
            # Read migration file
            migration_path = Path(__file__).parent.parent / "database" / "migrations" / "add_authentication_tables.sql"
            with open(migration_path, 'r') as f:
                sql = f.read()
            
            # Execute migration
            await conn.execute(sql)
            
            print("✅ Authentication migration executed successfully!")
            print("Created tables:")
            print("  - users (OAuth user accounts)")
            print("  - user_sessions (JWT session tracking)")
            print("  - user_permissions (Fine-grained permissions)")
            print("  - auth_audit_log (Security audit trail)")
            
            # Verify tables exist
            tables = await conn.fetch("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename IN ('users', 'user_sessions', 'user_permissions', 'auth_audit_log')
                ORDER BY tablename
            """)
            
            print(f"\nVerified {len(tables)} tables created:")
            for table in tables:
                print(f"  ✓ {table['tablename']}")
            
            # Check if default admin was created
            admin = await conn.fetchrow("SELECT email, role FROM users WHERE email = 'admin@nadia-hitl.com'")
            if admin:
                print(f"\n✓ Default admin user created: {admin['email']} (role: {admin['role']})")
            
            return True
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await db.close()


if __name__ == "__main__":
    print("🔐 Running Epic 53 Session 1: Authentication Tables Migration")
    print("=" * 60)
    success = asyncio.run(run_migration())
    sys.exit(0 if success else 1)