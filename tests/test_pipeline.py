import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core import fingerprint, input_files, load_targets, release_tag, wheel_version
from plan import make_plan
from release_store import release_is_valid
from verify import relabel, verify_wheel


class PipelineTests(unittest.TestCase):
    def setUp(self):
        temp_parent = ROOT / '.work' / 'tests'
        temp_parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='ssui-wheel-tests-', dir=temp_parent)
        self.root = Path(self.temp.name).resolve()
        # The only recursive cleanup target is this freshly-created temp directory.
        self.assertTrue(self.root.is_relative_to(temp_parent.resolve()))
        self.addCleanup(self.temp.cleanup)
        for name in ['packages', 'toolchains', 'scripts', '.github']:
            shutil.copytree(ROOT / name, self.root / name, ignore=shutil.ignore_patterns('__pycache__'))

    def item(self, name='pynini', target=None):
        return next(i for i in load_targets(self.root) if i['package'] == name and (target is None or i['target'] == target))

    def change(self, name, text='\n# changed\n'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(text)

    def test_all_enabled_targets_selected(self):
        self.assertEqual(make_plan(self.root)['count'], sum(i['config'].get('enabled', True) for i in load_targets(self.root)))

    def test_package_change_selects_only_its_targets(self):
        plan = make_plan(self.root, changed=['packages/cumesh/build.py'])
        self.assertEqual([i['package'] for i in plan['matrix']['include']], ['cumesh'])

    def test_target_change_selects_one_variant(self):
        plan = make_plan(self.root, changed=['packages/pynini/targets/windows-x64-cp312-cpu.json'])
        self.assertEqual([i['target'] for i in plan['matrix']['include']], ['windows-x64-cp312-cpu'])

    def test_gpu_toolchain_only_affects_gpu_packages(self):
        plan = make_plan(self.root, changed=['toolchains/windows-x64-rocm721.json'])
        expected = {i['package'] for i in load_targets(self.root)
                    if i['config']['toolchain'] == 'windows-x64-rocm721'}
        self.assertEqual({i['package'] for i in plan['matrix']['include']}, expected)

    def test_rocm_migration_selects_no_cpu_or_other_package_targets(self):
        names = {'cumesh', 'flex-gemm', 'o-voxel', 'natten', 'nvdiffrast',
                 'torch-cluster', 'torch-scatter', 'diso'}
        for name in names:
            with self.subTest(package=name):
                plan = make_plan(self.root, changed=[f'packages/{name}/build.py'])
                self.assertEqual({i['package'] for i in plan['matrix']['include']}, {name})
                self.assertEqual({i['target'] for i in plan['matrix']['include']},
                                 {'windows-x64-cp312-rocm721-gfx1201'})

    def test_shared_build_input_affects_every_target(self):
        self.assertEqual(make_plan(self.root, changed=['scripts/build.py'])['count'], make_plan(self.root)['count'])

    def test_docs_and_planning_code_do_not_build(self):
        self.assertEqual(make_plan(self.root, changed=['README.md', 'scripts/plan.py', 'tests/test_pipeline.py', 'packages/pynini/README.md'])['count'], 0)

    def test_deleted_patch_selects_owner(self):
        result = make_plan(self.root, changed=['packages/cumesh/patches/removed.patch'])
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['matrix']['include'][0]['package'], 'cumesh')

    def test_other_package_does_not_change_fingerprint(self):
        item = self.item()
        before = fingerprint(self.root, item)
        self.change('packages/cumesh/build.py')
        self.assertEqual(before, fingerprint(self.root, item))

    def test_other_variant_does_not_change_fingerprint(self):
        item = self.item(target='macos-arm64-cp312-cpu')
        before = fingerprint(self.root, item)
        self.change('packages/pynini/targets/windows-x64-cp312-cpu.json', '\n')
        self.assertEqual(before, fingerprint(self.root, item))

    def test_build_script_change_changes_owner_fingerprint(self):
        item = self.item()
        before = fingerprint(self.root, item)
        self.change('packages/pynini/build.py')
        self.assertNotEqual(before, fingerprint(self.root, item))

    def test_shared_build_change_changes_fingerprint(self):
        item = self.item()
        before = fingerprint(self.root, item)
        self.change('scripts/runtime.py')
        self.assertNotEqual(before, fingerprint(self.root, item))

    def test_planner_edit_does_not_change_fingerprint(self):
        item = self.item()
        before = fingerprint(self.root, item)
        self.change('scripts/plan.py')
        self.assertEqual(before, fingerprint(self.root, item))

    def test_publication_and_index_edits_do_not_recompile_wheels(self):
        item = self.item()
        before = fingerprint(self.root, item)
        self.change('scripts/publish.py')
        self.change('.github/workflows/index.yml', '\n')
        self.assertEqual(before, fingerprint(self.root, item))
        self.assertEqual(make_plan(self.root, changed=['scripts/publish.py', '.github/workflows/index.yml'])['count'], 0)

    def test_docs_edit_does_not_change_fingerprint(self):
        item = self.item()
        before = fingerprint(self.root, item)
        self.change('packages/pynini/README.md')
        self.assertEqual(before, fingerprint(self.root, item))

    def test_pin_change_changes_package_not_other_package(self):
        recipe = self.root / 'packages/pynini/recipe.json'
        other = self.item('cumesh')
        other_hash = fingerprint(self.root, other)
        before = fingerprint(self.root, self.item())
        data = json.loads(recipe.read_text())
        data['source']['commit'] = 'a' * 40
        recipe.write_text(json.dumps(data))
        self.assertNotEqual(before, fingerprint(self.root, self.item()))
        self.assertEqual(other_hash, fingerprint(self.root, other))

    def test_floating_source_ref_rejected(self):
        recipe = self.root / 'packages/pynini/recipe.json'
        data = json.loads(recipe.read_text())
        data['source']['commit'] = 'main'
        recipe.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            load_targets(self.root)

    def test_unknown_package_or_target_rejected(self):
        with self.assertRaises(ValueError):
            make_plan(self.root, package='typo')
        with self.assertRaises(ValueError):
            make_plan(self.root, target='typo')

    def published(self, entry):
        file = {'name': 'example.whl', 'size': 42, 'sha256': 'a' * 64}
        return {'release': {'draft': False, 'assets': [
            {'name': 'release.json', 'size': 100},
            {'name': file['name'], 'size': file['size'], 'digest': 'sha256:' + file['sha256']} ]},
            'manifest': {**entry, 'schema': 1, 'checks': {'smoke': 'passed'}, 'files': [file]}}

    def test_existing_fingerprint_and_asset_digests_skip_build(self):
        first = make_plan(self.root, package='cumesh')['matrix']['include'][0]
        result = make_plan(self.root, package='cumesh', lookup=lambda _: self.published(first))
        self.assertEqual(result['count'], 0)
        self.assertEqual(len(result['skipped']), 1)

    def test_force_bypasses_skip(self):
        first = make_plan(self.root, package='cumesh')['matrix']['include'][0]
        self.assertEqual(make_plan(self.root, package='cumesh', force=True, lookup=lambda _: self.published(first))['count'], 1)

    def test_missing_asset_never_skips(self):
        entry = make_plan(self.root, package='cumesh')['matrix']['include'][0]
        published = self.published(entry)
        published['release']['assets'].pop()
        self.assertFalse(release_is_valid(published, entry))

    def test_bad_digest_never_skips(self):
        entry = make_plan(self.root, package='cumesh')['matrix']['include'][0]
        published = self.published(entry)
        published['release']['assets'][1]['digest'] = 'sha256:' + 'b' * 64
        self.assertFalse(release_is_valid(published, entry))

    def test_incomplete_draft_never_skips(self):
        entry = make_plan(self.root, package='cumesh')['matrix']['include'][0]
        published = self.published(entry)
        published['release']['draft'] = True
        self.assertFalse(release_is_valid(published, entry))

    def test_wrong_target_or_fingerprint_never_skips(self):
        entry = make_plan(self.root, package='cumesh')['matrix']['include'][0]
        for key in ('target', 'fingerprint', 'channel', 'version', 'package'):
            published = self.published(entry)
            published['manifest'][key] = 'wrong'
            self.assertFalse(release_is_valid(published, entry))

    def test_no_successful_smoke_never_skips(self):
        entry = make_plan(self.root, package='cumesh')['matrix']['include'][0]
        published = self.published(entry)
        published['manifest']['checks']['smoke'] = 'failed'
        self.assertFalse(release_is_valid(published, entry))

    def test_relabel_updates_metadata_filename_and_record(self):
        item = self.item(target='windows-x64-cp312-cpu')
        original = self.root / 'pynini-2.1.6.post1-cp312-cp312-win_amd64.whl'
        with zipfile.ZipFile(original, 'w') as wheel:
            wheel.writestr('pynini/__init__.py', '# synthetic fixture\n')
            wheel.writestr('_pynini.cp312-win_amd64.pyd', b'synthetic native fixture')
            wheel.writestr('pynini-2.1.6.post1.dist-info/METADATA', 'Metadata-Version: 2.1\nName: pynini\nVersion: 2.1.6.post1\n\n')
            wheel.writestr('pynini-2.1.6.post1.dist-info/RECORD', '')
        output = relabel(original, wheel_version(item), self.root / 'out')
        verify_wheel(output, item, wheel_version(item))
        with zipfile.ZipFile(output) as archive:
            self.assertFalse(any(name.startswith('pynini-2.1.6.post1.dist-info') for name in archive.namelist()))

    def test_toolchain_binding_rejects_wrong_architecture(self):
        target = self.root / 'packages/pynini/targets/windows-x64-cp312-cpu.json'
        data = json.loads(target.read_text())
        data['arch'] = 'arm64'
        target.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            load_targets(self.root)

    def test_release_names_are_per_package_and_target(self):
        tags = [release_tag(item, fingerprint(self.root, item)) for item in load_targets(self.root)]
        self.assertEqual(len(tags), len(set(tags)))


if __name__ == '__main__':
    unittest.main()
