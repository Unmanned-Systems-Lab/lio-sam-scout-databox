#!/usr/bin/env python3
"""Relocate a private copy of the existing GTSAM build-tree CMake exports."""

import argparse
from pathlib import Path


OLD_SOURCE = '/media/agx/82133ec0-91fe-483a-a6e5-17cbae4e4526/autoware/gtsam'
SOURCE = Path('/mnt/nvme0n1/autoware/gtsam')


def prepare(workspace, source=SOURCE):
    build = source / 'build'
    files = sorted(build.glob('*.cmake'))
    if not (build / 'GTSAMConfig.cmake').is_file():
        raise RuntimeError(f'Existing GTSAM build exports missing: {build}')
    destination = workspace / 'deps' / 'gtsam-cmake'
    destination.mkdir(parents=True, exist_ok=True)
    for original in files:
        text = original.read_text(encoding='utf-8')
        relocated = text.replace(OLD_SOURCE, source.as_posix())
        (destination / original.name).write_text(relocated, encoding='utf-8')
    print(f'Prepared {len(files)} GTSAM CMake exports: {destination}')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    prepare(args.workspace.resolve())


if __name__ == '__main__':
    main()
