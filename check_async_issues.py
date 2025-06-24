#!/usr/bin/env python3
import ast
import os

def find_async_issues(directory='.'):
    """Busca problemas de async/await en el código."""
    issues = []
    
    for root, dirs, files in os.walk(directory):
        # Skip some directories
        if any(skip in root for skip in ['.git', '__pycache__', 'venv', '.pytest_cache']):
            continue
            
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r') as f:
                        content = f.read()
                        
                    # Quick checks for common issues
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        # Check for Redis operations without await (more specific patterns)
                        stripped = line.strip()
                        
                        # Skip comments and empty lines
                        if stripped.startswith('#') or not stripped:
                            continue
                            
                        # Look for Redis-specific patterns (more precise)
                        redis_patterns = [
                            'r.get(', 'r.set(', 'r.delete(', 'r.lpush(', 'r.rpush(',
                            'r.hget(', 'r.hset(', 'r.zadd(', 'r.zrem(', 'r.llen(',
                            'r.zcard(', 'r.keys(', 'r.ttl(', 'r.ping(', 'r.brpop(',
                            'r.scan_iter(', 'r.aclose(', 'r.close('
                        ]
                        
                        # Check if line contains redis pattern
                        has_redis = any(pattern in stripped for pattern in redis_patterns)
                        
                        # Exclude false positives
                        is_excluded = any(word in stripped for word in [
                            'logger.', 'print(', 'f"', "f'",  # logging/printing
                            'async for', 'scan_iter',  # async iterators are OK without await
                            '"', "'",  # string literals
                            '#',  # comments
                            '.close()',  # database close operations
                            'cur.close'  # cursor close
                        ])
                        
                        if has_redis and not is_excluded:
                            if 'await' not in stripped:
                                issues.append(f"{filepath}:{i+1} - Missing await on Redis operation: {stripped}")
                                
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    
    return issues

if __name__ == "__main__":
    print("🔍 Buscando problemas de async/await...\n")
    
    issues = find_async_issues()
    
    if issues:
        print(f"❌ Encontrados {len(issues)} problemas potenciales:\n")
        for issue in issues[:20]:  # Show first 20
            print(f"  {issue}")
        if len(issues) > 20:
            print(f"\n  ... y {len(issues) - 20} más")
    else:
        print("✅ No se encontraron problemas obvios de async/await")