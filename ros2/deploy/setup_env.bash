#!/usr/bin/env bash
# Source this file; no processes are started here.
_lio_deploy_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export SCOUT_LIO_WS="$(cd -- "$_lio_deploy_dir/.." && pwd)"

for _lio_setup in \
  /opt/ros/humble/setup.bash \
  /mnt/nvme0n1/autoware/autoware.scout/install/scout_vehicle_description/share/scout_vehicle_description/local_setup.bash \
  /mnt/nvme0n1/autoware/autoware.ez21/install/rslidar_sdk/share/rslidar_sdk/local_setup.bash \
  /mnt/nvme0n1/autoware/zed_ros2_ws/install/local_setup.bash; do
  if [[ ! -f "$_lio_setup" ]]; then
    echo "缺少依赖环境：$_lio_setup" >&2
    return 1
  fi
  source "$_lio_setup" || return
done
if [[ -f "$SCOUT_LIO_WS/install/lio_sam/share/lio_sam/local_setup.bash" \
   && -f "$SCOUT_LIO_WS/install/local_setup.bash" ]]; then
  source "$SCOUT_LIO_WS/install/local_setup.bash" || return
elif [[ "${SCOUT_LIO_ALLOW_UNBUILT:-0}" != 1 ]]; then
  echo "请先运行 $SCOUT_LIO_WS/deploy/build_lio_sam.bash" >&2
  return 1
fi

export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}"
export ZED_DIR=/mnt/nvme0n1/autoware/zed_sdk_5.5.1
# Keep the caller's ROS_DOMAIN_ID and DDS network configuration.
export LD_LIBRARY_PATH="/mnt/nvme0n1/autoware/zed_sdk_5.5.1/lib:/mnt/nvme0n1/autoware/gtsam/build/gtsam:/mnt/nvme0n1/autoware/gtsam/build/gtsam_unstable:/mnt/nvme0n1/autoware/gtsam/build/gtsam/3rdparty/metis/libmetis${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
unset _lio_setup _lio_deploy_dir
