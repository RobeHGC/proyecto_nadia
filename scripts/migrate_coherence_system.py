#!/usr/bin/env python3
"""
Migration script for Coherence and Schedule System
Executes the SQL migration to add tables for commitment tracking and coherence analysis.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def run_migration():
    """Execute the coherence system migration"""
    print("🔄 Starting Coherence System Migration...")
    
    try:
        # Get database URL from environment
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print("❌ DATABASE_URL environment variable not set")
            return False
        
        # Read migration SQL file
        migration_file = project_root / "database" / "migrations" / "add_coherence_system.sql"
        
        if not migration_file.exists():
            print(f"❌ Migration file not found: {migration_file}")
            return False
            
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        print("📄 Executing migration SQL...")
        
        # Execute migration in a transaction
        conn = await asyncpg.connect(database_url)
        try:
            async with conn.transaction():
                await conn.execute(migration_sql)
        finally:
            await conn.close()
        
        print("✅ Migration completed successfully!")
        print("📊 Created tables:")
        print("   - nadia_commitments (with indices)")
        print("   - coherence_analysis")
        print("   - prompt_rotations")
        print("   - active_commitments_view")
        print("🔧 Added columns to interactions table")
        print("⚙️ Created helper functions and triggers")
        
        # Verify tables were created
        await verify_migration(database_url)
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

async def verify_migration(database_url: str):
    """Verify the migration was successful"""
    print("🔍 Verifying migration...")
    
    try:
        conn = await asyncpg.connect(database_url)
        try:
            # Check if tables exist
            tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('nadia_commitments', 'coherence_analysis', 'prompt_rotations')
            ORDER BY table_name;
            """
            
            tables = await conn.fetch(tables_query)
            table_names = [row['table_name'] for row in tables]
            
            expected_tables = ['coherence_analysis', 'nadia_commitments', 'prompt_rotations']
            
            for table in expected_tables:
                if table in table_names:
                    print(f"   ✅ Table '{table}' created successfully")
                else:
                    print(f"   ❌ Table '{table}' not found")
            
            # Check indices
            indices_query = """
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename IN ('nadia_commitments', 'coherence_analysis', 'prompt_rotations')
            ORDER BY indexname;
            """
            
            indices = await conn.fetch(indices_query)
            print(f"📋 Created {len(indices)} indices for performance optimization")
            
            # Check if interactions table was modified
            columns_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'interactions' 
            AND column_name IN ('coherence_analysis_id', 'llm1_quality_rating', 'has_commitments', 'commitment_count')
            ORDER BY column_name;
            """
            
            new_columns = await conn.fetch(columns_query)
            print(f"🔧 Added {len(new_columns)} columns to interactions table")
            
            # Test view exists
            view_query = """
            SELECT viewname 
            FROM pg_views 
            WHERE viewname = 'active_commitments_view';
            """
            
            views = await conn.fetch(view_query)
            if views:
                print("👁️ Active commitments view created successfully")
        finally:
            await conn.close()
            
    except Exception as e:
        print(f"⚠️ Verification failed: {e}")

async def rollback_migration():
    """Rollback the migration if needed"""
    print("🔄 Rolling back Coherence System Migration...")
    
    rollback_sql = """
    -- Remove added columns from interactions
    ALTER TABLE interactions 
    DROP COLUMN IF EXISTS coherence_analysis_id,
    DROP COLUMN IF EXISTS llm1_quality_rating,
    DROP COLUMN IF EXISTS has_commitments,
    DROP COLUMN IF EXISTS commitment_count;
    
    -- Drop tables in reverse order (respecting foreign keys)
    DROP VIEW IF EXISTS active_commitments_view;
    DROP TABLE IF EXISTS prompt_rotations;
    DROP TABLE IF EXISTS coherence_analysis;
    DROP TABLE IF EXISTS nadia_commitments;
    
    -- Drop functions
    DROP FUNCTION IF EXISTS update_expired_commitments();
    DROP FUNCTION IF EXISTS check_commitment_conflicts(TEXT, TIMESTAMPTZ, TIMESTAMPTZ);
    DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
    """
    
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print("❌ DATABASE_URL environment variable not set")
            return False
        
        conn = await asyncpg.connect(database_url)
        try:
            async with conn.transaction():
                await conn.execute(rollback_sql)
        finally:
            await conn.close()
        
        print("✅ Rollback completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        return False

async def main():
    """Main function to handle command line arguments"""
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        success = await rollback_migration()
    else:
        success = await run_migration()
    
    if success:
        print("🎉 Operation completed successfully!")
        sys.exit(0)
    else:
        print("💥 Operation failed!")
        sys.exit(1)

if __name__ == "__main__":
    # Check if DATABASE_URL is set
    if not os.getenv("DATABASE_URL"):
        print("❌ DATABASE_URL environment variable not set")
        print("💡 Set it with: export DATABASE_URL=postgresql://username:password@localhost/nadia_hitl")
        sys.exit(1)
    
    asyncio.run(main())