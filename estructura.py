#!/usr/bin/env python3
# genera_estructura.py
# Recorre un directorio y escribe su árbol de archivos y carpetas en un .txt,
# excluyendo carpetas especificadas.

import argparse
import os
from typing import Set


def write_tree(dir_path: str,
               output_file: str,
               ignore_dirs: Set[str]) -> None:
    """
    Recorre recursivamente dir_path y escribe la estructura
    de carpetas y archivos en output_file, saltando las carpetas en ignore_dirs.
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        for root, dirs, files in os.walk(dir_path):
            # Filtra en-lugar para que os.walk no entre en esas carpetas
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            # Cálculo de nivel e indentación
            rel = os.path.relpath(root, dir_path)
            level = 0 if rel == '.' else rel.count(os.sep) + 1
            indent = '│   ' * (level - 1) + ('├── ' if level > 0 else '')
            folder_name = os.path.basename(root) or root
            f.write(f"{indent}{folder_name}/\n")

            for i, filename in enumerate(files):
                connector = '└── ' if i == len(files) - 1 else '├── '
                subindent = '│   ' * level + connector
                f.write(f"{subindent}{filename}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Genera un txt con la estructura de un directorio."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Ruta al directorio (por defecto: directorio actual)."
    )
    parser.add_argument(
        "-o", "--output",
        default="estructura.txt",
        help="Nombre del archivo de salida (por defecto: estructura.txt)."
    )
    parser.add_argument(
        "-i", "--ignore",
        nargs="*",
        default=[".git", ".github"],
        help="Lista de carpetas a excluir (por defecto: .git, .github)."
    )
    args = parser.parse_args()

    target = os.path.abspath(args.path)
    ignore_set = set(args.ignore)

    write_tree(target, args.output, ignore_set)
    print(f"Estructura de '{args.path}' escrita en '{args.output}' "
          f"(ignorando: {', '.join(ignore_set)})")
