# Scout ROS 2 LIO-SAM 部署

这套配置用于 Jetson AGX Orin / ROS 2 Humble、RSHELIOS 32 线雷达和 ZED 2i IMU。依赖源码已整理到同一 ROS 2 工作区；编译和运行从当前目录定位。工作区布局与平台前提见 [ROS 2 说明](../README.md)。

## 首次安装和编译

先准备 Ubuntu 22.04、JetPack 6.2.2（L4T 36.5、CUDA 12.6）及 ROS 2 Humble 官方软件源。在仓库的 `ros2/` 目录运行：

```bash
bash deploy/install_dependencies.bash
bash deploy/install_zed_sdk.bash
bash deploy/build_lio_sam.bash
```

系统开发依赖通过 apt/rosdep 安装。GTSAM 从 `third_party/gtsam` 编译到 `.deps/gtsam-install`，ROS 2 包从当前 `src/` 构建。无需准备其他车辆、雷达或 ZED ROS 2 工作区，也无需初始化子模块。

ZED SDK 为独立厂商开发包，未复制到仓库。安装脚本下载并校验官方 5.5.1 安装包，默认交互审阅许可证，标准安装位置为 `/usr/local/zed`。已有完整开发包时，可设置 `ZED_DIR=/绝对路径/SDK根目录`。离线安装及明确同意许可证后的自动安装选项见 [SDK 说明](../third_party/zed_sdk/README.md)。

首次构建 GTSAM 和驱动可能耗时较长，默认两个编译任务；可通过 `SCOUT_LIO_BUILD_JOBS` 调整。`build/`、`install/`、`log/`、`.deps/` 为本机产物，不提交到源码仓库。

## 启动和查看界面

```bash
bash deploy/start_lio_sam.bash
```

默认启动雷达、ZED 2i、机器人静态坐标系、点云适配、LIO-SAM 和 RViz2。请先登录 Orin 图形桌面，再在桌面终端运行；通过 SSH 启动时，辅助脚本会尝试复用当前用户已经登录的桌面。RViz 窗口显示在 Orin，可用显示器或远程桌面查看。

| RViz 显示 | 内容 |
| --- | --- |
| 彩色点云 | 累计地图 `/lio_sam/mapping/map_global` |
| 橙色点云 | 最新密集配准点云 `/lio_sam/mapping/cloud_registered_raw` |
| 青色轨迹 | 建图路径 `/lio_sam/mapping/path` |

固定坐标系为 `lio_odom`，视角跟随 `base_link`。左键拖动旋转、滚轮缩放、Shift 加左键拖动平移。慢速移动时观察墙面是否重影、地面是否倾斜；静止时观察地图和轨迹是否持续漂移。

建图已在运行时，只打开查看窗口：

```bash
bash deploy/view_lio_sam.bash
```

无界面启动，或复用正在运行的传感器及静态坐标系：

```bash
bash deploy/start_lio_sam.bash rviz:=false
bash deploy/start_lio_sam.bash start_sensors:=false publish_robot_tf:=false
```

不要同时重复启动同一传感器或动态 TF 发布源。Ctrl+C 停止本次启动；等待全部进程退出后再重启，旧版雷达驱动可能需要等待 ROS 2 启动器的退出超时。

## 数据与坐标配置

| 项目 | 当前配置 |
| --- | --- |
| 雷达输入 | 在线 RSHELIOS，UDP MSOP `3344` / DIFOP `5566`，`/rslidar_points`，`frame_id=rslidar` |
| 雷达扫描 | 32 线，每圈 1800 列，约 10Hz；系统时钟、整圈首点时间戳 |
| 点云适配 | 读取原生 XYZIRCAEDT 的 `channel` 和 `time_stamp`，输出 `/lio_sam/points` 的 XYZIRT |
| IMU | `/zed2i/zed_node/imu/data`，请求 400Hz，关闭图像同步，保留 SDK 校准姿态 |
| ZED 图像处理 | 深度模式 `NONE`，关闭位置跟踪；IMU 仍使用 SDK 后端 |
| 坐标 | 地图 `lio_map`、里程计 `lio_odom`，机器人 `base_link`，雷达 `rslidar` |

