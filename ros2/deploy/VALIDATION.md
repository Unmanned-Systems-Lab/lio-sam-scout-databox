# 目标机验证记录

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
