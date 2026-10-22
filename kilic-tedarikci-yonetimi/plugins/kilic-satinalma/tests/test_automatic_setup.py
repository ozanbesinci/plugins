"""Bootstrap regression tests; Windows cases execute the shipped CMD entry."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / 'scripts'
SHA = '928ff61174f8d01c8441090f4c45376cae98c312147c946aa22d54d50a8c29c4'


def launcher():
    spec = importlib.util.spec_from_file_location('automatic_setup_launcher', SCRIPTS / 'runtime_launcher.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BootstrapContractTests(unittest.TestCase):
    def test_all_six_skills_route_startup_through_python_free_entry(self):
        skills = list((PACKAGE / 'skills').glob('*/SKILL.md'))
        self.assertEqual(len(skills), 6)
        for skill in skills:
            text = skill.read_text(encoding='utf-8')
            self.assertIn(f'& "<aktif-paket>/scripts/teklif.cmd" skill_startup --skill {skill.parent.name}', text)
            self.assertNotIn('Ortam yoksa kurulum mesajını bildir; analiz içinde kurulum yapma.', text)
            self.assertEqual((skill.parent / 'VERSION').read_text().strip(), '5.2.1')

    def test_download_pin_matches_release_manifest_and_dependency_profiles(self):
        manifest = json.loads((PACKAGE / 'release-manifest.json').read_text())
        command = (SCRIPTS / 'ensure_runtime.cmd').read_text()
        self.assertIn(manifest['automatic_setup']['installer_url'], command)
        self.assertEqual(manifest['automatic_setup']['sha256'], SHA)
        self.assertIn(SHA, command)
        # Runtime installation still uses exactly the accepted 1.4.0 lock.
        distribution = PACKAGE.parents[1]
        self.assertEqual((PACKAGE/'config/runtime-profile.json').read_bytes(),
                         (distribution/'kurulum/runtime-profile.json').read_bytes())
        self.assertEqual(hashlib.sha256((distribution/'kurulum/requirements-win-cp314.lock').read_bytes()).hexdigest(),
                         json.loads((PACKAGE/'config/runtime-profile.json').read_text())['lock_sha256'])

    def test_probe_verifies_engine_without_running_original_command(self):
        module = launcher()
        engine = types.ModuleType('calculation_runtime')
        engine.current = Mock(return_value={'status': 'READY'})
        with patch.dict(sys.modules, {'calculation_runtime': engine}), patch.object(sys, 'argv', ['launcher', 'runtime_probe']), contextlib.redirect_stdout(io.StringIO()) as out:
            module.main({'runtime_id': 'existing'})
        engine.current.assert_called_once_with(verify_files=True)
        self.assertEqual(json.loads(out.getvalue()), {'status': 'READY', 'runtime_id': 'existing'})

    def test_probe_rejects_extra_command_arguments(self):
        with patch.object(sys, 'argv', ['launcher', 'runtime_probe', 'workflow']):
            with self.assertRaisesRegex(ValueError, 'argüman'):
                launcher().main({'runtime_id': 'existing'})

    def test_probe_does_not_hide_engine_corruption(self):
        module = launcher()
        engine = types.ModuleType('calculation_runtime')
        engine.current = Mock(side_effect=ValueError('engine changed'))
        with patch.dict(sys.modules, {'calculation_runtime': engine}), patch.object(sys, 'argv', ['launcher', 'runtime_probe']):
            with self.assertRaisesRegex(ValueError, 'engine changed'):
                module.main({'runtime_id': 'existing'})

    def test_missing_runtime_returns_wrapper_recovery_without_installing_in_python(self):
        module = launcher()
        with patch.object(module, 'current', side_effect=OSError('missing')), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(module.entry(), 3)
        result = json.loads(out.getvalue())
        self.assertEqual(result['status'], 'BLOCKED_ENVIRONMENT')
        self.assertIn('scripts/teklif.cmd', result['next_step'])
        self.assertFalse(result['automatic_installation'])


@unittest.skipUnless(sys.platform == 'win32' and os.environ.get('KILIC_REAL_BOOTSTRAP_TEST') == '1', 'requires isolated real Windows bootstrap runner')
class RealWindowsBootstrapTests(unittest.TestCase):
    def run_cmd(self, entry, profile, *, base_python=None, arguments='skill_startup --skill teklif-degerlendirme'):
        env = os.environ.copy()
        env['USERPROFILE'] = str(profile)
        env['KILIC_BASE_PYTHON'] = str(base_python or sys.executable)
        command = f'"{env["ComSpec"]}" /d /s /c ""{entry}" {arguments}"'
        return subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, encoding='utf-8', errors='replace', env=env, timeout=1200)

    def test_clean_profile_installs_then_reuses_same_runtime_and_resumes_original_skill(self):
        with tempfile.TemporaryDirectory(prefix='kilic bootstrap & test ') as td:
            profile = Path(td)
            first = self.run_cmd(SCRIPTS/'teklif.cmd', profile)
            self.assertEqual(first.returncode, 0, first.stdout+'\n'+first.stderr)
            self.assertIn('INSTALLING_ENVIRONMENT', first.stdout)
            self.assertIn('Sürüm: 5.2.1', first.stdout)
            record_path = profile/'KilicPython/teklif-runtime.json'
            original = record_path.read_bytes()
            second = self.run_cmd(SCRIPTS/'teklif.cmd', profile)
            self.assertEqual(second.returncode, 0, second.stdout+'\n'+second.stderr)
            self.assertNotIn('INSTALLING_ENVIRONMENT', second.stdout)
            self.assertEqual(record_path.read_bytes(), original)
            self.assertIn('Sürüm: 5.2.1', second.stdout)

    def test_existing_install_lock_blocks_without_download_or_analysis(self):
        with tempfile.TemporaryDirectory() as td:
            profile = Path(td)
            (profile/'KilicPython/teklif-setup.lock').mkdir(parents=True)
            result = self.run_cmd(SCRIPTS/'teklif.cmd', profile)
            self.assertEqual(result.returncode, 3, result.stdout+result.stderr)
            self.assertIn('SETUP_ALREADY_RUNNING_OR_LOCKED', result.stdout)
            self.assertNotIn('Sürüm:', result.stdout)

    def test_changed_download_hash_is_never_extracted_or_executed(self):
        with tempfile.TemporaryDirectory() as td:
            profile = Path(td)/'profile'
            profile.mkdir()
            entry = Path(td)/'bad-hash.cmd'
            entry.write_bytes((SCRIPTS/'ensure_runtime.cmd').read_bytes().replace(SHA.encode(), b'0'*64))
            result = self.run_cmd(entry, profile, arguments='')
            self.assertEqual(result.returncode, 3, result.stdout+result.stderr)
            self.assertIn('INSTALLER_HASH_MISMATCH', result.stdout)
            self.assertFalse(list(profile.rglob('payload')))
            self.assertFalse((profile/'KilicPython/teklif-runtime.json').exists())

    def test_installer_failure_does_not_resume_original_skill(self):
        with tempfile.TemporaryDirectory() as td:
            profile = Path(td)
            result = self.run_cmd(SCRIPTS/'teklif.cmd', profile, base_python=profile/'missing.exe')
            self.assertEqual(result.returncode, 3, result.stdout+result.stderr)
            self.assertIn('INSTALLER_FAILED', result.stdout)
            self.assertNotIn('Sürüm:', result.stdout)
            self.assertFalse((profile/'KilicPython/teklif-runtime.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
