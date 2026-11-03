#!/usr/bin/env python3
"""Inspect binary PCD map snapshots and plot their saved keyframe trajectory."""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np


class PCDFormatError(ValueError):
    pass


@dataclass
class PCD:
    path: Path
    data: np.ndarray
    fields: list[str]
    points: int
    point_step: int
    header_bytes: int


def read_binary_pcd(path: Path) -> PCD:
    """Memory-map packed, little-endian PCD DATA binary; validate its layout."""
    path = Path(path)
    header: dict[str, list[str]] = {}
    with path.open('rb') as stream:
        for _ in range(200):
            line = stream.readline(65537)
            if not line or len(line) > 65536:
                raise PCDFormatError(f'{path}: incomplete or oversized PCD header')
            try:
                text = line.decode('ascii').strip()
            except UnicodeDecodeError as exc:
                raise PCDFormatError(f'{path}: non-ASCII PCD header') from exc
            if not text or text.startswith('#'):
                continue
            pieces = text.split()
            name, values = pieces[0].upper(), pieces[1:]
            if name in header:
                raise PCDFormatError(f'{path}: duplicate header key {name}')
            header[name] = values
            if name == 'DATA':
                offset = stream.tell()
                break
        else:
            raise PCDFormatError(f'{path}: DATA header not found')
    if header.get('DATA') != ['binary']:
        raise PCDFormatError(f'{path}: expected uncompressed DATA binary, got {header.get("DATA")}')
    fields = header.get('FIELDS', header.get('FIELD', []))
    if not fields:
        raise PCDFormatError(f'{path}: no FIELDS')
    try:
        sizes = [int(v) for v in header['SIZE']]
        types = header['TYPE']
        counts = [int(v) for v in header.get('COUNT', ['1'] * len(fields))]
        width = int(header.get('WIDTH', ['0'])[0])
        height = int(header.get('HEIGHT', ['1'])[0])
        points = int(header.get('POINTS', [str(width * height)])[0])
    except (KeyError, ValueError, IndexError) as exc:
        raise PCDFormatError(f'{path}: malformed SIZE/TYPE/COUNT/dimensions') from exc
    if not (len(fields) == len(sizes) == len(types) == len(counts)):
        raise PCDFormatError(f'{path}: FIELDS/SIZE/TYPE/COUNT lengths differ')
    if points < 0 or any(c < 1 for c in counts):
        raise PCDFormatError(f'{path}: invalid POINTS or COUNT')
    names, formats, offsets = [], [], []
    stride = 0
    for index, (name, size, kind, count) in enumerate(zip(fields, sizes, types, counts)):
        if (kind.upper(), size) not in {
            ('F', 4), ('F', 8), ('I', 1), ('I', 2), ('I', 4), ('I', 8),
            ('U', 1), ('U', 2), ('U', 4), ('U', 8),
        }:
            raise PCDFormatError(f'{path}: unsupported field type {kind}{size}')
        # PCL can describe more than one padding field with the name '_'.
        unique_name = f'_padding_{index}' if name == '_' else name
        if unique_name in names:
            raise PCDFormatError(f'{path}: duplicate non-padding field {name}')
        base = np.dtype('<' + {'F': 'f', 'I': 'i', 'U': 'u'}[kind.upper()] + str(size))
        names.append(unique_name)
        formats.append(base if count == 1 else (base, (count,)))
        offsets.append(stride)
        stride += size * count
    dtype = np.dtype({'names': names, 'formats': formats, 'offsets': offsets, 'itemsize': stride})
    expected = offset + points * stride
    if path.stat().st_size < expected:
        raise PCDFormatError(f'{path}: truncated binary body; expected >= {expected} bytes')
    data = np.memmap(path, mode='r', dtype=dtype, offset=offset, shape=(points,)) if points else np.empty(0, dtype=dtype)
    return PCD(path.resolve(), data, fields, points, stride, offset)


def scalar_column(pcd: PCD, name: str) -> np.ndarray:
    if name not in pcd.data.dtype.names:
        raise PCDFormatError(f'{pcd.path}: required field {name} is missing')
    result = pcd.data[name]
    if result.ndim != 1:
        raise PCDFormatError(f'{pcd.path}: {name} must have COUNT 1')
    return np.asarray(result, dtype=np.float64)


def xyz(pcd: PCD, indices=None) -> np.ndarray:
    for name in ('x', 'y', 'z'):
        if name not in pcd.data.dtype.names or pcd.data[name].ndim != 1:
            raise PCDFormatError(f'{pcd.path}: scalar {name} is required')
    return np.column_stack([pcd.data[name] if indices is None else pcd.data[name][indices]
                            for name in ('x', 'y', 'z')]).astype(np.float64, copy=False)


