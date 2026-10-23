"""Exercise installed native executables, H.264 video and PCM audio."""
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import wave
import imageio_ffmpeg

exe = Path(imageio_ffmpeg.get_ffmpeg_exe())
assert exe.name == 'ffmpeg.exe', exe
for path in [exe, exe.with_name('ffprobe.exe'), *exe.parent.glob('*.dll')]:
    data = path.read_bytes()
    offset = struct.unpack_from('<I', data, 60)[0]
    assert data[:2] == b'MZ' and data[offset:offset+4] == b'PE\0\0'
    assert struct.unpack_from('<H', data, offset + 4)[0] == 0xaa64, path
subprocess.run([str(exe), '-version'], check=True)
with tempfile.TemporaryDirectory() as temp:
    video = str(Path(temp) / 'probe.mp4')
    writer = imageio_ffmpeg.write_frames(video, (16, 16), fps=4, codec='libx264')
    writer.send(None)
    for _ in range(3):
        writer.send(bytes([240, 0, 0]) * 256)
    writer.close()
    reader = imageio_ffmpeg.read_frames(video)
    meta = next(reader)
    frames = list(reader)
    assert meta['size'] == (16, 16) and len(frames) == 3
    details = json.loads(subprocess.check_output([str(exe.with_name('ffprobe.exe')), '-v', 'error',
        '-show_streams', '-of', 'json', video], text=True))
    assert details['streams'][0]['codec_name'] == 'h264'
    wav = str(Path(temp) / 'probe.wav')
    with wave.open(wav, 'wb') as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(16000)
        output.writeframes(b'\0\0' * 1600)
    raw = subprocess.check_output([str(exe), '-v', 'error', '-i', wav, '-f', 'f32le', '-ac', '1', '-ar', '16000', '-'])
    assert len(raw) == 1600 * 4
print('Native ARM64 H.264 encode/decode, ffprobe and PCM audio decode passed')
