#!/usr/bin/env python3
"""Configuration script for switching between OpenAI and local embeddings."""
import asyncio
import os
import sys
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def update_env_file(use_local: bool = True):
    """Update .env file with embeddings configuration."""
    env_file = ".env"
    env_config = {}
    
    # Read existing .env file if it exists
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_config[key.strip()] = value.strip()
    
    # Update embeddings configuration
    if use_local:
        env_config['USE_LOCAL_EMBEDDINGS'] = 'true'
        env_config['LOCAL_EMBEDDINGS_MODEL'] = 'sentence-transformers/all-MiniLM-L6-v2'
        print("✅ Configured for local embeddings")
        
        # Make OpenAI API key optional
        if 'OPENAI_API_KEY' not in env_config:
            env_config['# OPENAI_API_KEY'] = 'sk-your-key-here  # Optional for local embeddings'
    else:
        env_config['USE_LOCAL_EMBEDDINGS'] = 'false'
        print("✅ Configured for OpenAI embeddings")
        
        # Ensure OpenAI API key is set
        if 'OPENAI_API_KEY' not in env_config:
            print("⚠️  Warning: OPENAI_API_KEY not found in .env file")
    
    # Write updated .env file
    with open(env_file, 'w') as f:
        f.write("# NADIA Environment Configuration\n")
        f.write("# Updated by configure_embeddings.py\n\n")
        
        # Core settings first
        core_keys = ['API_ID', 'API_HASH', 'PHONE_NUMBER', 'DATABASE_URL', 'DASHBOARD_API_KEY']
        for key in core_keys:
            if key in env_config:
                f.write(f"{key}={env_config[key]}\n")
        
        f.write("\n# LLM API Keys\n")
        llm_keys = ['OPENAI_API_KEY', 'GEMINI_API_KEY']
        for key in llm_keys:
            if key in env_config:
                f.write(f"{key}={env_config[key]}\n")
            elif key.startswith('#'):
                f.write(f"{key}={env_config[key]}\n")
        
        f.write("\n# Embeddings Configuration\n")
        emb_keys = ['USE_LOCAL_EMBEDDINGS', 'LOCAL_EMBEDDINGS_MODEL']
        for key in emb_keys:
            if key in env_config:
                f.write(f"{key}={env_config[key]}\n")
        
        # Other settings
        f.write("\n# Other Settings\n")
        for key, value in env_config.items():
            if key not in core_keys + llm_keys + emb_keys and not key.startswith('#'):
                f.write(f"{key}={value}\n")
    
    print(f"📝 Updated {env_file}")


async def test_embeddings():
    """Test embeddings configuration."""
    print("\n🧪 Testing embeddings configuration...")
    
    use_local = os.getenv('USE_LOCAL_EMBEDDINGS', 'false').lower() == 'true'
    
    if use_local:
        try:
            from knowledge.local_embeddings_service import get_local_embeddings_service
            print("✅ Local embeddings service imported successfully")
            
            service = get_local_embeddings_service()
            print(f"✅ Service initialized: {service.model_name}")
            
            # Test embedding generation
            result = await service.get_embedding("test message for embeddings")
            if result:
                print(f"✅ Test embedding generated: {len(result.embedding)} dimensions")
                
                # Get stats
                stats = service.get_cache_stats()
                print(f"📊 Model info: {stats['model']}")
                print(f"📏 Dimensions: {stats['embedding_dimension']}")
                print(f"⚡ Performance: {stats.get('avg_time_per_embedding_ms', 0):.1f}ms avg")
            else:
                print("❌ Failed to generate test embedding")
                
        except ImportError as e:
            print(f"❌ Local embeddings not available: {e}")
            print("💡 Install with: pip install -r requirements-rag.txt")
        except Exception as e:
            print(f"❌ Error testing local embeddings: {e}")
    else:
        try:
            from knowledge.embeddings_service import get_embeddings_service
            print("✅ OpenAI embeddings service imported successfully")
            
            service = get_embeddings_service()
            print(f"✅ Service initialized: {service.model}")
            
            # Test embedding generation
            result = await service.get_embedding("test message for embeddings")
            if result:
                print(f"✅ Test embedding generated: {len(result.embedding)} dimensions")
                
                # Get stats
                stats = service.get_cache_stats()
                print(f"📊 Model info: {stats['model']}")
                print(f"📏 Dimensions: {stats['embedding_dimension']}")
            else:
                print("❌ Failed to generate test embedding")
                
        except Exception as e:
            print(f"❌ Error testing OpenAI embeddings: {e}")
            if "api key" in str(e).lower():
                print("💡 Make sure OPENAI_API_KEY is set in .env file")


