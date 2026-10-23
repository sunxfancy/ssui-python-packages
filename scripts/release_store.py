"""Immutable GitHub Release storage. Cache artifacts are never release evidence."""
import json
import re
import subprocess
from urllib.parse import quote


def gh(*args, check=True):
    return subprocess.run(['gh', *args], capture_output=True, text=True, encoding='utf-8', check=check)


def find_release(repo, tag):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('Invalid destination repository')
    result = gh('api', f'repos/{repo}/releases/tags/{quote(tag, safe="")}', check=False)
    if result.returncode:
        if 'HTTP 404' in result.stderr or 'Not Found (HTTP 404)' in result.stderr:
            return None
        raise RuntimeError(f'Cannot read release metadata: {result.stderr}')
    release = json.loads(result.stdout)
    if release.get('draft'):
        return {'release': release, 'manifest': None}
    manifest = gh('release', 'download', tag, '--repo', repo, '--pattern', 'release.json', '--output', '-', check=False)
    if manifest.returncode:
        return {'release': release, 'manifest': None}
    try:
        value = json.loads(manifest.stdout)
    except ValueError:
        value = None
    return {'release': release, 'manifest': value}


def release_is_valid(published, expected):
    release, manifest = published['release'], published.get('manifest')
    if release.get('draft') or not isinstance(manifest, dict):
        return False
    for key in ('package', 'target', 'fingerprint', 'version', 'channel'):
        if manifest.get(key) != expected[key]:
            return False
    if manifest.get('schema') != 1 or manifest.get('checks', {}).get('smoke') != 'passed':
        return False
    files = manifest.get('files', [])
    if not files or len({f['name'] for f in files}) != len(files):
        return False
    assets = {asset['name']: asset for asset in release.get('assets', [])}
    if 'release.json' not in assets:
        return False
    for file in files:
        asset = assets.get(file['name'], {})
        if asset.get('size') != file['size'] or asset.get('digest') != 'sha256:' + file['sha256']:
            return False
    return True
