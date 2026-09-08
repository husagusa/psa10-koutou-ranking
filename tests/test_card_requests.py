import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('requests', Path(__file__).resolve().parents[1] / 'scripts/card_requests.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class CardRequestsTest(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(m.normalize_url(' https://www.snkrdunk.com/apparels/91156/?utm_source=share#x '),
                         'https://snkrdunk.com/apparels/91156')

    def test_rejects_unsafe_urls(self):
        for url in ['http://snkrdunk.com/apparels/1', 'https://snkrdunk.com.evil.org/apparels/1',
                    'https://snkrdunk.com@evil.org/apparels/1', 'https://snkrdunk.com:443/apparels/1',
                    'https://snkrdunk.com/apparels/../1', 'https://snkrdunk.com/apparels/%31',
                    'https://snkrdunk.com/apparels/1\nhttps://evil.org',
                    'https://snkrdunk.com/apparels/1?x=$(touch /tmp/pwned)',
                    'https://snkrdunk.com/apparels/1\\evil', 'https://127.0.0.1/apparels/1']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                m.normalize_url(url)

    def test_issue_form(self):
        self.assertEqual(m.parse_body('### SNKRDUNK URL\n\nhttps://snkrdunk.com/apparels/1\n\n'),
                         'https://snkrdunk.com/apparels/1')
        with self.assertRaises(ValueError):
            m.parse_body('do something else')

    def test_repeated_requests_do_not_duplicate_or_erase(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'cards.csv'
            p.write_text('url\nhttps://snkrdunk.com/apparels/1/\n')
            one = 'https://snkrdunk.com/apparels/1'
            two = 'https://snkrdunk.com/apparels/2'
            self.assertEqual(m.add_urls(p, [one, two, two]), [two])
            first = p.read_bytes()
            self.assertEqual(m.add_urls(p, [one, two]), [])
            self.assertEqual(p.read_bytes(), first)
            with p.open() as f:
                self.assertEqual(len(list(csv.DictReader(f))), 2)

    def test_untrusted_and_invalid_requests_not_registered(self):
        issues = [dict(number=1, title='[カード追加] test', user={'login':'visitor'}, body='### SNKRDUNK URL\nhttps://snkrdunk.com/apparels/1'),
                  dict(number=2, title='[カード追加] test', user={'login':'owner'}, body='### SNKRDUNK URL\nhttps://evil.org/apparels/1'),
                  dict(number=3, title='[カード追加] test', user={'login':'owner'}, body='### SNKRDUNK URL\nhttps://snkrdunk.com/apparels/3')]
        with tempfile.TemporaryDirectory() as d, patch.object(m, 'pages', return_value=issues), \
             patch.object(m, 'api', side_effect=lambda path: {'permission':'read' if 'visitor' in path else 'admin'}), \
             patch.object(m, 'add_urls') as add, patch.object(m, 'comment_once') as comment, \
             patch.object(m, 'RESULTS', Path(d)/'result.json'), patch.object(m, 'ROOT', Path(d)):
            m.prepare()
            self.assertEqual(add.call_args.args[1], ['https://snkrdunk.com/apparels/3'])
            self.assertEqual(comment.call_args.args[0], 2)

    def test_quantity_validation(self):
        for value in ['0', '1', '9999']:
            self.assertEqual(m.parse_quantity('### 所持枚数\n\n'+value), int(value))
        for value in ['', '-1', '1.5', '10000', '1e2', 'NaN', '１', '1\n2', '$(id)']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.parse_quantity('### 所持枚数\n'+value)

    def test_zero_restore_and_add_preserve_data(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'cards.csv'
            url = 'https://snkrdunk.com/apparels/1'
            p.write_text('url,quantity\n'+url+',2\n')
            for quantity in [1, 0, 3]:
                m.set_quantity(p, url, quantity)
                with p.open() as f:
                    self.assertEqual(list(csv.DictReader(f)), [{'url': url, 'quantity': str(quantity)}])
            m.add_urls(p, [url, 'https://snkrdunk.com/apparels/2'])
            with p.open() as f:
                self.assertEqual([r['quantity'] for r in csv.DictReader(f)], ['3', '1'])
            with self.assertRaises(ValueError):
                m.set_quantity(p, 'https://snkrdunk.com/apparels/3', 0)

    def test_retry_does_not_replay_older_quantity_and_untrusted_is_ignored(self):
        url = 'https://snkrdunk.com/apparels/1'
        def issue(number, quantity, login='owner'):
            return dict(number=number, title='[所持枚数] test', user={'login':login},
                        body='### SNKRDUNK URL\n'+url+'\n### 所持枚数\n'+str(quantity))
        with tempfile.TemporaryDirectory() as d, patch.object(m, 'ROOT', Path(d)), \
             patch.object(m, 'RESULTS', Path(d)/'results.json'), \
             patch.object(m, 'api', side_effect=lambda path: {'permission':'read' if 'visitor' in path else 'admin'}):
            p = Path(d)/'cards.csv';p.write_text('url,quantity\n'+url+',2\n')
            with patch.object(m, 'pages', return_value=[issue(1, 0), issue(2, 3), issue(3, 9, 'visitor')]):
                m.prepare()
            # Newer request closed, old request still open after a reporting failure.
            with patch.object(m, 'pages', return_value=[issue(1, 0)]):
                m.prepare()
            with p.open() as f:
                self.assertEqual(next(csv.DictReader(f))['quantity'], '3')
            with patch.object(m, 'pages', return_value=[issue(4, 0)]):
                m.prepare()
            with p.open() as f:
                self.assertEqual(next(csv.DictReader(f))['quantity'], '0')

if __name__ == '__main__':
    unittest.main()
