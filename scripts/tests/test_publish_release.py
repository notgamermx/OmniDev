"""Release API boundary tests; no network or publication is performed."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('publisher', Path(__file__).parents[1] / 'publish_release.py')
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


class LookupTests(unittest.TestCase):
    def response(self, code, body='{}'):
        return subprocess.CompletedProcess([], int(code != 200), f'HTTP/2.0 {code} Status\n\n{body}', 'diagnostic\n')

    def test_only_404_means_absent(self):
        with patch.object(publisher.subprocess, 'run', return_value=self.response(404)):
            self.assertIsNone(publisher.lookup('endpoint', missing=True))
        for status in (403, 429, 500, 502):
            with self.subTest(status=status), patch.object(publisher.subprocess, 'run', return_value=self.response(status)) as run, patch.object(publisher.time, 'sleep'):
                with self.assertRaises(RuntimeError):
                    publisher.lookup('endpoint', missing=True)
                self.assertEqual(run.call_count, 3)

    def test_transient_failure_retries(self):
        with patch.object(publisher.subprocess, 'run', side_effect=[self.response(502), self.response(200, '{"id": 7}')]), patch.object(publisher.time, 'sleep'):
            self.assertEqual(publisher.lookup('endpoint'), {'id': 7})

    def test_freshness_rejects_moved_and_newer_runs(self):
        env = {'GITHUB_SHA': 'current', 'GITHUB_RUN_ID': '10'}
        with patch.dict(os.environ, env), patch.object(publisher, 'lookup', return_value={'object': {'sha': 'other', 'type': 'commit'}}):
            with self.assertRaisesRegex(RuntimeError, 'no longer'):
                publisher.fresh('repo', 'v1')
        replies = [{'object': {'sha': 'tag', 'type': 'tag'}}, {'object': {'sha': 'current', 'type': 'commit'}}, {'workflow_id': 1, 'run_number': 10}, {'workflow_runs': [{'run_number': 11}]}]
        with patch.dict(os.environ, env), patch.object(publisher, 'lookup', side_effect=replies):
            with self.assertRaisesRegex(RuntimeError, 'newer run'):
                publisher.fresh('repo', 'v1')


class PublishTests(unittest.TestCase):
    def scenario(self, draft=False, fail_upload=False, missing=False, fail_rollback=False):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'release'
            directory.mkdir()
            for name in ('OmniDev-Windows-x64.msi', 'omnidev-2.whl', 'SHA256SUMS'):
                (directory / name).write_text('new')
            assets = [{'name': n} for n in ('OmniDev-Windows-x64.msi', 'omnidev-1.whl', 'SHA256SUMS', 'notes.txt')]
            release = {'draft': draft, 'assets': assets}
            calls = []

            def gh(*args):
                calls.append(args)
                if args[:2] == ('release', 'download'):
                    target = Path(args[args.index('--dir') + 1]) / args[args.index('--pattern') + 1]
                    target.write_text('original')
                if args[:2] == ('release', 'upload'):
                    if '--clobber' in args and fail_upload:
                        raise RuntimeError('upload failed')
                    if '--clobber' not in args:
                        if fail_rollback:
                            raise RuntimeError('rollback failed')
                        self.assertTrue(all(Path(f).read_text() == 'original' for f in args[3:]))
                return ''

            replies = [None, release] if missing else [release]
            if fail_upload:
                replies.append({'assets': assets + [{'name': 'omnidev-2.whl'}]})
            with patch.dict(os.environ, {'GH_REPO': 'owner/repo', 'RELEASE_TAG': 'v1'}), patch.object(publisher, 'fresh') as fresh, patch.object(publisher, 'lookup', side_effect=replies), patch.object(publisher, 'gh', side_effect=gh):
                if fail_upload:
                    with self.assertRaises(RuntimeError):
                        publisher.publish(directory)
                else:
                    publisher.publish(directory)
                    self.assertEqual(fresh.call_count, 3)
            self.assertFalse(any('notes.txt' in c for c in calls))
            return calls

    def test_published_release_replaces_and_removes_stale_wheel(self):
        calls = self.scenario()
        self.assertIn(('release', 'delete-asset', 'v1', 'omnidev-1.whl', '--yes'), calls)
        self.assertEqual(calls[-1], ('release', 'edit', 'v1', '--draft=false'))
        self.assertLess(next(i for i,c in enumerate(calls) if c[1] == 'download'), next(i for i,c in enumerate(calls) if c[1] == 'edit'))

    def test_existing_draft_is_published(self):
        self.assertEqual(self.scenario(draft=True)[-1], ('release', 'edit', 'v1', '--draft=false'))

    def test_absent_release_created_as_draft(self):
        calls = self.scenario(draft=True, missing=True)
        self.assertIn('--draft', calls[0])
        self.assertEqual(calls[-1][-1], '--draft=false')

    def test_failure_restores_originals_before_republishing(self):
        calls = self.scenario(fail_upload=True)
        self.assertEqual(calls[-2][1], 'upload')
        self.assertNotIn('--clobber', calls[-2])
        self.assertEqual(calls[-1][-1], '--draft=false')

    def test_failed_draft_stays_draft(self):
        self.assertFalse(any('--draft=false' in c for c in self.scenario(draft=True, fail_upload=True)))

    def test_failed_rollback_stays_hidden(self):
        self.assertFalse(any('--draft=false' in c for c in self.scenario(fail_upload=True, fail_rollback=True)))


if __name__ == '__main__':
    unittest.main()
