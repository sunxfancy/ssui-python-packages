import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core import channel, fingerprint, load_targets, sha256, wheel_version
from index import write_site
from publish import validate_bundle
from verify import relabel


class PublicationTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.work/tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent, prefix='publication-')
        self.directory = Path(self.temp.name).resolve()
        self.assertTrue(self.directory.is_relative_to(parent.resolve()))
        self.addCleanup(self.temp.cleanup)

    def bundle(self):
        item = next(i for i in load_targets() if i['package'] == 'pynini' and i['config']['os'] == 'windows')
        digest = fingerprint(ROOT, item)
        original = self.directory / 'pynini-2.1.6.post1-cp312-cp312-win_amd64.whl'
        with zipfile.ZipFile(original, 'w') as wheel:
            wheel.writestr('_pynini.cp312-win_amd64.pyd', b'native test fixture')
            wheel.writestr('pynini-2.1.6.post1.dist-info/METADATA', 'Metadata-Version: 2.1\nName: pynini\nVersion: 2.1.6.post1\n\n')
            wheel.writestr('pynini-2.1.6.post1.dist-info/RECORD', '')
        out = self.directory / 'release'
        wheel = relabel(original, wheel_version(item, digest), out, python_version='3.12')
        manifest = {'schema': 1, 'package': 'pynini', 'target': item['target'], 'channel': channel(item),
                    'version': wheel_version(item, digest), 'fingerprint': digest,
                    'source': item['recipe']['source'], 'config': item['config'],
                    'checks': {'smoke': 'passed'}, 'files': [
                        {'name': wheel.name, 'size': wheel.stat().st_size, 'sha256': sha256(wheel)}]}
        (out / 'release.json').write_text(json.dumps(manifest), encoding='utf-8')
        return item, digest, out, wheel

    def test_publisher_validates_exact_bundle_before_network(self):
        item, digest, out, _ = self.bundle()
        manifest, _ = validate_bundle(out, item, digest)
        self.assertEqual(manifest['fingerprint'], digest)

    def test_tampered_wheel_cannot_publish(self):
        item, digest, out, wheel = self.bundle()
        with wheel.open('ab') as stream:
            stream.write(b'tampered')
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            validate_bundle(out, item, digest)

    def test_wrong_fingerprint_cannot_publish(self):
        item, _, out, _ = self.bundle()
        with self.assertRaises(ValueError):
            validate_bundle(out, item, 'f' * 64)

    def test_undeclared_file_cannot_publish(self):
        item, digest, out, _ = self.bundle()
        (out / 'undeclared.txt').write_text('not in the manifest')
        with self.assertRaisesRegex(ValueError, 'Unexpected release files'):
            validate_bundle(out, item, digest)

    def test_index_retains_siblings_and_isolates_gpu_channels(self):
        cpu = {'package': 'pynini', 'channel': 'windows/x64/cpu', 'files': [{'name': 'pynini.whl', 'sha256': 'a' * 64}]}
        gpu = {'package': 'cumesh', 'channel': 'windows/x64/rocm/7.2.1/2.9.1/gfx1201', 'files': [{'name': 'cumesh.whl', 'sha256': 'b' * 64}]}
        records = [(cpu, [{'name': 'pynini.whl', 'browser_download_url': 'https://github.com/example/releases/pynini.whl'}]),
                   (gpu, [{'name': 'cumesh.whl', 'browser_download_url': 'https://github.com/example/releases/cumesh.whl'}])]
        output = self.directory / 'site'
        write_site(records, output)
        cpu_html = (output / 'simple/windows/x64/cpu/pynini/index.html').read_text()
        self.assertIn('#sha256=' + 'a' * 64, cpu_html)
        self.assertNotIn('cumesh', cpu_html)
        self.assertTrue((output / 'simple/windows/x64/rocm/7.2.1/2.9.1/gfx1201/cumesh/index.html').is_file())
        self.assertEqual(len(json.loads((output / 'catalog.json').read_text())), 2)

    def test_index_rejects_directory_escape(self):
        record = {'package': 'pynini', 'channel': '../escape', 'files': []}
        with self.assertRaises(ValueError):
            write_site([(record, [])], self.directory / 'site')

    def test_different_fingerprints_have_distinct_wheel_versions(self):
        item = load_targets()[0]
        self.assertNotEqual(wheel_version(item, 'a' * 64), wheel_version(item, 'b' * 64))


if __name__ == '__main__':
    unittest.main()
