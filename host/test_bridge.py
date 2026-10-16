import unittest
from bridge import normalize, acquire_instance, find_port
from unittest.mock import patch
from types import SimpleNamespace
import tempfile
from pathlib import Path
class NormalizationTests(unittest.TestCase):
    def test_missing_is_not_zero(self):
        self.assertEqual(normalize({'rateLimits': {'primary': None}}), [])
        self.assertEqual(normalize({'rateLimits': {'primary': {'windowDurationMins': 300}}}), [])
    def test_weekly_can_be_primary(self):
        self.assertEqual(normalize({'rateLimits': {'primary': {'usedPercent': 12, 'windowDurationMins': 10080}}}), [{'used':12,'mins':10080,'reset':0}])
    def test_specific_bucket_wins_and_clamps(self):
        self.assertEqual(normalize({'rateLimits': {'primary': {'usedPercent': 1,'windowDurationMins':300}},'rateLimitsByLimitId': {'codex': {'secondary': {'usedPercent': 105, 'windowDurationMins':300,'resetsAt':123}}}}), [{'used':100,'mins':300,'reset':123}])
    def test_other_bucket_is_not_codex(self):
        self.assertEqual(normalize({'rateLimitsByLimitId': {'other': {}}}), [])
class PortTests(unittest.TestCase):
    def test_other_board_never_selected(self):
        other = SimpleNamespace(device='/dev/other', vid=0x303a, pid=0x1001, serial_number='TEST-OTHER')
        target = SimpleNamespace(device='/dev/new-port', vid=0x303a, pid=0x1001, serial_number='TEST-TARGET')
        with patch.dict('os.environ', {'WAVESHARE_SERIAL':'TEST-TARGET'}), patch('bridge.list_ports.comports', return_value=[other, target]):
            self.assertEqual(find_port(), '/dev/new-port')
        with patch.dict('os.environ', {'WAVESHARE_SERIAL':'TEST-TARGET'}), patch('bridge.list_ports.comports', return_value=[other]):
            with self.assertRaises(RuntimeError): find_port()

class InstanceTests(unittest.TestCase):
    def test_duplicate_rejected_and_release_allows_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bridge.lock'
            first = acquire_instance(path)
            try:
                with self.assertRaises(RuntimeError): acquire_instance(path)
            finally: first.close()
            acquire_instance(path).close()

if __name__ == '__main__': unittest.main()
