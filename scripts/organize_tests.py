#!/usr/bin/env python3
"""Script to organize tests into unit/integration/e2e categories."""

import os
import shutil
from pathlib import Path

# Define test categorization
TEST_CATEGORIES = {
    'unit': [
        'test_supervisor_core.py',
        'test_memory_core.py', 
        'test_protocol_manager_unit.py',
        'test_cognitive_controller.py',
        'test_constitution.py',
        'test_greet.py',
        'test_redis_connection.py',
        'test_recovery_agent.py',
        'test_intermediary_agent.py',
        'test_post_llm2_agent.py'
    ],
    'integration': [
        'test_coherence_integration.py',
        'test_protocol_api_integration.py',
        'test_protocol_manager.py',
        'test_protocol_manager_simple.py',
        'test_multi_llm_integration.py',
        'test_hitl_api.py',
        'test_hitl_database.py',
        'test_hitl_supervisor.py',
        'test_hitl_constitution.py',
        'test_gdpr_api.py',
        'test_nadia_personality_gemini.py',
        'test_wal_integration.py'
    ],
    'e2e': [
        'automated_e2e_tester.py',
        'visual_test_monitor.py'
    ]
}

def organize_tests(dry_run=True):
    """Organize test files into categories."""
    test_dir = Path('tests')
    
    # Create subdirectories
    for category in TEST_CATEGORIES:
        category_dir = test_dir / category
        if not dry_run:
            category_dir.mkdir(exist_ok=True)
        else:
            print(f"Would create: {category_dir}")
    
    # Move files
    for category, files in TEST_CATEGORIES.items():
        for filename in files:
            src = test_dir / filename
            dst = test_dir / category / filename
            
            if src.exists():
                if not dry_run:
                    shutil.move(str(src), str(dst))
                    print(f"Moved: {filename} -> {category}/{filename}")
                else:
                    print(f"Would move: {filename} -> {category}/{filename}")
            else:
                print(f"Warning: {filename} not found")
    
    # Update imports in moved files
    if not dry_run:
        update_imports()

def update_imports():
    """Update relative imports in test files after reorganization."""
    test_dir = Path('tests')
    
    for category in TEST_CATEGORIES:
        category_dir = test_dir / category
        if category_dir.exists():
            for test_file in category_dir.glob('test_*.py'):
                content = test_file.read_text()
                
                # Update conftest imports
                content = content.replace(
                    'from conftest import',
                    'from ..conftest import'
                )
                content = content.replace(
                    'import conftest',
                    'from .. import conftest'
                )
                
                test_file.write_text(content)
                print(f"Updated imports in: {test_file}")

def add_markers_to_tests():
    """Add pytest markers to test files based on category."""
    test_dir = Path('tests')
    
    marker_mapping = {
        'unit': '@pytest.mark.unit',
        'integration': '@pytest.mark.integration', 
        'e2e': '@pytest.mark.e2e'
    }
    
    for category, marker in marker_mapping.items():
        category_dir = test_dir / category
        if category_dir.exists():
            for test_file in category_dir.glob('test_*.py'):
                content = test_file.read_text()
                
                # Check if marker already exists
                if marker not in content:
                    lines = content.split('\n')
                    
                    # Find the first test class or function
                    for i, line in enumerate(lines):
                        if line.startswith('class Test') or line.startswith('def test_'):
                            # Insert marker before the test
                            lines.insert(i, marker)
                            break
                    
                    test_file.write_text('\n'.join(lines))
                    print(f"Added {marker} to: {test_file}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Organize test files into categories')
    parser.add_argument('--execute', action='store_true', 
                       help='Actually move files (default is dry run)')
    parser.add_argument('--add-markers', action='store_true',
                       help='Add pytest markers to test files')
    
    args = parser.parse_args()
    
    if args.execute:
        print("Organizing tests...")
        organize_tests(dry_run=False)
        
        if args.add_markers:
            print("\nAdding markers...")
            add_markers_to_tests()
    else:
        print("DRY RUN - No files will be moved")
        organize_tests(dry_run=True)
        print("\nTo execute, run with --execute flag")