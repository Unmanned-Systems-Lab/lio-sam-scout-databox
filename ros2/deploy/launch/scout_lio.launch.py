"""Standalone 32-channel RSHELIOS + ZED 2i LIO-SAM; no vehicle control."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    deploy_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_dir = os.path.join(deploy_dir, 'config')
    zed_share = get_package_share_directory('zed_wrapper')
    vehicle_share = get_package_share_directory('scout_vehicle_description')
    params = LaunchConfiguration('params_file')
    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=os.path.join(config_dir, 'lio_sam.yaml')),
        DeclareLaunchArgument('start_sensors', default_value='true'),
        DeclareLaunchArgument('publish_robot_tf', default_value='true'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('rviz', default_value='true',
                              description='Open the live map, point cloud and trajectory viewer.'),
        DeclareLaunchArgument('rviz_config', default_value=os.path.join(config_dir, 'scout_lio.rviz')),
        GroupAction(condition=IfCondition(LaunchConfiguration('start_sensors')), actions=[
            Node(
                package='rslidar_sdk', executable='rslidar_sdk_node', output='screen',
                parameters=[{'config_path': os.path.join(config_dir, 'rslidar.yaml')}],
                remappings=[('param_handle:__node', 'rslidar_sdk')],
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(os.path.join(zed_share, 'launch', 'zed_camera.launch.py')),
                launch_arguments={
                    'camera_model': 'zed2i',
                    'camera_name': 'zed2i',
                    'ros_params_override_path': os.path.join(config_dir, 'zed2i_imu.yaml'),
                    'publish_tf': 'false',
                    'publish_map_tf': 'false',
                    'publish_imu_tf': 'true',
                }.items(),
            ),
        ]),
        GroupAction(condition=IfCondition(LaunchConfiguration('publish_robot_tf')), actions=[
            Node(
                package='robot_state_publisher', executable='robot_state_publisher',
                name='scout_lio_state_publisher', output='screen',
                parameters=[{
                    'robot_description': ParameterValue(Command([
                        'xacro ', os.path.join(vehicle_share, 'urdf', 'vehicle.xacro')
                    ]), value_type=str),
                    'use_sim_time': ParameterValue(LaunchConfiguration('use_sim_time'), value_type=bool),
                }],
            ),
            Node(
                package='tf2_ros', executable='static_transform_publisher',
                name='scout_lio_zed_mount_tf', output='screen',
                arguments=['--x', '0', '--y', '0', '--z', '0', '--roll', '0', '--pitch', '0', '--yaw', '0',
                           '--frame-id', 'zed2i_link', '--child-frame-id', 'zed2i_camera_link'],
            ),
        ]),
        Node(
            package='tf2_ros', executable='static_transform_publisher',
            name='scout_lio_map_odom_tf', output='screen',
            arguments=['--x', '0', '--y', '0', '--z', '0', '--roll', '0', '--pitch', '0', '--yaw', '0',
                       '--frame-id', 'lio_map', '--child-frame-id', 'lio_odom'],
        ),
        Node(
            package='scout_lio_support', executable='robosense_to_lio',
            name='robosense_to_lio', output='screen',
            parameters=[{
                'input_topic': '/rslidar_points', 'output_topic': '/lio_sam/points',
                'n_scan': 32, 'ring_field': 'channel',
                'timestamp_field': 'time_stamp', 'timestamp_mode': 'relative_ns',
                'max_scan_duration': 0.2, 'time_tolerance': 0.001,
                'use_sim_time': ParameterValue(LaunchConfiguration('use_sim_time'), value_type=bool),
            }],
        ),
        *[
            Node(
                package='lio_sam', executable='lio_sam_' + executable,
                # This executable creates both ImuP and TransformFusion. A global
                # __node override would give both nodes the same ROS name.
                name=('lio_sam_' + executable) if executable != 'imuPreintegration' else None,
                output='screen',
                parameters=[params, {
                    'use_sim_time': ParameterValue(LaunchConfiguration('use_sim_time'), value_type=bool)
                }],
            )
            for executable in ['imuPreintegration', 'imageProjection', 'featureExtraction', 'mapOptimization']
        ],
        Node(
            package='rviz2', executable='rviz2', name='scout_lio_rviz',
            arguments=['-d', LaunchConfiguration('rviz_config')], output='screen',
            condition=IfCondition(LaunchConfiguration('rviz')),
            parameters=[{'use_sim_time': ParameterValue(LaunchConfiguration('use_sim_time'), value_type=bool)}],
        ),
    ])
