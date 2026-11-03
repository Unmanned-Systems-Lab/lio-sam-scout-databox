#!/usr/bin/env bash
set -eo pipefail
deploy_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace="$(cd -- "$deploy_dir/.." && pwd)"
jobs="${SCOUT_LIO_BUILD_JOBS:-2}"
if [[ ! "$jobs" =~ ^[1-9][0-9]*$ ]]; then
  echo 'SCOUT_LIO_BUILD_JOBS 必须是正整数。' >&2
  exit 2
fi

# Package lookup must not depend on a previously sourced Autoware checkout.
unset AMENT_PREFIX_PATH COLCON_PREFIX_PATH CMAKE_PREFIX_PATH PYTHONPATH
export SCOUT_LIO_ALLOW_UNBUILT=1
source "$deploy_dir/setup_env.bash"
unset SCOUT_LIO_ALLOW_UNBUILT

gtsam_source="$workspace/third_party/gtsam"
gtsam_build="$workspace/.deps/gtsam-build"
gtsam_install="$workspace/.deps/gtsam-install"
if [[ ! -f "$gtsam_source/CMakeLists.txt" ]]; then
  echo "仓库缺少 GTSAM 源码：$gtsam_source。请使用包含 third_party 的完整分支。" >&2
  exit 1
fi
export CMAKE_BUILD_PARALLEL_LEVEL="$jobs"
export MAKEFLAGS="-j$jobs"
cmake -S "$gtsam_source" -B "$gtsam_build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$gtsam_install" -DCMAKE_INSTALL_LIBDIR=lib \
  -DBUILD_SHARED_LIBS=ON -DGTSAM_USE_SYSTEM_EIGEN=ON \
  -DGTSAM_WITH_TBB=OFF -DGTSAM_BUILD_WITH_MARCH_NATIVE=OFF \
  -DGTSAM_BUILD_TESTS=OFF -DGTSAM_BUILD_EXAMPLES_ALWAYS=OFF \
  -DGTSAM_BUILD_TIMING_ALWAYS=OFF -DGTSAM_BUILD_PYTHON=OFF \
  -DGTSAM_INSTALL_MATLAB_TOOLBOX=OFF -DGTSAM_BUILD_UNSTABLE=OFF
cmake --build "$gtsam_build" --parallel "$jobs"
cmake --install "$gtsam_build"

export GTSAM_DIR="$gtsam_install/lib/cmake/GTSAM"
export CMAKE_PREFIX_PATH="$gtsam_install${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
export LD_LIBRARY_PATH="$gtsam_install/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
if [[ ! -f "$GTSAM_DIR/GTSAMConfig.cmake" ]]; then
  echo "GTSAM 安装不完整：$GTSAM_DIR/GTSAMConfig.cmake 不存在。" >&2
  exit 1
fi
cd "$workspace"
exec colcon build --base-paths "$workspace/src" --symlink-install \
  --executor sequential \
  --packages-up-to lio_sam scout_lio_support scout_vehicle_description \
    rslidar_sdk rslidar_msg zed_wrapper zed_components zed_msgs zed_description \
  --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    -DGTSAM_DIR="$GTSAM_DIR" -DGTSAM_INCLUDE_DIR="$gtsam_install/include" \
    -DZED_DIR="$SCOUT_LIO_ZED_CMAKE_DIR"
