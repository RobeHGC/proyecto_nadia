#!/usr/bin/env python3
"""
Standalone verification script for multi-LLM system.
Quick verification that the multi-LLM pipeline is working correctly.
"""
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents.supervisor_agent import SupervisorAgent
from llms.openai_client import OpenAIClient
from llms.quota_manager import GeminiQuotaManager
from memory.user_memory import UserMemoryManager
from utils.config import Config
import redis

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MultiLLMVerifier:
    """Verifies multi-LLM system functionality."""
    
    def __init__(self):
        self.config = Config.from_env()
        self.redis_client = None
        self.supervisor = None
        self.quota_manager = None
        
    async def setup(self):
        """Initialize components."""
        try:
            # Setup Redis
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            
            # Test Redis connection
            self.redis_client.ping()
            logger.info("✓ Redis connection established")
            
            # Setup memory manager
            memory_manager = UserMemoryManager(redis_url)
            
            # Setup supervisor (with legacy compatibility)
            mock_llm = OpenAIClient("dummy-key", "gpt-3.5-turbo")
            self.supervisor = SupervisorAgent(mock_llm, memory_manager, self.config)
            
            # Setup quota manager
            self.quota_manager = GeminiQuotaManager(redis_url)
            
            logger.info("✓ All components initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Setup failed: {e}")
            return False
    
    async def verify_configuration(self):
        """Verify configuration is correct."""
        logger.info("\n🔧 CONFIGURATION VERIFICATION")
        logger.info("=" * 50)
        
        # Check required API keys
        openai_key = os.getenv('OPENAI_API_KEY')
        gemini_key = os.getenv('GEMINI_API_KEY')
        
        if not openai_key:
            logger.error("❌ OPENAI_API_KEY not found")
            return False
        else:
            logger.info(f"✓ OpenAI API key configured (ends with: ...{openai_key[-4:]})")
            
        if not gemini_key:
            logger.error("❌ GEMINI_API_KEY not found")
            return False
        else:
            logger.info(f"✓ Gemini API key configured (ends with: ...{gemini_key[-4:]})")
        
        # Check LLM configuration
        logger.info(f"✓ LLM1 Provider: {self.config.llm1_provider}")
        logger.info(f"✓ LLM1 Model: {self.config.llm1_model}")
        logger.info(f"✓ LLM2 Provider: {self.config.llm2_provider}")
        logger.info(f"✓ LLM2 Model: {self.config.llm2_model}")
        
        return True
    
    async def verify_quota_manager(self):
        """Verify quota manager functionality."""
        logger.info("\n📊 QUOTA MANAGER VERIFICATION")
        logger.info("=" * 50)
        
        test_user = "verify_test_user"
        
        try:
            # Reset quota for clean test
            await self.quota_manager.reset_daily()
            
            # Check initial state
            daily_usage = await self.quota_manager.get_daily_usage()
            minute_usage = await self.quota_manager.get_minute_usage()
            
            logger.info(f"✓ Initial daily usage: {daily_usage} tokens")
            logger.info(f"✓ Initial minute usage: {minute_usage} tokens")
            
            # Test quota check
            can_use = await self.quota_manager.can_use_free_tier()
            logger.info(f"✓ Can use free tier: {can_use}")
            
            # Record usage
            test_tokens = 1000
            await self.quota_manager.record_usage(test_tokens)
            daily_after = await self.quota_manager.get_daily_usage()
            logger.info(f"✓ Daily usage after recording: {daily_after} tokens")
            
            # Get quota status
            status = await self.quota_manager.get_quota_status()
            logger.info(f"✓ Daily limit: {status['daily_limit']:,} tokens")
            logger.info(f"✓ Minute limit: {status['minute_limit']:,} tokens")
            logger.info(f"✓ Can use free tier: {status['can_use_free_tier']}")
            
            # Cleanup
            await self.quota_manager.reset_daily()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Quota manager verification failed: {e}")
            return False
    
    async def verify_llm_clients(self):
        """Verify individual LLM clients work."""
        logger.info("\n🤖 LLM CLIENTS VERIFICATION")
        logger.info("=" * 50)
        
        try:
            # Test LLM1 (usually Gemini)
            llm1 = self.supervisor.llm1
            logger.info(f"✓ LLM1 client type: {type(llm1).__name__}")
            logger.info(f"✓ LLM1 model: {llm1.get_model_name()}")
            
            # Test LLM2 (usually GPT)
            llm2 = self.supervisor.llm2
            logger.info(f"✓ LLM2 client type: {type(llm2).__name__}")
            logger.info(f"✓ LLM2 model: {llm2.get_model_name()}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ LLM client verification failed: {e}")
            return False
    
    async def verify_end_to_end(self):
        """Verify complete end-to-end processing."""
        logger.info("\n🚀 END-TO-END VERIFICATION")
        logger.info("=" * 50)
        
        test_user = "verify_e2e_user"
        test_messages = [
            "Hi! My name is TestUser and I'm verifying the system.",
            "What's your favorite color?",
            "Tell me about yourself!"
        ]
        
        total_cost = 0
        total_tokens = 0
        
        try:
            for i, message in enumerate(test_messages, 1):
                logger.info(f"\n--- Processing Message {i}/3 ---")
                logger.info(f"Input: {message}")
                
                start_time = time.time()
                
                # Process through multi-LLM pipeline
                review_item = await self.supervisor.process_message(test_user, message)
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                # Extract results
                ai_response = review_item.ai_suggestion
                
                # Display results
                logger.info(f"✓ Processing time: {processing_time:.2f}s")
                logger.info(f"✓ LLM1 model used: {ai_response.llm1_model}")
                logger.info(f"✓ LLM2 model used: {ai_response.llm2_model}")
                logger.info(f"✓ LLM1 cost: ${ai_response.llm1_cost:.6f}")
                logger.info(f"✓ LLM2 cost: ${ai_response.llm2_cost:.6f}")
                logger.info(f"✓ Total tokens: {ai_response.tokens_used}")
                logger.info(f"✓ Bubbles generated: {len(ai_response.llm2_bubbles)}")
                logger.info(f"✓ Constitution risk: {ai_response.constitution_analysis.risk_score:.3f}")
                
                # Show sample bubbles
                for j, bubble in enumerate(ai_response.llm2_bubbles[:2], 1):
                    logger.info(f"   Bubble {j}: {bubble[:100]}{'...' if len(bubble) > 100 else ''}")
                
                # Accumulate metrics
                total_cost += ai_response.llm1_cost + ai_response.llm2_cost
                total_tokens += ai_response.tokens_used
                
                # Small delay between messages
                await asyncio.sleep(1)
            
            # Summary
            logger.info(f"\n🎯 VERIFICATION SUMMARY")
            logger.info("=" * 50)
            logger.info(f"✓ Total messages processed: {len(test_messages)}")
            logger.info(f"✓ Total cost: ${total_cost:.6f}")
            logger.info(f"✓ Total tokens: {total_tokens:,}")
            logger.info(f"✓ Average cost per message: ${total_cost/len(test_messages):.6f}")
            
            # Cleanup test user memory
            if self.redis_client:
                self.redis_client.delete(f"user_memory:{test_user}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ End-to-end verification failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def verify_cost_optimization(self):
        """Show cost optimization analysis."""
        logger.info("\n💰 COST OPTIMIZATION ANALYSIS")
        logger.info("=" * 50)
        
        # Approximate costs (per 1K tokens)
        gemini_cost_per_1k = 0.0  # Free tier
        gpt4o_mini_cost_per_1k = 0.00015  # $0.15 per 1M tokens
        gpt4_cost_per_1k = 0.03  # $30 per 1M tokens
        
        # Simulate daily usage
        daily_messages = 100
        avg_tokens_per_message = 500
        daily_tokens = daily_messages * avg_tokens_per_message
        
        # Current multi-LLM cost (assuming 70% Gemini free + 30% GPT-4o-mini)
        gemini_portion = 0.7
        gpt_portion = 0.3
        
        current_cost = (gemini_portion * daily_tokens * gemini_cost_per_1k / 1000) + \
                      (gpt_portion * daily_tokens * gpt4o_mini_cost_per_1k / 1000)
        
        # Alternative: All GPT-4o-mini
        gpt4o_mini_only_cost = daily_tokens * gpt4o_mini_cost_per_1k / 1000
        
        # Alternative: All GPT-4
        gpt4_only_cost = daily_tokens * gpt4_cost_per_1k / 1000
        
        logger.info(f"Daily usage simulation: {daily_messages} messages, {daily_tokens:,} tokens")
        logger.info(f"✓ Current multi-LLM cost: ${current_cost:.4f}/day")
        logger.info(f"✓ GPT-4o-mini only cost: ${gpt4o_mini_only_cost:.4f}/day")
        logger.info(f"✓ GPT-4 only cost: ${gpt4_only_cost:.4f}/day")
        
        savings_vs_mini = gpt4o_mini_only_cost - current_cost
        savings_vs_gpt4 = gpt4_only_cost - current_cost
        
        logger.info(f"💰 Daily savings vs GPT-4o-mini: ${savings_vs_mini:.4f}")
        logger.info(f"💰 Daily savings vs GPT-4: ${savings_vs_gpt4:.4f}")
        logger.info(f"💰 Monthly savings vs GPT-4: ${savings_vs_gpt4 * 30:.2f}")
        
        return True
    
    async def run_verification(self):
        """Run complete verification suite."""
        logger.info("🔍 MULTI-LLM SYSTEM VERIFICATION")
        logger.info("=" * 60)
        logger.info("This script verifies the multi-LLM system is working correctly.")
        logger.info("=" * 60)
        
        # Setup
        if not await self.setup():
            return False
        
        # Run verification steps
        steps = [
            ("Configuration", self.verify_configuration),
            ("Quota Manager", self.verify_quota_manager),
            ("LLM Clients", self.verify_llm_clients),
            ("End-to-End Processing", self.verify_end_to_end),
            ("Cost Optimization", self.verify_cost_optimization)
        ]
        
        results = []
        for step_name, step_func in steps:
            try:
                result = await step_func()
                results.append((step_name, result))
                if result:
                    logger.info(f"\n✅ {step_name}: PASSED")
                else:
                    logger.error(f"\n❌ {step_name}: FAILED")
            except Exception as e:
                logger.error(f"\n❌ {step_name}: ERROR - {e}")
                results.append((step_name, False))
        
        # Final summary
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"VERIFICATION COMPLETE: {passed}/{total} steps passed")
        logger.info(f"{'='*60}")
        
        if passed == total:
            logger.info("🎉 All verifications PASSED! Multi-LLM system is ready.")
            return True
        else:
            logger.error(f"⚠️  {total - passed} verification(s) FAILED. Check logs above.")
            return False
    
    def cleanup(self):
        """Cleanup resources."""
        if self.redis_client:
            self.redis_client.close()

async def main():
    """Main function."""
    verifier = MultiLLMVerifier()
    
    try:
        success = await verifier.run_verification()
        return 0 if success else 1
    
    except KeyboardInterrupt:
        logger.info("\n⏹️  Verification interrupted by user")
        return 1
    
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        verifier.cleanup()

if __name__ == "__main__":
    # Run the verification
    exit_code = asyncio.run(main())
    sys.exit(exit_code)