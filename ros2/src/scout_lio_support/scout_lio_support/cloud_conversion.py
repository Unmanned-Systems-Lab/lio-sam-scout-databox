"""PointCloud2 byte conversion without ROS imports or fabricated measurements."""

from dataclasses import dataclass
from typing import Iterable

import numpy as np


class InvalidCloud(ValueError):
    """Input cannot safely be interpreted as a LIO-SAM scan."""


@dataclass(frozen=True)
class Field:
    name: str
    offset: int
    datatype: int
    count: int = 1


@dataclass(frozen=True)
class ConvertedCloud:
    data: bytes
    count: int
    dropped: int
    min_time: float
    max_time: float


# sensor_msgs/PointField numeric datatype values.
_TYPES = {1: "i1", 2: "u1", 3: "i2", 4: "u2", 5: "i4", 6: "u4", 7: "f4", 8: "f8"}
OUTPUT_DTYPE = np.dtype({
    "names": ["x", "y", "z", "intensity", "ring", "time"],
    "formats": ["<f4", "<f4", "<f4", "<f4", "<u2", "<f4"],
    "offsets": [0, 4, 8, 12, 16, 20],
    "itemsize": 24,
})


def convert_cloud(
    *, data, fields: Iterable[Field], width: int, height: int,
    point_step: int, row_step: int, is_bigendian: bool,
    stamp_seconds: float, n_scan: int = 32,
    ring_field: str = "ring", timestamp_field: str = "timestamp",
    timestamp_mode: str = "absolute",
    max_scan_duration: float = 0.2, time_tolerance: float = 0.001,
) -> ConvertedCloud:
    """Convert measured points to little-endian, unorganized XYZIRT.

    ``timestamp_mode=absolute`` requires a FLOAT64 epoch-seconds field and
    subtracts the unchanged input header stamp *before* casting to FLOAT32.
    Relative mode accepts FLOAT32/FLOAT64 seconds from the input scan start;
    relative_ns accepts measured UINT32 nanoseconds, as used by Autoware.
    Negative times within ``time_tolerance`` are rounded to zero; larger clock
    disagreements reject the entire scan. Point order and real rings survive.
    """
    if timestamp_mode not in ("absolute", "relative", "relative_ns"):
        raise InvalidCloud("timestamp_mode must be absolute, relative or relative_ns")
    if not 1 <= n_scan <= 65536:
        raise InvalidCloud("n_scan must be in 1..65536")
    if max_scan_duration <= 0 or not 0 <= time_tolerance < max_scan_duration:
        raise InvalidCloud("invalid scan duration or timestamp tolerance")
    if width <= 0 or height <= 0:
        raise InvalidCloud("empty input cloud")
    if point_step <= 0 or row_step < width * point_step:
        raise InvalidCloud("invalid point_step/row_step")
    if not np.isfinite(stamp_seconds):
        raise InvalidCloud("non-finite header timestamp")
    if len(data) < height * row_step:
        raise InvalidCloud("data is shorter than height * row_step")

    field_map = {}
    for field in fields:
        if field.name in field_map:
            raise InvalidCloud("duplicate point field: " + field.name)
        field_map[field.name] = field
    names = ["x", "y", "z", "intensity", ring_field, timestamp_field]
    if len(set(names)) != len(names):
        raise InvalidCloud("ring/time fields must be distinct from each other and XYZ/intensity")
    missing = set(names).difference(field_map)
    if missing:
        raise InvalidCloud("missing measured point fields: " + ", ".join(sorted(missing)))
    endian = ">" if is_bigendian else "<"
    formats = []
    offsets = []
    for name in names:
        field = field_map[name]
        if field.count != 1 or field.datatype not in _TYPES:
            raise InvalidCloud("unsupported scalar point field: " + name)
        dtype = np.dtype(endian + _TYPES[field.datatype])
        if field.offset < 0 or field.offset + dtype.itemsize > point_step:
            raise InvalidCloud("field extends beyond point_step: " + name)
        formats.append(dtype)
        offsets.append(field.offset)
    if field_map[ring_field].datatype not in (1, 2, 3, 4, 5, 6):
        raise InvalidCloud("ring must be an integer field, never estimated")
    time_type = field_map[timestamp_field].datatype
    if timestamp_mode == "relative_ns":
        if time_type != 6:
            raise InvalidCloud("relative_ns timestamps require UINT32 measured nanoseconds")
    elif time_type not in (7, 8):
        raise InvalidCloud("second timestamps must be FLOAT32 or FLOAT64")
    if timestamp_mode == "absolute" and time_type != 8:
        raise InvalidCloud("absolute timestamps require FLOAT64 epoch seconds")
    dtype = np.dtype({"names": names, "formats": formats, "offsets": offsets,
                      "itemsize": point_step})
    points = np.ndarray((height, width), dtype=dtype, buffer=data,
                        strides=(row_step, point_step))
    # Flatten only after honoring each organized row's byte stride.
    values = {name: points[name].reshape(-1) for name in names}
    raw_times = values[timestamp_field].astype(np.float64)
    if timestamp_mode == "absolute":
        times = raw_times - stamp_seconds
    elif timestamp_mode == "relative_ns":
        times = raw_times * 1e-9
    else:
        times = raw_times
    rings = values[ring_field]
    valid = np.isfinite(times) & (rings >= 0) & (rings < n_scan)
    for name in ("x", "y", "z", "intensity"):
        # Finite float64 inputs could overflow their float32 output representation.
        valid &= np.isfinite(values[name]) & (np.abs(values[name]) <= np.finfo(np.float32).max)
    if not valid.any():
        raise InvalidCloud("no finite points with valid measured rings and times")
    valid_times = times[valid]
    if valid_times.min() < -time_tolerance or valid_times.max() > max_scan_duration + time_tolerance:
        raise InvalidCloud(
            "point/header time mismatch: relative range "
            f"[{valid_times.min():.9f}, {valid_times.max():.9f}] s; "
            f"expected [0, {max_scan_duration:.6f}] s"
        )
    valid_times = np.maximum(valid_times, 0.0)
    result = np.zeros(int(valid.sum()), dtype=OUTPUT_DTYPE)
    for name in ("x", "y", "z", "intensity"):
        result[name] = values[name][valid]
    result["ring"] = rings[valid]
    result["time"] = valid_times
    return ConvertedCloud(
        data=result.tobytes(), count=len(result), dropped=width * height - len(result),
        min_time=float(valid_times.min()), max_time=float(valid_times.max()),
    )
