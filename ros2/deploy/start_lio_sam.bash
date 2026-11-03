#!/usr/bin/env bash
set -eo pipefail
deploy_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$deploy_dir/setup_env.bash"
set -u

start_sensors=true
show_rviz=true
for argument in "$@"; do
  case "$argument" in
    start_sensors:=false|start_sensors:=False|start_sensors:=0) start_sensors=false ;;
    rviz:=false|rviz:=False|rviz:=0) show_rviz=false ;;
  esac
done
if [[ "$show_rviz" == true ]]; then
  source "$deploy_dir/desktop_env.bash"
fi
existing_nodes="$(timeout 15 ros2 node list 2>/dev/null || true)"
if printf '%s\n' "$existing_nodes" | grep -Eq '/lio_sam_(imageProjection|featureExtraction|mapOptimization|imu_preintegration|imuPreintegration|transformFusion)$|/robosense_to_lio$'; then
  echo '已有 LIO-SAM 节点运行，请先停止该次启动。' >&2
  exit 1
fi
if [[ "$start_sensors" == true ]]; then
  if printf '%s\n' "$existing_nodes" | grep -Eq '^(/zed2i/zed_node|/rslidar_sdk|/param_handle)$'; then
    echo '已有雷达或 ZED 驱动运行。复用现有驱动时加 start_sensors:=false。' >&2
    exit 1
  fi
  if ss -H -lun | grep -Eq ':(3344|5566)[[:space:]]'; then
    echo '雷达 UDP 端口 3344/5566 已占用；复用现有驱动时加 start_sensors:=false。' >&2
    exit 1
  fi
fi

echo '启动 LIO-SAM、32 线雷达和 ZED 2i IMU；默认打开地图查看界面。按 Ctrl+C 停止。'
exec ros2 launch "$deploy_dir/launch/scout_lio.launch.py" "$@"
