"""Check fresh device acknowledgements without exposing account data."""
import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def read_health(since):
    try:
        data = json.loads((ROOT / '.runtime/health.json').read_text())
        if data.get('checked', 0) < since or not 0 <= time.time() - data['checked'] < 10:
            return {}
        return data
    except (OSError, ValueError, TypeError, KeyError):
        return {}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--since', type=int, default=int(time.time()))
    parser.add_argument('--timeout', type=int, default=45)
    parser.add_argument('--expected-firmware')
    args = parser.parse_args()
    end = time.monotonic() + args.timeout
    data = {}
    required = ('usb', 'clock', 'codex', 'workbuddy', 'deepseek')
    while time.monotonic() < end:
        data = read_health(args.since)
        if all(data.get(key) for key in required):
            break
        time.sleep(1)
    for key, label in [('usb','USB 设备回执'),('clock','时间同步'),('codex','Codex 额度'),('workbuddy','WorkBuddy 积分'),('deepseek','DeepSeek 余额')]:
        print(f"{label}：{'正常' if data.get(key) else '尚未就绪'}")
    print('固件：' + str(data.get('firmware', '未连接')))
    version_ok = not args.expected_firmware or data.get('firmware') == args.expected_firmware
    if not version_ok:
        print('固件版本不匹配：预期 ' + args.expected_firmware + '。请更新固件；启动脚本不会自动烧录。')
    sd = data.get('sd_state')
    print('SD 存储：' + {0:'请进入硬件页触发检查',1:'正在读取，BOOT 仍可切换',2:'已成功读取',3:'无卡或不可读取'}.get(sd,'等待设备'))
    print('页面顺序：Codex → WorkBuddy → DeepSeek → 硬件信息 → 农历时辰；短按 BOOT 切换。')
    print('农历时辰页：从首页短按 BOOT 四次查看；经络与生活提示随时辰切换。')
    print('中文字形和按键效果需在屏幕上确认。')
    if not data.get('deepseek'):
        print('DeepSeek 未就绪：检查登录钥匙串，或运行“配置DeepSeek密钥.command”。不要发送 Key 到聊天。')
    if not data.get('workbuddy'):
        print('WorkBuddy 未就绪：检查客户端登录与网络。')
    if not data.get('codex'):
        from codex_executable import resolve
        try:
            resolve()
            print('Codex 未就绪：程序存在，请检查 Codex 登录与网络。')
        except RuntimeError:
            print('Codex 未就绪：找不到程序，请检查桌面应用安装。')
    if not data.get('usb'):
        print('检查目标屏幕 USB 连接和 macOS 后台运行许可。')
    return 0 if version_ok and all(data.get(key) for key in required) else 1

if __name__ == '__main__':
    raise SystemExit(main())
