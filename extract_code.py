#!/usr/bin/env python3
"""
extract_code_from_docx.py
-------------------------
Extrae todos los fragmentos de código Python contenidos en un .docx
(formateados con encabezados tipo 'Archivo:' / 'Ubicación:')
y los escribe en un directorio con la misma jerarquía que el proyecto original.

Uso:
    python extract_code_from_docx.py all_python_code.txt  out_dir

Si tu archivo ya tiene extensión .docx, indícala tal cual.
"""

import argparse
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


NAMESPACES = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def iter_paragraphs(docx_path: Path):
    """Rinde cada párrafo (string) del documento Word sin dependencias externas."""
    with zipfile.ZipFile(docx_path) as z:
        xml_bytes = z.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    for p in root.findall(".//w:p", NAMESPACES):
        # concatena todos los <w:t> de un párrafo
        yield "".join(t.text or "" for t in p.findall(".//w:t", NAMESPACES))


HEADER_RE = re.compile(r"^\s*Archivo:\s*(.+?)\s*$", re.I)
LOCATION_RE = re.compile(r"^\s*Ubicaci[oó]n:", re.I)


def extract_files(docx_path: Path, output_dir: Path):
    current_file = None
    buffer = []

    def flush():
        """Escribe el buffer acumulado al disco y lo limpia."""
        nonlocal current_file, buffer
        if current_file and buffer:
            target = output_dir / current_file
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("\n".join(buffer), encoding="utf-8")
            print(f" [+] {target.relative_to(output_dir)} ({len(buffer)} líns)")
        current_file, buffer = None, []

    for paragraph in iter_paragraphs(docx_path):
        hdr = HEADER_RE.match(paragraph)
        if hdr:                       # ————— nuevo archivo
            flush()
            current_file = hdr.group(1).strip()
            continue
        if LOCATION_RE.match(paragraph) or paragraph.startswith("="):
            # descartamos “Ubicación:” y separadores de =========
            continue
        if current_file is None:      # aún no hemos visto 'Archivo:'
            continue
        if not buffer and not paragraph.strip():
            # salta líneas vacías justo después del encabezado
            continue
        buffer.append(paragraph)

    flush()  # último archivo


def main():
    parser = argparse.ArgumentParser(description="Reconstruir árbol de código desde docx")
    parser.add_argument("docx", help="Ruta a all_python_code.txt (o .docx)")
    parser.add_argument("out_dir", help="Directorio destino para el código extraído")
    args = parser.parse_args()

    src = Path(args.docx).expanduser().resolve()
    dst = Path(args.out_dir).expanduser().resolve()

    if not src.exists():
        sys.exit(f"[!] Archivo no encontrado: {src}")

    print(f"Extrayendo código de {src.name} → {dst}")
    extract_files(src, dst)
    print("\n✓ Directorio recreado correctamente.")


if __name__ == "__main__":
    main()
