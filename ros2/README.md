# ROS 2 工作区

在本目录执行 `bash deploy/build_lio_sam.bash` 和 `bash deploy/start_lio_sam.bash`。默认打开 Orin 桌面的 RViz2；无界面运行使用 `bash deploy/start_lio_sam.bash rviz:=false`。

此目录包含两个包：`src/lio_sam_ros2` 和 `src/scout_lio_support`。分支根目录的 `src/` 是保留的 ROS 1 参考文件，已通过 `COLCON_IGNORE` 排除 ROS 2 包发现。

配置使用目标 Orin 已安装的 Autoware Scout 驱动、车辆描述、ZED SDK 和 GTSAM。依赖路径及详细操作见 [部署说明](deploy/README.md)，版本与更改概要见 [分支说明](../README.md)。

运行生成的 `build/`、`install/`、`log/`、`validation/`、`maps/`、`deps/` 不纳入版本控制。
