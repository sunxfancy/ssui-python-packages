"""Regenerate a cumulative channel-isolated Simple API from immutable releases."""
import argparse
import html
import json
import os
from pathlib import Path
import re
from urllib.parse import quote

from release_store import find_release, gh, release_is_valid


def write_site(records, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    channels = {}
    for manifest, assets in records:
        channel = manifest['channel']
        if any(not re.fullmatch(r'[a-zA-Z0-9._-]+', part) or part in ('.', '..') for part in channel.split('/')):
            raise ValueError('Unsafe index channel')
        package = re.sub(r'[-_.]+', '-', manifest['package']).lower()
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', package):
            raise ValueError('Unsafe package name')
        links = channels.setdefault(channel, {}).setdefault(package, [])
        for file in manifest['files']:
            if not file['name'].endswith('.whl'):
                continue
            asset = next(a for a in assets if a['name'] == file['name'])
            url = asset['browser_download_url'] + '#sha256=' + file['sha256']
            links.append(f'<a href="{html.escape(url, quote=True)}">{html.escape(file["name"])}</a>')
    for channel, packages in channels.items():
        directory = output / 'simple' / channel
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'index.html').write_text('<!DOCTYPE html>\n' + '\n'.join(
            f'<a href="{quote(name)}/">{html.escape(name)}</a>' for name in sorted(packages)) + '\n', encoding='utf-8')
        for name, links in packages.items():
            package_dir = directory / name
            package_dir.mkdir(exist_ok=True)
            (package_dir / 'index.html').write_text('<!DOCTYPE html>\n' + '\n'.join(sorted(set(links))) + '\n', encoding='utf-8')
    (output / 'index.html').write_text('<!DOCTYPE html><h1>SSUI Python Packages</h1>\n'
        '<p>Choose a channel matching your OS, architecture, compute backend, toolkit, PyTorch ABI and GPU architecture. Hosted builds do not verify GPU kernels.</p>\n'
        + '\n'.join(f'<p><a href="simple/{quote(name, safe="/")}/">{html.escape(name)}</a></p>' for name in sorted(channels)), encoding='utf-8')
    (output / '.nojekyll').write_text('', encoding='utf-8')
    (output / 'catalog.json').write_text(json.dumps([m for m, _ in records], indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY'), required=not os.environ.get('GITHUB_REPOSITORY'))
    parser.add_argument('--output', default='.work/site')
    args = parser.parse_args()
    pages = json.loads(gh('api', f'repos/{args.repo}/releases?per_page=100', '--paginate', '--slurp').stdout)
    records = []
    for release in (release for page in pages for release in page):
        if release['draft'] or not any(a['name'] == 'release.json' for a in release['assets']):
            continue
        value = find_release(args.repo, release['tag_name'])
        manifest = value.get('manifest')
        if manifest and release_is_valid(value, manifest):
            records.append((manifest, release['assets']))
        else:
            # Do not silently replace a healthy index with an incomplete subset.
            raise ValueError(f'Published release failed verification: {release["tag_name"]}')
    write_site(records, args.output)
    print(f'Indexed {len(records)} independently published target build(s)')


if __name__ == '__main__':
    main()
