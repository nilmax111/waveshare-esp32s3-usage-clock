#!/bin/zsh
# 五页版 v5.3 启动入口；launchd 管理后台，关闭窗口不停止同步。
PROJECT_DIR="${0:A:h}"
SERVICE_TARGET="gui/$(id -u)/local.waveshare.codex-clock"
finish() {
  print -r -- '' "$1"
  if [[ -t 0 ]]; then
    print -n -- '按回车关闭此窗口…'
    read -r reply
  fi
  exit "$2"
}
cd "$PROJECT_DIR" || finish '找不到项目目录，请检查项目是否被移动。' 1
[[ -x .venv/bin/python && -f host/service.py && -f host/check_startup.py ]] || finish '缺少环境或启动检查程序。' 1
.venv/bin/python -c 'import serial, requests' || finish 'Python 依赖不完整。' 1
if [[ ! -x .runtime/deepseek-keychain ]]; then
  print '提示：DeepSeek 辅助程序缺失，请运行“配置DeepSeek密钥.command”；其他功能仍会启动。'
fi
.venv/bin/python host/codex_executable.py
started_at=$(/bin/date +%s)
print '微雪五页屏：Codex / WorkBuddy / DeepSeek / 硬件 / 农历时辰'
print '正在启动同步服务并检查固件与数据（最多约 45 秒）…'
/bin/launchctl enable "$SERVICE_TARGET" || finish '无法启用服务，请检查 macOS 后台运行权限。' 1
# Restart a loaded service; avoid a bootout/bootstrap race during process exit.
if /bin/launchctl print "$SERVICE_TARGET" >/dev/null 2>&1; then
  /bin/launchctl kickstart -k "$SERVICE_TARGET" || finish '重启失败，请检查本项目后台运行许可。' 1
else
  .venv/bin/python host/service.py install || finish '安装启动失败，请检查本项目后台运行许可与目录权限。' 1
fi
.venv/bin/python host/check_startup.py --since "$started_at" --timeout 45 --expected-firmware clock-quota-v5.3
check_result=$?
if (( check_result == 0 )); then
  finish '同步检查通过，可以关闭此窗口。SD 和屏幕按键请按上方提示检查。' 0
fi
finish '服务已提交启动，但部分功能未就绪。请按上方提示检查；后台会继续自动重试。' 1
