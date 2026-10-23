"""Materialize immutable Git commits or hash-checked PyPI source archives."""
from pathlib import Path
import subprocess
import tarfile
import urllib.request
import zipfile

from core import sha256
from runtime import run


def extract_archive(archive, destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as handle:
            for entry in handle.infolist():
                if not (destination / entry.filename).resolve().is_relative_to(destination):
                    raise ValueError('Unsafe archive member')
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('Archive symlinks are not supported')
            handle.extractall(destination)
    else:
        with tarfile.open(archive) as handle:
            handle.extractall(destination, filter='data')
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError('Expected one source archive root')
    return roots[0]


def checkout(pin, source):
    source = Path(source)
    source.parent.mkdir(parents=True, exist_ok=True)
    if 'url' in pin:
        archive = source.parent / 'source.archive'
        urllib.request.urlretrieve(pin['url'], archive)
        if sha256(archive) != pin['sha256']:
            raise ValueError('Source archive SHA256 mismatch')
        root = extract_archive(archive, source.parent / 'unpack')
        root.rename(source)
        return
    run(['git', 'init', source])
    run(['git', 'remote', 'add', 'origin', 'https://github.com/' + pin['repository'] + '.git'], cwd=source)
    run(['git', 'fetch', '--depth=1', 'origin', pin['commit']], cwd=source)
    run(['git', 'checkout', '--detach', 'FETCH_HEAD'], cwd=source)
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() != pin['commit']:
        raise ValueError('Source checkout SHA mismatch')
    run(['git', 'submodule', 'update', '--init', '--recursive', '--depth=1'], cwd=source)
