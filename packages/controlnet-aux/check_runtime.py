import hashlib
import os
from pathlib import Path
import tempfile
import urllib.request
import numpy as np
from PIL import Image
from controlnet_aux import CannyDetector, MediapipeFaceDetector

image = np.zeros((128,128,3), dtype=np.uint8)
image[32:96,32:96] = 255
assert CannyDetector()(image, output_type='np').any()
pins = {
 'face_landmarker.task': ('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task', '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'),
 'portrait.jpg': ('https://storage.googleapis.com/mediapipe-assets/portrait.jpg', 'a6f11efaa834706db23f275b6115058fa87fc7f14362681e6abe14e82749de3e')
}
with tempfile.TemporaryDirectory() as temp:
    for name, (url, digest) in pins.items():
        path = Path(temp) / name
        cached = Path(os.environ.get('SSUI_NATIVE_DOWNLOAD_CACHE', temp)) / name
        if cached.is_file():
            path.write_bytes(cached.read_bytes())
        else:
            urllib.request.urlretrieve(url, path)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    os.environ['SSUI_MEDIAPIPE_FACE_MODEL'] = str(Path(temp) / 'face_landmarker.task')
    result = MediapipeFaceDetector()(Image.open(Path(temp) / 'portrait.jpg').convert('RGB'), output_type='np')
    assert result.ndim == 3 and result.any()
print('ControlNet Canny and native MediaPipe Tasks face detector passed')
