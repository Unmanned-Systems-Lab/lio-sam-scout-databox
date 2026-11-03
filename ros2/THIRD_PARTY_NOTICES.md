# 第三方源码与许可证

本仓库保留项目所需的开源依赖源码，以便从当前检出目录构建。嵌套 Git 元数据已移除；各源码目录原有的 `LICENSE`、`COPYING`、`NOTICE`、版权头及第三方声明继续适用。下表是来源索引，不能替代对应源码中的完整许可文本。

准确来源、提交和本地修改记录以 [SOURCE_VERSIONS.json](SOURCE_VERSIONS.json) 为准。带本地适配的源码不能视为未经修改的上游发行包。

| 源码目录 | 来源 / 固定基线 | 主要许可证 |
| --- | --- | --- |
| `src/lio_sam_ros2` | [TixiaoShan/LIO-SAM](https://github.com/TixiaoShan/LIO-SAM)，`ros2` 分支，`08af3f32f01725372d4269838dc44c19c6d9e76b`，附本地适配 | BSD 3-Clause |
| `src/scout_vehicle_description` | 本项目使用的 Autoware Scout 车辆描述，来源和本地版本见清单 | `LICENSE-ELE` 为 MIT；`package.xml` 和来源仓库根 `LICENSE` 声明 Apache-2.0，详见下文 |
| `src/scout_sensor_kit_description` | 本项目使用的 Autoware Scout 传感器描述，来源和本地版本见清单 | Apache-2.0，依据包声明与来源仓库根许可证 |
| `src/rslidar_sdk` | [RoboSense rslidar_sdk](https://github.com/RoboSense-LiDAR/rslidar_sdk)，含本地 ROS 2 / 点云格式适配 | BSD，具体条款见原文件 |
| `src/rslidar_sdk/src/rs_driver` | [RoboSense rs_driver](https://github.com/RoboSense-LiDAR/rs_driver) | BSD，具体条款见原文件 |
| `src/rslidar_msg` | [RoboSense rslidar_msg](https://github.com/RoboSense-LiDAR/rslidar_msg) | BSD，具体条款见原文件 |
| `src/zed-ros2-wrapper` | [Stereolabs zed-ros2-wrapper](https://github.com/stereolabs/zed-ros2-wrapper)，5.5.0，`b19902daf0136b6e841b5e415c2d01f425411c45` | Apache-2.0 |
| `src/zed_msgs` | [Stereolabs zed-ros2-interfaces](https://github.com/stereolabs/zed-ros2-interfaces)，5.5.0，`24f8d513ac8d4145a3bb6d72258f7e030443c1d8` | Apache-2.0 |
| `src/zed_description` | [Stereolabs zed-ros2-description](https://github.com/stereolabs/zed-ros2-description)，0.2.0，`22468247c1653d08a1e213809f3e9ce76291487d` | Apache-2.0 |
| `third_party/gtsam` | [borglab/gtsam](https://github.com/borglab/gtsam)，4.2.0，`c57988fe554e7213c77fe379c1d7c483de26ad33` | BSD 3-Clause；内含第三方代码另有许可 |

GTSAM、雷达驱动和其他上游工程可能包含各自的第三方组件。分发或修改时，应一并保留这些组件原有的许可证和声明。项目自己的 `scout_lio_support` 适配代码按其目录中的许可文件处理。

Scout 车辆描述的来源声明存在差异：目录中的 [`LICENSE-ELE`](src/scout_vehicle_description/LICENSE-ELE) 为 MIT，版权标注为 © 2026 CQULzz；其 `package.xml` 声明 Apache-2.0，来源仓库根 `LICENSE` 也为 Apache-2.0。本次归档保留这些原始声明，不将整个车辆描述统一认定为 Apache-2.0，也不修改原生许可证内容。传感器描述包的 `package.xml` 与来源仓库根许可证均声明 Apache-2.0。

## 独立安装的系统组件

ROS 2、JetPack/CUDA、系统软件包及 ZED SDK 由各自的软件源或官方安装器安装，适用各自许可证。编译后的库、模型、安装包和缓存不作为上述开源源码归档的一部分上传。

**ZED ROS 2 包采用 Apache-2.0，不代表 ZED SDK 同样采用该许可证。** 当前 SDK 安装包的厂商许可包含复制限制，因此本仓库不镜像 SDK 文件。`deploy/install_zed_sdk.bash` 从官方地址取得 ZED SDK 5.5.1，并核验固定校验值；默认显示厂商安装交互供用户审阅。SDK 的使用和分发应遵循随安装包提供的条款及 [Stereolabs 软件许可](https://www.stereolabs.com/SoftwareandServicesLicenseAgreement)。

安装过程见 [SDK 说明](third_party/zed_sdk/README.md) 与 [Stereolabs Linux 安装文档](https://docs.stereolabs.com/docs/development/zed-sdk/linux)。本次整理保留原有 SDK IMU 后端及其姿态输出。
