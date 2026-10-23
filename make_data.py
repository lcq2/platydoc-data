#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build and publish standalone layout data. All compilation and checks are local."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / 'tools/layouts'
CACHE = ROOT / '.docs-cache/layouts'
DIST = ROOT / 'dist'
sys.path[:0] = [str(TOOLS), str(ROOT / 'tools')]

def read(path): return json.loads(path.read_bytes())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def run(*args):
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=ROOT, check=True)
def script(name, *args): run(sys.executable, TOOLS / name, *args)
def download(url, target, checksum):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and sha(target) == checksum: return
    pending = target.with_suffix('.download')
    try:
        with urllib.request.urlopen(url, timeout=120) as response, pending.open('wb') as output:
            shutil.copyfileobj(response, output)
        if sha(pending) != checksum: raise ValueError('Download checksum differs: ' + url)
        pending.replace(target)
    finally: pending.unlink(missing_ok=True)

def setup():
    """Explicit dependency download; never called by build/check/publish."""
    run('git', 'submodule', 'update', '--init')
    pins = read(TOOLS / 'toolchain.lock.json')
    for name, url, checksum in (
        ('llvm.tar.gz', pins['llvm']['archive_url'], pins['llvm']['archive_sha256']),
        ('emsdk.tar.gz', pins['emscripten']['emsdk_archive_url'], pins['emscripten']['emsdk_archive_sha256'])):
        download(url, CACHE / 'downloads' / name, checksum)
    sdk = CACHE / 'emsdk'
    if not sdk.exists():
        with tarfile.open(CACHE / 'downloads/emsdk.tar.gz') as archive:
            with tempfile.TemporaryDirectory(dir=CACHE) as temp:
                archive.extractall(temp, filter='data')
                source, = Path(temp).iterdir()
                shutil.move(str(source), sdk)
    version = pins['emscripten']['version']
    run(sys.executable, sdk / 'emsdk.py', 'install', version)
    run(sys.executable, sdk / 'emsdk.py', 'activate', version)

def compiler_current(compiler):
    path = compiler / 'toolchain-provenance.json'
    if not path.is_file(): return False
    provenance = read(path)
    return (all(provenance['inputs'].get(name) == sha(TOOLS / name) for name in ('engine.cpp', 'CMakeLists.txt', 'toolchain.lock.json', 'build.py')) and
            all((compiler / name).is_file() and sha(compiler / name) == value['sha256']
                for name, value in provenance['artifacts'].items()))

