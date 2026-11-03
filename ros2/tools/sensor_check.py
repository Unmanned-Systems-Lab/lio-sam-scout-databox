#!/usr/bin/env python3
"""Capture sensor timing, point fields, mounting TF and optional LIO odometry."""
import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, PointCloud2
from nav_msgs.msg import Odometry
from tf2_ros import Buffer, TransformListener

parser = argparse.ArgumentParser()
parser.add_argument('--seconds', type=float, default=10.0)
parser.add_argument('--output', default='validation/sensors.json')
args = parser.parse_args()
rclpy.init()
node = rclpy.create_node('scout_lio_validation')
buffer = Buffer()
listener = TransformListener(buffer, node)
samples = {}
details = {}
imu_acc = []
imu_gyro = []
poses = []


def stamp(msg):
    return msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9


def record(topic, msg):
    samples.setdefault(topic, []).append((stamp(msg), time.time()))


def cloud(topic, msg):
    record(topic, msg)
    if topic in details:
        return
    fields = {f.name: f for f in msg.fields}
    types = {1: 'i1', 2: 'u1', 3: 'i2', 4: 'u2', 5: 'i4', 6: 'u4', 7: 'f4', 8: 'f8'}
    dtype = np.dtype({'names': list(fields),
                      'formats': [('>' if msg.is_bigendian else '<') + types[f.datatype] for f in fields.values()],
                      'offsets': [f.offset for f in fields.values()], 'itemsize': msg.point_step})
    data = np.ndarray((msg.height, msg.width), buffer=msg.data, dtype=dtype,
                      strides=(msg.row_step, msg.point_step))
    ring_name = 'ring' if 'ring' in fields else 'channel'
    time_name = 'time' if 'time' in fields else 'time_stamp'
    rings = data[ring_name].reshape(-1)
    times = data[time_name].reshape(-1).astype(float)
    if time_name == 'time_stamp':
        times *= 1e-9
    details[topic] = {'frame': msg.header.frame_id, 'shape': [msg.height, msg.width],
                      'fields': [[f.name, f.datatype, f.offset] for f in msg.fields],
                      'ring_min': int(rings.min()), 'ring_max': int(rings.max()),
                      'ring_count': len(np.unique(rings)), 'scan_seconds': [float(times.min()), float(times.max())],
                      'finite_xyz': int(np.count_nonzero(np.isfinite(data['x']) & np.isfinite(data['y']) & np.isfinite(data['z'])))}


def imu(msg):
    record('imu', msg)
    imu_acc.append([msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z])
    imu_gyro.append([msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z])
    q = msg.orientation
    details['imu'] = {'frame': msg.header.frame_id, 'quaternion_norm': math.sqrt(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w)}


def odom(msg):
    record('odometry', msg)
    p = msg.pose.pose.position
    poses.append([p.x, p.y, p.z])


subscriptions = [node.create_subscription(PointCloud2, topic, lambda msg, topic=topic: cloud(topic, msg), qos_profile_sensor_data)
                 for topic in ['/rslidar_points', '/lio_sam/points']]
subscriptions.append(node.create_subscription(Imu, '/zed2i/zed_node/imu/data', imu, qos_profile_sensor_data))
subscriptions.append(node.create_subscription(Odometry, '/lio_sam/mapping/odometry', odom, qos_profile_sensor_data))
deadline = time.monotonic() + args.seconds
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)
result = {'duration_seconds': args.seconds, 'topics': details}
for topic, values in samples.items():
    stamps, receipts = np.array(values).T
    dt = np.diff(stamps)
    result['topics'].setdefault(topic, {}).update({
        'messages': len(values), 'stamp_hz': float((len(values)-1)/(stamps[-1]-stamps[0])) if len(values)>1 else 0,
        'non_increasing_stamps': int(np.count_nonzero(dt <= 0)),
        'receive_lag_seconds_median': float(np.median(receipts-stamps)),
        'max_stamp_gap_seconds': float(dt.max()) if len(dt) else None})
if imu_acc:
    result['topics']['imu']['mean_acceleration'] = np.mean(imu_acc, axis=0).tolist()
    result['topics']['imu']['mean_angular_velocity'] = np.mean(imu_gyro, axis=0).tolist()
if poses:
    p = np.array(poses)
    result['topics']['odometry'].update({'first_position': p[0].tolist(), 'last_position': p[-1].tolist(),
                                        'position_span': np.ptp(p, axis=0).tolist(), 'all_finite': bool(np.isfinite(p).all())})
try:
    transform = buffer.lookup_transform('rslidar', 'zed2i_imu_link', rclpy.time.Time()).transform
    t, q = transform.translation, transform.rotation
    x, y, z, w = q.x, q.y, q.z, q.w
    norm = math.sqrt(x*x+y*y+z*z+w*w)
    x, y, z, w = x/norm, y/norm, z/norm, w/norm
    rotation = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                         [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                         [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
    result['mount_from_tf'] = {'source': 'Scout CAD mount + ZED factory IMU transform; not a new physical calibration',
                               'extrinsicTrans': [t.x, t.y, t.z], 'extrinsicRot': rotation.ravel().tolist(),
                               'extrinsicRPY': rotation.T.ravel().tolist()}
except Exception as exc:
    result['tf_error'] = str(exc)
text = json.dumps(result, ensure_ascii=False, indent=2)
Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text(text + '\n', encoding='utf-8')
print(text)
node.destroy_node()
rclpy.shutdown()
