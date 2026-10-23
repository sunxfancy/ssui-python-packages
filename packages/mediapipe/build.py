"""Repackage verified upstream ARM64 DLLs with one coherent cv2 dependency."""
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from core import sha256
from runtime import context

ctx = context()
pin = json.loads(Path(__file__).with_name('upstream-wheel.json').read_text())
download = Path(ctx['source']).parent / pin['url'].rsplit('/', 1)[-1]
urllib.request.urlretrieve(pin['url'], download)
if sha256(download) != pin['sha256']:
    raise ValueError('Upstream MediaPipe wheel SHA256 mismatch')
provenance = dict(pin, native_files={})
with zipfile.ZipFile(download) as src, zipfile.ZipFile(Path(ctx['raw']) / download.name, 'w', zipfile.ZIP_DEFLATED) as dest:
    for entry in src.infolist():
        data = src.read(entry.filename)
        if entry.filename.endswith(('.dll', '.pyd')):
            provenance['native_files'][entry.filename] = hashlib.sha256(data).hexdigest()
        if entry.filename.endswith('.dist-info/METADATA'):
            text, count = re.subn(r'^Requires-Dist: opencv-contrib-python[^\r\n]*',
                'Requires-Dist: ' + pin['opencv_requirement'], data.decode(), flags=re.M)
            if count != 1:
                raise ValueError('Unexpected upstream OpenCV dependency metadata')
            data = text.encode()
        dest.writestr(entry, data)
if not provenance['native_files']:
    raise ValueError('Expected native upstream ARM64 library')
out = Path(ctx['out'])
out.mkdir()
(out / 'upstream-wheel-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