def analyze_trajectory(pcd: PCD):
    position = xyz(pcd)
    time = scalar_column(pcd, 'time')
    roll, pitch, yaw = [scalar_column(pcd, name) for name in ('roll', 'pitch', 'yaw')]
    valid_position = np.isfinite(position).all(axis=1)
    valid_orientation = np.isfinite(np.column_stack([roll, pitch, yaw])).all(axis=1)
    valid_time = np.isfinite(time)
    finite = valid_position & valid_orientation & valid_time
    if not valid_position.any():
        raise PCDFormatError(f'{pcd.path}: no finite keyframe XYZ positions')
    steps = np.linalg.norm(np.diff(position, axis=0), axis=1)
    adjacent = valid_position[:-1] & valid_position[1:]
    gaps = np.diff(time)
    valid_gap = valid_time[:-1] & valid_time[1:]
    valid_speed = adjacent & valid_gap & (gaps > 0)
    speeds = steps[valid_speed] / gaps[valid_speed]
    cumulative = np.r_[0.0, np.cumsum(np.where(adjacent, steps, 0.0))]
    finite_positions = position[valid_position]
    finite_times = time[valid_time]
    finite_yaw = yaw[np.isfinite(yaw)]
    yaw_unwrapped = np.unwrap(finite_yaw)
    bounds = np.stack([finite_positions.min(axis=0), finite_positions.max(axis=0)])
    summary = {
        'keyframes': pcd.points,
        'finite_complete_keyframes': int(finite.sum()),
        'invalid_xyz_keyframes': int((~valid_position).sum()),
        'invalid_orientation_keyframes': int((~valid_orientation).sum()),
        'invalid_time_keyframes': int((~valid_time).sum()),
        'keyframe_path_length_m': float(steps[adjacent].sum()),
        'first_position_m': finite_positions[0].tolist(),
        'last_position_m': finite_positions[-1].tolist(),
        'xyz_min_m': bounds[0].tolist(), 'xyz_max_m': bounds[1].tolist(),
        'xyz_extent_m': (bounds[1] - bounds[0]).tolist(),
        'z_range_m': [float(bounds[0, 2]), float(bounds[1, 2])],
        'max_adjacent_keyframe_step_m': float(steps[adjacent].max()) if adjacent.any() else None,
        'max_adjacent_keyframe_speed_mps': float(speeds.max()) if len(speeds) else None,
        'max_adjacent_keyframe_time_gap_s': float(gaps[valid_gap].max()) if valid_gap.any() else None,
        'non_increasing_keyframe_times': int(np.count_nonzero(gaps[valid_gap] <= 0)),
        'first_keyframe_time': float(finite_times[0]) if len(finite_times) else None,
        'last_keyframe_time': float(finite_times[-1]) if len(finite_times) else None,
        'duration_s': float(finite_times[-1] - finite_times[0]) if len(finite_times) else None,
        'time_span_s': float(np.ptp(finite_times)) if len(finite_times) else None,
        'yaw_unwrapped_min_deg': float(np.degrees(yaw_unwrapped.min())) if len(yaw_unwrapped) else None,
        'yaw_unwrapped_max_deg': float(np.degrees(yaw_unwrapped.max())) if len(yaw_unwrapped) else None,
        'yaw_unwrapped_range_deg': float(np.degrees(np.ptp(yaw_unwrapped))) if len(yaw_unwrapped) else None,
        'return_to_start_assumed': False,
        'note': 'Keyframe path length is a sampled route estimate; endpoint separation is not interpreted as drift.',
    }
    return summary, position, cumulative, valid_position


def sample_map(pcd: PCD, maximum: int):
    stride = max(1, math.ceil(pcd.points / maximum))
    indices = np.arange(0, pcd.points, stride, dtype=np.int64)
    sampled = xyz(pcd, indices)
    sampled = sampled[np.isfinite(sampled).all(axis=1)]
    count = 0
    lower, upper = np.full(3, np.inf), np.full(3, -np.inf)
    # Bound temporary memory even if the saved map contains millions of points.
    for start in range(0, pcd.points, 100_000):
        points = xyz(pcd, slice(start, min(start + 100_000, pcd.points)))
        points = points[np.isfinite(points).all(axis=1)]
        count += len(points)
        if len(points):
            lower = np.minimum(lower, points.min(axis=0)); upper = np.maximum(upper, points.max(axis=0))
    summary = {
        'points': pcd.points, 'finite_xyz_points': count, 'invalid_xyz_points': pcd.points - count,
        'plotted_points': len(sampled), 'uniform_sample_stride': stride,
        'xyz_min_m': lower.tolist() if count else None, 'xyz_max_m': upper.tolist() if count else None,
        'xyz_extent_m': (upper - lower).tolist() if count else None,
    }
    return summary, sampled


