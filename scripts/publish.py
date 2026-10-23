"""Publish one immutable release, independently of other matrix targets."""
import argparse
import json
import os
from pathlib import Path
import time

from core import ROOT, channel, fingerprint, load_targets, release_tag, sha256, wheel_version
from release_store import find_release, gh, release_is_valid
from verify import verify_wheel


def validate_bundle(directory, item, expected_fingerprint, root=ROOT):
    directory = Path(directory)
    manifest = json.loads((directory / 'release.json').read_text(encoding='utf-8'))
    expected = {'package': item['package'], 'target': item['target'],
                'fingerprint': expected_fingerprint, 'version': wheel_version(item, expected_fingerprint), 'channel': channel(item)}
    if fingerprint(root, item) != expected_fingerprint:
        raise ValueError('Publisher checkout differs from planned build inputs')
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f'Unexpected release manifest {key}')
    if manifest.get('source') != item['recipe']['source'] or manifest.get('config') != item['config']:
        raise ValueError('Release provenance does not match source/target recipe')
    if manifest.get('schema') != 1 or manifest.get('checks', {}).get('smoke') != 'passed':
        raise ValueError('Build/smoke checks did not pass')
    files = manifest.get('files', [])
    if not files or len({entry['name'] for entry in files}) != len(files):
        raise ValueError('Invalid release file list')
    for entry in files:
        if Path(entry['name']).name != entry['name'] or entry['name'] == 'release.json':
            raise ValueError('Unsafe release filename')
        path = directory / entry['name']
        if not path.is_file() or path.stat().st_size != entry['size'] or sha256(path) != entry['sha256']:
            raise ValueError('Release file digest mismatch')
    if set(path.name for path in directory.iterdir()) != {'release.json', *(entry['name'] for entry in files)}:
        raise ValueError('Unexpected release files')
    wheels = [directory / entry['name'] for entry in files if entry['name'].endswith('.whl')]
    if len(wheels) != 1:
        raise ValueError('Expected one independently published package wheel')
    verify_wheel(wheels[0], item, expected['version'])
    return manifest, expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--fingerprint', required=True)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY'), required=not os.environ.get('GITHUB_REPOSITORY'))
    args = parser.parse_args()
    # Publishing consumes only successful bundles from the same trusted main run.
    if os.environ.get('GITHUB_ACTIONS') == 'true' and (
        os.environ.get('GITHUB_REF') != 'refs/heads/main' or os.environ.get('GITHUB_EVENT_NAME') == 'pull_request'
    ):
        raise ValueError('Only trusted main builds may publish')
    item = next(i for i in load_targets() if i['package'] == args.package and i['target'] == args.target)
    directory = Path(args.directory).resolve()
    manifest, expected = validate_bundle(directory, item, args.fingerprint)
    tag = release_tag(item, args.fingerprint)
    existing = find_release(args.repo, tag)
    if existing:
        if release_is_valid(existing, expected) and existing['manifest']['files'] == manifest['files']:
            print('Identical immutable release already exists:', tag)
            gh('api', '--method', 'POST', f'repos/{args.repo}/dispatches', '-f', 'event_type=wheel-published')
            return
        raise ValueError(f'Release {tag} already exists with different/incomplete assets; never overwrite it. Bump recipe revision to publish a new build.')
    notes = directory.parent / 'release-notes.txt'
    notes.write_text(f"Package: {item['package']}\nTarget: {item['target']}\nVersion: {expected['version']}\n"
                     f"Fingerprint: {args.fingerprint}\nSource: {json.dumps(item['recipe']['source'], sort_keys=True)}\n"
                     f"Validation: {manifest['checks']['smoke_kind']}\nGPU runtime test: NOT RUN (hosted CPU runner)\n"
                     f"Limitations: {json.dumps(manifest.get('limitations', []))}\n"
                     'See release.json for checksums and exact build provenance.\n', encoding='utf-8')
    gh('release', 'create', tag, '--repo', args.repo, '--draft', '--target', os.environ.get('GITHUB_SHA', 'main'),
       '--title', f"{item['package']} {expected['version']} ({item['target']})", '--notes-file', str(notes))
    gh('release', 'upload', tag, '--repo', args.repo, *[str(path) for path in sorted(directory.iterdir())])
    gh('release', 'edit', tag, '--repo', args.repo, '--draft=false', '--latest=false')
    for _ in range(10):
        if release_is_valid(find_release(args.repo, tag), expected):
            print('Published and verified:', tag)
            # repository_dispatch is intentionally allowed to trigger another
            # workflow with GITHUB_TOKEN. It needs only contents:write.
            gh('api', '--method', 'POST', f'repos/{args.repo}/dispatches', '-f', 'event_type=wheel-published')
            return
        time.sleep(2)
    raise RuntimeError('Release published but asset digest verification is not yet available; inspect release before retrying')


if __name__ == '__main__':
    main()
