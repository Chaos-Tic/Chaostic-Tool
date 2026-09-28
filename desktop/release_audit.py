"""Fail closed when runtime user state accidentally enters a distribution."""
from pathlib import Path

STATE_FILES={'settings.json','linux.json','linux-status.json','wsl-setup.json',
             'run.json','output.txt','desktop-errors.log','desktop.lock',
             'smoke-result.json','smoke-initial-state.json'}

def assert_clean_bundle(directory):
    root=Path(directory)
    if not root.is_dir():raise ValueError('Missing application bundle')
    forbidden=[]
    for path in root.rglob('*'):
        name=path.name.casefold()
        if name in STATE_FILES or (path.is_dir() and name in ('runs','flows')) or name.startswith('settings-unreadable-'):
            forbidden.append(str(path.relative_to(root)))
    if forbidden:
        raise ValueError('User state must not be shipped: '+', '.join(forbidden))
