"""Read-only adapter for the installed WorkBuddy desktop client's billing API.
Internal API: may change. Never copy credentials into logs, packets or the project.
"""
import json, math, time, os, subprocess, re
from pathlib import Path
import requests
AUTH = Path.home() / 'Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info'
ENDPOINT = 'https://copilot.tencent.com/billing/meter/get-user-resource-summary'

def number(value):
    if isinstance(value, bool): raise ValueError('Invalid credit amount')
    try: n = float(value)
    except (ValueError, TypeError): raise ValueError('Missing credit amount') from None
    if not math.isfinite(n) or n < 0: raise ValueError('Invalid credit amount')
    return n

def normalize(data):
    packages = data.get('Packages')
    if not isinstance(packages, list): raise ValueError('Credit packages unavailable')
    total = left = used = 0.0
    for p in packages:
        total += number(p.get('CycleTotalCapacity'))
        left += number(p.get('CycleRemainCapacity'))
        used += number(p.get('CycleUsedCapacity'))
    return {'total': total, 'left': left, 'used': used, 'ok': True, 'updated': int(time.time())}

def read_encrypted_usage():
    runtime = Path('/Applications/WorkBuddy.app/Contents/MacOS/Electron')
    helper = Path(__file__).with_name('workbuddy_encrypted.cjs')
    if not runtime.is_file():
        raise RuntimeError('WorkBuddy runtime missing; install the official desktop app')
    env = dict(os.environ, ELECTRON_RUN_AS_NODE='1')
    for key in ('NODE_OPTIONS', 'NODE_PATH'):
        env.pop(key, None)
    try:
        result = subprocess.run([str(runtime), str(helper)], env=env,
                                capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError('WorkBuddy encrypted reader could not finish') from None
    if result.returncode:
        # Never forward arbitrary runtime output, which may contain credentials.
        match = re.fullmatch(r'WorkBuddy reader failed \((runtime|login|enterprise|decode|network|response|http-[0-9]{3})\)\s*', result.stderr)
        stage = match.group(1) if match else 'runtime'
        raise RuntimeError('WorkBuddy encrypted reader failed: ' + stage)
    try:
        return normalize(json.loads(result.stdout))
    except (ValueError, TypeError, AttributeError):
        raise RuntimeError('WorkBuddy encrypted reader returned invalid metrics') from None

def read_usage():
    if Path(str(AUTH)+'.logged-out').exists(): raise RuntimeError('WorkBuddy is logged out')
    try: session = json.loads(AUTH.read_text())
    except (OSError, ValueError): raise RuntimeError('Open WorkBuddy and sign in') from None
    auth, account = session.get('auth', {}), session.get('account', {})
    token = auth.get('accessToken')
    if isinstance(token, dict) and token.get('$wbEncrypted') == 1:
        return read_encrypted_usage()
    if not isinstance(token, str) or token.count('.') != 2: raise RuntimeError('Unsupported WorkBuddy login format')
    if account.get('enterpriseId'): raise RuntimeError('Enterprise billing is not configured')
    headers = {'Authorization': 'Bearer '+token, 'X-User-Id': account.get('uid', ''), 'Accept': 'application/json', 'User-Agent': 'WaveshareUsageMonitor/1.0', 'X-Product': 'WorkBuddy', 'X-IDE-Type': 'WorkBuddy', 'X-IDE-Name': 'WorkBuddy'}
    if auth.get('domain'): headers['X-Domain'] = auth['domain']
    try:
        r = requests.post(ENDPOINT, json={}, headers=headers, timeout=20, allow_redirects=False)
        if r.status_code in (401,403): raise RuntimeError('WorkBuddy authentication HTTP '+str(r.status_code)+'; open app to check login')
        if r.status_code != 200: raise RuntimeError('WorkBuddy billing HTTP '+str(r.status_code))
        body = r.json()
    except requests.RequestException: raise RuntimeError('WorkBuddy billing network error') from None
    if body.get('code') != 0 or not isinstance(body.get('data'), dict): raise RuntimeError('WorkBuddy billing response unavailable')
    return normalize(body['data'])

if __name__ == '__main__':
    print(json.dumps(read_usage()))
