"""Exercise release publication control flow using a local fake GitHub CLI."""
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == 'nt', 'Bash workflow is validated on POSIX runners')
class ReleaseWorkflowTests(unittest.TestCase):
    def run_publication(self, state):
        workflow = (ROOT / '.github/workflows/desktop.yml').read_text()
        script = textwrap.dedent(workflow.rsplit('        run: |\n', 1)[1])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            gh = bin_dir / 'gh'
            gh.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$CALLS"
if [ "$1 $2" = 'release view' ]; then
    [ "$STATE" = missing ] && exit 1
    printf '{"isDraft":%s}\\n' "$STATE"
fi
''')
            gh.chmod(0o755)
            jq = bin_dir / 'jq'
            jq.write_text('#!/bin/sh\nprintf "%s\\n" "$STATE"\n')
            jq.chmod(0o755)
            (root / 'packages').mkdir()
            (root / 'packages/test asset.zip').write_bytes(b'tested bundle')
            calls = root / 'calls'
            env = dict(os.environ, PATH=str(bin_dir)+os.pathsep+os.environ['PATH'],
                       STATE=state, CALLS=str(calls), GITHUB_REF_NAME='desktop-v1.0.2',
                       GITHUB_REPOSITORY='local/test')
            subprocess.run(['bash', '-eo', 'pipefail', '-c', script], cwd=root,
                           env=env, capture_output=True, text=True, check=True)
            return calls.read_text()

    def test_public_release_is_preserved(self):
        calls = self.run_publication('false')
        self.assertNotIn('release create', calls)
        self.assertNotIn('release upload', calls)

    def test_existing_draft_resumes_without_duplicate(self):
        calls = self.run_publication('true')
        self.assertNotIn('release create', calls)
        self.assertIn('release upload', calls)
        self.assertIn('--clobber', calls)

    def test_new_release_stays_draft_and_uses_existing_tag(self):
        calls = self.run_publication('missing')
        self.assertIn('release create', calls)
        self.assertIn('--draft --verify-tag', calls)
        self.assertIn('release upload', calls)
