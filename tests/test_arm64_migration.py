import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('arm64_migration', ROOT/'arm64/migrate.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
from plan import make_plan


class Arm64MigrationTests(unittest.TestCase):
    def test_imports_do_not_schedule_existing_builds(self):
        plan = make_plan(changed=['arm64/migrate.py','arm64/registry.json','package.json'])
        self.assertEqual(plan['count'],0)

    def test_channels_and_binary_architectures_are_isolated(self):
        entries=m.entries()
        self.assertEqual(len(entries),14)
        for e in entries:
            ident=m.identity(e)
            self.assertEqual(ident['config']['arch'],'arm64')
            self.assertTrue(ident['channel'].startswith('windows/arm64/'))
            if not e['pure_python']:
                self.assertTrue(e['input']['name'].endswith('win_arm64.whl'))
            if e['backend']=='cuda':
                self.assertEqual(ident['config']['torch'],m.TORCH)
                self.assertIn('sm121',ident['channel'])

    def test_unrecognized_input_bytes_rejected_before_relabel(self):
        e=m.entries()[0]
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            (Path(directory)/e['input']['name']).write_bytes(b'not the pinned wheel')
            with patch.object(m,'entries',return_value=[e]), self.assertRaisesRegex(ValueError,'digest mismatch'):
                m.prepare(directory)

    def test_other_package_entry_does_not_change_fingerprint(self):
        e=m.entries()[0]
        before=m.identity(e)
        unrelated=dict(m.entries()[1],version='99.0')
        with patch.object(m,'entries',return_value=[e,unrelated]):
            self.assertEqual(before,m.identity(e))

    def test_new_input_bytes_change_identity(self):
        e=m.entries()[0]
        changed=dict(e,input=dict(e['input'],sha256='0'*64))
        self.assertNotEqual(m.identity(e)['fingerprint'],m.identity(changed)['fingerprint'])


if __name__=='__main__': unittest.main()
