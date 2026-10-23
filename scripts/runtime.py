"""Shared process setup for package-owned build adapters."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def run(args, cwd=None, env=None):
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True)


def context():
    parser = argparse.ArgumentParser()
    parser.add_argument('--context', required=True)
    return json.loads(Path(parser.parse_args().context).read_text(encoding='utf-8'))


def build_env(ctx):
    env = dict(os.environ)
    venv = Path(ctx['venv'])
    bin_dir = venv / ('Scripts' if os.name == 'nt' else 'bin')
    env['PATH'] = str(bin_dir) + os.pathsep + env.get('PATH', '')
    env['VIRTUAL_ENV'] = str(venv)
    env['MAX_JOBS'] = '4'
    if ctx['target']['backend'] == 'rocm':
        sdk = venv / 'Lib/site-packages/_rocm_sdk_core'
        env['PATH'] = str(sdk / 'bin') + os.pathsep + env['PATH']
        env['ROCM_HOME'] = env['ROCM_PATH'] = env['HIP_PATH'] = str(sdk)
        env['ROCM_DEVEL_INCLUDE'] = str(venv / 'Lib/site-packages/_rocm_sdk_devel/include')
    if ctx['target']['os'] == 'macos':
        env['MACOSX_DEPLOYMENT_TARGET'] = '11.0'
    lib_dir = Path(ctx['source']) / 'third_party/openfst_install/lib'
    env['DYLD_LIBRARY_PATH'] = str(lib_dir) + os.pathsep + env.get('DYLD_LIBRARY_PATH', '')
    env['PATH'] = str(lib_dir.parent / 'bin') + os.pathsep + str(lib_dir) + os.pathsep + env['PATH']
    return env
