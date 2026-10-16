"""Official read-only balance API. Credentials stay in Keychain/host memory."""
import subprocess
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
import requests

URL = 'https://api.deepseek.com/user/balance'
HELPER = Path(__file__).resolve().parent.parent / '.runtime/deepseek-keychain'

class BalanceError(Exception):
    pass

def normalize(data):
    try:
        if type(data['is_available']) is not bool:
            raise ValueError()
        rows = data['balance_infos']
        if not isinstance(rows, list) or not 1 <= len(rows) <= 2:
            raise ValueError()
        balances = []
        for row in rows:
            currency = row['currency']
            if currency not in ('CNY', 'USD') or any(b['currency'] == currency for b in balances):
                raise ValueError()
            values = {}
            for field, name in [('total_balance', 'total'), ('granted_balance', 'gift'), ('topped_up_balance', 'paid')]:
                raw = row[field]
                if not isinstance(raw, str) or len(raw) > 40:
                    raise ValueError()
                value = Decimal(raw)
                if not value.is_finite() or abs(value) > Decimal('999999999'):
                    raise ValueError()
                values[name] = float(round(value, 4))
            balances.append(dict(currency=currency, **values))
        return dict(ok=True, available=data['is_available'], balances=balances, updated=int(time.time()))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise BalanceError('response') from None

def read_balance():
    try:
        result = subprocess.run([str(HELPER), 'read'], capture_output=True, timeout=5)
    except FileNotFoundError:
        raise BalanceError('setup') from None
    except (OSError, subprocess.TimeoutExpired):
        raise BalanceError('keychain') from None
    if result.returncode:
        raise BalanceError('key_missing' if result.returncode == 4 else 'keychain')
    try:
        key = result.stdout.decode('ascii')
    except UnicodeError:
        raise BalanceError('keychain') from None
    if not key.startswith('sk-') or not 12 <= len(key) <= 512 or not all(33 <= ord(c) <= 126 for c in key):
        raise BalanceError('keychain')
    try:
        with requests.Session() as session:
            # No implicit netrc credentials or environment proxy; fixed HTTPS destination.
            session.trust_env = False
            with session.get(URL, headers={'Authorization': 'Bearer ' + key},
                             timeout=(5, 15), allow_redirects=False, stream=True) as response:
                if response.status_code in (401, 403):
                    raise BalanceError('auth')
                if response.status_code != 200:
                    raise BalanceError('http')
                body = bytearray()
                for chunk in response.iter_content(4096):
                    body.extend(chunk)
                    if len(body) > 32768:
                        raise BalanceError('response')
                import json
                return normalize(json.loads(body))
    except BalanceError:
        raise
    except requests.RequestException:
        raise BalanceError('network') from None
    except (ValueError, TypeError):
        raise BalanceError('response') from None
    finally:
        key = None
