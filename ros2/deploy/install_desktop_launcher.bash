#!/usr/bin/env bash
set -eo pipefail
deploy_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace="$(cd -- "$deploy_dir/.." && pwd)"
launcher="$deploy_dir/start_lio_sam.bash"
if [[ ! -f "$launcher" ]]; then
  echo "缺少启动脚本：$launcher。" >&2
  exit 1
fi
desktop_dir="${SCOUT_LIO_DESKTOP_DIR:-}"
if [[ -z "$desktop_dir" ]] && command -v xdg-user-dir >/dev/null; then
  desktop_dir="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
fi
desktop_dir="${desktop_dir:-$HOME/Desktop}"
mkdir -p -- "$desktop_dir"
shortcut="$desktop_dir/Scout-LIO-SAM.desktop"
python3 - "$launcher" "$workspace" "$shortcut" "${ROS_DISTRO:-humble}" <<'PY'
import os
import sys
import tempfile
from pathlib import Path

launcher, workspace, destination, distro = sys.argv[1:]
for value in (launcher, workspace, destination):
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise SystemExit('目录路径含控制字符，无法创建桌面快捷方式。')


def desktop_string(value):
    # Desktop Entry string decoding happens before Exec argument decoding.
    return value.replace('\\', '\\\\')


def exec_argument(value):
    # Quote one argv item without invoking a shell; %% represents literal %.
    value = value.replace('%', '%%')
    value = ''.join('\\' + char if char in '\\"`$' else char for char in value)
    return '"' + desktop_string(value) + '"'


icon = 'applications-science'
for candidate in (
    Path('/opt/ros') / distro / 'share/rviz2/icons/rviz.png',
    Path('/opt/ros') / distro / 'share/rviz2/icons/rviz.svg',
):
    if candidate.is_file():
        icon = str(candidate)
        break
text = '\n'.join((
    '[Desktop Entry]', 'Type=Application', 'Version=1.0',
    'Name=Scout LIO-SAM', 'Name[zh_CN]=Scout 激光建图',
    'Comment=Live LiDAR map, aligned scan and trajectory',
    'Exec=bash ' + exec_argument(launcher),
    'Path=' + desktop_string(workspace),
    'Icon=' + desktop_string(icon), 'Terminal=true', 'Categories=Science;', '',
))
target = Path(destination)
temporary = None
try:
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                     dir=target.parent, prefix='.scout-launcher-',
                                     suffix='.desktop', delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(text)
    temporary.chmod(0o755)
    os.replace(temporary, target)
    temporary = None
finally:
    if temporary is not None:
        temporary.unlink(missing_ok=True)
print('已创建快捷方式：' + str(target))
PY
if command -v gio >/dev/null; then
  gio set "$shortcut" metadata::trusted true >/dev/null 2>&1 || true
fi
