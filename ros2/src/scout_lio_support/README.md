# Scout LIO-SAM point-cloud adapter

This ROS 2 Humble package converts measured RoboSense point-cloud data to the
Velodyne XYZIRT layout consumed by LIO-SAM. It does not produce IMU messages or
infer missing rings/timestamps.

```bash
ros2 run scout_lio_support robosense_to_lio --ros-args \
  -p input_topic:=/rslidar_points -p output_topic:=/lio_sam/points \
  -p n_scan:=32 -p timestamp_field:=timestamp -p timestamp_mode:=absolute
```

Input requires scalar `x`, `y`, `z`, `intensity`, integer `ring`, and a measured
time field. The default `timestamp` is FLOAT64 epoch seconds. The original
header must represent the first point's sampling time in the same clock domain.
Epoch subtraction happens in float64 before conversion to float32. For an input
already containing relative seconds, set `timestamp_field:=time` and
`timestamp_mode:=relative`; relative FLOAT32 and FLOAT64 are supported. Changing
the mode is appropriate only after checking the actual driver format.

The installed Scout Autoware driver uses `channel` (UINT16, offset 14) and
`time_stamp` (UINT32 measured relative nanoseconds, offset 28) with a 32-byte
point stride. For this verified native format use:

```bash
ros2 run scout_lio_support robosense_to_lio --ros-args \
  -p ring_field:=channel -p timestamp_field:=time_stamp \
  -p timestamp_mode:=relative_ns
```

`relative_ns` requires a UINT32 field and converts it to seconds in float64;
it neither recomputes point time nor changes the header. Its timestamp is
already relative to the frame start, so no epoch subtraction is applied.
`ring_field` defaults to `ring`; it simply names the measured integer channel.

Output is little-endian, unorganized, dense PointCloud2 with unchanged header:

| Field | Type | Byte offset |
|---|---|---:|
| x, y, z | float32 | 0, 4, 8 |
| intensity | float32 | 12 |
| ring | uint16 | 16 |
| time | float32, seconds from header | 20 |

The output point stride is 24 bytes. Organized inputs and row padding are
handled using their advertised byte strides; both input byte orders work.
Finite points with real rings in `0..n_scan-1` survive in input order. Invalid
XYZ, intensity, times or rings are removed. If the remaining measured times
disagree with the header by more than the allowed scan duration, the entire
cloud is rejected. By default times must be in `[-0.001, 0.201]` seconds:
negative values within 1 ms are clamped to zero to accommodate driver timestamp
rounding, and the nominal maximum scan duration is 0.2 s. Configure
`max_scan_duration` for the actual scan rate and reduce `time_tolerance` after
measuring synchronization. These checks detect gross clock errors; they do not
prove LiDAR/IMU synchronization or calibrate latency.

No sorting is performed. LIO-SAM must calculate scan end from the **maximum**
point time, rather than the last point, when organized clouds use ring-major
ordering. Diagnostics report received/published/rejected scan counts and the
last retained time interval every 10 seconds; rejection messages are throttled.

Run the ROS-independent tests from this package directory:

```bash
python3 -m unittest discover -s test -v
```
