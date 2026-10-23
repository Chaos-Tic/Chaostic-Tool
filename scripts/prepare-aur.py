"""Fill a release PKGBUILD from a locally verified GitHub source archive."""
import argparse
import hashlib
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("archive", type=Path)
parser.add_argument("--version", required=True)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args.version):
    parser.error("version must be X.Y.Z")
source = Path(__file__).resolve().parents[1] / "packaging/arch/PKGBUILD"
text = re.sub(r"(?m)^pkgver=.*$", "pkgver=" + args.version, source.read_text())
digest = hashlib.sha256(args.archive.read_bytes()).hexdigest()
text = text.replace("RELEASE_CHECKSUM_REQUIRED", digest)
args.output.write_text(text)
