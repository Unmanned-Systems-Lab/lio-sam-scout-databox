# 目标机验证记录

## 2026-11-03：依赖源码归档后的新目录验证

平台为 Jetson AGX Orin 32GB、Ubuntu 22.04.5、JetPack 6.2.2 / L4T 36.5、CUDA 12.6、ROS 2 Humble。以下是在已有操作系统上的全新项目构建，不是空白系统安装测试。

- 清空继承的 ROS、CMake、Python 和动态库路径，只加载系统 ROS、标准 `/usr/local/zed` SDK 与当前仓库。
- ZED SDK 5.5.1 官方安装成功，安装器 SHA256 与固定清单一致；未复制 SDK 二进制到 Git。
- 从 `third_party/gtsam` 编译 GTSAM 4.2.0（系统 Eigen、关闭 TBB），随后源码构建所需的 9 个 ROS 2 包全部成功，退出码 0；ROS 2 构建耗时约 8 分 22 秒，不含 GTSAM。编译日志有上游弃用提示和各包未使用的通用 CMake 参数提示。
- 11 项点云转换测试通过；Bash、项目 Python、配置 YAML/XML 和包清单检查通过；rosdep 检查所需系统依赖齐全。
- 9 个来源组件的文件数和 SHA256 核验通过。从 Git 暂存区导出到不含 Git 元数据的新目录后也通过。无嵌套 Git、gitlink、未解析 LFS 指针、外部源码链接或预编译库。
- 运行时检查实际库映射：GTSAM 来自本工作区 `.deps/gtsam-install`，ZED SDK 来自 `/usr/local/zed`；未加载旧 Autoware、旧 ZED ROS 或旧建图工作区的库。
- 使用仓库内 Cyclone DDS 本机配置启动完整传感器、LIO-SAM 和 RViz。12 秒采样：原始与转换点云均约 10.0Hz，32 条线齐全；ZED IMU 约 325.7Hz，姿态四元数范数约 1；建图里程计约 5.0Hz。
- 30 秒静止采样收到 151 帧建图里程计，约 5.0Hz，位置有限且时间戳递增；x/y/z 跨度约 3.04/4.50/4.20mm。最大里程计间隔约 0.210 秒；12 秒传感器窗口中点云最大间隔约 0.110 秒，IMU 约 0.030 秒。
- `lio_odom → base_link`、车辆到雷达、雷达到 IMU 的 TF 均可查询，旋转四元数范数为 1。
- 启动时一帧带 `UINT32_MAX` 逐点时间的无效点云被适配器拒绝；后续稳定采样正常。未观察到运行错误、崩溃或异常速度/偏置复位。
- 重复启动检查通过：运行中再次启动会拒绝创建第二套节点。桌面入口会指向当前检出目录。

默认 DDS 使用本机回环和本机 peer，避免依赖用户目录中的配置。目标机已有较大的 Linux 接收缓冲上限；新机安装脚本会持久设置 `rmem_max` 为现有值与 16MiB 中较大者。自定义 DDS、跨机器通信及不同硬件仍需按部署条件验证。

原始日志和截图保存在目标工作区 `validation/`，不提交到 Git。此前遥控行程地图已另存，仍可用独立 PCD 查看窗口查看。此轮为静止运行验证，未新增运动精度或闭环结论。

## 源码归档前的验证记录

日期：2026-11-03（香港时间）。主机：`agx@192.168.1.102`，Jetson AGX Orin 32GB，Ubuntu 22.04.5 / ROS 2 Humble。

- 两个包 `lio_sam`、`scout_lio_support` 编译成功；最终增量编译退出码 0。
- 点云转换的 11 项测试在目标机全部通过。
- 在清空继承环境的 shell 中，使用 `deploy/start_lio_sam.bash` 启动整套雷达、ZED、坐标系和 LIO-SAM。
- 30 秒实时静止测试收到 146 帧建图里程计，约 4.87Hz；所有位置数值有限，时间戳单调递增。
- 该窗口的 x/y/z 位置最大跨度分别约 4.09/4.81/4.33mm。这只描述短时间静止稳定性，不代表运动精度。
- 雷达与转换后点云约 9.7Hz，32 条线齐全，逐点时间约 0～0.100s；过滤 NaN 后约 5.17 万点/帧。
- ZED IMU 约 394.6Hz，四元数范数接近 1，时间戳单调递增。
- 该测试窗口中，点云最大帧间隔约 0.30s，IMU 最大间隔约 0.018s；运动测试应继续检查数据间隔与时空标定。
- 实时运行测试阶段没有检测到错误、警告或进程崩溃。

目标机的原始记录保存在工作区 `validation/`：`build_final.log`、`lio_full.log`、`lio_live_smoke.json`。测试后停止本次启动，不设置开机自启。

停止时，现有雷达驱动未及时响应退出信号，ROS 2 启动器超时后将其结束。已确认所有本次传感器和 LIO-SAM 进程停止、雷达端口释放；此退出行为与运行阶段的建图验证分开记录。

外参来自现有 Scout CAD 模型与当前 ZED 相机的出厂 IMU 标定。尚未进行实车雷达/IMU 联合标定、运动去畸变精度或长距离闭环测试。

UI update verified: RViz2 is running on the logged-in Orin desktop, global status OK; map_global, cloud_registered_raw and mapping/path configured. Default launcher opens RViz; rviz:=false retains headless mode.

## 运动功能验证

2026-11-03 遥控测试的关键帧路线约 57.3m / 102.6s，保存了 69 个关键帧和 287360 个有限地图点。检查到的当前点云约 10Hz、建图里程计约 4.91Hz，相关节点日志未记录异常速度、IMU 偏置复位或特征不足。轨迹高度估计跨度约 0.232m，需结合实际地形核对。机器人没有返回相同物理起点，本次不能用于闭环或回程漂移精度结论；闭环当前关闭。原始地图、轨迹和日志仅保存在目标机，不在本分支内。