def plot_review(output: Path, points, position, cumulative, valid_position, trajectory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as effects
    from matplotlib.colors import Normalize

    fig, (map_ax, height_ax) = plt.subplots(2, 1, figsize=(13, 11),
                                           gridspec_kw={'height_ratios': [3.4, 1]}, layout='constrained')
    fig.suptitle(f'Map snapshot and keyframe trajectory\n{trajectory["keyframes"]:,} keyframes  |  '
                 f'{trajectory["keyframe_path_length_m"]:.1f} m sampled route', fontsize=16, weight='bold')
    if len(points):
        low, high = np.percentile(points[:, 2], [2, 98])
        if high <= low:
            low, high = low - 0.05, high + 0.05
        cloud = map_ax.scatter(points[:, 0], points[:, 1], c=points[:, 2], s=0.65, alpha=0.65,
                               cmap='viridis', norm=Normalize(low, high, clip=True), linewidths=0, rasterized=True)
        colorbar = fig.colorbar(cloud, ax=map_ax, fraction=0.035, pad=0.025)
        colorbar.set_label('Map Z (m); colors clipped at 2nd/98th percentiles', fontsize=10)
    displayed = position.copy(); displayed[~valid_position] = np.nan
    map_ax.plot(displayed[:, 0], displayed[:, 1], color='#202731', lw=1.8, label='Keyframe trajectory',
                path_effects=[effects.Stroke(linewidth=3.4, foreground='white'), effects.Normal()], zorder=4)
    first, last = position[valid_position][[0, -1]]
    map_ax.scatter(first[0], first[1], color='#159447', edgecolors='white', s=95, marker='o', zorder=6, label='Start')
    map_ax.scatter(last[0], last[1], color='#d63d36', linewidths=2.5, s=100, marker='x', zorder=7, label='End')
    map_ax.annotate('Start', first[:2], xytext=(9, 10), textcoords='offset points', color='#126c36', weight='bold',
                    bbox={'boxstyle': 'round,pad=0.2', 'facecolor': 'white', 'alpha': 0.8, 'edgecolor': 'none'}, zorder=8)
    map_ax.annotate('End', last[:2], xytext=(9, -17), textcoords='offset points', color='#b12b25', weight='bold',
                    bbox={'boxstyle': 'round,pad=0.2', 'facecolor': 'white', 'alpha': 0.8, 'edgecolor': 'none'}, zorder=8)
    map_ax.set(xlabel='X (m)', ylabel='Y (m)', title='Top view, frame: lio_odom')
    map_ax.set_aspect('equal', adjustable='datalim'); map_ax.margins(0.08)
    map_ax.grid(alpha=0.18); map_ax.legend(loc='upper right', framealpha=0.95)
    height_ax.plot(cumulative, displayed[:, 2], color='#23658b', lw=1.8)
    height_ax.set(xlabel='Cumulative keyframe path length (m)', ylabel='Trajectory Z (m)',
                  title='Estimated sensor elevation along the sampled route')
    height_ax.grid(alpha=0.25)
    height_ax.text(0, -0.42, 'Endpoint separation measures drift only when a return to the same physical location is confirmed.',
                   transform=height_ax.transAxes, fontsize=10, color='#4a5158')
    fig.savefig(output, dpi=170, facecolor='white')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path, help='Directory containing transformations.pcd and GlobalMap.pcd')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-map-points', type=int, default=200_000)
    args = parser.parse_args()
    if not 1 <= args.max_map_points <= 200_000:
        parser.error('--max-map-points must be in 1..200000')
    trajectory_pcd = read_binary_pcd(args.input / 'transformations.pcd')
    map_pcd = read_binary_pcd(args.input / 'GlobalMap.pcd')
    trajectory, position, cumulative, valid_position = analyze_trajectory(trajectory_pcd)
    map_summary, points = sample_map(map_pcd, args.max_map_points)
    args.output.mkdir(parents=True, exist_ok=True)
    summary = {'input_directory': str(args.input.resolve()), 'trajectory': trajectory, 'map': map_summary,
               'pcd_fields': {'transformations': trajectory_pcd.fields, 'GlobalMap': map_pcd.fields}}
    summary_path = args.output / 'summary.json'
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    image_path = args.output / 'map_and_trajectory.png'
    plot_review(image_path, points, position, cumulative, valid_position, trajectory)
    print(json.dumps({'summary': str(summary_path.resolve()), 'plot': str(image_path.resolve()), **summary}, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
