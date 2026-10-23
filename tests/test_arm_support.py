import copy
import io
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core import fingerprint, load_targets, wheel_version
from plan import make_plan
from source import checkout, extract_archive
from verify import relabel, verify_wheel


class ArmSupportTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.work/tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name).resolve()
        self.assertTrue(self.root.is_relative_to(parent.resolve()))
        self.addCleanup(self.temp.cleanup)

    def item(self, name='pynini'):
        return next(i for i in load_targets() if i['package'] == name and i['config']['arch'] == 'arm64' and i['config']['os'] == 'windows')

    def wheel(self, item, machine=0xaa64, pure=False):
        dist = item['package'].replace('-', '_')
        original = self.root / (f'{dist}-1.0-' + ('py3-none-any' if pure else 'cp312-cp312-win_arm64') + '.whl')
        with zipfile.ZipFile(original, 'w') as archive:
            archive.writestr(f'{dist}/__init__.py', '')
            if not pure:
                pe = bytearray(128)
                pe[:2] = b'MZ'
                struct.pack_into('<I', pe, 60, 64)
                pe[64:68] = b'PE\0\0'
                struct.pack_into('<H', pe, 68, machine)
                archive.writestr(f'{dist}/_native.pyd', pe)
            archive.writestr(f'{dist}-1.0.dist-info/METADATA', f'Metadata-Version: 2.1\nName: {item["package"]}\nVersion: 1.0\n\n')
            archive.writestr(f'{dist}-1.0.dist-info/RECORD', '')
        return relabel(original, wheel_version(item), self.root / 'out')

    def test_arm_pynini_target_is_independently_selectable(self):
        plan = make_plan(changed=['packages/pynini/targets/windows-arm64-cp312-cpu.json'])
        self.assertEqual([(x['package'], x['target']) for x in plan['matrix']['include']], [('pynini', 'windows-arm64-cp312-cpu')])

    def test_arm_toolchain_does_not_select_existing_x64_or_macos(self):
        plan = make_plan(changed=['toolchains/windows-arm64-cpu.lock'])
        self.assertGreater(plan['count'], 10)
        self.assertTrue(all(x['runner'] == 'windows-11-arm' for x in plan['matrix']['include']))

    def test_blocked_ffmpeg_never_runs_even_with_force(self):
        plan = make_plan(package='imageio-ffmpeg', force=True)
        self.assertEqual(plan['count'], 0)
        self.assertIn('FFmpeg', plan['blocked'][0]['reason'])

    def test_real_arm_pe_machine_accepted(self):
        item = self.item()
        verify_wheel(self.wheel(item), item, wheel_version(item))

    def test_renamed_x64_binary_rejected(self):
        item = self.item()
        with self.assertRaisesRegex(ValueError, 'not Windows ARM64'):
            verify_wheel(self.wheel(item, machine=0x8664), item, wheel_version(item))

    def test_explicit_pure_python_recipe_allowed(self):
        item = self.item('antlr4-python3-runtime')
        verify_wheel(self.wheel(item, pure=True), item, wheel_version(item))

    def test_native_recipe_cannot_publish_any_wheel(self):
        item = self.item()
        with self.assertRaisesRegex(ValueError, 'platform tag'):
            verify_wheel(self.wheel(item, pure=True), item, wheel_version(item))

    def test_source_archive_traversal_rejected(self):
        archive = self.root / 'bad.tar.gz'
        with tarfile.open(archive, 'w:gz') as handle:
            member = tarfile.TarInfo('../outside.txt')
            member.size = 1
            handle.addfile(member, io.BytesIO(b'x'))
        with self.assertRaises(tarfile.FilterError):
            extract_archive(archive, self.root / 'unpack')

    def test_source_hash_verified_before_extraction(self):
        with patch('source.urllib.request.urlretrieve', side_effect=lambda url, path: Path(path).write_bytes(b'bad archive')):
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                checkout({'url': 'https://files.pythonhosted.org/packages/test', 'sha256': '0' * 64}, self.root / 'source')
