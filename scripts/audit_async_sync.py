#!/usr/bin/env python3
"""
Auditoría de código async/sync para detectar mezclas peligrosas.
Busca patrones problemáticos que pueden causar deadlocks o bloqueos.
"""
import ast
import os
from pathlib import Path
from typing import List, Tuple

class AsyncSyncAuditor(ast.NodeVisitor):
    """Analiza código Python para detectar mezclas async/sync problemáticas."""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.issues = []
        self.current_function = None
        self.is_async_function = False
        
    def visit_AsyncFunctionDef(self, node):
        """Visita funciones async."""
        self.current_function = node.name
        self.is_async_function = True
        self.generic_visit(node)
        self.is_async_function = False
        self.current_function = None
        
    def visit_FunctionDef(self, node):
        """Visita funciones sync."""
        self.current_function = node.name
        self.is_async_function = False
        self.generic_visit(node)
        self.current_function = None
        
    def visit_Call(self, node):
        """Detecta llamadas problemáticas."""
        if self.is_async_function:
            # Detectar time.sleep en función async
            if (isinstance(node.func, ast.Attribute) and 
                isinstance(node.func.value, ast.Name) and
                node.func.value.id == 'time' and 
                node.func.attr == 'sleep'):
                self.issues.append({
                    'file': self.filename,
                    'function': self.current_function,
                    'line': node.lineno,
                    'issue': 'time.sleep() en función async - usar await asyncio.sleep()',
                    'severity': 'HIGH'
                })
                
            # Detectar requests en función async
            if (isinstance(node.func, ast.Attribute) and
                isinstance(node.func.value, ast.Name) and
                node.func.value.id == 'requests'):
                self.issues.append({
                    'file': self.filename,
                    'function': self.current_function,
                    'line': node.lineno,
                    'issue': 'requests en función async - usar aiohttp o httpx',
                    'severity': 'HIGH'
                })
                
            # Detectar open() sin async
            if isinstance(node.func, ast.Name) and node.func.id == 'open':
                self.issues.append({
                    'file': self.filename,
                    'function': self.current_function,
                    'line': node.lineno,
                    'issue': 'open() en función async - considerar aiofiles',
                    'severity': 'MEDIUM'
                })
                
        # Detectar llamadas async sin await
        if hasattr(node.func, 'attr'):
            suspicious_async_methods = [
                'create_task', 'gather', 'wait', 'shield',
                'execute', 'fetch', 'fetchone', 'fetchall',  # DB
                'get', 'set', 'delete', 'lpush', 'rpop',     # Redis
                'generate_response', 'process_message'         # Custom
            ]
            if node.func.attr in suspicious_async_methods:
                # Verificar si está dentro de un await
                parent = getattr(node, 'parent', None)
                if not isinstance(parent, ast.Await):
                    self.issues.append({
                        'file': self.filename,
                        'function': self.current_function,
                        'line': node.lineno,
                        'issue': f'{node.func.attr}() probablemente necesita await',
                        'severity': 'HIGH'
                    })
                    
        self.generic_visit(node)

def check_dangerous_patterns(file_path: str) -> List[dict]:
    """Busca patrones peligrosos en el archivo."""
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Patrones regex peligrosos
        dangerous_patterns = [
            (r'def\s+\w+.*:\s*\n.*await\s+', 'Función sync con await'),
            (r'async\s+def.*\n.*(?<!await\s)asyncio\.run', 'asyncio.run() dentro de async'),
            (r'async\s+def.*\n.*threading\.|Thread\(', 'Threading en código async'),
            (r'\.result\(\)', 'Uso de .result() puede bloquear'),
            (r'asyncio\.get_event_loop\(\)\.run_until_complete', 'run_until_complete puede bloquear'),
        ]
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            # Buscar imports problemáticos
            if 'from threading import' in line or 'import threading' in line:
                if 'async' in content:
                    issues.append({
                        'file': file_path,
                        'line': i + 1,
                        'issue': 'Threading importado en código async',
                        'severity': 'MEDIUM'
                    })
                    
    except Exception as e:
        print(f"Error analizando {file_path}: {e}")
        
    return issues

