#!/usr/bin/env bash
set -eo pipefail
deploy_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export SCOUT_LIO_ALLOW_UNBUILT=1
source "$deploy_dir/setup_env.bash"
unset SCOUT_LIO_ALLOW_UNBUILT
set -u
cd "$SCOUT_LIO_WS"
python3 "$deploy_dir/prepare_gtsam.py" --workspace "$SCOUT_LIO_WS"
export MAKEFLAGS="-j2"
export CMAKE_BUILD_PARALLEL_LEVEL=2
exec colcon build --symlink-install --executor sequential \
  --packages-select lio_sam scout_lio_support \
  --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
  -DGTSAM_DIR="$SCOUT_LIO_WS/deps/gtsam-cmake" \
  -DGTSAM_INCLUDE_DIR=/mnt/nvme0n1/autoware/gtsam
