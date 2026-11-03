#!/usr/bin/env bash
# Reuse this user's existing graphical desktop when invoked over SSH.
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  for _lio_desktop_pid in $(pgrep -u "$(id -u)" -x gnome-shell || true); do
    if [[ -r "/proc/$_lio_desktop_pid/environ" ]]; then
      while IFS= read -r -d '' _lio_desktop_var; do
        case "$_lio_desktop_var" in
          DISPLAY=*|WAYLAND_DISPLAY=*|XAUTHORITY=*|XDG_RUNTIME_DIR=*|DBUS_SESSION_BUS_ADDRESS=*)
            export "$_lio_desktop_var" ;;
        esac
      done < "/proc/$_lio_desktop_pid/environ"
      [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]] || break
    fi
  done
fi
unset _lio_desktop_pid _lio_desktop_var
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  echo '没有可用的图形桌面。请先登录 Orin 桌面，再从桌面终端启动。' >&2
  echo '只运行建图时可加 rviz:=false；之后用 deploy/view_lio_sam.bash 打开界面。' >&2
  return 1
fi
