# Scout Autoware：ROS 2 LIO-SAM 建图

分支 `scout-autoware-ros2-helios32` 面向 **Jetson AGX Orin、ROS 2 Humble、RSHELIOS 32 线雷达和 ZED 2i IMU**。项目需要的车辆描述、雷达驱动、ZED ROS 2 包和 GTSAM 开源源码已放入本仓库；编译和启动从当前检出目录定位依赖。

```text
legacy/ros1/                 原 ROS 1 代码、文档与说明
ros2/
  src/                      LIO-SAM、适配器、车辆描述、传感器驱动与消息
  third_party/gtsam/        GTSAM 4.2.0 源码
  third_party/zed_sdk/       ZED SDK 安装与许可证说明
  deploy/                   安装、编译、启动和 RViz 配置
  tools/                    传感器检查、地图保存与 PCD 分析
```

## 从新检出目录运行

目标平台为 Ubuntu 22.04 / JetPack 6.2.2（L4T 36.5、CUDA 12.6）/ ROS 2 Humble。先准备 JetPack 和 ROS 2 官方软件源，然后运行：

```bash
git clone --branch scout-autoware-ros2-helios32 git@github.com:Unmanned-Systems-Lab/lio-sam-scout-databox.git
cd lio-sam-scout-databox/ros2
bash deploy/install_dependencies.bash
bash deploy/install_zed_sdk.bash
bash deploy/build_lio_sam.bash
bash deploy/start_lio_sam.bash
```

ZED SDK 是独立的厂商二进制开发包，没有复制到仓库。安装脚本从官方地址下载校验过的 **5.5.1** 安装包，默认由用户阅读并处理厂商许可证。ROS、JetPack/CUDA 及 apt 系统开发包也由系统安装；项目专用开源依赖从仓库源码编译，GTSAM 安装在 `ros2/.deps/gtsam-install`。完整边界和离线安装方法见 [ROS 2 说明](ros2/README.md) 与 [SDK 说明](ros2/third_party/zed_sdk/README.md)。

启动后默认在 Orin 已登录的桌面打开 RViz2。无界面启动：

```bash
bash deploy/start_lio_sam.bash rviz:=false
```

## 建图适配

| 部分 | 当前实现 |
| --- | --- |
| ROS 2 | 基于官方 LIO-SAM `ros2` 分支，使用 ament/colcon、ROS 2 消息和启动文件 |
| 32 线雷达 | `N_SCAN=32`、`Horizon_SCAN=1800`；读取真实 `channel` 和逐点 `time_stamp`，转换为 XYZIRT |
| 点云时间 | 相对纳秒转相对秒；过滤无效点、检查时间范围；用最晚点确认整帧 IMU 覆盖，按帧首去畸变 |
| ZED IMU | 保留 SDK 提供姿态的 `/zed2i/zed_node/imu/data`，请求 400Hz，区分向量与姿态外参方向 |
| 坐标与保护 | 使用 `lio_map/lio_odom`；单一动态里程计 TF；处理空点云、空 IMU 队列和缺失 TF |
| 可视化 | RViz2 显示累计地图、密集配准点云和轨迹，支持单独打开查看窗口 |
| 源码组织 | 依赖源码随仓库保存，移除嵌套 Git 元数据，保留原许可证、版权和第三方声明 |

核心算法仍为 LIO-SAM。GPS 融合、闭环和自动保存 PCD 当前关闭；启动文件只运行建图相关节点。退出前如需保留地图，请按 [部署说明](ros2/deploy/README.md) 显式保存。

## 验证状态

此前目标机运行完成了 11 项点云转换测试和静止联调；约 57m 的遥控行程得到 69 个关键帧和约 28.7 万个有限地图点，未见明显位置突跳。此次未回到出发位置，不能据此评估回程误差或闭环；高度估计跨度约 23cm，仍需结合地形和外参核对。

本次在目标机新目录中清空继承路径，从仓库源码重编译 GTSAM 和 9 个 ROS 2 包并完成运行检查：点云约 10Hz、IMU 约 326Hz、里程计约 5Hz，RViz 显示正常。详见 [验证记录](ros2/deploy/VALIDATION.md)。这是已有 JetPack/ROS 系统上的验证，尚未测试空白系统整机安装。外参来自 Scout 安装模型与当前相机出厂 IMU 标定，仍需实车时空标定和长距离精度验证。

- [ROS 2 工作区与依赖](ros2/README.md)
- [部署、RViz 与地图保存](ros2/deploy/README.md)
- [源码来源与许可证](ros2/THIRD_PARTY_NOTICES.md)
- [传感器与 PCD 分析工具](ros2/tools/README.md)
- [原 ROS 1 说明](legacy/ros1/README.md)

地图、rosbag、原始日志、截图和编译产物不纳入源码仓库。
