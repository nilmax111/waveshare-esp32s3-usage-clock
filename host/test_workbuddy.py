import unittest
from workbuddy import normalize, read_usage, read_encrypted_usage
from unittest.mock import patch
import json
class WorkBuddyTests(unittest.TestCase):
    def test_sums_server_packages(self):
        r=normalize({'Packages':[{'CycleTotalCapacity':'100','CycleRemainCapacity':'60.5','CycleUsedCapacity':'39.5'},{'CycleTotalCapacity':20,'CycleRemainCapacity':10,'CycleUsedCapacity':10}]})
        self.assertEqual((r['total'],r['left'],r['used']),(120,70.5,49.5))
    def test_missing_is_unavailable(self):
        for d in ({},{'Packages':[{}]}):
            with self.assertRaises(ValueError):normalize(d)
    def test_invalid_numbers_rejected(self):
        for x in (None,True,'NaN',-1,'inf'):
            with self.assertRaises(ValueError):normalize({'Packages':[{'CycleTotalCapacity':x,'CycleRemainCapacity':0,'CycleUsedCapacity':0}]})
    def test_encrypted_login_uses_helper_without_direct_request(self):
        session={'auth':{'accessToken':{'$wbEncrypted':1,'envelope':'SECRET_TEST_ONLY'}}}
        expected={'total':10,'left':7,'used':3,'ok':True,'updated':1}
        with patch('workbuddy.Path.exists', return_value=False), patch('workbuddy.Path.read_text', return_value=json.dumps(session)), patch('workbuddy.requests.post') as post, patch('workbuddy.read_encrypted_usage',return_value=expected):
            self.assertEqual(read_usage(),expected)
            post.assert_not_called()

    def test_helper_metrics_are_normalized(self):
        from types import SimpleNamespace
        response=SimpleNamespace(returncode=0,stdout=json.dumps({'Packages':[{'CycleTotalCapacity':10,'CycleRemainCapacity':7,'CycleUsedCapacity':3}]}),stderr='')
        with patch('workbuddy.Path.is_file',return_value=True), patch('workbuddy.subprocess.run',return_value=response):
            result=read_encrypted_usage()
            self.assertEqual((result['total'],result['left'],result['used']),(10,7,3))

    def test_helper_error_does_not_leak_output(self):
        from types import SimpleNamespace
        response=SimpleNamespace(returncode=1,stdout='SECRET',stderr='SECRET')
        with patch('workbuddy.Path.is_file',return_value=True), patch('workbuddy.subprocess.run',return_value=response):
            with self.assertRaises(RuntimeError) as error:read_encrypted_usage()
            self.assertNotIn('SECRET',str(error.exception))

    def test_empty_packages_are_valid_zero(self):
        self.assertEqual(normalize({'Packages':[]})['total'],0)
if __name__=='__main__':unittest.main()
