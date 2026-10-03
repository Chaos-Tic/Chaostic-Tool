"""Standard-library executable discovery shared with the standalone Linux bridge."""
import os
from functools import lru_cache
from pathlib import Path
import shutil
import subprocess


def tool_search_path():
    directories = os.environ.get('PATH', os.defpath).split(os.pathsep)
    if os.name != 'nt':
        home = Path.home()
        if os.geteuid() == 0 and os.environ.get('SUDO_USER'):
            import pwd
            try:
                home = Path(pwd.getpwnam(os.environ['SUDO_USER']).pw_dir)
            except KeyError:
                pass
        directories += [str(home / suffix) for suffix in
                        ('.local/bin', 'go/bin', '.local/share/go/bin', '.cargo/bin')]
        for variable, suffix in (('GOBIN', ''), ('GOPATH', 'bin'), ('CARGO_HOME', 'bin'), ('PIPX_BIN_DIR', '')):
            for value in os.environ.get(variable, '').split(os.pathsep):
                if value:
                    directories.append(str(Path(value).expanduser() / suffix))
    return os.pathsep.join(dict.fromkeys(directory for directory in directories if directory))


def resolve_tool(candidates, markers=()):
    """Keep symlinks/shebangs intact and reject same-name unrelated programs."""
    search = tool_search_path()
    checked = set()
    for name in candidates:
        name = os.path.expanduser(name)
        locations = [shutil.which(name, path=search)]
        if os.name != 'nt' and not os.path.dirname(name):
            locations += [str(Path(directory) / name) for directory in search.split(os.pathsep)]
        for value in locations:
            if not value or value in checked:
                continue
            checked.add(value)
            path = Path(value)
            if not path.is_file() or (os.name != 'nt' and not os.access(path, os.X_OK)):
                continue
            if markers:
                try:
                    stamp = path.stat()
                    if not _matches_markers(str(path), tuple(markers), search,
                                            stamp.st_mtime_ns, stamp.st_size):
                        continue
                except OSError:
                    continue
            return os.path.abspath(path)
    return None


@lru_cache(maxsize=128)
def _matches_markers(path, markers, search, mtime, size):
    # Refresh when an executable changes; avoid probing on every UI redraw.
    try:
        result = subprocess.run([path, '-h'], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=4,
                                env=dict(os.environ, PATH=search),
                                creationflags=0x08000000 if os.name == 'nt' else 0)
        output = result.stdout.decode('utf-8', errors='replace').lower()
        return any(marker.lower() in output for marker in markers)
    except (OSError, subprocess.TimeoutExpired):
        return False
