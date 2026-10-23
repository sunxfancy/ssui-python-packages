"""Relabel downstream builds correctly, regenerate RECORD and verify wheel metadata."""
import base64
import csv
from email.parser import Parser
import hashlib
import io
from pathlib import Path
import re
import zipfile


def relabel(wheel, version, out_dir, torch_version=None, python_version=None):
    wheel, out_dir = Path(wheel), Path(out_dir)
    dist, _, *tags = wheel.name[:-4].split('-')
    # Upstream wheels may use an optional build tag. Preserve their ABI/platform.
    filename = '-'.join([dist, version, *tags]) + '.whl'
    out_dir.mkdir(parents=True, exist_ok=True)
    destination = out_dir / filename
    rows = []
    with zipfile.ZipFile(wheel) as zin, zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as zout:
        for entry in zin.infolist():
            name = entry.filename
            if name.endswith(('.dist-info/RECORD', '.dist-info/RECORD.jws', '.dist-info/RECORD.p7s')):
                continue
            if name.startswith('/') or '..' in Path(name).parts:
                raise ValueError('Unsafe wheel member')
            payload = zin.read(name)
            name = re.sub(r'^[^/]+\.dist-info/', f'{dist}-{version}.dist-info/', name)
            name = re.sub(r'^[^/]+\.data/', f'{dist}-{version}.data/', name)
            if name.endswith('.dist-info/METADATA'):
                text = payload.decode('utf-8')
                text, count = re.subn(r'^Version: .*$', f'Version: {version}', text, count=1, flags=re.M)
                if count != 1:
                    raise ValueError('Missing wheel Version metadata')
                if torch_version:
                    # pip cannot encode GPU compatibility; the channel also isolates it.
                    text = text.replace('\n\n', f'\nRequires-Dist: torch=={torch_version}\n\n', 1)
                if python_version:
                    major, minor = map(int, python_version.split('.'))
                    requires_python = f'>={major}.{minor},<{major}.{minor + 1}'
                    text, count = re.subn(r'^Requires-Python: .*$', f'Requires-Python: {requires_python}', text, count=1, flags=re.M)
                    if not count:
                        text = text.replace('\n\n', f'\nRequires-Python: {requires_python}\n\n', 1)
                payload = text.encode('utf-8')
            zout.writestr(entry, payload) if name == entry.filename else zout.writestr(name, payload)
            digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b'=').decode()
            rows.append([name, 'sha256=' + digest, str(len(payload))])
        record = f'{dist}-{version}.dist-info/RECORD'
        rows.append([record, '', ''])
        stream = io.StringIO()
        csv.writer(stream, lineterminator='\n').writerows(rows)
        zout.writestr(record, stream.getvalue())
    return destination


def verify_wheel(wheel, item, version):
    parts = Path(wheel).name[:-4].split('-')
    python_tag, abi_tag, platform_tag = parts[-3:]
    cfg = item['config']
    expected = {'windows': {'x64': 'win_amd64', 'arm64': 'win_arm64'}}
    if cfg['os'] == 'windows' and platform_tag != expected['windows'][cfg['arch']]:
        raise ValueError(f'Wrong platform tag: {platform_tag}')
    if cfg['os'] == 'macos' and not (platform_tag.startswith('macosx_') and platform_tag.endswith('_' + cfg['arch'])):
        raise ValueError(f'Wrong macOS platform tag: {platform_tag}')
    if python_tag not in ('py3', 'cp' + cfg['python'].replace('.', '')) or abi_tag not in ('none', 'abi3', 'cp' + cfg['python'].replace('.', '')):
        raise ValueError('Wrong Python or ABI tag')
    with zipfile.ZipFile(wheel) as archive:
        metadata = [name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
        if len(metadata) != 1:
            raise ValueError('Expected one METADATA file')
        message = Parser().parsestr(archive.read(metadata[0]).decode())
        if message['Name'].lower().replace('_', '-') != item['package'] or message['Version'] != version:
            raise ValueError('Wheel identity differs from release recipe')
        if parts[1] != version:
            raise ValueError('Wheel filename and METADATA versions differ')
        if not any(name.endswith(('.pyd', '.dll', '.so', '.dylib')) for name in archive.namelist()):
            raise ValueError('Native wheel contains no native libraries')
        record = next(name for name in archive.namelist() if name.endswith('.dist-info/RECORD'))
        rows = list(csv.reader(io.StringIO(archive.read(record).decode())))
        if {row[0] for row in rows} != set(archive.namelist()):
            raise ValueError('RECORD does not enumerate every wheel member')
        for name, digest, size in rows:
            if name == record:
                continue
            payload = archive.read(name)
            actual = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b'=').decode()
            if digest != 'sha256=' + actual or int(size) != len(payload):
                raise ValueError('RECORD checksum mismatch')
