import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from codex_executable import resolve, candidates

class ExecutableTests(unittest.TestCase):
    def test_missing_old_path_falls_back_to_new(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            new=base/'codex';new.write_text('#!/bin/sh\n');new.chmod(0o700)
            with patch('codex_executable.candidates',return_value=iter([base/'old',new])):
                self.assertEqual(resolve(),str(new))
            new.chmod(0o600)
            with patch('codex_executable.candidates',return_value=iter([new])):
                with self.assertRaises(RuntimeError):resolve()
    def test_launchd_without_shell_path(self):
        with patch('codex_executable.shutil.which',return_value=None):
            self.assertIn(Path('/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'), list(candidates()))
