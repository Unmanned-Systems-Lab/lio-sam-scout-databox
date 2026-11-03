#!/usr/bin/env bash
# Source only ROS and this checkout. Do not load another Autoware workspace.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo '请使用 source deploy/setup_env.bash 加载环境。' >&2
  exit 2
fi

_scout_lio_load_environment() {
  local deploy_dir workspace ros_distro ros_setup sdk_root sdk_config sdk_lib
  local gtsam_prefix gtsam_config config candidate
  deploy_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || return
  workspace="$(cd -- "$deploy_dir/.." && pwd)" || return
  ros_distro="${ROS_DISTRO:-humble}"
  ros_setup="/opt/ros/$ros_distro/setup.bash"
  if [[ ! -f "$ros_setup" ]]; then
    echo "缺少 ROS 2 $ros_distro：$ros_setup。请先安装对应 ROS 2 发行版。" >&2
    return 1
  fi
  # Reusing another workspace's prefixes can silently select its packages.
  # CUDA/NVIDIA system libraries remain available through the system loader.
  unset AMENT_PREFIX_PATH COLCON_PREFIX_PATH CMAKE_PREFIX_PATH PYTHONPATH LD_LIBRARY_PATH
  unset AMENT_CURRENT_PREFIX COLCON_CURRENT_PREFIX
  source "$ros_setup" || return
  export SCOUT_LIO_WS="$workspace"

  sdk_root="${ZED_DIR:-/usr/local/zed}"
  if [[ ! -d "$sdk_root" ]]; then
    echo "缺少 ZED SDK：$sdk_root。" >&2
    echo "请运行 bash $deploy_dir/install_zed_sdk.bash，或用 ZED_DIR 指定已安装的 SDK 根目录。" >&2
    return 1
  fi
  sdk_root="$(cd -- "$sdk_root" && pwd -P)" || return
  sdk_config=''
  for config in "$sdk_root/zed-config.cmake" "$sdk_root/ZEDConfig.cmake" \
    "$sdk_root/lib/cmake/zed/zed-config.cmake"; do
    if [[ -f "$config" ]]; then sdk_config="$config"; break; fi
  done
  sdk_lib=''
  for candidate in "$sdk_root/lib" "$sdk_root/lib64"; do
    if compgen -G "$candidate/libsl_zed.so*" >/dev/null; then sdk_lib="$candidate"; break; fi
  done
  if [[ -z "$sdk_config" || -z "$sdk_lib" || ! -f "$sdk_root/include/sl/Camera.hpp" ]]; then
    echo "ZED_DIR=$sdk_root 不是完整的 ZED SDK 开发目录（需 CMake 配置、头文件和 libsl_zed.so）。" >&2
    echo "请运行 bash $deploy_dir/install_zed_sdk.bash，或修正 ZED_DIR。" >&2
    return 1
  fi
  export ZED_DIR="$sdk_root"
  export SCOUT_LIO_ZED_CMAKE_DIR="$(dirname -- "$sdk_config")"

  gtsam_prefix="$workspace/.deps/gtsam-install"
  gtsam_config="$gtsam_prefix/lib/cmake/GTSAM/GTSAMConfig.cmake"
  export SCOUT_LIO_GTSAM_PREFIX="$gtsam_prefix"
  export GTSAM_DIR="$(dirname -- "$gtsam_config")"
  if [[ "${SCOUT_LIO_ALLOW_UNBUILT:-0}" != 1 && ! -f "$gtsam_config" ]]; then
    echo "本仓库的 GTSAM 尚未构建，请先运行 bash $deploy_dir/build_lio_sam.bash。" >&2
    return 1
  fi
  export CMAKE_PREFIX_PATH="$gtsam_prefix:$SCOUT_LIO_ZED_CMAKE_DIR${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
  export LD_LIBRARY_PATH="$gtsam_prefix/lib:$sdk_lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

  if [[ -f "$workspace/install/local_setup.bash" ]]; then
    source "$workspace/install/local_setup.bash" || return
  elif [[ "${SCOUT_LIO_ALLOW_UNBUILT:-0}" != 1 ]]; then
    echo "本仓库 ROS 2 包尚未构建，请先运行 bash $deploy_dir/build_lio_sam.bash。" >&2
    return 1
  fi
  if [[ "${SCOUT_LIO_ALLOW_UNBUILT:-0}" != 1 ]]; then
    local package package_prefix resolved_prefix
    for package in lio_sam scout_lio_support scout_vehicle_description \
      rslidar_sdk rslidar_msg zed_wrapper zed_components zed_msgs zed_description; do
      if ! package_prefix="$(ros2 pkg prefix "$package" 2>/dev/null)"; then
        echo "本仓库未安装必要包 $package，请重新运行 deploy/build_lio_sam.bash。" >&2
        return 1
      fi
      if ! resolved_prefix="$(realpath -e -- "$package_prefix")"; then
        echo "包 $package 的安装目录无效：$package_prefix。" >&2
        return 1
      fi
      case "$resolved_prefix" in
        "$workspace/install"|"$workspace/install"/*) ;;
        *)
          echo "拒绝加载工作区外的包 $package：$resolved_prefix。" >&2
          echo "请构建本仓库源码，不要使用旧 Autoware 或 ZED 工作区补齐依赖。" >&2
          return 1 ;;
      esac
    done
  fi
  if [[ -z "${RMW_IMPLEMENTATION:-}" ]]; then
    if [[ -f "/opt/ros/$ros_distro/share/rmw_cyclonedds_cpp/package.xml" ]]; then
      export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
    else
      export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
    fi
  fi
  if [[ "$RMW_IMPLEMENTATION" == rmw_cyclonedds_cpp && ! -v CYCLONEDDS_URI ]]; then
    if [[ ! -f "$deploy_dir/config/cyclonedds.xml" ]]; then
      echo "缺少本仓库 DDS 配置：$deploy_dir/config/cyclonedds.xml。" >&2
      return 1
    fi
    export CYCLONEDDS_URI="file://$deploy_dir/config/cyclonedds.xml"
  fi
  # ROS_DOMAIN_ID and any explicitly provided CYCLONEDDS_URI are preserved.
}

# ROS setup files may reference unset variables. Restore the caller's setting.
_scout_lio_restore_nounset=0
if [[ "$-" == *u* ]]; then _scout_lio_restore_nounset=1; set +u; fi
if _scout_lio_load_environment; then _scout_lio_env_status=0; else _scout_lio_env_status=$?; fi
unset -f _scout_lio_load_environment
if [[ "$_scout_lio_restore_nounset" == 1 ]]; then set -u; fi
if [[ "$_scout_lio_env_status" == 0 ]]; then
  unset _scout_lio_env_status _scout_lio_restore_nounset
  return 0
fi
unset _scout_lio_env_status _scout_lio_restore_nounset
return 1
