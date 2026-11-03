#!/usr/bin/env python3
"""Read the running graph and preserve a new, uniquely named map snapshot."""
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, PointCloud2
from nav_msgs.msg import Odometry, Path as RosPath
from lio_sam.srv import SaveMap

workspace = Path(__file__).resolve().parent.parent
run_name = 'lap_review_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8]
out = workspace / 'maps' / run_name
out.mkdir(parents=True, exist_ok=False)
rclpy.init()
node = rclpy.create_node('scout_lap_review')
samples = {}
latest = {}
degenerate = []


def record(name, msg):
    stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
    samples.setdefault(name, []).append(stamp)


def imu(msg):
    record('imu', msg)


def odometry(msg):
    record('odometry', msg)
    p = msg.pose.pose.position
    latest['position'] = [p.x, p.y, p.z]


def incremental(msg):
    record('incremental_odometry', msg)
    degenerate.append(int(msg.pose.covariance[0] > 0.5))


def path(msg):
    record('path', msg)
    latest['keyframe_path_count'] = len(msg.poses)


def cloud(name, msg):
    record(name, msg)
    latest[name] = {'points': msg.width * msg.height, 'frame': msg.header.frame_id,
                    'fields': [[f.name, f.datatype, f.offset] for f in msg.fields]}


subscriptions = [
    node.create_subscription(Imu, '/zed2i/zed_node/imu/data', imu, qos_profile_sensor_data),
    node.create_subscription(Odometry, '/lio_sam/mapping/odometry', odometry, qos_profile_sensor_data),
    node.create_subscription(Odometry, '/lio_sam/mapping/odometry_incremental', incremental, qos_profile_sensor_data),
    node.create_subscription(RosPath, '/lio_sam/mapping/path', path, qos_profile_sensor_data),
]
for topic in ['/rslidar_points', '/lio_sam/points', '/lio_sam/mapping/map_global']:
    subscriptions.append(node.create_subscription(PointCloud2, topic,
        lambda msg, topic=topic: cloud(topic, msg), qos_profile_sensor_data))
deadline = time.monotonic() + 12.0
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)
report = {'directory': str(out), 'live_topics': latest, 'sample_seconds': 12.0}
now = time.time()
for name, stamps in samples.items():
    dt = np.diff(stamps)
    report.setdefault('rates', {})[name] = {
        'messages': len(stamps), 'last_stamp_age_seconds': now - stamps[-1],
        'hz': (len(stamps)-1)/(stamps[-1]-stamps[0]) if len(stamps)>1 and stamps[-1]>stamps[0] else None,
        'non_increasing_stamps': int(np.count_nonzero(dt <= 0)),
        'max_stamp_gap_seconds': float(dt.max()) if len(dt) else None}
report['recent_degenerate_fraction'] = float(np.mean(degenerate)) if degenerate else None

# The upstream service prepends HOME and removes its destination. Use a new
# home symlink and a verified nonexistent child, so no existing data is removed.
link = Path.home() / ('lio_snapshot_' + uuid.uuid4().hex)
link.symlink_to(out, target_is_directory=True)
target = (link / 'map').resolve()
if target != out / 'map' or target.exists():
    raise RuntimeError('Refusing export: destination must be a new map directory')
if not target.is_relative_to(workspace / 'maps'):
    raise RuntimeError('Refusing export: destination escapes this workspace maps directory')
client = node.create_client(SaveMap, '/lio_sam/save_map')
report['safe_export_target'] = str(target)
if client.wait_for_service(timeout_sec=8.0):
    request = SaveMap.Request()
    request.resolution = 0.0
    request.destination = '/' + link.name + '/map'
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=45.0)
    if future.done():
        report['save_success'] = bool(future.result().success)
        link.unlink()
    else:
        report['save_error'] = 'Service response timed out; temporary symlink retained until export completion'
else:
    report['save_error'] = 'Save service not discovered'
    link.unlink()
report['pcd_files'] = {}
for file in sorted(target.glob('*.pcd')):
    header = []
    with file.open('rb') as stream:
        for _ in range(50):
            line = stream.readline().decode('ascii').strip()
            header.append(line)
            if line.startswith('DATA '):
                break
    report['pcd_files'][file.name] = {'bytes': file.stat().st_size,
        'points': next((int(s.split()[1]) for s in header if s.startswith('POINTS ')), None)}
(out / 'live_review.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2), flush=True)
print('SNAPSHOT_DIRECTORY=' + str(out), flush=True)
node.destroy_node()
rclpy.shutdown()