def audit_project(root_dir: str) -> Tuple[List[dict], dict]:
    """Audita todo el proyecto."""
    all_issues = []
    stats = {
        'total_files': 0,
        'async_files': 0,
        'sync_files': 0,
        'mixed_files': 0
    }
    
    for file_path in Path(root_dir).rglob('*.py'):
        if any(skip in str(file_path) for skip in ['__pycache__', '.git', 'venv']):
            continue
            
        stats['total_files'] += 1
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Analizar AST
            tree = ast.parse(content)
            
            # Agregar referencias parent para mejor análisis
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    child.parent = node
                    
            auditor = AsyncSyncAuditor(str(file_path))
            auditor.visit(tree)
            all_issues.extend(auditor.issues)
            
            # Clasificar archivo
            has_async = 'async def' in content
            has_sync_io = any(pattern in content for pattern in [
                'time.sleep', 'requests.', 'open('
            ])
            
            if has_async and not has_sync_io:
                stats['async_files'] += 1
            elif not has_async:
                stats['sync_files'] += 1
            else:
                stats['mixed_files'] += 1
                
            # Buscar patrones peligrosos
            pattern_issues = check_dangerous_patterns(str(file_path))
            all_issues.extend(pattern_issues)
            
        except Exception as e:
            print(f"Error procesando {file_path}: {e}")
            
    return all_issues, stats

def main():
    """Ejecuta la auditoría."""
    print("🔍 Auditando código async/sync...")
    print("=" * 60)
    
    root_dir = Path(__file__).parent.parent
    issues, stats = audit_project(str(root_dir))
    
    # Mostrar estadísticas
    print(f"\n📊 Estadísticas:")
    print(f"  Total archivos: {stats['total_files']}")
    print(f"  Archivos async puros: {stats['async_files']}")
    print(f"  Archivos sync puros: {stats['sync_files']}")
    print(f"  Archivos mixtos: {stats['mixed_files']}")
    
    if not issues:
        print("\n✅ No se encontraron problemas async/sync!")
        return
        
    # Agrupar por severidad
    high_severity = [i for i in issues if i.get('severity') == 'HIGH']
    medium_severity = [i for i in issues if i.get('severity') == 'MEDIUM']
    
    if high_severity:
        print(f"\n🚨 Problemas CRÍTICOS encontrados: {len(high_severity)}")
        for issue in high_severity[:10]:  # Mostrar primeros 10
            print(f"\n  📍 {issue['file']}:{issue.get('line', '?')}")
            print(f"     Función: {issue.get('function', 'N/A')}")
            print(f"     Problema: {issue['issue']}")
            
    if medium_severity:
        print(f"\n⚠️  Problemas MEDIOS encontrados: {len(medium_severity)}")
        for issue in medium_severity[:5]:  # Mostrar primeros 5
            print(f"\n  📍 {issue['file']}:{issue.get('line', '?')}")
            print(f"     Problema: {issue['issue']}")
            
    # Generar reporte completo
    report_file = 'async_sync_audit_report.txt'
    with open(report_file, 'w') as f:
        f.write("REPORTE DE AUDITORÍA ASYNC/SYNC\n")
        f.write("=" * 60 + "\n\n")
        
        for issue in sorted(issues, key=lambda x: (x['severity'], x['file'])):
            f.write(f"[{issue['severity']}] {issue['file']}:{issue.get('line', '?')}\n")
            f.write(f"  Función: {issue.get('function', 'N/A')}\n")
            f.write(f"  Problema: {issue['issue']}\n\n")
            
    print(f"\n📄 Reporte completo guardado en: {report_file}")
    
    # Recomendaciones
    if issues:
        print("\n💡 Recomendaciones:")
        print("  1. Reemplazar time.sleep() con await asyncio.sleep()")
        print("  2. Usar aiohttp/httpx en lugar de requests")
        print("  3. Verificar que todas las llamadas async tengan await")
        print("  4. Considerar aiofiles para operaciones de archivo en async")

if __name__ == "__main__":
    main()
