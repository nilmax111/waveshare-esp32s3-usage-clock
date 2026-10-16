import json
import unittest
from unittest.mock import patch
from check_startup import read_health

class StartupTests(unittest.TestCase):
    def test_only_fresh_post_start_ack(self):
        for checked, since, accepted in [(199,190,True),(180,170,False),(199,200,False),(201,190,False)]:
            with self.subTest(checked=checked,since=since):
                with patch('check_startup.time.time',return_value=200), patch('pathlib.Path.read_text',return_value=json.dumps({'checked':checked,'usb':True})):
                    self.assertEqual(bool(read_health(since)),accepted)
    def test_missing_or_invalid_status(self):
        with patch('pathlib.Path.read_text',side_effect=FileNotFoundError):
            self.assertEqual(read_health(0),{})
        with patch('pathlib.Path.read_text',return_value='broken'):
            self.assertEqual(read_health(0),{})
