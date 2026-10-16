#!/usr/bin/env python3
"""Install/manage the per-user macOS USB bridge LaunchAgent."""
import os, pathlib, plistlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
LABEL = 'local.waveshare.codex-clock'
PLIST = pathlib.Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')
DOMAIN = 'gui/' + str(os.getuid())

def run(*args, check=True):
    return subprocess.run(['launchctl', *args], check=check)

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if action == 'install':
        runtime = ROOT / '.runtime'; runtime.mkdir(exist_ok=True)
        config = {'Label': LABEL, 'ProgramArguments': [str(ROOT / '.venv/bin/python'), str(ROOT / 'host/bridge.py')],
                  'WorkingDirectory': str(ROOT), 'RunAtLoad': True, 'KeepAlive': True,
                  'ThrottleInterval': 10, 'ProcessType': 'Background',
                  'EnvironmentVariables': {'PATH': '/Applications/ChatGPT.app/Contents/Resources:/usr/local/bin:/usr/bin:/bin', 'PYTHONUNBUFFERED': '1'},
                  'StandardOutPath': '/dev/null', 'StandardErrorPath': '/dev/null'}
        PLIST.parent.mkdir(exist_ok=True)
        run('bootout', DOMAIN + '/' + LABEL, check=False)
        PLIST.write_bytes(plistlib.dumps(config))
        run('bootstrap', DOMAIN, str(PLIST))
        run('print', DOMAIN + '/' + LABEL)
    elif action == 'status': run('print', DOMAIN + '/' + LABEL)
    elif action == 'restart': run('kickstart', '-k', DOMAIN + '/' + LABEL)
    elif action == 'uninstall':
        run('bootout', DOMAIN + '/' + LABEL, check=False)
        PLIST.unlink(missing_ok=True)
    else: raise SystemExit('Usage: service.py install|status|restart|uninstall')
if __name__ == '__main__': main()
