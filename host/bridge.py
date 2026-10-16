#!/usr/bin/env python3
"""Read Codex's documented app-server API; send sanitized metrics over USB."""
import os, argparse, fcntl, json, logging, math, queue, shutil, signal, subprocess, threading, time
from logging.handlers import RotatingFileHandler
from pathlib import Path

RUNTIME = Path(__file__).resolve().parent.parent / ".runtime"
LOG = logging.getLogger("waveshare")

def log_line(*parts, **kwargs):
    LOG.info(" ".join(str(p) for p in parts))

def acquire_instance(path):
    handle = path.open("a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError("USB sync is already running")
    return handle

from codex_executable import resolve as resolve_codex
from workbuddy import read_usage as read_workbuddy
from deepseek import read_balance, BalanceError

import serial
from serial.tools import list_ports

class Codex:
    def __init__(self):
        exe = resolve_codex()
        self.p = subprocess.Popen([exe, 'app-server', '--stdio'], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.q = queue.Queue()
        self.seq = 0
        threading.Thread(target=self.reader, daemon=True).start()
        try:
            self.call('initialize', {'clientInfo': {'name': 'waveshare_usage_clock', 'version': '1.0.0'}})
            self.send({'method': 'initialized'})
        except Exception:
            self.close()
            raise
    def reader(self):
        for line in self.p.stdout:
            try: self.q.put(json.loads(line))
            except ValueError: pass
        self.q.put(None)
    def send(self, value):
        self.p.stdin.write(json.dumps(value) + '\n'); self.p.stdin.flush()
    def call(self, method, params=None):
        self.seq += 1
        req = {'id': self.seq, 'method': method}
        if params is not None: req['params'] = params
        self.send(req)
        end = time.monotonic() + 25
        while time.monotonic() < end:
            value = self.q.get(timeout=max(.01, end-time.monotonic()))
            if value is None: raise RuntimeError('Codex app-server exited; check login / permissions')
            if value.get('id') == self.seq:
                if 'error' in value: raise RuntimeError(value['error'].get('message', 'API error'))
                return value['result']
        raise TimeoutError(method)
    def close(self):
        self.p.terminate()
        try: self.p.wait(timeout=5)
        except subprocess.TimeoutExpired: self.p.kill(); self.p.wait()

def normalize(result):
    buckets = result.get('rateLimitsByLimitId')
    bucket = buckets.get('codex', {}) if buckets else (result.get('rateLimits') or {})
    windows = []
    for key in ('primary', 'secondary'):
        w = bucket.get(key)
        if not w: continue
        used, mins, reset = w.get('usedPercent'), w.get('windowDurationMins'), w.get('resetsAt')
        if not isinstance(used, (int, float)) or not math.isfinite(used): continue
        if not isinstance(mins, int) or mins <= 0: continue
        windows.append({'used': max(0, min(100, used)), 'mins': mins,
                        'reset': reset if isinstance(reset, int) else 0})
    return sorted(windows, key=lambda w: w['mins'])[:2]

def find_port():
    # Never select an arbitrary board when more than one is connected.
    config_path = Path(__file__).resolve().parent.parent / 'device.local.json'
    configured = {}
    if config_path.exists():
        try: configured = json.loads(config_path.read_text())
        except (OSError, ValueError): raise RuntimeError('Invalid device.local.json') from None
    serial_number = os.environ.get('WAVESHARE_SERIAL', configured.get('serial_number', ''))
    if not isinstance(serial_number, str): raise RuntimeError('Invalid device serial configuration')
    ports = [p.device for p in list_ports.comports()
             if p.vid == 0x303a and p.pid == 0x1001
             and (not serial_number or (p.serial_number or '').upper() == serial_number.upper())]
    if len(ports) != 1:
        raise RuntimeError('Display not found uniquely; configure device.local.json or use --port')
    return ports[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port'); ap.add_argument('--once', action='store_true', help='Read real quota without opening USB')
    args = ap.parse_args()
    if args.once:
        c = Codex()
        try: print(json.dumps(normalize(c.call('account/rateLimits/read'))))
        finally: c.close()
        return
    RUNTIME.mkdir(exist_ok=True)
    try:
        instance = acquire_instance(RUNTIME / 'bridge.lock')
    except RuntimeError as e:
        print(str(e)); return
    handler = RotatingFileHandler(RUNTIME / 'bridge.log', maxBytes=1024*1024, backupCount=2)
    handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    LOG.addHandler(handler); LOG.setLevel(logging.INFO)
    LOG.addHandler(logging.StreamHandler())
    stop = threading.Event()
    refresh = threading.Event()
    clients = []
    def shutdown(*_):
        stop.set(); refresh.set()
        for client in clients[:]:
            client.close()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    state = {'windows': [], 'updated': 0, 'ok': False, 'workbuddy': {'ok': False, 'updated': 0}, 'deepseek': {'ok': False, 'status': 'setup'}}
    lock = threading.Lock()
    def poll():
        c = None
        while not stop.is_set():
            refresh.clear()
            try:
                if c is None:
                    c = Codex(); clients.append(c)
                windows = normalize(c.call('account/rateLimits/read'))
                with lock: state.update(windows=windows, updated=int(time.time()), ok=bool(windows))
                log_line('Codex refreshed')
            except Exception as e:
                with lock: state['ok'] = False
                log_line('Quota unavailable:', str(e), flush=True)
                if c:
                    c.close(); clients.remove(c); c = None
            refresh.wait(60)
    wb_refresh = threading.Event()
    def poll_workbuddy():
        while not stop.is_set():
            wb_refresh.clear()
            try:
                usage = read_workbuddy()
                with lock: state['workbuddy'] = usage
                log_line('WorkBuddy refreshed')
            except Exception as e:
                with lock: state['workbuddy'] = dict(state['workbuddy'], ok=False)
                log_line('WorkBuddy unavailable:', type(e).__name__, str(e))
            wb_refresh.wait(60)
    ds_refresh = threading.Event()
    def poll_deepseek():
        while not stop.is_set():
            ds_refresh.clear()
            try:
                balance = read_balance()
                with lock: state['deepseek'] = balance
                log_line('DeepSeek refreshed')
            except Exception as e:
                code = str(e) if isinstance(e, BalanceError) else 'internal'
                # Clear old account balances on every failure; never log exception bodies.
                with lock: state['deepseek'] = {'ok': False, 'status': code}
                log_line('DeepSeek unavailable:', code)
            ds_refresh.wait(60)
    threading.Thread(target=poll_deepseek, daemon=True).start()
    threading.Thread(target=poll, daemon=True).start()
    threading.Thread(target=poll_workbuddy, daemon=True).start()
    while True:
        try:
            port = args.port or find_port()
            with serial.Serial(port, 115200, timeout=.2, write_timeout=2) as dev:
                log_line('Connected:', port, flush=True)
                refresh.set(); wb_refresh.set(); ds_refresh.set()
                missed = 0
                while not stop.is_set():
                    with lock: packet = dict(state)
                    packet.update(v=1, epoch=int(time.time()))
                    dev.write((json.dumps(packet, separators=(',', ':'))+'\n').encode())
                    response = dev.readline().decode(errors='replace').strip()
                    try:
                        reply = json.loads(response)
                        ack = reply.get('ack') == 1
                    except (ValueError, AttributeError):
                        ack = False
                    if ack:
                        # Only readiness flags, never balances or credentials, for the launcher.
                        checked = int(time.time())
                        def recent(value):
                            stamp = value.get('updated', 0)
                            return bool(value.get('ok') and 0 <= checked - stamp < 180)
                        health = {'checked': checked, 'usb': True,
                                  'firmware': reply.get('screen'), 'page': reply.get('page'),
                                  'clock': abs(checked - reply.get('epoch', 0)) < 10,
                                  'codex': recent(packet) and reply.get('windows') == 2,
                                  'workbuddy': recent(packet.get('workbuddy', {})) and reply.get('wb_ok') == 1,
                                  'deepseek': recent(packet.get('deepseek', {})) and reply.get('ds_ok') == 1,
                                  'sd_state': reply.get('sd_state')}
                        temporary = RUNTIME / 'health.tmp'
                        temporary.write_text(json.dumps(health))
                        temporary.replace(RUNTIME / 'health.json')
                        if missed or getattr(dev, '_last_status', None) != (reply.get('windows'), reply.get('page'), reply.get('wb_ok'), reply.get('ds_ok'), reply.get('sd_state')):
                            log_line('Device:', response)
                            dev._last_status = (reply.get('windows'), reply.get('page'), reply.get('wb_ok'), reply.get('ds_ok'), reply.get('sd_state'))
                        missed = 0
                    else:
                        missed += 1
                        if missed >= 5:
                            raise RuntimeError('No device acknowledgement; reopening USB')
                    stop.wait(2)
        except (OSError, serial.SerialException, RuntimeError) as e:
            log_line('USB waiting:', str(e), flush=True); time.sleep(3)

if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt: pass
