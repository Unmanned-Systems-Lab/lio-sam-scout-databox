#!/usr/bin/env bash
set -eo pipefail
deploy_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$deploy_dir/setup_env.bash"
source "$deploy_dir/desktop_env.bash"
exec ros2 run rviz2 rviz2 -d "$deploy_dir/config/scout_lio.rviz" "$@"
