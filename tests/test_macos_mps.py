"""Keep the macOS supplement isolated from existing published targets."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core import fingerprint, load_targets
from plan import make_plan


class MacMpsTests(unittest.TestCase):
    def test_package_selection_is_macos_only(self):
        plan = make_plan(package='ssui-trellis-mps')
        self.assertEqual(plan['count'], 1)
        self.assertEqual(plan['matrix']['include'][0]['target'], 'macos-arm64-cp312-mps-torch241')

    def test_mac_toolchain_selection_is_isolated(self):
        plan = make_plan(changed=['toolchains/macos-arm64-mps-torch241.lock'])
        self.assertEqual(plan['count'], 1)
        self.assertEqual(plan['matrix']['include'][0]['package'], 'ssui-trellis-mps')

    def test_metal_source_changes_only_new_package_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'repo'
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('.git', '.work', '__pycache__'))
            items = load_targets(root)
            before = {(i['package'], i['target']): fingerprint(root, i) for i in items}
            source = root / 'packages/ssui-trellis-mps/src/ssui_trellis_mps/neighbors.mm'
            source.write_text(source.read_text() + '\n// fingerprint regression\n')
            changed = [i['package'] for i in items if fingerprint(root, i) != before[i['package'], i['target']]]
            self.assertEqual(changed, ['ssui-trellis-mps'])


if __name__ == '__main__':
    unittest.main()
