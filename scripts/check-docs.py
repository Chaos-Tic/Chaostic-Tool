"""Check repository-local Markdown links and image paths without network access."""
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def check():
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    failures = []
    count = 0
    for name in tracked:
        if not name.endswith('.md'):
            continue
        document = ROOT / name
        content = document.read_text(encoding='utf-8')
        content = re.sub(r'```.*?```', '', content, flags=re.S)
        links = re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', content)
        links += re.findall(r'(?:src|href)=["\']([^"\']+)["\']', content)
        for link in links:
            parts = urlsplit(link.strip('<>'))
            if parts.scheme or parts.netloc or not parts.path:
                continue
            count += 1
            target = document.parent / unquote(parts.path)
            if not target.exists():
                failures.append(f'{name}: missing {link}')
    print(f'Checked {count} local documentation paths (external URLs and anchors excluded).')
    for failure in failures:
        print(failure)
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(check())