def input_identity():
    result = {}
    for base in (ROOT / 'tools', ROOT / 'inputs'):
        for path in sorted(base.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.name not in {'artifact-ios.lock.json', 'artifact.lock.json'}:
                result[path.relative_to(ROOT).as_posix()] = sha(path)
    result['make_data.py'] = sha(Path(__file__))
    for name in ('xnu', 'bootstrap_cmds'):
        result[name] = subprocess.check_output(['git', '-C', str(ROOT / name), 'rev-parse', 'HEAD'], text=True).strip()
        if subprocess.check_output(['git', '-C', str(ROOT / name), 'status', '--porcelain', '--untracked-files=all']).strip():
            raise ValueError(name + ' source checkout must be clean')
    return result


def build(args):
    from catalog import generate, inventory, encoded, digest, seal, write_json
    CACHE.mkdir(parents=True, exist_ok=True)
    compiler = CACHE / 'compiler'
    identity = input_identity()
    receipt = CACHE / 'build-receipt.json'
    archive = DIST / 'prepared-layouts.tar.gz'
    if receipt.is_file() and archive.is_file() and compiler_current(compiler):
        previous = read(receipt)
        if previous.get('inputs') == identity and previous.get('archive_sha256') == sha(archive):
            print('Layout inputs unchanged; reusing ' + str(archive))
            return
    build_cache = args.compiler_cache or CACHE / 'compiler-build'
    llvm_archive = args.llvm_archive or CACHE / 'downloads/llvm.tar.gz'
    emsdk_archive = args.emsdk_archive or CACHE / 'downloads/emsdk.tar.gz'
    emsdk = args.emsdk or CACHE / 'emsdk'
    if not compiler_current(compiler):
        # Activation refreshes SDK paths after this checkout is moved. No download.
        run(sys.executable, emsdk / 'emsdk.py', 'activate', read(TOOLS / 'toolchain.lock.json')['emscripten']['version'])
        script('build.py', '--llvm-archive', llvm_archive, '--emsdk', emsdk,
               '--emsdk-archive', emsdk_archive, '--cache', build_cache,
               '--artifact-output', compiler, '--jobs', args.jobs)
    llvm_source = build_cache / 'llvm-source'
    if not llvm_source.exists():
        from build import extract
        extract(llvm_archive, llvm_source, read(TOOLS / 'toolchain.lock.json')['llvm']['archive_sha256'])
    native = compiler / 'build-native/bin/layout-engine'
    wasm = compiler / 'build-wasm/bin/layout-engine.js'
    configs, bundles, runtime = (CACHE / name for name in ('configs', 'bundles', 'runtime'))
    comparison = CACHE / 'comparison.json'
    script('generate_configs.py', '--platform', 'iPhoneOS', '--output', configs)
    script('generate_sysproto.py')
    script('generate_mig.py')
    script('survey_catalog.py', '--native', native, '--config-root', configs,
           '--llvm-source', build_cache / 'llvm-source', '--output', bundles)
    reuse = ['--reuse-report', comparison] if comparison.is_file() else []
    script('tests/compare_catalog.py', '--bundles', bundles, '--native', native,
           '--wasm', wasm, '--output', comparison, *reuse)
    script('package_catalog_runtime.py', '--native', native, '--wasm', wasm,
           '--native-report', comparison, '--bundles', bundles, '--config-root', configs,
           '--notices', compiler / 'notices', '--provenance', compiler / 'toolchain-provenance.json',
           '--llvm-source', build_cache / 'llvm-source', '--output', runtime)
    package, manifest = read(runtime / 'manifest.json'), read(runtime / 'runtime-manifest.json')
    snapshot = inventory(ROOT / 'xnu')
    pin = {'contract': 'platydoc.layout-artifact-lock', 'version': 2, 'source': package['source'],
           'source_inventory': {'algorithm': 'sha256-canonical-json-path-hashes-v1',
                                'files': len(snapshot), 'sha256': digest(encoded(snapshot))},
           'platform': 'iPhoneOS', 'profile_spec': 'profiles/ios-catalog.json',
           'inventory': 'profiles/structure-catalog.json',
           'expected_profiles': [p['id'] for p in manifest['profiles']], 'compiler': manifest['compiler'],
           'native_sha256': sha(native), 'runtime_manifest_sha256': sha(runtime / 'runtime-manifest.json'),
           'runtime_package_manifest_sha256': sha(runtime / 'manifest.json'),
           'config_provenance_sha256': sha(runtime / 'config-provenance.json')}
    write_json(TOOLS / 'artifact-ios.lock.json', pin)
    DIST.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.package-', dir=DIST) as temp:
        output = Path(temp) / 'layouts'
        generate(output, None, CACHE / 'common-profiles', runtime, native, configs)
        write_json(output / 'data-package.json', {'format': 'platydoc.layout-data', 'version': 1,
            'source': package['source'], 'reader_api': 1})
        seal(output)
        from prepared import export
        export(output, DIST / 'prepared-layouts.tar.gz')
    check()
    if input_identity() != identity: raise ValueError('Producer inputs changed during generation')
    write_json(receipt, {'inputs': identity, 'archive_sha256': sha(archive)})

def check():
    """Check shipped files and recorded native/Wasm parity without rerunning the compiler."""
    from prepared import unpack
    archive = DIST / 'prepared-layouts.tar.gz'
    with tempfile.TemporaryDirectory(prefix='platydoc-data-check-') as temp:
        output = Path(temp) / 'layouts'
        unpack(archive, output)
        manifest = read(output / 'manifest.json')
        names = {p.relative_to(output).as_posix() for p in output.rglob('*')
                 if p.is_file() and p.name != 'manifest.json'}
        if names != set(manifest['files']): raise ValueError('Package membership differs')
        for name, identity in manifest['files'].items():
            path = output / name
            if path.stat().st_size != identity['bytes'] or sha(path) != identity['sha256']:
                raise ValueError('Package file differs: ' + name)
        from catalog import validate_coverage_package
        validate_coverage_package(output, read(output / 'runtime-manifest.json'), read(output / 'bundle-manifest.json'))
        print('Package integrity and native/Wasm evidence passed.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    subs.add_parser('setup', help='Initialize pinned submodules and download/install pinned compiler dependencies')
    p = subs.add_parser('build', help='Build compiler as needed, generate headers/layouts, compare native/Wasm and package')
    p.add_argument('--jobs', type=int, default=min(os.cpu_count() or 2, 16))
    for name in ('compiler-cache', 'llvm-archive', 'emsdk', 'emsdk-archive'):
        p.add_argument('--' + name, type=Path)
    subs.add_parser('check', help='Check the existing package without rebuilding')
    p = subs.add_parser('publish', help='Upload the checked package; never build during publication')
    p.add_argument('--repo', default='lcq2/platydoc-data')
    args = parser.parse_args()
    if args.command == 'setup': setup()
    elif args.command == 'build': build(args)
    elif args.command == 'check': check()
    else:
        check()
        from prepared import publish
        publish(args.repo, DIST / 'prepared-layouts.release.json', archive=DIST / 'prepared-layouts.tar.gz')
        tag = read(DIST / 'prepared-layouts.release.json')['tag']
        print('Select in Platydoc: python3 make_docs.py --update-data ' + tag + ' --data-repo ' + args.repo)

if __name__ == '__main__': main()
