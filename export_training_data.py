#!/usr/bin/env python3
"""Export NADIA training data to CSV for analysis and model training"""

import csv
import json
import psycopg2
from datetime import datetime
import os

DATABASE_URL = "postgresql:///nadia_hitl"

def export_to_csv():
    """Export all training data to CSV files"""
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Main training dataset
        print("📊 Exporting main training dataset...")
        cur.execute("""
            SELECT 
                id,
                user_id,
                conversation_id,
                message_number,
                user_message,
                user_message_timestamp,
                
                -- LLM outputs
                llm1_raw_response,
                array_to_string(llm2_bubbles, ' | ') as llm2_bubbles_joined,
                array_to_string(final_bubbles, ' | ') as final_bubbles_joined,
                
                -- Human feedback
                quality_score,
                array_to_string(edit_tags, ', ') as edit_tags_joined,
                reviewer_notes,
                review_time_seconds,
                
                -- Constitution analysis
                constitution_risk_score,
                array_to_string(constitution_flags, ', ') as constitution_flags_joined,
                constitution_recommendation,
                
                -- Costs and models
                llm1_tokens_used,
                llm2_tokens_used,
                llm1_cost_usd,
                llm2_cost_usd,
                total_cost_usd,
                
                -- Status and timing
                review_status,
                created_at,
                messages_sent_at
                
            FROM interactions 
            ORDER BY created_at DESC;
        """)
        
        # Write main dataset
        filename = f"nadia_training_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Headers
            writer.writerow([
                'id', 'user_id', 'conversation_id', 'message_number',
                'user_message', 'user_message_timestamp',
                'llm1_raw_response', 'llm2_bubbles', 'final_bubbles_human_edited',
                'quality_score', 'edit_tags', 'reviewer_notes', 'review_time_seconds',
                'constitution_risk_score', 'constitution_flags', 'constitution_recommendation',
                'llm1_tokens', 'llm2_tokens', 'llm1_cost_usd', 'llm2_cost_usd', 'total_cost_usd',
                'review_status', 'created_at', 'messages_sent_at'
            ])
            
            # Data rows
            rows = cur.fetchall()
            for row in rows:
                writer.writerow(row)
        
        print(f"✅ Main dataset exported: {filename} ({len(rows)} rows)")
        
        # Edit patterns analysis
        print("📝 Exporting edit patterns...")
        cur.execute("""
            SELECT edit_tag, frequency, avg_quality, avg_review_time
            FROM edit_pattern_analysis 
            ORDER BY frequency DESC;
        """)
        
        patterns_filename = f"edit_patterns_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(patterns_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['edit_tag', 'frequency', 'avg_quality', 'avg_review_time'])
            
            patterns = cur.fetchall()
            for row in patterns:
                writer.writerow(row)
        
        print(f"✅ Edit patterns exported: {patterns_filename} ({len(patterns)} rows)")
        
        # Conversation-level analysis
        print("💬 Exporting conversation summaries...")
        cur.execute("""
            SELECT 
                conversation_id,
                user_id,
                COUNT(*) as message_count,
                MIN(created_at) as conversation_start,
                MAX(created_at) as conversation_end,
                AVG(quality_score) as avg_quality,
                SUM(total_cost_usd) as total_conversation_cost,
                COUNT(CASE WHEN review_status = 'approved' THEN 1 END) as approved_messages,
                COUNT(CASE WHEN review_status = 'rejected' THEN 1 END) as rejected_messages
            FROM interactions
            GROUP BY conversation_id, user_id
            ORDER BY conversation_start DESC;
        """)
        
        conv_filename = f"conversations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(conv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'conversation_id', 'user_id', 'message_count', 
                'conversation_start', 'conversation_end', 'avg_quality',
                'total_cost_usd', 'approved_messages', 'rejected_messages'
            ])
            
            conversations = cur.fetchall()
            for row in conversations:
                writer.writerow(row)
        
        print(f"✅ Conversations exported: {conv_filename} ({len(conversations)} rows)")
        
        # LLM vs Human comparison dataset
        print("🤖 Exporting LLM vs Human comparisons...")
        cur.execute("""
            SELECT 
                id,
                user_message,
                llm1_raw_response as creative_response,
                array_to_string(llm2_bubbles, ' | ') as refined_response,
                array_to_string(final_bubbles, ' | ') as human_edited_response,
                quality_score,
                CASE 
                    WHEN array_to_string(llm2_bubbles, ' | ') = array_to_string(final_bubbles, ' | ') 
                    THEN 'no_edit' 
                    ELSE 'edited' 
                END as human_edited,
                array_to_string(edit_tags, ', ') as edit_types,
                constitution_risk_score,
                review_time_seconds
            FROM interactions 
            WHERE llm1_raw_response IS NOT NULL 
                AND llm2_bubbles IS NOT NULL 
                AND final_bubbles IS NOT NULL
            ORDER BY created_at DESC;
        """)
        
        comparison_filename = f"llm_human_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(comparison_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'id', 'user_message', 'creative_response', 'refined_response', 
                'human_edited_response', 'quality_score', 'human_edited', 
                'edit_types', 'constitution_risk_score', 'review_time_seconds'
            ])
            
            comparisons = cur.fetchall()
            for row in comparisons:
                writer.writerow(row)
        
        print(f"✅ LLM vs Human comparisons exported: {comparison_filename} ({len(comparisons)} rows)")
        
        cur.close()
        conn.close()
        
        print(f"\n🎯 Export Summary:")
        print(f"   📁 Main training data: {filename}")
        print(f"   📊 Edit patterns: {patterns_filename}")
        print(f"   💬 Conversations: {conv_filename}")
        print(f"   🤖 LLM comparisons: {comparison_filename}")
        print(f"\n✨ All files ready for analysis and model training!")
        
    except Exception as e:
        print(f"❌ Export error: {e}")

def preview_data():
    """Preview some sample data before export"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        print("👀 Data Preview - Latest 3 interactions:")
        print("=" * 80)
        
        cur.execute("""
            SELECT 
                user_message,
                llm1_raw_response,
                array_to_string(llm2_bubbles, ' | ') as llm2,
                array_to_string(final_bubbles, ' | ') as final,
                quality_score,
                array_to_string(edit_tags, ', ') as tags
            FROM interactions 
            WHERE final_bubbles IS NOT NULL
            ORDER BY created_at DESC 
            LIMIT 3;
        """)
        
        results = cur.fetchall()
        for i, (user_msg, llm1, llm2, final, quality, tags) in enumerate(results, 1):
            print(f"\n--- Interaction {i} ---")
            print(f"👤 User: {user_msg[:60]}...")
            print(f"🎨 LLM1: {llm1[:60] if llm1 else 'None'}...")
            print(f"⚡ LLM2: {llm2[:60] if llm2 else 'None'}...")
            print(f"✏️  Final: {final[:60] if final else 'None'}...")
            print(f"⭐ Quality: {quality}/5")
            print(f"🏷️  Tags: {tags if tags else 'None'}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Preview error: {e}")

if __name__ == "__main__":
    print("🗂️  NADIA Training Data Exporter")
    print("=" * 40)
    
    # Preview first
    preview_data()
    
    # Auto export
    print("\n📤 Exporting all data to CSV files...")
    export_to_csv()