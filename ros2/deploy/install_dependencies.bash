#!/usr/bin/env bash
set -eo pipefail
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
  echo '用法：bash deploy/install_dependencies.bash'
  echo '安装 ROS 2 工作区的系统开发依赖；ROS 2 apt 源须已配置。ZED SDK 由 install_zed_sdk.bash 单独安装。'
  exit 0
fi
if [[ $# -ne 0 ]]; then echo '用法：bash deploy/install_dependencies.bash' >&2; exit 2; fi
deploy_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace="$(cd -- "$deploy_dir/.." && pwd)"
ros_distro="${ROS_DISTRO:-humble}"
if [[ ! "$ros_distro" =~ ^[a-z][a-z0-9_]*$ ]]; then echo 'ROS_DISTRO 格式无效。' >&2; exit 2; fi
if [[ ! -d "$workspace/src" || ! -f "$workspace/third_party/gtsam/CMakeLists.txt" ]]; then
  echo '源码目录不完整，请使用含 src/ 和 third_party/gtsam/ 的完整仓库。' >&2
  exit 1
fi
root_command=()
if [[ "$EUID" -ne 0 ]]; then
  if ! command -v sudo >/dev/null; then echo '安装系统依赖需要 sudo。' >&2; exit 1; fi
  sudo -v
  root_command=(sudo)
fi
"${root_command[@]}" apt-get update
if ! apt-cache show "ros-$ros_distro-ros-base" >/dev/null 2>&1; then
  echo "系统尚未配置 ROS 2 $ros_distro apt 源。请按 ROS 官方安装说明配置后重试。" >&2
  exit 1
fi
packages=(
  build-essential cmake ninja-build git pkg-config curl ca-certificates zstd procps iproute2
  python3-colcon-common-extensions
  python3-rosdep python3-numpy python3-yaml
  libboost-all-dev libeigen3-dev libpcl-dev libopencv-dev libyaml-cpp-dev
  libpcap-dev libusb-1.0-0-dev libudev-dev nlohmann-json3-dev
  "ros-$ros_distro-ros-base" "ros-$ros_distro-ament-cmake-auto"
  "ros-$ros_distro-rviz2" "ros-$ros_distro-rmw-cyclonedds-cpp"
  "ros-$ros_distro-cv-bridge" "ros-$ros_distro-pcl-conversions" "ros-$ros_distro-pcl-ros"
  "ros-$ros_distro-tf2-eigen" "ros-$ros_distro-tf2-geometry-msgs" "ros-$ros_distro-tf2-sensor-msgs"
  "ros-$ros_distro-robot-state-publisher" "ros-$ros_distro-xacro"
  "ros-$ros_distro-robot-localization" "ros-$ros_distro-diagnostic-updater"
  "ros-$ros_distro-image-transport" "ros-$ros_distro-image-transport-plugins"
  "ros-$ros_distro-compressed-image-transport" "ros-$ros_distro-compressed-depth-image-transport"
  "ros-$ros_distro-theora-image-transport" "ros-$ros_distro-nmea-msgs"
  "ros-$ros_distro-geographic-msgs" "ros-$ros_distro-backward-ros"
)
"${root_command[@]}" apt-get install -y --no-install-recommends "${packages[@]}"
if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
  "${root_command[@]}" rosdep init
fi
rosdep update
source "/opt/ros/$ros_distro/setup.bash"
# GTSAM is built from the checked-in third_party source, not from apt or a PPA.
rosdep install --from-paths "$workspace/src" --ignore-src --rosdistro "$ros_distro" \
  --skip-keys gtsam -r -y
# Large local PointCloud2 samples need enough receive-buffer capacity.
# Preserve a higher pre-existing Autoware setting; apply only this sysctl.
receive_buffer_current="$(sysctl -n net.core.rmem_max)"
if [[ ! "$receive_buffer_current" =~ ^[0-9]+$ ]]; then
  echo '无法读取 Linux 接收缓冲上限。' >&2
  exit 1
fi
receive_buffer_target="$receive_buffer_current"
if (( receive_buffer_target < 16777216 )); then receive_buffer_target=16777216; fi
printf '# Scout LIO-SAM local DDS receive capacity; preserves existing higher limit.\nnet.core.rmem_max=%s\n' "$receive_buffer_target" | \
  "${root_command[@]}" tee /etc/sysctl.d/99-scout-lio-dds.conf >/dev/null
"${root_command[@]}" sysctl -w "net.core.rmem_max=$receive_buffer_target" >/dev/null
echo '系统依赖已安装。若缺少 ZED SDK，运行 deploy/install_zed_sdk.bash；随后运行 deploy/build_lio_sam.bash。'
