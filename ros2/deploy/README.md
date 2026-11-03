# Scout ROS 2 LIO-SAM

目标机现役部署位置：`/mnt/nvme0n1/autoware/lio_sam_ros2_ws`。本分支的工作区是仓库中的 `ros2/`，在该目录执行下列脚本。底座是官方 LIO-SAM `ros2` 分支；参考 `Unmanned-Systems-Lab/lio-sam-scout-databox` 的 ZED 2i IMU 接入与噪声初值，改为 ROS 2 Humble 和 32 线 RSHELIOS。原 ROS 1 工作区保持不变。

## 编译与启动

工作区结构为 `src/lio_sam_ros2`、`src/scout_lio_support` 和 `deploy`。远端复用 `autoware.scout/install` 中的车辆描述、`autoware.ez21/install` 中的雷达驱动、`zed_ros2_ws/install` 中的 ZED 节点、ZED SDK 5.5.1，以及以系统 Eigen 编译的 GTSAM 4.2.0 构建目录。环境只加载这些所需包，避免加载旧工作区的其他依赖链。

现有 GTSAM 导出文件仍记录旧硬盘路径。编译脚本会运行 `prepare_gtsam.py`，仅在本工作区 `deps/gtsam-cmake` 生成修正路径的导出副本；原 GTSAM 构建目录保持不变，并显式指定当前头文件目录以覆盖旧 CMake 缓存。

```bash
# 在本分支的 ros2/ 工作区中运行
bash deploy/build_lio_sam.bash
bash deploy/start_lio_sam.bash
```

默认启动雷达、ZED 2i、机器人静态坐标系、点云适配、LIO-SAM 和 RViz2 图形界面，无底盘控制节点。请先登录 Orin 图形桌面；在桌面终端运行命令，或通过 SSH 复用已登录的桌面。窗口显示在 Orin 上，可用显示器或远程桌面查看。

界面中，彩色点云是累计地图，橙色是最新配准点云，青色是运动轨迹。左键拖动旋转、滚轮缩放，按住 Shift 加左键拖动平移。慢速移动时观察墙面是否重影、地面是否倾斜，静止时观察地图和轨迹是否持续漂移。

已在运行建图时，只打开查看窗口：

```bash
bash deploy/view_lio_sam.bash
```

无界面运行可加 `rviz:=false`。复用已经运行的传感器及机器人坐标系时：

```bash
bash deploy/start_lio_sam.bash start_sensors:=false publish_robot_tf:=false
```

停止使用 Ctrl+C。此部署不会设置自动启动。`setup_env.bash` 保留调用方的 `ROS_DOMAIN_ID` 和 DDS 网络设置。

现有雷达驱动在退出时可能等待至启动器超时，随后被启动器强制结束；请等整个启动退出后再重启，避免 UDP 端口仍被占用。

## 数据与坐标

- 雷达：RSHELIOS，UDP 3344/5566，系统时钟，整圈首点时间戳，点云 `/rslidar_points`，`frame_id=rslidar`。
- 现有驱动输出原生 Autoware `XYZIRCAEDT`；适配器读取 `channel` 作为真实线号 `ring=0..31`，读取 `time_stamp`（逐点相对帧首的 `UINT32` 纳秒），先除以 `1e9` 再生成单精度相对秒 `time`，发布到 `/lio_sam/points` 并过滤无效点。没有真实线号或逐点时间会拒绝发布。无需重新编译现有雷达驱动。
- IMU：`/zed2i/zed_node/imu/data`，请求 400Hz，关闭图像同步，使用 SDK 的真实姿态；不套用参考库的 ROS 1 NED→ENU 脚本。
- 地图及里程计坐标：`lio_map`、`lio_odom`，避免占用现有 `map/odom` 名称；机器人子树仍使用现有 `base_link/rslidar`。运行时同一子坐标系只能有一个动态发布源。
- 已禁用 GPS 融合、自动 PCD 保存与闭环，先验证连续里程计。

## 尚需现场确认

现场已确认雷达每帧 `1800×32` 点、约 10Hz，配置为 `Horizon_SCAN=1800`、`N_SCAN=32`；适配器继续逐帧检查真实线号和逐点时间。

IMU 外参已在目标机读取 `rslidar <- zed2i_imu_link` 的完整 TF 后填入，平移约为 `[0.092994, 0.036939, -0.170658] m`。该变换来自现有 Scout CAD 安装模型和当前相机的出厂 IMU 标定；它是可运行的初始估计，仍需实车雷达/IMU 时空标定验证。官方 ROS 2 源码中 `extrinsicRot=R_lidar_imu`，`extrinsicRPY=R_imu_lidar`，`extrinsicTrans=t_lidar_imu`；旋转矩阵取转置，平移直接使用 TF 的值。噪声参数来自参考装置，需要实际静态数据复核。

上游基于 `ros2` 分支提交 `08af3f32f01725372d4269838dc44c19c6d9e76b`。本地补丁使用最大逐点时间检查完整扫描的 IMU 覆盖，忽略空点云，保护空的 IMU 里程计队列，并只由 TransformFusion 发布 `lio_odom -> base_link` 动态坐标变换。

## 验证

```bash
source deploy/setup_env.bash
ros2 topic hz /rslidar_points
ros2 topic hz /lio_sam/points
ros2 topic hz /zed2i/zed_node/imu/data
ros2 topic echo /lio_sam/mapping/odometry --once
ros2 run tf2_ros tf2_echo lio_odom base_link
```

检查点云帧时长合理、32 条线齐全、IMU 时间覆盖完整一帧、姿态四元数有效、静止时加速度约为重力大小。不能仅以节点启动成功代替建图验证。长距离精度与运动去畸变还需实际运动数据验证。

2026-11-03 目标机编译、11 项转换测试及 30 秒整套静止联调已通过，详见 [验证记录](VALIDATION.md)。完整上游源码补丁保存在 `lio_sam_ros2.patch`。

本配置依赖这台 Orin 已安装的驱动、SDK 和 GTSAM，依赖根路径是目标机配置。桌面快捷方式示例的 Exec 指向现役部署目录；若为新克隆安装快捷方式，应先将 Exec 改为该克隆 ros2/deploy/start_lio_sam.bash 的绝对路径。
