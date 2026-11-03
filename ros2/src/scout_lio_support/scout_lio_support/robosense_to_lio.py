"""ROS 2 wrapper for the byte-level RoboSense point conversion."""

from array import array

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2, PointField

from .cloud_conversion import Field, InvalidCloud, convert_cloud


class RobosenseToLio(Node):
    def __init__(self):
        super().__init__("robosense_to_lio")
        defaults = {
            "input_topic": "/rslidar_points", "output_topic": "/lio_sam/points",
            "n_scan": 32, "ring_field": "ring",
            "timestamp_field": "timestamp", "timestamp_mode": "absolute",
            "max_scan_duration": 0.2, "time_tolerance": 0.001,
        }
        self.options = {name: self.declare_parameter(name, value).value
                        for name, value in defaults.items()}
        self.publisher = self.create_publisher(
            PointCloud2, self.options["output_topic"], qos_profile_sensor_data)
        self.subscription = self.create_subscription(
            PointCloud2, self.options["input_topic"], self.on_cloud,
            qos_profile_sensor_data)
        self.received = self.published = self.rejected = 0
        self.last_stats = "waiting for input"
        self.timer = self.create_timer(10.0, self.report)
        self.get_logger().info(
            f"{self.options['input_topic']} -> {self.options['output_topic']}; "
            f"{self.options['n_scan']} rings, measured {self.options['timestamp_field']} "
            f"({self.options['timestamp_mode']})")

    def report(self):
        self.get_logger().info(
            f"received={self.received} published={self.published} "
            f"rejected={self.rejected}; {self.last_stats}")

    def on_cloud(self, msg):
        self.received += 1
        try:
            converted = convert_cloud(
                data=msg.data,
                fields=[Field(f.name, f.offset, f.datatype, f.count) for f in msg.fields],
                width=msg.width, height=msg.height, point_step=msg.point_step,
                row_step=msg.row_step, is_bigendian=msg.is_bigendian,
                stamp_seconds=msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                **{key: self.options[key] for key in (
                    "n_scan", "ring_field", "timestamp_field", "timestamp_mode",
                    "max_scan_duration", "time_tolerance")},
            )
        except (InvalidCloud, ValueError, TypeError, BufferError) as exc:
            self.rejected += 1
            self.last_stats = str(exc)
            self.get_logger().warning("Rejected scan: " + str(exc), throttle_duration_sec=5.0)
            return
        output = PointCloud2()
        output.header = msg.header
        output.height = 1
        output.width = converted.count
        output.fields = [
            PointField(name=name, offset=offset, datatype=datatype, count=1)
            for name, offset, datatype in (
                ("x", 0, PointField.FLOAT32), ("y", 4, PointField.FLOAT32),
                ("z", 8, PointField.FLOAT32), ("intensity", 12, PointField.FLOAT32),
                ("ring", 16, PointField.UINT16), ("time", 20, PointField.FLOAT32),
            )
        ]
        output.is_bigendian = False
        output.point_step = 24
        output.row_step = 24 * converted.count
        output.is_dense = True
        output.data = array("B", converted.data)
        self.publisher.publish(output)
        self.published += 1
        self.last_stats = (
            f"points={converted.count} dropped={converted.dropped} "
            f"relative_time=[{converted.min_time:.6f}, {converted.max_time:.6f}] s")


def main(args=None):
    rclpy.init(args=args)
    node = RobosenseToLio()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
