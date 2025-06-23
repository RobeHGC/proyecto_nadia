#!/usr/bin/env python3
"""
Script to verify database saving functionality after review approval.
Checks if interactions are properly saved to PostgreSQL.
"""
import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

async def verify_database_saving():
    """Check recent database entries for approved interactions."""
    
    database_url = os.getenv("DATABASE_URL", "postgresql://localhost/nadia_hitl")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        print(f"✅ Connected to database: {database_url}")
        
        # Check for recent interactions (last 24 hours)
        query = """
        SELECT 
            id,
            user_id,
            user_message,
            review_status,
            final_bubbles,
            llm1_model,
            llm2_model,
            llm1_cost_usd,
            llm2_cost_usd,
            edit_tags,
            quality_score,
            created_at,
            review_completed_at
        FROM interactions
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        ORDER BY created_at DESC
        LIMIT 10
        """
        
        rows = await conn.fetch(query)
        
        if not rows:
            print("\n⚠️  No interactions found in the last 24 hours")
        else:
            print(f"\n📊 Found {len(rows)} recent interactions:\n")
            
            for row in rows:
                print(f"ID: {row['id']}")
                print(f"User: {row['user_id']}")
                print(f"Message: {row['user_message'][:50]}...")
                print(f"Status: {row['review_status']}")
                print(f"Final bubbles: {row['final_bubbles']}")
                print(f"Models: {row['llm1_model']} → {row['llm2_model']}")
                print(f"Costs: ${row['llm1_cost_usd'] or 0:.4f} + ${row['llm2_cost_usd'] or 0:.4f}")
                print(f"Tags: {row['edit_tags']}")
                print(f"Quality: {row['quality_score']}")
                print(f"Created: {row['created_at']}")
                print(f"Reviewed: {row['review_completed_at']}")
                print("-" * 50)
        
        # Check for pending reviews
        pending_query = """
        SELECT COUNT(*) as count 
        FROM interactions 
        WHERE review_status = 'pending'
        """
        
        pending_count = await conn.fetchval(pending_query)
        print(f"\n📋 Pending reviews: {pending_count}")
        
        # Check for approved reviews today
        approved_query = """
        SELECT COUNT(*) as count 
        FROM interactions 
        WHERE review_status = 'approved' 
        AND DATE(review_completed_at) = CURRENT_DATE
        """
        
        approved_count = await conn.fetchval(approved_query)
        print(f"✅ Approved today: {approved_count}")
        
        # Check CTA insertions
        cta_query = """
        SELECT COUNT(*) as count 
        FROM interactions 
        WHERE cta_data IS NOT NULL
        AND DATE(created_at) = CURRENT_DATE
        """
        
        cta_count = await conn.fetchval(cta_query)
        print(f"🎯 CTAs inserted today: {cta_count}")
        
        # Check multi-LLM tracking
        llm_query = """
        SELECT 
            llm1_model, 
            llm2_model,
            COUNT(*) as count,
            AVG(llm1_cost_usd) as avg_llm1_cost,
            AVG(llm2_cost_usd) as avg_llm2_cost
        FROM interactions
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        GROUP BY llm1_model, llm2_model
        """
        
        llm_stats = await conn.fetch(llm_query)
        print(f"\n🤖 Multi-LLM Usage (last 24h):")
        for stat in llm_stats:
            print(f"  {stat['llm1_model']} → {stat['llm2_model']}: "
                  f"{stat['count']} messages, "
                  f"avg cost ${(stat['avg_llm1_cost'] or 0) + (stat['avg_llm2_cost'] or 0):.4f}")
        
        # Close connection
        await conn.close()
        print("\n✅ Database verification complete")
        
    except Exception as e:
        print(f"\n❌ Error verifying database: {e}")
        print("\nPossible issues:")
        print("1. Database connection string incorrect")
        print("2. Database not initialized")
        print("3. Missing migrations")
        print("\nCheck DATABASE_URL in .env file")

async def check_database_structure():
    """Verify database tables and columns exist."""
    database_url = os.getenv("DATABASE_URL", "postgresql://localhost/nadia_hitl")
    
    try:
        conn = await asyncpg.connect(database_url)
        
        # Check if interactions table exists
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'interactions'
            )
        """)
        
        if not table_exists:
            print("❌ 'interactions' table does not exist!")
            print("Run: psql -d nadia_hitl -f DATABASE_SCHEMA.sql")
        else:
            print("✅ 'interactions' table exists")
            
            # Check for important columns
            columns_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'interactions'
            """
            
            columns = await conn.fetch(columns_query)
            column_names = [col['column_name'] for col in columns]
            
            required_columns = [
                'llm1_model', 'llm2_model', 'llm1_cost_usd', 'llm2_cost_usd',
                'constitution_risk_score', 'constitution_flags', 'constitution_recommendation',
                'final_bubbles', 'edit_tags', 'quality_score', 'cta_data'
            ]
            
            missing = [col for col in required_columns if col not in column_names]
            if missing:
                print(f"⚠️  Missing columns: {missing}")
                print("Run migrations:")
                print("  psql -d nadia_hitl -f database/migrations/add_llm_tracking.sql")
                print("  psql -d nadia_hitl -f database/migrations/add_cta_support.sql")
            else:
                print("✅ All required columns present")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error checking database structure: {e}")

if __name__ == "__main__":
    print("🔍 Verifying NADIA database saving functionality...\n")
    asyncio.run(check_database_structure())
    print("\n" + "="*60 + "\n")
    asyncio.run(verify_database_saving())