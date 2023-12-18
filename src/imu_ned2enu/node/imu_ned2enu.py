#!/usr/bin/env python3

import rospy
from sensor_msgs.msg import Imu
import numpy as np

def imu_callback(data):
    # 创建一个新的IMU消息
    converted_imu = Imu()
    converted_imu.header.stamp = data.header.stamp
    converted_imu.header.frame_id = "imu_correct_link"  
    # 将NED坐标转换为ENU坐标
    # NED to ENU: (x, y, z) -> (y, x, -z)
    converted_imu.linear_acceleration.x = data.linear_acceleration.y
    converted_imu.linear_acceleration.y = data.linear_acceleration.x
    converted_imu.linear_acceleration.z = -data.linear_acceleration.z
    
    converted_imu.angular_velocity.x = data.angular_velocity.y
    converted_imu.angular_velocity.y = data.angular_velocity.x
    converted_imu.angular_velocity.z = -data.angular_velocity.z
    # 假设方向（四元数）也需要转换
    converted_imu.orientation.x = data.orientation.y
    converted_imu.orientation.y = data.orientation.x
    converted_imu.orientation.z = -data.orientation.z
    converted_imu.orientation.w = data.orientation.w

    # 转换矩阵
    trans_matrix = np.array([[0, 1, 0],
                             [1, 0, 0],
                             [0, 0, -1]])

    # 转换线性加速度协方差
    linear_cov_matrix = np.array(data.linear_acceleration_covariance).reshape(3, 3)
    converted_linear_cov_matrix = np.dot(trans_matrix, np.dot(linear_cov_matrix, trans_matrix.T))
    converted_imu.linear_acceleration_covariance = tuple(converted_linear_cov_matrix.flatten())

    # 转换角速度协方差
    angular_cov_matrix = np.array(data.angular_velocity_covariance).reshape(3, 3)
    converted_angular_cov_matrix = np.dot(trans_matrix, np.dot(angular_cov_matrix, trans_matrix.T))
    converted_imu.angular_velocity_covariance = tuple(converted_angular_cov_matrix.flatten())
    # 发布转换后的IMU数据
    pub.publish(converted_imu)

if __name__ == '__main__':
    rospy.init_node('imu_ned2enu', anonymous=True)

    # 订阅原始IMU数据
    rospy.Subscriber("/zed2i/zed_node/imu/data", Imu, imu_callback)

    # 创建发布者发布转换后的数据
    pub = rospy.Publisher('imu_correct', Imu, queue_size=10)

    rospy.spin()
