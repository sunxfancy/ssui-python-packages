"""Native CPU Tasks inference with pinned official face and pose models."""
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import tempfile
import urllib.request
import mediapipe as mp
import numpy as np

assert metadata.version('opencv-python-headless').startswith('4.11.0.86+ssui.')
installed = {d.metadata['Name'].lower().replace('_', '-') for d in metadata.distributions()}
assert not installed & {'opencv-python', 'opencv-contrib-python', 'opencv-contrib-python-headless'}
pins = json.loads(Path(__file__).with_name('models.json').read_text())
pins.update(json.loads(Path(__file__).with_name('fixtures.json').read_text()))
image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.zeros((128, 128, 3), dtype=np.uint8))
with tempfile.TemporaryDirectory() as temp:
    paths = {}
    for name, pin in pins.items():
        path = Path(temp) / pin['url'].rsplit('/', 1)[-1]
        cache = os.environ.get('SSUI_NATIVE_DOWNLOAD_CACHE')
        cached = Path(cache) / pin['url'].rsplit('/', 1)[-1] if cache else None
        if cached and cached.is_file():
            path.write_bytes(cached.read_bytes())
        else:
            urllib.request.urlretrieve(pin['url'], path)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
        paths[name] = path
    base = mp.tasks.BaseOptions
    options = mp.tasks.vision.FaceLandmarkerOptions(base_options=base(
        model_asset_path=str(paths['face']), delegate=base.Delegate.CPU), num_faces=1)
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as detector:
        assert not detector.detect(image).face_landmarks
        detected = detector.detect(mp.Image.create_from_file(str(paths['portrait'])))
        assert detected.face_landmarks and len(detected.face_landmarks[0]) >= 468
    options = mp.tasks.vision.PoseLandmarkerOptions(base_options=base(
        model_asset_path=str(paths['pose']), delegate=base.Delegate.CPU),
        running_mode=mp.tasks.vision.RunningMode.VIDEO)
    with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
        assert not detector.detect_for_video(image, 0).pose_landmarks
        assert not detector.detect_for_video(image, 33).pose_landmarks
        detected = detector.detect_for_video(mp.Image.create_from_file(str(paths['pose_image'])), 66)
        assert detected.pose_landmarks and len(detected.pose_landmarks[0]) == 33
        assert detected.pose_world_landmarks and len(detected.pose_world_landmarks[0]) == 33
print('MediaPipe native CPU face/pose inference passed with one headless cv2 provider')
