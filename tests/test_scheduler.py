from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import Mock, patch
import requests
from scripts.radar_schedule import latest_completed_scan, should_scan, stale, alert_stale

NOW = datetime(2026, 11, 22, 19, tzinfo=timezone.utc)


def response(payload):
    r = Mock()
    r.json.return_value = payload
    return r


class SchedulerTests(unittest.TestCase):
    def test_dispatch_never_skips_but_recent_backup_does(self):
        last = NOW - timedelta(minutes=5)
        self.assertTrue(should_scan('workflow_dispatch', last, NOW))
        self.assertFalse(should_scan('schedule', last, NOW))
        self.assertTrue(should_scan('schedule', NOW - timedelta(minutes=13), NOW))
        self.assertTrue(should_scan('schedule', None, NOW))

    def test_watchdog_uses_45_minutes_from_completion(self):
        self.assertFalse(stale(NOW - timedelta(minutes=44), NOW))
        self.assertFalse(stale(NOW - timedelta(minutes=45), NOW))
        self.assertTrue(stale(NOW - timedelta(minutes=46), NOW))
        self.assertTrue(stale(None, NOW))

    def test_successful_skipped_workflow_does_not_hide_missing_scans(self):
        get = Mock(side_effect=[
            response({'workflow_runs': [{'id': 2}, {'id': 1}]}),
            response({'jobs': [{'steps': [{'name': 'Run job alert', 'conclusion': 'skipped'}]}]}),
            response({'jobs': [{'steps': [{'name': 'Run job alert', 'conclusion': 'success', 'completed_at': '2026-11-22T18:00:00Z'}]}]}),
        ])
        last = latest_completed_scan('owner/repo', 'test-only', get=get)
        self.assertEqual(NOW - timedelta(hours=1), last)
        self.assertTrue(stale(last, NOW))

    def test_failed_api_does_not_invent_a_fresh_heartbeat(self):
        r = response({})
        r.raise_for_status.side_effect = requests.HTTPError('test only')
        with self.assertRaises(requests.HTTPError):
            latest_completed_scan('owner/repo', 'test-only', get=Mock(return_value=r))

    def test_stale_alert_is_claimed_before_telegram_and_duplicates_are_silent(self):
        import main
        from delivery import History
        with patch.object(main, 'use_supabase', return_value=True), patch.object(main, 'TELEGRAM_TOKEN', 'test-only'), patch.object(main, 'TELEGRAM_CHAT_ID', 'test-chat'), patch('delivery.History') as factory, patch.object(main, 'save_job') as save, patch('scripts.radar_schedule.requests.post') as post:
            factory.return_value.claim.return_value = False
            self.assertFalse(alert_stale('owner/repo', None, NOW))
            post.assert_not_called()
            save.assert_not_called()
            factory.return_value.claim.return_value = True
            self.assertTrue(alert_stale('owner/repo', None, NOW))
            save.assert_called_once()
            post.assert_called_once()
            factory.return_value.delivered.assert_called_once()

    def test_watchdog_timeout_retains_claim_and_hides_token(self):
        import main
        with patch.object(main, 'use_supabase', return_value=True), patch.object(main, 'TELEGRAM_TOKEN', 'test-only-secret'), patch.object(main, 'TELEGRAM_CHAT_ID', 'test-chat'), patch('delivery.History') as factory, patch.object(main, 'save_job'), patch('scripts.radar_schedule.requests.post', side_effect=requests.Timeout('contains-token')):
            factory.return_value.claim.return_value = True
            with self.assertRaisesRegex(RuntimeError, 'claim retained') as error:
                alert_stale('owner/repo', None, NOW)
            self.assertNotIn('test-only-secret', str(error.exception))
            self.assertNotIn('contains-token', str(error.exception))
            factory.return_value.delivered.assert_not_called()


if __name__ == '__main__':
    unittest.main()
