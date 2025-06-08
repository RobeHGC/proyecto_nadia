#!/usr/bin/env python3
# generate_manifest.py
# Recorre un directorio y genera un manifest JSON con la estructura de un proyecto Python,
# ignorando específicamente el archivo "estructura.py".

import argparse
import ast
import json
import os
from typing import Any, Dict


def parse_python_file(path: str) -> Dict[str, Any]:
    """Parsea un archivo .py y extrae estructura de clases y funciones."""
    with open(path, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source)
    module_doc = ast.get_docstring(tree)

    classes = []
    functions = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [
                {
                    'name': m.name,
                    'args': [arg.arg for arg in m.args.args],
                    'docstring': ast.get_docstring(m)
                }
                for m in node.body if isinstance(m, ast.FunctionDef)
            ]
            classes.append({
                'name': node.name,
                'docstring': ast.get_docstring(node),
                'methods': methods
            })
        elif isinstance(node, ast.FunctionDef):
            functions.append({
                'name': node.name,
                'args': [arg.arg for arg in node.args.args],
                'docstring': ast.get_docstring(node)
            })

    return {
        'path': os.path.relpath(path),
        'docstring': module_doc,
        'classes': classes,
        'functions': functions
    }


def generate_manifest(root_dir: str) -> Dict[str, Any]:
    """Recorre root_dir y construye el manifest con todos los .py, ignorando estructura.py."""
    manifest = {'modules': []}
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            # Ignorar archivo estructura.py
            if fn == 'estructura.py':
                continue
            if fn.endswith('.py'):
                full_path = os.path.join(dirpath, fn)
                try:
                    info = parse_python_file(full_path)
                    manifest['modules'].append(info)
                except Exception as e:
                    print(f'⚠️ Error al parsear {full_path}: {e}')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Genera un manifest JSON con la estructura de un proyecto Python, ignorando estructura.py'
    )
    parser.add_argument(
        'project_path',
        help='Ruta al directorio raíz de tu proyecto'
    )
    parser.add_argument(
        '-o', '--output',
        default='manifest.json',
        help='Fichero de salida (por defecto: manifest.json)'
    )
    args = parser.parse_args()

    manifest = generate_manifest(args.project_path)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f'Manifest generado en {args.output} ({len(manifest["modules"])} módulos).')
