import unittest
from telegram_monitor import status_text


class FormattingTests(unittest.TestCase):
    def test_active_stage_is_not_reported_as_completion(self):
        text = status_text({'status': 'in_progress', 'html_url': 'https://example.com'},
                           [{'steps': [{'name': 'DeepSeek workers', 'status': 'in_progress'}]}])
        self.assertIn('in_progress', text)
        self.assertIn('DeepSeek workers', text)
        self.assertNotIn('success', text)

    def test_failed_run_and_uncertain_cost_remain_visible(self):
        text = status_text({'status': 'completed', 'conclusion': 'failure'},
                           [{'steps': [{'name': 'Proof build', 'conclusion': 'failure'}]}],
                           ({'confirmed_usd': '.02', 'reserved_usd': '.01'}, {'roles': {'lean': {'state': 'stopped'}}}))
        for expected in ['failure', 'Proof build', '.02', '.01', 'stopped']:
            self.assertIn(expected, text)


if __name__ == '__main__':
    unittest.main()
