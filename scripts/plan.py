"""Select targets by changed input paths, then skip verified published fingerprints."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

from core import ROOT, SHA, channel, fingerprint, input_files, load_targets, release_tag, wheel_version
from release_store import find_release, release_is_valid


def changed_files(base, head, root=ROOT):
    if not SHA.fullmatch(head):
        raise ValueError('head must be a full SHA')
    if not base or base == '0' * 40:
        return None  # Initial push: select every declared target.
    if not SHA.fullmatch(base):
        raise ValueError('base must be a full SHA')
    result = subprocess.check_output(['git', 'diff', '--name-only', '--no-renames', '-z', base, head], cwd=root)
    return [entry.decode('utf-8') for entry in result.split(b'\0') if entry]


def make_plan(root=ROOT, changed=None, package=None, target=None, force=False, lookup=None):
    items = load_targets(root)
    if package and package not in {item['package'] for item in items}:
        raise ValueError(f'Unknown package: {package}')
    if target and not any(item['target'] == target and (not package or item['package'] == package) for item in items):
        raise ValueError(f'Unknown target: {target}')
    tasks, skipped, blocked = [], [], []
    for item in items:
        if package and item['package'] != package:
            continue
        if target and item['target'] != target:
            continue
        if item['config'].get('enabled') is False:
            blocked.append({'package': item['package'], 'target': item['target'], 'reason': item['config']['reason']})
            continue
        inputs = input_files(root, item)
        # Path filtering is only an optimization. The fingerprint is authoritative.
        if changed is not None and not (package or target):
            package_prefix = f"packages/{item['package']}/"
            owned_change = any(name.startswith(package_prefix) and '/targets/' not in name
                               and not name.lower().endswith(('.md', '.rst')) for name in changed)
            if not owned_change and not set(changed).intersection(inputs):
                continue
        digest = fingerprint(root, item)
        entry = {'package': item['package'], 'target': item['target'], 'fingerprint': digest,
                 'tag': release_tag(item, digest), 'runner': item['config']['runner'],
                 'python': item['config']['python'], 'architecture': item['config']['arch'],
                 'version': wheel_version(item, digest), 'channel': channel(item)}
        published = lookup(entry['tag']) if lookup and not force else None
        if published and release_is_valid(published, entry):
            skipped.append({**entry, 'reason': 'Published fingerprint and release asset digests match'})
        else:
            tasks.append(entry)
    return {'schema': 1, 'matrix': {'include': tasks}, 'count': len(tasks), 'skipped': skipped, 'blocked': blocked}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate', action='store_true')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--package')
    parser.add_argument('--target')
    parser.add_argument('--base')
    parser.add_argument('--head')
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY'))
    parser.add_argument('--output', default='plan.json')
    args = parser.parse_args()
    if args.validate:
        for item in load_targets():
            fingerprint(ROOT, item)
        print('Recipes, source pins, target/toolchain bindings and inputs are valid')
        return
    changed = None if args.all or args.package or args.target else changed_files(args.base, args.head)
    if not args.offline and not args.repo:
        parser.error('--repo is required unless --offline is used')
    result = make_plan(changed=changed, package=args.package, target=args.target, force=args.force,
                       lookup=None if args.offline else lambda tag: find_release(args.repo, tag))
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    output = os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output, 'a', encoding='utf-8') as stream:
            stream.write('matrix=' + json.dumps(result['matrix'], separators=(',', ':')) + '\n')
            stream.write(f"count={result['count']}\n")
    print(f"Build {result['count']} target(s); reuse {len(result['skipped'])} published target(s)")
    for entry in result['matrix']['include']:
        print(f"  {entry['package']} / {entry['target']} / {entry['fingerprint'][:12]}")
    for entry in result['blocked']:
        print(f"Blocked: {entry['package']} / {entry['target']}: {entry['reason']}")


if __name__ == '__main__':
    main()
