"""Comprueba las versiones fijadas de IA sin importar TensorFlow ni usar red."""
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys


def check(path):
    missing = []
    for raw in path.read_text(encoding='utf-8-sig').splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        if line.count('==') != 1:
            raise ValueError(f'Se requiere una versión exacta con ==: {line}')
        package, wanted = (part.strip() for part in line.split('=='))
        try:
            installed = version(package)
        except PackageNotFoundError:
            installed = 'no instalado'
        if installed != wanted:
            missing.append(f'{package}: {installed}; requerido {wanted}')
    return missing


if __name__ == '__main__':
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        if sys.version_info[:2] != (3, 12):
            raise RuntimeError('El entorno de IA requiere Python 3.12.')
        problems = check(Path(sys.argv[1]))
        print('\n'.join(problems) if problems else 'OK: versiones de IA instaladas.')
        sys.exit(1 if problems else 0)
    except (IndexError, OSError, ValueError, RuntimeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(2)
