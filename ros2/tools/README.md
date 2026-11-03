# 检查与离线分析

请先在 ROS 2 工作区执行 `source deploy/setup_env.bash`。检查程序需与运行中的建图进程使用相同的用户、ROS_DOMAIN_ID 和 DDS 配置。

```bash
python3 tools/sensor_check.py --seconds 10 --output validation/sensors.json
python3 tools/inspect_lap.py
```

`sensor_check.py` 检查消息频率、时间戳、线号、逐点时间、姿态和坐标系。`inspect_lap.py` 会读取实时话题，并通过 `/lio_sam/save_map` 保存到本工作区 `maps/lap_review_.../map` 下的全新目录，不重启建图。

原 LIO-SAM 保存服务会删除目的目录，并在目的路径前拼接 HOME。检查程序为此次保存创建临时 HOME 符号链接，显式检查目的目录不存在且最终路径留在工作区 `maps/` 下；不要手工对已有目录直接调用该服务。服务超时后，程序会保留临时链接并在结果中说明。

离线读取导出的二进制 PCD：

```bash
python3 tools/review_lap.py --input maps/<本次目录>/map --output maps/<本次目录>/analysis
```

分析工具需要 NumPy；绘图另需 Matplotlib。可在单独的 Python 环境中安装 `tools/requirements.txt`。报告中的行程是关键帧采样估计；只有确实回到同一物理位置，首尾距离才可用于评估回程误差。关键帧时间间隔较长不等于传感器丢帧。

PCD 使用原生 `pcl_ros` 工具也可发布到单独话题查看：

```bash
ros2 run pcl_ros pcd_to_pointcloud --ros-args \
  -p file_name:=/绝对路径/GlobalMap.pcd \
  -p tf_frame:=pcd_map -p publishing_period_ms:=1000 \
  -r cloud_pcd:=/saved_map/points
```

在单独 RViz2 窗口把 Fixed Frame 设为 `pcd_map`，添加 PointCloud2 并选择 `/saved_map/points`。
