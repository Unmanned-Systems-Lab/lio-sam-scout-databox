# ROS 2 工作区

本目录是 Scout / RSHELIOS 32 线 / ZED 2i 的 LIO-SAM 工作区。所需项目源码已随仓库保存，工作区可以放在任意有足够空间的目录；构建脚本通过自身位置寻找源码和安装目录。

## 源码布局

| 路径 | 用途 |
| --- | --- |
| `src/lio_sam_ros2` | 官方 ROS 2 LIO-SAM 与本项目补丁 |
| `src/scout_lio_support` | 点云字段适配、系统启动与 RViz 配置 |
| `src/scout_vehicle_description` | Scout 车辆安装模型 |
| `src/scout_sensor_kit_description` | 传感器安装模型与静态坐标关系 |
| `src/rslidar_sdk` | RoboSense 驱动，包含 `src/rs_driver` 源码 |
| `src/rslidar_msg` | 雷达驱动消息 |
| `src/zed-ros2-wrapper` | ZED ROS 2 驱动源码 |
| `src/zed_msgs`、`src/zed_description` | ZED 消息与相机描述源码 |
| `third_party/gtsam` | GTSAM 4.2.0 源码 |
| `third_party/zed_sdk` | 独立 SDK 的安装与许可说明 |
| `deploy`、`tools` | 部署、配置、验证与地图分析 |

源码版本见 [SOURCE_VERSIONS.json](SOURCE_VERSIONS.json)，许可证说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。嵌套仓库的 Git 元数据已移除，无需初始化 Git 子模块。源码自带的许可证、版权和第三方声明仍保留在对应目录。

下载后可先核验源码快照完整性（不需要 ROS）：

```bash
python3 tools/audit_source_bundle.py
```

该检查同时拒绝嵌套 Git、预编译库和旧工作区依赖路径；源码修改后需同步更新版本清单中的快照哈希。

## 平台与依赖

当前配置针对 Jetson AGX Orin / Ubuntu 22.04 / JetPack 6.2.2（L4T 36.5、CUDA 12.6）/ ROS 2 Humble。新机器需要先安装兼容的 JetPack，并按 [ROS 2 官方 Ubuntu 安装说明](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html) 配置软件源。

项目专用开源依赖随仓库提供；ROS、PCL、Eigen、Boost、OpenCV 等标准系统包通过 apt 安装。`install_dependencies.bash` 安装构建和运行所需软件包，并用 rosdep 解析源码依赖。GTSAM 不使用系统旧构建目录：`build_lio_sam.bash` 从 `third_party/gtsam` 编译，以系统 Eigen 构建，安装到本工作区 `.deps/gtsam-install`。

ZED ROS 2 源码与 ZED SDK 是不同组件。本仓库包含前者；后者的厂商二进制、模型和安装包未上传。保留 SDK 的校准 IMU 姿态后端，由 [官方 SDK 安装脚本](deploy/install_zed_sdk.bash) 下载固定版本并校验 SHA256。默认交互安装让用户阅读厂商许可证；明确同意后，可使用 `--accept-license` 自动安装。详见 [SDK 安装说明](third_party/zed_sdk/README.md) 和 [厂商安装文档](https://docs.stereolabs.com/docs/development/zed-sdk/linux)。

## 安装、编译和运行

以下命令均在本目录执行：

```bash
bash deploy/install_dependencies.bash
bash deploy/install_zed_sdk.bash
bash deploy/build_lio_sam.bash
bash deploy/start_lio_sam.bash
```

SDK 默认安装到 `/usr/local/zed`。已有完整 SDK 开发环境时，可通过 `ZED_DIR` 指定其根目录。只安装运行库不足以编译 ZED ROS 2 包，还需要头文件和 CMake 配置。

构建默认最多使用两个编译任务，可按内存条件调整：

```bash
SCOUT_LIO_BUILD_JOBS=2 bash deploy/build_lio_sam.bash
```

构建会先编译仓库内 GTSAM，再用 colcon 构建本仓库需要的 ROS 2 包。构建产物位于 `.deps/`、`build/`、`install/`、`log/`，不提交到 Git。首次安装依赖和下载 SDK 需要网络；离线机器可预先准备系统软件包，并使用 `install_zed_sdk.bash --installer /绝对路径/安装包.run` 提供已取得的官方安装包。

默认启动 RViz2，需先登录 Orin 图形桌面；窗口显示在 Orin 桌面，可通过显示器或远程桌面查看。无界面运行：

```bash
bash deploy/start_lio_sam.bash rviz:=false
```

运行中的话题检查、地图保存和工具调用需要加载本目录环境：

```bash
source deploy/setup_env.bash
python3 tools/sensor_check.py --seconds 10 --output validation/sensors.json
```

`setup_env.bash` 加载 `/opt/ros/humble`、当前 SDK、本工作区 GTSAM 和 ROS 2 安装结果，并保留调用方的 `ROS_DOMAIN_ID` 与 DDS 网络配置。部署细节、可视化和检查方法见 [deploy/README.md](deploy/README.md)。

## 实车配置与验证边界

雷达配置为在线 RSHELIOS、32 线、每圈 1800 列、约 10Hz；ZED IMU 请求 400Hz。当前安装外参和噪声参数是该 Scout 的初值，换装传感器或更换安装位置后，需要重新确认型号、网络、坐标关系和标定。

[VALIDATION.md](deploy/VALIDATION.md) 记录了本次新目录内 GTSAM 和 9 个 ROS 2 包源码构建、依赖映射、约 10Hz 点云及 5Hz 静止建图验证；同时保留此前运动记录。该验证在已有 JetPack/ROS 的目标机上完成，不代表空白系统整机安装测试。没有回到同一物理起点的行程不能用于证明闭环或累计误差达标。

## 本机通信配置

未设置 `CYCLONEDDS_URI` 且使用 Cyclone DDS 时，环境脚本自动加载仓库内 `deploy/config/cyclonedds.xml`（部署目录中的 `config/cyclonedds.xml`）。默认通过 `lo` 和本机 peer 通信，无需用户目录配置文件或启用回环组播。适用于雷达、建图和 RViz 都在机器人上的部署。需要跨机器 ROS 2 通信时，在加载环境前显式设置自己的 `CYCLONEDDS_URI`；用户已有设置和 `ROS_DOMAIN_ID` 会保留。

依赖安装脚本将 Linux `net.core.rmem_max` 设置为当前值与 16MiB 中较大者，并单独持久化这一项，避免新机器的小接收缓冲限制大点云性能。不会降低已有的更大上限。相关参数含义见 [Cyclone DDS 配置说明](https://cyclonedds.io/docs/cyclonedds/latest/config/config_file_reference.html)。
