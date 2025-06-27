#!/usr/bin/env python3
"""Create protocol tables using Python."""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def create_tables():
    """Create protocol tables."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment")
        return False
    
    print(f"Connecting to: {db_url}")
    
    try:
        # Connect directly with asyncpg
        conn = await asyncpg.connect(db_url)
        
        print("✅ Connected to database")
        
        # Create user_protocol_status table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_protocol_status (
                user_id TEXT PRIMARY KEY,
                status VARCHAR(20) NOT NULL DEFAULT 'INACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
                activated_by TEXT,
                activated_at TIMESTAMPTZ,
                reason TEXT,
                messages_quarantined INTEGER DEFAULT 0,
                cost_saved_usd DECIMAL(10,4) DEFAULT 0.0000,
                last_message_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        print("✅ Created user_protocol_status table")
        
        # Create protocol_audit_log table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS protocol_audit_log (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                action VARCHAR(20) NOT NULL CHECK (action IN ('ACTIVATED', 'DEACTIVATED', 'ONE_TIME_PASS')),
                performed_by TEXT NOT NULL,
                reason TEXT,
                previous_status VARCHAR(20),
                new_status VARCHAR(20),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        print("✅ Created protocol_audit_log table")
        
        # Create quarantine_messages table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS quarantine_messages (
                id SERIAL PRIMARY KEY,
                message_id TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                message_text TEXT NOT NULL,
                telegram_message_id INTEGER,
                received_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '7 days'),
                processed BOOLEAN DEFAULT FALSE,
                processed_at TIMESTAMPTZ,
                processed_by TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        print("✅ Created quarantine_messages table")
        
        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_protocol_status_active ON user_protocol_status(status) WHERE status = 'ACTIVE'",
            "CREATE INDEX IF NOT EXISTS idx_protocol_updated ON user_protocol_status(updated_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_audit_user_created ON protocol_audit_log(user_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_quarantine_user_expires ON quarantine_messages(user_id, expires_at) WHERE NOT processed",
            "CREATE INDEX IF NOT EXISTS idx_quarantine_expires ON quarantine_messages(expires_at) WHERE NOT processed"
        ]
        
        for index_sql in indexes:
            await conn.execute(index_sql)
        
        print("✅ Created all indexes")
        
        # Verify tables exist
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename IN ('user_protocol_status', 'protocol_audit_log', 'quarantine_messages')
            ORDER BY tablename
        """)
        
        print(f"\n✅ Verified {len(tables)} protocol tables created:")
        for table in tables:
            print(f"  - {table['tablename']}")
        
        await conn.close()
        print("\n🎉 Protocol tables created successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(create_tables())
    sys.exit(0 if success else 1)