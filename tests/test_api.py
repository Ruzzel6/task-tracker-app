import unittest
from unittest.mock import patch
from app.main import app

class APIValidation(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
    def test_live_without_database(self):
        self.assertEqual(self.client.get('/health/live').status_code, 200)
    def test_invalid_titles_do_not_touch_database(self):
        with patch('app.main.connect') as connect:
            for body in ({}, {'title': ''}, {'title': '  '}, {'title': 7}, {'title': 'x'*201}, []):
                self.assertEqual(self.client.post('/api/tasks', json=body).status_code, 400)
            connect.assert_not_called()
    def test_completed_requires_boolean(self):
        for body in ({}, {'completed': 'false'}, {'completed': 1}, []):
            self.assertEqual(self.client.patch('/api/tasks/1', json=body).status_code, 400)
    def test_home(self):
        self.assertIn(b'Ops Tasks', self.client.get('/').data)

if __name__ == '__main__':
    unittest.main()