适配器将真实 `channel` 映射为 `ring=0..31`，将逐点相对帧首的 `UINT32` 纳秒除以 `1e9` 得到相对秒 `time`，过滤无效点并检查时间范围。缺少真实线号或逐点时间时拒绝发布。LIO-SAM 使用最大有效逐点时间检查整帧 IMU 覆盖，以点云头时间作为去畸变参考。

IMU 接入不使用原 ROS 1 的 NED→ENU 脚本。外参来自 Scout CAD 安装模型和当前 ZED 出厂 IMU 标定，平移初值约为 `[0.092994, 0.036939, -0.170658] m`。在当前实现中，`extrinsicRot=R_lidar_imu`、`extrinsicRPY=R_imu_lidar`、`extrinsicTrans=t_lidar_imu`，两种旋转矩阵互为转置。换装或改变位置后需重新确认时空标定，噪声参数也需静态数据复核。

只有 TransformFusion 发布 `lio_odom → base_link` 动态 TF，车辆描述发布安装静态关系。运行时同一子坐标系应只有一个动态发布源。

## 检查与保存地图

在另一个终端加载环境，保持与运行进程相同的用户、`ROS_DOMAIN_ID` 和 DDS 设置：

```bash
source deploy/setup_env.bash
python3 tools/sensor_check.py --seconds 10 --output validation/sensors.json
ros2 topic echo /lio_sam/mapping/odometry --once
ros2 run tf2_ros tf2_echo lio_odom base_link
```

检查 32 条线齐全、点云和 IMU 时间戳递增、逐点时间范围约覆盖一圈、IMU 时间覆盖整帧、姿态四元数有效，以及静止加速度大小接近重力。节点启动成功本身不能说明建图精度达标。

**当前关闭自动保存 PCD、GPS 融合和闭环。停止或重启前需要显式保存地图。** 在建图运行时执行：

```bash
python3 tools/inspect_lap.py
```

该工具通过 `/lio_sam/save_map` 将快照保存到本工作区 `maps/lap_review_.../map` 的全新目录，并读取实时轨迹供分析。上游保存服务会删除目的目录并在路径前拼接 HOME；工具会检查新目的地和路径范围。不要对已有目录手工调用该服务。

离线分析和 PCD 显示方法见 [工具说明](../tools/README.md)。可将导出的 `GlobalMap.pcd` 发布为独立话题，再在 RViz 中选择 `pcd_map` 坐标系查看。

## 已有验证及限制

[VALIDATION.md](VALIDATION.md) 保留源码归档前的目标机记录：11 项转换测试通过，静止点云约 10Hz、IMU 约 395Hz、建图里程计约 4.9Hz。此前约 57m 行程生成了 69 个关键帧和约 28.7 万个有限地图点，未见明显位置突跳。

本次新目录已从仓库源码编译 GTSAM 和 9 个 ROS 2 包并运行验证：点云约 10Hz、IMU 约 326Hz、建图约 5Hz。详见验证记录；尚未测试空白系统整机安装。外参仍是初始估计，测试行程未回到出发位置；高度估计约 23cm 的跨度还需结合实际地形核对。长距离精度、运动去畸变和闭环效果需要进一步实车验证。

## 本机通信配置

未设置 `CYCLONEDDS_URI` 且使用 Cyclone DDS 时，环境脚本自动加载仓库内 `deploy/config/cyclonedds.xml`（部署目录中的 `config/cyclonedds.xml`）。默认通过 `lo` 和本机 peer 通信，无需用户目录配置文件或启用回环组播。适用于雷达、建图和 RViz 都在机器人上的部署。需要跨机器 ROS 2 通信时，在加载环境前显式设置自己的 `CYCLONEDDS_URI`；用户已有设置和 `ROS_DOMAIN_ID` 会保留。

依赖安装脚本将 Linux `net.core.rmem_max` 设置为当前值与 16MiB 中较大者，并单独持久化这一项，避免新机器的小接收缓冲限制大点云性能。不会降低已有的更大上限。相关参数含义见 [Cyclone DDS 配置说明](https://cyclonedds.io/docs/cyclonedds/latest/config/config_file_reference.html)。
