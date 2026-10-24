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
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        marker = '      - name: Compute SHA-256 fingerprints and publish release\n'
        section = workflow.split(marker)[1]
        script_block = section.split('        run: |\n')[1]
        script_raw = script_block.split('\n      - name:')[0]
        script = textwrap.dedent(script_raw)
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
            (root / 'dist').mkdir()
            (root / 'dist' / 'tested bundle.tar.gz').write_bytes(b'tested bundle')
            stage = root / 'dist/_CPack_Packages/stage'
            stage.mkdir(parents=True)
            (stage / 'private-runtime.so').write_bytes(b'not a public asset')
            calls = root / 'calls'
            env = dict(os.environ, PATH=str(bin_dir)+os.pathsep+os.environ['PATH'],
                       STATE=state, CALLS=str(calls), GITHUB_REF_NAME='v2.0.0', TAG='v2.0.0',
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
        self.assertIn('tested bundle.tar.gz', calls)
        self.assertNotIn('private-runtime.so', calls)

    def test_new_release_stays_draft_and_uses_existing_tag(self):
        calls = self.run_publication('missing')
        self.assertIn('release create', calls)
        self.assertIn('--draft --verify-tag', calls)
        self.assertIn('release upload', calls)

