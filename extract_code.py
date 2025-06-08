#!/usr/bin/env python3
import argparse
import os


def main():
    parser = argparse.ArgumentParser(
        description="Extrae el contenido de todos los .py del proyecto, excluyendo archivos específicos"
    )
    parser.add_argument(
        'root',
        nargs='?',
        default='.',
        help='Directorio raíz del proyecto (por defecto: .)'
    )
    parser.add_argument(
        '-o', '--output',
        default='all_code.txt',
        help='Fichero donde volcar todo el código (por defecto: all_code.txt)'
    )
    parser.add_argument(
        '-e', '--exclude',
        nargs='*',
        default=['estructura.py', 'generate_manifest.py', os.path.basename(__file__)],
        help='Lista de archivos a excluir'
    )
    args = parser.parse_args()

    excl = set(args.exclude)
    with open(args.output, 'w', encoding='utf-8') as out:
        for dirpath, _, files in os.walk(args.root):
            for fn in files:
                if not fn.endswith('.py') or fn in excl:
                    continue
                path = os.path.join(dirpath, fn)
                out.write(f"# ==== {path} ====\n\n")
                with open(path, 'r', encoding='utf-8') as f:
                    out.write(f.read())
                    out.write("\n\n")
    print(f"Código extraído en {args.output} ({len(excl)} archivos excluidos)")

if __name__ == '__main__':
    main()
