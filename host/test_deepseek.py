import json
import subprocess
import unittest
from unittest.mock import patch, MagicMock
from deepseek import normalize, read_balance, BalanceError, URL

class DeepSeekTests(unittest.TestCase):
    def data(self):
        return {'is_available': True, 'balance_infos': [{'currency':'CNY', 'total_balance':'12.34', 'granted_balance':'2.34','topped_up_balance':'10'}]}
    def test_balance_semantics(self):
        value=normalize(self.data())
        self.assertEqual(value['balances'][0], {'currency':'CNY','total':12.34,'gift':2.34,'paid':10.0})
        self.assertNotIn('used',value)
    def test_currencies_not_summed(self):
        data=self.data(); data['balance_infos'].append(dict(data['balance_infos'][0],currency='USD'))
        self.assertEqual(len(normalize(data)['balances']),2)
    def test_invalid_balance_not_zero(self):
        for value in ('NaN','Infinity','bad',None,True,'1e999'):
            with self.subTest(value=value):
                data=self.data();data['balance_infos'][0]['total_balance']=value
                with self.assertRaisesRegex(BalanceError,'response'): normalize(data)
    def test_missing_and_duplicate(self):
        for data in ({}, {'is_available':True,'balance_infos':[]}, {'is_available':'true','balance_infos':[]}):
            with self.assertRaises(BalanceError):normalize(data)
        data=self.data();data['balance_infos']*=2
        with self.assertRaises(BalanceError):normalize(data)
    @patch('deepseek.subprocess.run')
    def test_missing_key_no_network(self, run):
        run.return_value=subprocess.CompletedProcess([],4,b'',b'')
        with patch('deepseek.requests.Session') as session:
            with self.assertRaisesRegex(BalanceError,'key_missing'):read_balance()
            session.assert_not_called()
    @patch('deepseek.subprocess.run')
    @patch('deepseek.requests.Session')
    def test_fixed_destination_and_no_redirect(self, factory, run):
        run.return_value=subprocess.CompletedProcess([],0,b'sk-test-placeholder',b'')
        session=factory.return_value.__enter__.return_value
        response=session.get.return_value.__enter__.return_value
        response.status_code=200
        response.iter_content.return_value=[json.dumps(self.data()).encode()]
        self.assertTrue(read_balance()['ok'])
        self.assertFalse(session.trust_env)
        args,kwargs=session.get.call_args
        self.assertEqual(args,(URL,));self.assertFalse(kwargs['allow_redirects'])
        response.status_code=401
        with self.assertRaisesRegex(BalanceError,'^auth$'):read_balance()
    def test_packet_fits(self):
        data=self.data();data['balance_infos']*=2;data['balance_infos'][1]=dict(data['balance_infos'][1],currency='USD')
        packet={'v':1,'epoch':1890000000,'ok':True,'updated':1890000000,
                'windows':[{'used':99.9999999999,'mins':10080,'reset':1890000000}]*2,
                'workbuddy':{'ok':True,'total':999999999.99999,'left':999999999.99999,'used':999999999.99999,'updated':1890000000},
                'deepseek':normalize(data)}
        self.assertLess(len(json.dumps(packet).encode()),1024)

if __name__=='__main__':unittest.main()
