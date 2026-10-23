"""Validated recipes and fingerprints of declared build inputs (stdlib only)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SLUG = re.compile(r'^[a-z0-9][a-z0-9._-]*$')
SHA = re.compile(r'^[a-f0-9]{40}$')
RUNNERS = {'windows-2022', 'macos-15'}
BUILD_INPUTS = ['scripts/core.py', 'scripts/build.py', 'scripts/runtime.py',
                'scripts/verify.py', '.github/workflows/build-wheel.yml']


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def inside(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f'Path escapes repository: {relative}')
    return path


def load_targets(root=ROOT):
    root = Path(root)
    targets = []
    for recipe_path in sorted((root / 'packages').glob('*/recipe.json')):
        recipe = read_json(recipe_path)
        package = recipe_path.parent.name
        if not SLUG.fullmatch(package) or recipe['name'] != package:
            raise ValueError(f'Invalid package: {package}')
        if not SHA.fullmatch(recipe['source']['commit']):
            raise ValueError(f'{package}: source must use a full commit SHA')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', recipe['source']['repository']):
            raise ValueError('Invalid source repository')
        if not isinstance(recipe['revision'], int) or recipe['revision'] < 1:
            raise ValueError('revision must be a positive integer')
        if not re.fullmatch(r'[0-9][a-zA-Z0-9.]*', recipe['version']):
            raise ValueError('Invalid upstream version')
        if not list((recipe_path.parent / 'targets').glob('*.json')):
            raise ValueError(f'{package}: no targets')
        for target_path in sorted((recipe_path.parent / 'targets').glob('*.json')):
            target = read_json(target_path)
            target_id = target_path.stem
            if not SLUG.fullmatch(target_id) or target['runner'] not in RUNNERS:
                raise ValueError(f'Invalid target: {target_id}')
            if target['os'] not in ('windows', 'macos', 'linux') or target['arch'] not in ('x64', 'arm64'):
                raise ValueError('Invalid OS or architecture')
            if target['backend'] not in ('cpu', 'cuda', 'rocm', 'mps', 'qnn'):
                raise ValueError('Invalid compute backend')
            if not re.fullmatch(r'3\.\d+', target['python']):
                raise ValueError('Python must be a major.minor version')
            if not SLUG.fullmatch(target['toolchain']):
                raise ValueError('Invalid toolchain')
            tool_path = inside(root, f"toolchains/{target['toolchain']}.json")
            toolchain = read_json(tool_path)
            if toolchain['os'] != target['os'] or toolchain['arch'] != target['arch']:
                raise ValueError('Target and toolchain OS/arch disagree')
            if toolchain['backend'] != target['backend']:
                raise ValueError('Target and toolchain backend disagree')
            if recipe.get('build_dependencies'):
                raise ValueError('Cross-package build dependencies require an explicit planner implementation')
            for script in ('build.py', 'smoke_test.py'):
                if not (recipe_path.parent / script).is_file():
                    raise ValueError(f'{package}: missing {script}')
            targets.append({'package': package, 'target': target_id, 'recipe': recipe,
                            'config': target, 'toolchain': toolchain})
    if not targets:
        raise ValueError('No package recipes')
    return targets


def input_files(root, item):
    root = Path(root)
    files = set(BUILD_INPUTS)
    package_root = root / 'packages' / item['package']
    for path in package_root.rglob('*'):
        rel = path.relative_to(root).as_posix()
        if path.is_file() and '__pycache__' not in path.parts and 'targets' not in path.relative_to(package_root).parts:
            # Documentation does not influence a wheel.
            if path.suffix.lower() not in ('.md', '.rst'):
                files.add(rel)
    files.add(f"packages/{item['package']}/targets/{item['target']}.json")
    files.add(f"toolchains/{item['config']['toolchain']}.json")
    for relative in item['toolchain']['inputs']:
        files.add(relative)
    for relative in sorted(files):
        if not inside(root, relative).is_file():
            raise ValueError(f'Missing input: {relative}')
    return sorted(files)


def fingerprint(root, item):
    inputs = {name: sha256(inside(root, name)) for name in input_files(root, item)}
    return hashlib.sha256(canonical({'schema': 1, 'inputs': inputs})).hexdigest()


def wheel_version(item, digest=None):
    cfg, recipe = item['config'], item['recipe']
    label = ['ssui', cfg['backend']]
    for key in ('sdk', 'torch', 'gpu_arch'):
        if cfg.get(key):
            label.append(re.sub(r'[^a-z0-9]', '', str(cfg[key]).lower()))
    label.append(f"r{recipe['revision']}")
    if digest:
        label.append('b' + digest[:12])
    return recipe['version'] + '+' + '.'.join(label)


def release_tag(item, digest):
    return f"{item['package']}-{item['recipe']['version']}-r{item['recipe']['revision']}--{item['target']}--{digest[:20]}"


def channel(item):
    cfg = item['config']
    parts = [cfg['os'], cfg['arch'], cfg['backend']]
    parts.extend(str(cfg[key]) for key in ('sdk', 'torch', 'gpu_arch') if cfg.get(key))
    return '/'.join(parts)
