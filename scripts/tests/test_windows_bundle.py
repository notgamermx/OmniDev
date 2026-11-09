import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('bundle', Path(__file__).parents[1] / 'windows_bundle.py')
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class RetryTests(unittest.TestCase):
    def run_build(self, failures):
        attempts = []

        def run(command, **kwargs):
            if 'tauri' in command:
                attempts.append(command)
                if len(attempts) <= failures:
                    raise subprocess.CalledProcessError(1, command)

        with patch.object(bundle.sys, 'platform', 'win32'), patch.object(bundle.shutil, 'which', return_value='npm.cmd'), patch.object(bundle.shutil, 'make_archive'), patch.object(bundle.subprocess, 'run', side_effect=run), patch.object(bundle.time, 'sleep'):
            if failures >= 3:
                with self.assertRaises(subprocess.CalledProcessError):
                    bundle.main()
            else:
                bundle.main()
        return len(attempts)

    def test_transient_failure_retries(self):
        self.assertEqual(self.run_build(1), 2)

    def test_success_does_not_retry(self):
        self.assertEqual(self.run_build(0), 1)

    def test_persistent_failure_fails_after_three_attempts(self):
        self.assertEqual(self.run_build(3), 3)
