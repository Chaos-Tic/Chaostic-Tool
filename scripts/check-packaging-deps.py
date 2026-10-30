"""Fail when the Python runtime floors diverge between the packaging recipes.

The same interpreter and library floors are declared in the Debian control
file, the Fedora spec, the Arch PKGBUILD, the CPack strings of CMakeLists.txt
and requirements.txt. This check keeps them identical so that a bump in one
place cannot silently leave another channel behind.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
# Canonical name -> package name in each recipe family.
DEPENDENCIES = {
    'python': {'deb': 'python3', 'rpm': 'python3', 'arch': 'python', 'pip': None},
    'rich': {'deb': 'python3-rich', 'rpm': 'python3-rich', 'arch': 'python-rich', 'pip': 'rich'},
    'prompt-toolkit': {'deb': 'python3-prompt-toolkit', 'rpm': 'python3-prompt-toolkit',
                       'arch': 'python-prompt_toolkit', 'pip': 'prompt_toolkit'},
}
PATTERNS = {
    'deb': r'{name} \(>= ([0-9.]+)\)',
    'rpm': r'{name} >= ([0-9.]+)',
    'arch': r"'{name}>=([0-9.]+)'",
    'pip': r'^{name}>=([0-9.]+)',
}
SOURCES = {
    'packaging/debian/control': 'deb',
    'packaging/fedora/chaostictool.spec': 'rpm',
    'packaging/arch/PKGBUILD': 'arch',
    'CMakeLists.txt (Debian)': 'deb',
    'CMakeLists.txt (RPM)': 'rpm',
}


def floors(text, family, source):
    """Return {dependency: floor} for every declaration of that family in text."""
    found = {}
    for dependency, names in DEPENDENCIES.items():
        name = names[family]
        if name is None:
            continue
        pattern = PATTERNS[family].format(name=re.escape(name))
        values = set(re.findall(pattern, text, re.M))
        if len(values) > 1:
            raise SystemExit(f'{source}: {name} declared with several floors {sorted(values)}')
        if values:
            found[dependency] = values.pop()
    return found


def version(value):
    return tuple(int(part) for part in value.split('.'))


def main():
    declared = {}
    for source, family in SOURCES.items():
        text = (ROOT / source.split(' ')[0]).read_text()
        declared[source] = floors(text, family, source)
    errors = []
    native = {}
    for dependency in DEPENDENCIES:
        values = {source: found[dependency] for source, found in declared.items() if dependency in found}
        missing = [source for source in declared if source not in values]
        if missing:
            errors.append(f'{dependency}: no floor in {", ".join(missing)}')
        if len(set(values.values())) > 1:
            errors.append(f'{dependency}: floors differ: '
                          + ', '.join(f'{source}={value}' for source, value in values.items()))
        elif values:
            native[dependency] = next(iter(values.values()))
    pip = floors((ROOT / 'requirements.txt').read_text(), 'pip', 'requirements.txt')
    for dependency, names in DEPENDENCIES.items():
        if names['pip'] is None or dependency not in native:
            continue
        if dependency not in pip:
            errors.append(f'{dependency}: requirements.txt has no >= floor')
            continue
        floor = version(native[dependency])
        if version(pip[dependency])[:len(floor)] != floor:
            errors.append(f'{dependency}: requirements.txt floor {pip[dependency]} does not match '
                          f'the native packages ({native[dependency]})')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('Packaging floors consistent:', ', '.join(f'{d}>={v}' for d, v in native.items()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
