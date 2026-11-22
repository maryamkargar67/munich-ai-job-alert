import importlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from delivery import History, canonical_url, deliver_batch
from language_filter import requires_advanced_german
from location_filter import location_allowed
from linkedin_source import extract_job_id


class RadarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Importing main must never fetch sources, connect to DB or send jobs.
        with patch('requests.get', side_effect=AssertionError('unexpected network')), patch('requests.post', side_effect=AssertionError('unexpected send')):
            self.b = importlib.import_module('main')
        self.patch_db = patch.object(self.b, 'DB_NAME', str(Path(self.tmp.name)/'jobs.db'))
        self.patch_db.start()
        self.addCleanup(self.patch_db.stop)
        self.patch_remote = patch.object(self.b, 'use_supabase', return_value=False)
        self.patch_remote.start()
        self.addCleanup(self.patch_remote.stop)
        self.b.init_database()

    def job(self, id='one', url='https://example.com/jobs/123'):
        return dict(id=id, company='Company', title='Working Student AI', location='Munich', url=url, source='Existing', type='Working Student', score=80)

    def test_legacy_sqlite_schema_is_upgraded_without_losing_history(self):
        self.b.save_job(self.job())
        self.b.init_database()
        self.assertTrue(self.b.job_exists('one'))
        self.b.mark_source_initialized('Existing')
        self.assertTrue(self.b.source_is_initialized('Existing'))

    def test_initial_sync_suppresses_entire_batch_across_both_lanes(self):
        sender = Mock()
        cache = {}
        history = History(self.b)
        deliver_batch([self.job('a'), self.job('b', 'https://example.com/jobs/456')], sender, cache, self.b, history)
        deliver_batch([self.job('c', 'https://example.com/jobs/789')], sender, cache, self.b, history)
        sender.assert_not_called()
        self.assertEqual({'Existing': False}, cache)

    def test_same_job_from_two_sources_only_sends_once(self):
        self.b.mark_source_initialized('Existing')
        sender = Mock(return_value=True)
        history = History(self.b)
        jobs = [self.job(), self.job('other', 'https://example.com/jobs/123?utm_source=linkedin')]
        self.assertEqual(1, len(deliver_batch(jobs, sender, {}, self.b, history)))
        sender.assert_called_once()
        with sqlite3.connect(self.b.DB_NAME) as db:
            self.assertIsNotNone(db.execute("SELECT alerted_at FROM jobs WHERE job_id='one'").fetchone()[0])

    def test_timeout_is_not_retried_in_later_run(self):
        self.b.mark_source_initialized('Existing')
        sender = Mock(side_effect=TimeoutError())
        deliver_batch([self.job()], sender, {}, self.b, History(self.b))
        deliver_batch([self.job('different')], sender, {}, self.b, History(self.b))
        sender.assert_called_once()

    def test_separate_history_snapshots_still_have_one_atomic_claim(self):
        first, second = History(self.b), History(self.b)
        self.assertTrue(first.claim(self.job()))
        self.assertFalse(second.claim(self.job('another')))

    def test_existing_history_prevents_cross_source_repost(self):
        self.b.save_job(self.job())
        self.assertFalse(History(self.b).claim(self.job('other')))

    def test_database_failure_does_not_send(self):
        self.b.mark_source_initialized('Existing')
        sender = Mock()
        with patch.object(self.b, 'save_job', side_effect=RuntimeError('database failure')):
            with self.assertRaises(RuntimeError):
                deliver_batch([self.job()], sender, {}, self.b, History(self.b))
        sender.assert_not_called()

    def test_linkedin_id_forms_and_tracking_share_identity(self):
        for url in ('https://www.linkedin.com/jobs/view/test-role-123456/', 'https://de.linkedin.com/jobs/view/123456/?trk=x'):
            self.assertEqual('123456', extract_job_id(url))
            self.assertEqual('linkedin:123456', canonical_url(url))
        self.assertNotEqual(canonical_url('https://x.com/job?id=1'), canonical_url('https://x.com/job?id=2'))

    def test_german_level_belongs_to_german(self):
        for text in ('English at least C1. Basic German A1.', 'German C1 is a plus.', 'English C1; German optional', 'English required and German C1 optional', 'At least C1 English and basic German'):
            self.assertFalse(requires_advanced_german(text), text)
        for text in ('Fluent German required.', 'Deutsch auf C1-Niveau', 'Sehr gute Deutsch- und Englischkenntnisse', 'German optional; fluent German required', 'Fluent German required, Python optional', 'Fluent German required and Python optional', 'Python optional and fluent German required', 'German C1 optional and fluent German required'):
            self.assertTrue(requires_advanced_german(text), text)

    def test_remote_does_not_allow_distant_hybrid_office(self):
        self.assertFalse(location_allowed('Hamburg, Germany', 'We are in Germany and offer home office and hybrid working.'))
        self.assertTrue(location_allowed('Hamburg, Germany', 'Fully remote anywhere in Germany.'))
        self.assertTrue(location_allowed('Munich', 'Hybrid working.'))

    def test_all_source_language_functions_use_shared_policy(self):
        import ashby_source, hawk_source, check24_source
        for module in (ashby_source, hawk_source, check24_source):
            self.assertFalse(module.requires_advanced_german('English at least C1. German optional.'))
            self.assertTrue(module.requires_advanced_german('Fluent German required'))

    def test_linkedin_already_seen_skips_detail_request(self):
        import linkedin_source
        from discovery_cache import seed
        seed({'linkedin-123456'})
        self.addCleanup(seed, set())
        job = dict(title='Working Student AI', company='Company', location='Munich', url='https://linkedin.com/jobs/view/123456/')
        with patch.object(linkedin_source, 'QUERIES', ['AI']), patch.object(linkedin_source, 'search_linkedin', return_value=[job]), patch.object(linkedin_source, 'fetch_job_description') as detail:
            self.assertEqual([], linkedin_source.fetch_linkedin_jobs())
            detail.assert_not_called()

    def test_supabase_claim_is_insert_not_upsert_update(self):
        with patch.object(self.b, 'use_supabase', return_value=True), patch.object(self.b.requests, 'get') as get, patch.object(self.b.requests, 'post') as post:
            get.return_value.json.return_value = []
            post.return_value.json.return_value = [{'job_id': 'delivery:claimed'}]
            history = History(self.b)
            self.assertTrue(history.claim(self.job()))
            self.assertEqual('resolution=ignore-duplicates,return=representation', post.call_args.kwargs['headers']['Prefer'])
            self.assertTrue(post.call_args.kwargs['json']['job_id'].startswith('delivery:'))

if __name__ == '__main__':
    unittest.main()
