# Scout Autoware：ROS 2 LIO-SAM 建图

分支 `scout-autoware-ros2-helios32` 提供 **Jetson AGX Orin / Ubuntu 22.04 / ROS 2 Humble、RSHELIOS 32 线雷达和 ZED 2i IMU** 的实车配置。ROS 2 工作区在 [`ros2/`](ros2/)，原 ROS 1 文件保留在 `src/`，原说明见 [README_ROS1.md](README_ROS1.md)。

```bash
git clone --branch scout-autoware-ros2-helios32 git@github.com:Unmanned-Systems-Lab/lio-sam-scout-databox.git
cd lio-sam-scout-databox/ros2
bash deploy/build_lio_sam.bash
bash deploy/start_lio_sam.bash
```

这是已验证 Orin 的部署配置，不是独立安装全部驱动的通用安装器。编译前需具备下列工作区和库：

- `/opt/ros/humble`，以及 ROS 的 PCL、TF2、RViz2、xacro、robot_state_publisher。
- `/mnt/nvme0n1/autoware/autoware.scout/install` 的 Scout 车辆描述。
- `/mnt/nvme0n1/autoware/autoware.ez21/install` 的 RSHELIOS 驱动。
- `/mnt/nvme0n1/autoware/zed_ros2_ws/install` 与 ZED SDK 5.5.1。
- `/mnt/nvme0n1/autoware/gtsam/build` 中以系统 Eigen 编译的 GTSAM 4.2.0。

其他机器需先核对 `ros2/deploy/setup_env.bash`、`build_lio_sam.bash`、`prepare_gtsam.py` 的依赖路径。工作区本身的位置由脚本计算，无需覆盖现役建图目录。

## 本分支的更改

| 部分 | 更改 |
| --- | --- |
| ROS 2 | 基于官方 LIO-SAM `ros2` 分支 `08af3f32f01725372d4269838dc44c19c6d9e76b`，使用 ament/colcon、ROS 2 消息和启动文件 |
| 32 线雷达 | `N_SCAN=32`、`Horizon_SCAN=1800`；使用实测线号 `channel` 和逐点 `time_stamp`，转换为 LIO-SAM 的 XYZIRT |
| 点云时间 | 将相对纳秒转换为相对秒，保留真实采样时间；过滤无效点、拒绝明显时间错误；按最晚点检查整帧 IMU 覆盖，按帧首进行去畸变 |
| ZED IMU | 使用真实姿态的 `/zed2i/zed_node/imu/data`，请求 400Hz，不使用原 ROS 1 NED→ENU 脚本；区分向量与姿态外参方向 |
| 坐标和运行保护 | 独立 `lio_map/lio_odom`，保留单一 `odom→base_link` 发布源；保护空点云、空 IMU 队列和缺失 TF |
| Orin 环境 | 复用现有驱动与 SDK；为旧 GTSAM 路径生成工作区内的 CMake 副本，不修改原 GTSAM |
| 界面 | 默认打开 RViz2，显示地图、密集配准点云和轨迹；支持无界面启动与单独打开查看窗口 |
| 验证 | 11 项点云转换测试、实时传感器检查、安全保存新地图副本、离线 PCD/轨迹分析工具 |

核心仍是 LIO-SAM。本分支没有开启 GPS 融合、闭环或自动保存 PCD，也不包含底盘运动控制。

## 验证与限制

目标机已编译通过，11 项转换测试通过。实测点云约 10Hz、静止 IMU 约 395Hz、建图里程计约 4.9Hz。约 57m 的遥控测试生成 69 个关键帧和约 28.7 万个地图点，未见明显位置突跳或 IMU 异常复位。

外参是现有 Scout 安装模型与当前 ZED 出厂 IMU 标定的初始估计。此次运动的高度估计跨度约 23cm，尚需结合地形核对；未回到同一物理起点，因此不能据此认定闭环或累计误差达标。

地图、rosbag、截图、原始日志及编译产物不提交到本分支。运行数据继续保存在目标机现役工作区。

- [详细部署与 RViz 操作](ros2/deploy/README.md)
- [验证记录](ros2/deploy/VALIDATION.md)
- [传感器与 PCD 分析工具](ros2/tools/README.md)
- [相对官方 ROS 2 版本的核心补丁](ros2/deploy/lio_sam_ros2.patch)

上游 LIO-SAM 的 BSD 3-Clause 许可证和版权保留于 [`ros2/src/lio_sam_ros2/LICENSE`](ros2/src/lio_sam_ros2/LICENSE)。
