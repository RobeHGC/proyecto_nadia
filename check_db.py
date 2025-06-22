#!/usr/bin/env python3
"""Quick database checker for NADIA HITL system"""

import os
import asyncio
import psycopg2
from datetime import datetime

DATABASE_URL = "postgresql:///nadia_hitl"

def check_database():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        print("🗄️  NADIA Database Status")
        print("=" * 40)
        
        # Check tables
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
        tables = cur.fetchall()
        print(f"📊 Tables: {[t[0] for t in tables]}")
        
        # Check interactions count
        cur.execute("SELECT COUNT(*) FROM interactions;")
        total_interactions = cur.fetchone()[0]
        print(f"💬 Total interactions: {total_interactions}")
        
        # Check recent activity
        cur.execute("""
            SELECT review_status, COUNT(*) 
            FROM interactions 
            GROUP BY review_status;
        """)
        status_counts = cur.fetchall()
        print("📈 Status breakdown:")
        for status, count in status_counts:
            print(f"   {status}: {count}")
        
        # Check today's activity
        cur.execute("""
            SELECT COUNT(*) 
            FROM interactions 
            WHERE DATE(created_at) = CURRENT_DATE;
        """)
        today_count = cur.fetchone()[0]
        print(f"📅 Today's interactions: {today_count}")
        
        # Check LLM models used
        cur.execute("""
            SELECT llm1_model, llm2_model, COUNT(*) 
            FROM interactions 
            WHERE llm1_model IS NOT NULL 
            GROUP BY llm1_model, llm2_model 
            ORDER BY COUNT(*) DESC 
            LIMIT 5;
        """)
        model_usage = cur.fetchall()
        print("🤖 Top LLM combinations:")
        for llm1, llm2, count in model_usage:
            print(f"   {llm1} → {llm2}: {count}")
        
        # Check quality scores
        cur.execute("""
            SELECT AVG(quality_score), MIN(quality_score), MAX(quality_score)
            FROM interactions 
            WHERE quality_score IS NOT NULL;
        """)
        quality_stats = cur.fetchone()
        if quality_stats[0]:
            print(f"⭐ Quality scores - Avg: {quality_stats[0]:.2f}, Min: {quality_stats[1]}, Max: {quality_stats[2]}")
        
        # Check training data completeness
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(llm1_raw_response) as has_llm1,
                COUNT(llm2_bubbles) as has_llm2, 
                COUNT(final_bubbles) as has_final,
                COUNT(edit_tags) as has_edits,
                COUNT(quality_score) as has_quality
            FROM interactions;
        """)
        training_data = cur.fetchone()
        print("\n🎯 Training Data Completeness:")
        print(f"   Total interactions: {training_data[0]}")
        print(f"   With LLM1 data: {training_data[1]}")
        print(f"   With LLM2 data: {training_data[2]}")
        print(f"   With human edits: {training_data[3]}")
        print(f"   With edit tags: {training_data[4]}")
        print(f"   With quality scores: {training_data[5]}")
        
        # Show edit patterns
        cur.execute("""
            SELECT edit_tag, frequency, avg_quality
            FROM edit_pattern_analysis 
            LIMIT 5;
        """)
        edit_patterns = cur.fetchall()
        if edit_patterns:
            print("\n📝 Most Common Edit Patterns:")
            for tag, freq, quality in edit_patterns:
                print(f"   {tag}: {freq} times (avg quality: {quality:.1f})")
        
        # Show customer funnel metrics
        print("\n🎯 Customer Funnel Status:")
        cur.execute("""
            SELECT customer_status, COUNT(*) as count
            FROM interactions 
            WHERE customer_status IS NOT NULL
            GROUP BY customer_status
            ORDER BY 
                CASE customer_status
                    WHEN 'PROSPECT' THEN 1
                    WHEN 'LEAD_QUALIFIED' THEN 2  
                    WHEN 'CUSTOMER' THEN 3
                    WHEN 'CHURNED' THEN 4
                    WHEN 'LEAD_EXHAUSTED' THEN 5
                END;
        """)
        funnel_data = cur.fetchall()
        for status, count in funnel_data:
            print(f"   {status}: {count}")
        
        # Show CTA response patterns
        print("\n📞 CTA Response Patterns:")
        cur.execute("""
            SELECT cta_response_type, COUNT(*) as count
            FROM interactions 
            WHERE cta_response_type IS NOT NULL
            GROUP BY cta_response_type
            ORDER BY count DESC;
        """)
        cta_responses = cur.fetchall()
        if cta_responses:
            for response_type, count in cta_responses:
                print(f"   {response_type}: {count}")
        else:
            print("   No CTA responses recorded yet")
        
        # Show conversion metrics
        cur.execute("""
            SELECT 
                COUNT(DISTINCT user_id) as total_users,
                COUNT(CASE WHEN customer_status = 'CUSTOMER' THEN 1 END) as converted_users,
                SUM(ltv_usd) as total_ltv
            FROM interactions
            WHERE customer_status IS NOT NULL;
        """)
        conversion_data = cur.fetchone()
        if conversion_data[0] > 0:
            conversion_rate = (conversion_data[1] / conversion_data[0]) * 100
            print(f"\n💰 Conversion Metrics:")
            print(f"   Total users: {conversion_data[0]}")
            print(f"   Converted users: {conversion_data[1]}")
            print(f"   Conversion rate: {conversion_rate:.1f}%")
            print(f"   Total LTV: ${conversion_data[2] or 0:.2f}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    check_database()