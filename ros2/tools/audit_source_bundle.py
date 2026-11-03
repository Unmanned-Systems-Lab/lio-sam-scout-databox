#!/usr/bin/env python3
"""Check a Scout ROS 2 source bundle using Python's standard library.

The default workspace is the parent of this tools directory. A Git checkout is
not required: hashes also work for a downloaded source archive. If a Git index
is available, gitlinks below this workspace are checked as well. Build outputs
are excluded; this command never imports ROS, executes source, or changes files.

Component hashes match SOURCE_VERSIONS.json: sort relative POSIX path components,
then SHA256-update each UTF-8 relative path, NUL, and raw SHA256 of that file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath


IGNORED_DIRECTORIES = {
    'build', 'install', 'log', 'logs', '.deps', 'deps', 'validation', 'maps',
    'mapping_reviews', '__pycache__', '.pytest_cache', '.venv',
}
CODE_SUFFIXES = {
    '.bash', '.sh', '.py', '.cmake', '.in', '.yaml', '.yml', '.xml', '.xacro',
    '.urdf', '.rviz', '.desktop', '.cfg', '.json', '.h', '.hpp', '.c', '.cc',
    '.cpp', '.cxx',
}
DEFAULT_FORBIDDEN_ROOTS = (
    '/mnt/nvme0n1/autoware',
    '/media/agx',
    '/home/agx/autoware',
    '/home/agx/ele_scout_kit',
    '/home/agx/sample_sensor_kit_launch_for_scout',
    r'C:\scout_autoware',
    'C:/scout_autoware',
)
LIBRARY_SUFFIXES = {'.a', '.lib', '.dll', '.dylib', '.pyd', '.o'}
SDK_BINARY_SUFFIXES = {'.run', '.deb', '.rpm', '.appimage', '.onnx', '.engine', '.model2', '.plan'}
MACH_O_MAGICS = {
    b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe',
    b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe',
    b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca',
    b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca',
}


class Audit:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.errors: list[str] = []
        self.notes: list[str] = []
        self.components: list[dict] = []
        self.source_files_scanned = 0
        self.git_index_checked = False

    def label(self, path: Path) -> str:
        try:
            return path.relative_to(self.workspace).as_posix()
        except ValueError:
            return str(path)

    def fail(self, message: str) -> None:
        self.errors.append(message)


def collect_files(root: Path, audit: Audit) -> list[Path]:
    """Walk without following symlinks or entering runtime-output directories."""
    result: list[Path] = []

    def walk_error(error: OSError) -> None:
        audit.fail(f'Cannot scan source directory: {error}')

    for directory, names, files in os.walk(root, followlinks=False, onerror=walk_error):
        current = Path(directory)
        kept = []
        for name in names:
            path = current / name
            if name in IGNORED_DIRECTORIES:
                continue
            if path.is_symlink():
                audit.fail(f'Unmaterialized source symlink: {audit.label(path)}')
                continue
            if name.startswith('.git'):
                # Return metadata directory entries for the metadata audit, but
                # never descend into object stores or nested repositories.
                result.append(path)
                continue
            kept.append(name)
        names[:] = kept
        for name in files:
            path = current / name
            if path.is_symlink():
                audit.fail(f'Unmaterialized source symlink: {audit.label(path)}')
                continue
            if path.is_file():
                result.append(path)
    return result


def file_digest(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.digest()


def load_components(manifest: Path, audit: Audit) -> list[tuple[dict, Path]]:
    try:
        data = json.loads(manifest.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        audit.fail(f'Cannot read source-version manifest: {error}')
        return []
    components = data.get('components') if isinstance(data, dict) else None
    if not isinstance(components, list) or not components:
        audit.fail('SOURCE_VERSIONS.json must contain a nonempty components list')
        return []
    result = []
    seen = set()
    for item in components:
        if not isinstance(item, dict):
            audit.fail('Invalid component entry: expected an object')
            continue
        name = item.get('path')
        if not isinstance(name, str) or '\\' in name:
            audit.fail(f'Invalid component path: {name!r}')
            continue
        relative = PurePosixPath(name)
        if (relative.is_absolute() or '..' in relative.parts
                or not relative.parts or relative.parts[0] not in {'src', 'third_party'}):
            audit.fail(f'Component path must stay under src/ or third_party/: {name}')
            continue
        if name in seen:
            audit.fail(f'Duplicate component path: {name}')
            continue
        seen.add(name)
        path = audit.workspace.joinpath(*relative.parts)
        if not path.is_dir() or path.is_symlink():
            audit.fail(f'Missing component directory or source symlink: {name}')
            continue
        if not path.resolve().is_relative_to(audit.workspace):
            audit.fail(f'Component resolves outside this workspace: {name}')
            continue
        count, digest = item.get('files'), item.get('source_tree_sha256')
        if (not isinstance(count, int) or isinstance(count, bool) or count < 0
                or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', digest)):
            audit.fail(f'Invalid file count or SHA256 for component: {name}')
            continue
        result.append((item, path))
    return result


def audit_component_hashes(components: list[tuple[dict, Path]], audit: Audit) -> None:
    for item, root in components:
        files = collect_files(root, audit)
        # Use case-sensitive path components on every OS. This reproduces
        # sorted(PosixPath objects) used by the Linux source-version generator.
        files.sort(key=lambda path: path.relative_to(root).parts)
        digest = hashlib.sha256()
        regular_files = []
        for path in files:
            if path.name.startswith('.git'):
                audit.fail(f'Vendored Git metadata: {audit.label(path)}')
            if not path.is_file():
                continue
            try:
                child_digest = file_digest(path)
            except OSError as error:
                audit.fail(f'Cannot hash {audit.label(path)}: {error}')
                continue
            regular_files.append(path)
            digest.update(path.relative_to(root).as_posix().encode('utf-8') + b'\0')
            digest.update(child_digest)
        actual = digest.hexdigest()
        expected = item['source_tree_sha256'].lower()
        count = len(regular_files)
        good = count == item['files'] and actual == expected
        audit.components.append({'path': item['path'], 'files': count,
                                 'expected_files': item['files'], 'sha256': actual,
                                 'expected_sha256': expected, 'ok': good})
        if count != item['files']:
            audit.fail(f"File count mismatch for {item['path']}: expected {item['files']}, found {count}")
        if actual != expected:
            audit.fail(f"SHA256 mismatch for {item['path']}: expected {expected}, found {actual}")


def audit_source_files(paths: list[Path], forbidden_roots: list[str], audit: Audit) -> None:
    own_script = Path(__file__).resolve()
    sdk_docs = audit.workspace / 'third_party' / 'zed_sdk'
    for path in paths:
        label = audit.label(path)
        if path.name in {'.git', '.gitmodules'}:
            audit.fail(f'Nested Git repository or submodule metadata: {label}')
        if not path.is_file():
            continue
        audit.source_files_scanned += 1
        try:
            with path.open('rb') as stream:
                header = stream.read(160)
                magic = header[:8]
        except OSError as error:
            audit.fail(f'Cannot inspect {label}: {error}')
            continue
        reason = None
        if header.startswith(b'version https://git-lfs.github.com/spec/v1'):
            reason = 'unresolved Git LFS pointer, missing source asset'
        elif magic.startswith(b'\x7fELF'):
            reason = 'ELF executable/object/shared library'
        elif magic == b'!<arch>\n':
            reason = 'precompiled ar library/archive'
        elif magic.startswith(b'MZ'):
            reason = 'Windows executable/library'
        elif magic[:4] in MACH_O_MAGICS:
            reason = 'Mach-O executable/library or precompiled bytecode'
        elif path.suffix.lower() in LIBRARY_SUFFIXES or re.search(r'\.so(?:\.\d+)*$', path.name, re.I):
            reason = 'precompiled-library filename'
        elif re.search(r'zed[_-]?sdk.*\.(?:run|zip|zstd|deb|rpm)$', path.name, re.I):
            reason = 'ZED SDK binary installer/archive'
        elif re.search(r'\.model2(?:_|\.|$)', path.name, re.I):
            reason = 'SDK optimized model cache'
        elif path.is_relative_to(sdk_docs) and (
                path.suffix.lower() in SDK_BINARY_SUFFIXES
                or re.search(r'\.model2(?:_|\.|$)', path.name, re.I)):
            reason = 'SDK installer/model binary'
        if reason:
            audit.fail(f'Binary artifact ({reason}): {label}')

        # Historical Markdown, patches, datasets, meshes and images are not
        # deployment code. The auditor's own blacklist is intentionally exempt.
        if (path.resolve() == own_script or
                (path.suffix.lower() not in CODE_SUFFIXES and path.name not in {'CMakeLists.txt', 'Makefile'})):
            continue
        try:
            lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError as error:
            audit.fail(f'Cannot read deployment source {label}: {error}')
            continue
        for number, line in enumerate(lines, 1):
            normalized = line.replace('\\\\', '\\').casefold()
            for old_root in forbidden_roots:
                if old_root.casefold() in normalized:
                    audit.fail(f'Old workspace reference in {label}:{number}: {old_root}')


def audit_gitlinks(audit: Audit) -> None:
    git = shutil.which('git')
    marker = next((parent / '.git' for parent in [audit.workspace, *audit.workspace.parents]
                   if (parent / '.git').exists()), None)
    if git is None:
        if marker is not None:
            audit.fail('Git metadata exists but git is unavailable; cannot verify gitlinks')
        else:
            audit.notes.append('No Git checkout present; Git-index check does not apply to this source archive')
        return
    command = [git, '-C', str(audit.workspace), 'rev-parse', '--show-toplevel']
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        if marker is not None:
            audit.fail('Cannot inspect Git index: ' + result.stderr.strip())
        else:
            audit.notes.append('No Git checkout present; Git-index check does not apply to this source archive')
        return
    root = Path(result.stdout.strip()).resolve()
    try:
        relative = audit.workspace.relative_to(root).as_posix()
    except ValueError:
        audit.fail('Git repository root does not contain this workspace')
        return
    pathspec = relative if relative != '.' else '.'
    result = subprocess.run([git, '-C', str(root), 'ls-files', '--stage', '-z', '--', pathspec],
                            capture_output=True, check=False)
    if result.returncode:
        audit.fail('Cannot read Git index: ' + result.stderr.decode('utf-8', errors='replace').strip())
        return
    audit.git_index_checked = True
    for entry in result.stdout.split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        if metadata.split()[0] == b'160000':
            audit.fail('Gitlink/submodule in Git index: ' + name.decode('utf-8', errors='replace'))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--manifest', type=Path, help='Default: WORKSPACE/SOURCE_VERSIONS.json')
    parser.add_argument('--forbid-root', action='append', default=[],
                        help='Additional old absolute workspace root to reject in deployment code')
    parser.add_argument('--json', action='store_true', help='Print a machine-readable report')
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    audit = Audit(workspace)
    manifest = args.manifest.resolve() if args.manifest else workspace / 'SOURCE_VERSIONS.json'
    components = load_components(manifest, audit)
    audit_component_hashes(components, audit)
    sources = []
    for name in ('src', 'third_party'):
        root = workspace / name
        if not root.is_dir() or root.is_symlink():
            audit.fail(f'Missing source root or source-root symlink: {name}')
        else:
            sources.extend(collect_files(root, audit))
    # Deployment helpers also need the binary/metadata and old-root checks.
    for name in ('deploy', 'tools'):
        root = workspace / name
        if root.is_dir() and not root.is_symlink():
            sources.extend(collect_files(root, audit))
    roots = [root for root in [*DEFAULT_FORBIDDEN_ROOTS, *args.forbid_root] if root]
    audit_source_files(sources, roots, audit)
    audit_gitlinks(audit)
    report = {'ok': not audit.errors, 'workspace': str(workspace), 'manifest': str(manifest),
              'components': audit.components, 'source_files_scanned': audit.source_files_scanned,
              'git_index_checked': audit.git_index_checked,
              'ignored_directories': sorted(IGNORED_DIRECTORIES),
              'errors': audit.errors, 'notes': audit.notes}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for component in audit.components:
            state = 'OK' if component['ok'] else 'FAIL'
            print(f"[{state}] {component['path']}: {component['files']} files, SHA256 {component['sha256']}")
        for error in audit.errors:
            print('[FAIL] ' + error)
        for note in audit.notes:
            print('[NOTE] ' + note)
        print(f"{'PASS' if report['ok'] else 'FAIL'}: {len(audit.components)} components; "
              f'{audit.source_files_scanned} source/helper files inspected; {len(audit.errors)} errors')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