async def migrate_to_local():
    """Complete migration to local embeddings."""
    print("🚀 Migrating to local embeddings...")
    
    # Step 1: Install dependencies
    print("\n📦 Installing dependencies...")
    import subprocess
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "sentence-transformers", "torch", "transformers"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Dependencies installed successfully")
        else:
            print(f"⚠️  Warning: {result.stderr}")
    except Exception as e:
        print(f"❌ Failed to install dependencies: {e}")
        print("💡 Please run manually: pip install sentence-transformers torch transformers")
    
    # Step 2: Update configuration
    update_env_file(use_local=True)
    
    # Step 3: Test configuration
    await test_embeddings()
    
    # Step 4: Run benchmark
    print("\n🏁 Running performance benchmark...")
    try:
        from scripts.benchmark_embeddings import EmbeddingsBenchmark
        benchmark = EmbeddingsBenchmark()
        results = await benchmark.run_benchmark()
        print("✅ Benchmark completed - check benchmark_results.json for details")
    except Exception as e:
        print(f"⚠️  Benchmark failed: {e}")
        print("💡 You can run it manually later: python scripts/benchmark_embeddings.py")
    
    print("\n🎉 Migration to local embeddings complete!")
    print("💰 You can now remove the OPENAI_API_KEY from RAG usage")
    print("🚀 RAG system will use your Ryzen 7 5700 for embeddings")


def print_status():
    """Print current embeddings configuration status."""
    print("📊 Current Embeddings Configuration:")
    print("="*50)
    
    use_local = os.getenv('USE_LOCAL_EMBEDDINGS', 'false').lower() == 'true'
    local_model = os.getenv('LOCAL_EMBEDDINGS_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
    openai_key = os.getenv('OPENAI_API_KEY', '')
    
    print(f"Embeddings Type: {'Local' if use_local else 'OpenAI'}")
    if use_local:
        print(f"Local Model: {local_model}")
        print(f"Hardware: AMD Ryzen 7 5700 optimized")
        print(f"Cost: $0 (after setup)")
    else:
        print(f"OpenAI Model: text-embedding-3-small")
        print(f"API Key: {'Set' if openai_key else 'Not set'}")
        print(f"Cost: ~$0.00002 per embedding")
    
    # Check availability
    print("\nAvailability:")
    try:
        from knowledge.local_embeddings_service import LocalEmbeddingsService
        print("✅ Local embeddings: Available")
    except ImportError:
        print("❌ Local embeddings: Not available (install sentence-transformers)")
    
    try:
        from knowledge.embeddings_service import EmbeddingsService
        print("✅ OpenAI embeddings: Available")
    except ImportError:
        print("❌ OpenAI embeddings: Not available")


async def main():
    """Main configuration script."""
    print("🔧 NADIA Embeddings Configuration Tool")
    print("="*50)
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python configure_embeddings.py status       - Show current config")
        print("  python configure_embeddings.py local        - Switch to local embeddings")
        print("  python configure_embeddings.py openai       - Switch to OpenAI embeddings")
        print("  python configure_embeddings.py test         - Test current configuration")
        print("  python configure_embeddings.py migrate      - Full migration to local")
        return
    
    command = sys.argv[1].lower()
    
    if command == "status":
        print_status()
    
    elif command == "local":
        update_env_file(use_local=True)
        print("🎯 Switched to local embeddings")
        print("💡 Run 'python configure_embeddings.py test' to verify")
    
    elif command == "openai":
        update_env_file(use_local=False)
        print("🎯 Switched to OpenAI embeddings")
        print("💡 Make sure OPENAI_API_KEY is set in .env")
    
    elif command == "test":
        await test_embeddings()
    
    elif command == "migrate":
        await migrate_to_local()
    
    else:
        print(f"❌ Unknown command: {command}")


if __name__ == "__main__":
    asyncio.run(main())