"""App-owned dependency installation, independent of the GUI and system packages."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from desktop.storage import data_root, now, write_json

MANIFEST = json.loads((Path(__file__).parent / "packages.json").read_text(encoding="utf-8"))
PORTABLE_PACK = ["subfinder", "httpx", "ffuf", "gobuster", "nuclei", "katana", "gau", "waybackurls", "dalfox", "naabu"]
PYTHON_PACK = ["wafw00f", "dnsrecon", "theharvester", "shodan", "xsstrike", "bloodhound-python", "impacket", "sqlmap"]
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def platform_key():
    machine = platform.machine().lower()
    arch = {'amd64':'x86_64','arm64':'aarch64'}.get(machine,machine)
    return platform.system().lower() + '-' + arch


def package_spec(package):
    spec = dict(MANIFEST[package])
    key = platform_key()
    if 'artifacts' in spec:
        if key not in spec['artifacts']:
            raise ValueError('Aucune distribution native publiée pour ' + key + '. Utilisez le backend Linux si disponible.')
        spec.update(spec['artifacts'][key])
    elif spec.get('platforms') and key not in spec['platforms']:
        raise ValueError('Cette distribution est incompatible avec ' + key + '.')
    if os.name != 'nt':
        spec['binary'] = spec.get('binary_by_os',{}).get(platform.system().lower(),spec['binary'].removesuffix('.exe'))
    return spec


def can_install(package):
    try: package_spec(package); return True
    except (KeyError, ValueError): return False


def env_python(directory):
    return Path(directory) / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def ensure_python(root, configured=None, log=print):
    python = find_python(configured)
    if python:
        try:
            probe([python], ['-I','-c','import sys; assert sys.version_info >= (3,14)'])
            return python
        except Exception:
            log('Python 3.14 requis pour le pack complet ; préparation du runtime isolé.')
    record = installed('python-runtime',root)
    if record:
        executable = record['path'] / record['executable']
        if executable.is_file(): return str(executable)
    specs = json.loads((Path(__file__).parent/'runtimes.json').read_text(encoding='utf-8'))
    spec = specs.get(platform_key())
    if not spec: raise RuntimeError('Pas de runtime Python automatique pour cette architecture. Configurez Python 3.14 dans les paramètres.')
    destination = Path(root)/'tools/python-runtime'/uuid.uuid4().hex
    destination.mkdir(parents=True)
    log('Téléchargement de Python ' + spec['version'] + ' pour ' + platform_key())
    with tempfile.TemporaryDirectory() as tmp:
        archive=Path(tmp)/'python.tar.gz'
        download(spec['url'],archive,spec['sha256'],log)
        with tarfile.open(archive,'r:gz') as source:
            if sum(item.size for item in source.getmembers()) > 2*1024**3: raise ValueError('Runtime trop volumineux.')
            # CPython contains relative library links. The data filter rejects links
            # and paths escaping this fresh, application-owned destination.
            source.extractall(destination,filter='data')
    executable=destination/('python/python.exe' if os.name=='nt' else 'python/bin/python3')
    probe([str(executable)],['-I','-c','import sys; print(sys.version)'])
    write_json(Path(root)/'tools/manifests/python-runtime.json',dict(version=spec['version'],directory=str(destination.relative_to(Path(root)/'tools')),executable=str(executable.relative_to(destination))))
    return str(executable)


def find_python(configured=None):
    candidates = [configured, os.environ.get("CHAOSTIC_PYTHON")]
    if not getattr(sys, "frozen", False):
        candidates.append(sys.executable)
    candidates.extend([shutil.which("python"), shutil.which("python3")])
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and "windowsapps" not in str(candidate).lower():
            return str(Path(candidate).resolve())
    return None


def installed(package, root=None):
    root = Path(root or data_root()) / "tools"
    path = root / "manifests" / f"{package}.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        base = (root / record["directory"]).resolve()
        if not base.is_relative_to(root.resolve()):
            return None
        record["path"] = base
        return record
    except (OSError, ValueError, KeyError, TypeError):
        return None


def managed_command(package, binary=None, root=None):
    record = installed(package, root)
    if not record:
        return None
    spec = package_spec(package)
    name = binary or spec["binary"]
    if spec["kind"].startswith("pip"):
        # pip scripts are kept in an immutable environment: never move a venv.
        if spec.get('script'):
            path = record['path'] / record['script']
            return [str(env_python(record['path'])),str(path)] if path.is_file() else None
        name = name.removesuffix('.exe') if os.name != 'nt' else name
        path = record["path"] / ('Scripts' if os.name == 'nt' else 'bin') / Path(name).name
        if path.suffix.lower() == ".py":
            python = env_python(record["path"])
            return [str(python), str(path)] if python.is_file() and path.is_file() else None
        return [str(path)] if path.is_file() else None
    path = record["path"] / record["executable"]
    return [str(path)] if path.resolve().is_relative_to(record['path']) and path.is_file() else None


def installation_error(package, root=None):
    try:
        value = json.loads((Path(root or data_root()) / 'tools/failures' / f'{package}.json').read_text(encoding='utf-8'))
        return value.get('error', '')
    except (OSError, ValueError):
        return ''


def save_failure(package, error, root=None):
    write_json(Path(root or data_root()) / 'tools/failures' / f'{package}.json', {'error': str(error), 'date': now()})


def download(url, target, expected_hash=None, log=print):
    if not url.startswith("https://"):
        raise ValueError("Une source HTTPS est requise.")
    request = urllib.request.Request(url, headers={"User-Agent": "ChaosticTool-Desktop/0.2"})
    digest = hashlib.sha256()
    total, reported = 0, 0
    with urllib.request.urlopen(request, timeout=45) as response, Path(target).open("wb") as stream:
        if not response.geturl().startswith("https://"):
            raise ValueError("Redirection non HTTPS refusée.")
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > 1024 * 1024 * 1024:
                raise ValueError("Archive anormalement volumineuse.")
            stream.write(chunk)
            digest.update(chunk)
            if total - reported >= 10 * 1024 * 1024:
                log(f"  Téléchargement : {total // (1024 * 1024)} Mo")
                reported = total
    actual = digest.hexdigest()
    if expected_hash and actual.lower() != expected_hash.lower():
        raise ValueError("Empreinte SHA-256 incorrecte : installation annulée.")
    return actual


def _safe_member(name, root):
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or any(":" in p for p in path.parts):
        raise ValueError("Chemin d’archive non sûr.")
    destination = root.joinpath(*path.parts).resolve()
    if not destination.is_relative_to(root.resolve()):
        raise ValueError("L’archive sort du dossier prévu.")
    return destination


def extract_archive(archive, root, helper_root=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    total = 0
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                destination = _safe_member(member.filename, root)
                if stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError("Liens symboliques non acceptés dans un outil portable.")
                total += member.file_size
                if total > 2 * 1024**3:
                    raise ValueError("Archive décompressée trop volumineuse.")
                if member.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with source.open(member) as src, destination.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
    elif __import__('py7zr').is_7zfile(archive):
        import py7zr
        with py7zr.SevenZipFile(archive,'r') as source:
            for member in source.list():
                _safe_member(member.filename,root)
                if member.is_symlink: raise ValueError('Lien 7z non accepté.')
                total += member.uncompressed
                if total > 2*1024**3: raise ValueError('Archive trop volumineuse.')
        helper_root=Path(helper_root or data_root())
        install_package('7zip',helper_root)
        command=managed_command('7zip',root=helper_root)
        _run([*command,'x','-y','-o'+str(root.resolve()),str(Path(archive).resolve())],lambda line:None)
    else:
        with tarfile.open(archive, "r:*") as source:
            for member in source:
                destination = _safe_member(member.name, root)
                if not (member.isdir() or member.isfile()):
                    raise ValueError("Entrée spéciale non acceptée dans l’archive.")
                total += member.size
                if total > 2 * 1024**3:
                    raise ValueError("Archive décompressée trop volumineuse.")
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(member) as src, destination.open("wb") as dst:
                        shutil.copyfileobj(src, dst)


def _run(command, log, timeout=900):
    environment = dict(os.environ, PYTHONUTF8="1", PYTHONUNBUFFERED="1", PIP_DISABLE_PIP_VERSION_CHECK="1", NO_COLOR="1")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               encoding="utf-8", errors="replace", env=environment,
                               creationflags=CREATE_NO_WINDOW)
    # Parent Runner owns a Windows Job and enforces the overall installation timeout.
    for line in process.stdout:
        log(line.rstrip())
    code = process.wait(timeout=timeout)
    if code:
        raise RuntimeError(f"La commande a échoué (code {code}). Consultez le journal ci-dessus.")


def probe(command, arguments):
    completed = subprocess.run([*command, *arguments], capture_output=True, timeout=30,
                               text=True, encoding="utf-8", errors="replace", creationflags=CREATE_NO_WINDOW)
    text = (completed.stdout + completed.stderr).strip()
    if completed.returncode != 0:
        raise RuntimeError(f"Vérification de lancement échouée (code {completed.returncode}) : {text[-2000:]}")
    return text[:3000]


def install_package(package, root=None, python=None, log=print):
    if package not in MANIFEST:
        raise ValueError("Outil inconnu.")
    root = Path(root or data_root()).resolve()
    spec = package_spec(package)
    tools = root / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    existing = installed(package, root)
    if existing and existing.get("version") == spec["version"] and managed_command(package, root=root):
        probe(managed_command(package, root=root), spec['probe'])
        log(f"{package} {spec['version']} est déjà installé ; lancement revérifié.")
        return existing
    suffix = re.sub(r"[^a-zA-Z0-9._-]", "_", spec["version"]) + "-" + uuid.uuid4().hex[:8]
    destination = tools / package / suffix
    destination.mkdir(parents=True)
    log(f"Installation de {package} {spec['version']}…")
    record = dict(package=package, version=spec["version"], directory=str(destination.relative_to(tools)), source=spec["url"], installed=now())
    if spec["kind"] in ("release", "file"):
        with tempfile.TemporaryDirectory(prefix="download-", dir=tools, ignore_cleanup_errors=True) as temporary:
            archive = Path(temporary) / "package.archive"
            digest = download(spec["url"], archive, spec["sha256"], log)
            log("Empreinte SHA-256 vérifiée. Extraction…")
            if spec['kind'] == 'file': shutil.copyfile(archive,destination/spec['binary'])
            else: extract_archive(archive, destination, root)
        binaries = [p for p in destination.rglob("*") if p.is_file() and p.name.lower() == spec["binary"].lower()]
        if len(binaries) != 1:
            raise RuntimeError(f"L’exécutable {spec['binary']} est absent ou ambigu dans l’archive.")
        if os.name != 'nt': binaries[0].chmod(binaries[0].stat().st_mode | 0o755)
        command = [str(binaries[0])]
        record.update(executable=str(binaries[0].relative_to(destination)), sha256=digest)
    else:
        python = ensure_python(root, python, log)
        _run([python, '-m', 'venv', str(destination)],log)
        runtime = env_python(destination)
        if spec.get('extra_requirements'):
            _run([str(runtime),'-m','pip','install','--index-url','https://pypi.org/simple',*spec['extra_requirements']],log)
        if spec['kind'] == 'pip-source':
            with tempfile.TemporaryDirectory() as tmp:
                archive=Path(tmp)/'source.zip'
                download(spec['url'],archive,spec['sha256'],log)
                extract_archive(archive,destination/'source')
            sources=list((destination/'source').iterdir())
            if len(sources)!=1 or not sources[0].is_dir(): raise ValueError('Archive source ambiguë.')
            source=sources[0]
            if spec.get('script'):
                _run([str(runtime),'-m','pip','install','--index-url','https://pypi.org/simple','-r',str(source/'requirements.txt')],log)
                executable=source/spec['script']
                record['script']=str(executable.relative_to(destination))
            else:
                _run([str(runtime),'-m','pip','install','--index-url','https://pypi.org/simple',str(source)],log)
                executable=destination/('Scripts' if os.name=='nt' else 'bin')/spec['binary']
        else:
            _run([str(runtime),'-m','pip','install','--index-url','https://pypi.org/simple',f"{spec['package']}=={spec['version']}"],log)
            executable=destination/('Scripts' if os.name=='nt' else 'bin')/spec['binary']
        if not executable.is_file(): raise RuntimeError(f'Exécutable absent : {executable.name}. Consultez aussi l’historique de protection du système.')
        command=[str(runtime),str(executable)] if executable.suffix=='.py' else [str(executable)]
        record['executable']=str(executable.relative_to(destination))
    record["probe"] = probe(command, spec["probe"])
    record['platform'] = platform_key()
    write_json(tools / "manifests" / f"{package}.json", record)
    (tools/'failures'/f'{package}.json').unlink(missing_ok=True)
    log(f"{package} : installé et lancement vérifié.")
    return record


def install_request(request):
    packages = request.get("packages", [])
    if not packages or any(p not in MANIFEST for p in packages):
        raise ValueError("Liste d’outils invalide.")
    errors = []
    for package in packages:
        try:
            install_package(package, request["root"], request.get("python"), lambda line: print(line, flush=True))
        except Exception as exc:
            save_failure(package, exc, request['root'])
            print(f"\nÉchec de {package} : {exc}\n", flush=True)
            errors.append(package)
    if errors:
        raise RuntimeError("Installation incomplète : " + ", ".join(errors))
