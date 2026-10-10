"""Offline adversarial installation tests. Fixtures never contain company data."""
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import guncelle as u


def package(release="3.0.1", additions=None, rewrite=None, versions=None):
    files = {}
    for skill in u.SKILLS:
        v = versions[skill] if versions else release
        files[f"skills/{skill}/SKILL.md"] = f'---\nname: {skill}\ndescription: Fixture\nmetadata:\n  version: "{v}"\n---\nTest\n'.encode()
        files[f"skills/{skill}/VERSION"] = (v + "\n").encode()
        files[f"skills/{skill}/CHANGELOG.md"] = f"# Changes\n\n## v{v}\nFixture\n".encode()
    if additions:
        files.update(additions)
    manifest = {"schema": 1, "repository": u.REPO, "version": release,
                "files": {p: u.sha(b) for p, b in files.items()}}
    if versions:
        manifest.update(schema=2, versioning="independent/v1", skill_versions=versions)
    entries = {**files, u.MANIFEST: json.dumps(manifest).encode()}
    if rewrite:
        rewrite(entries)
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for name, data in entries.items():
            if isinstance(data, zipfile.ZipInfo):
                z.writestr(data, b"target")
            else:
                z.writestr(name, data)
    return b.getvalue(), u.sha(b.getvalue())


class UpdateTests(unittest.TestCase):
    def test_windows_crlf_skill_header_is_supported(self):
        additions={}
        for skill in u.SKILLS:
            additions[f'skills/{skill}/SKILL.md']=f'---\r\nname: {skill}\r\ndescription: Fixture\r\nmetadata:\r\n  version: "3.0.1"\r\n---\r\nTest\r\n'.encode()
        data,digest=package(additions=additions)
        manifest,_=u.validate_archive(data,digest)
        self.assertEqual(manifest['version'],'3.0.1')

    def test_v4_metadata_only_package_cannot_remove_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'skills'
            u.install(root,*package())
            partial,checksum=package('4.0.0',versions={u.SKILLS[0]:'4.0.0',u.SKILLS[1]:'1.1.0'})
            with self.assertRaises(u.UpdateError): u.install(root,partial,checksum)
            self.assertEqual(u.verify_install(root)['version'],'3.0.1')

    def test_transient_windows_sharing_error_retries_but_is_bounded(self):
        with patch.object(u.os,'replace',side_effect=[PermissionError('busy'),None]) as mocked, patch.object(u.time,'sleep'):
            u.replace_path('from','to')
            self.assertEqual(mocked.call_count,2)
        with patch.object(u.os,'replace',side_effect=PermissionError('locked')) as mocked, patch.object(u.time,'sleep'):
            with self.assertRaises(PermissionError): u.replace_path('from','to')
            self.assertEqual(mocked.call_count,5)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="teklif-update-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "skills"

    def test_install_pair_and_upgrade_then_verify(self):
        data, digest = package()
        self.assertEqual(u.install(self.root, data, digest)["status"], "installed")
        newer, newhash = package("3.0.2")
        u.install(self.root, newer, newhash)
        self.assertEqual(u.verify_install(self.root)["version"], "3.0.2")
        for skill in u.SKILLS:
            self.assertEqual((self.root / skill / "VERSION").read_text().strip(), "3.0.2")
        self.assertFalse((self.root / u.JOURNAL).exists())

    def test_staging_inherits_install_root_permissions(self):
        data, digest = package()
        with patch.object(u.tempfile, "mkdtemp", side_effect=AssertionError("Private staging DACL must not be used")):
            u.install(self.root, data, digest)
        self.assertEqual(u.verify_install(self.root)["version"], "3.0.1")

    def test_same_version_local_candidate_requires_explicit_flag_and_valid_old_tree(self):
        data, digest = package(); u.install(self.root, data, digest)
        changed, checksum = package(additions={"skills/teklif-degerlendirme/scripts/new.py": b"# fixture"})
        with self.assertRaises(u.UpdateError): u.install(self.root, changed, checksum)
        u.install(self.root, changed, checksum, replace_local=True)
        self.assertTrue((self.root / u.SKILLS[0] / "scripts/new.py").exists())
        older, oldsum = package("3.0.0")
        with self.assertRaises(u.UpdateError): u.install(self.root, older, oldsum, replace_local=True)
        (self.root / u.SKILLS[0] / "VERSION").write_text("changed")
        with self.assertRaises(u.UpdateError): u.install(self.root, data, digest, replace_local=True)

    def test_bad_archive_hash_does_not_touch_install(self):
        data, digest = package(); u.install(self.root, data, digest)
        with self.assertRaises(u.UpdateError):
            u.install(self.root, data, "0" * 64)
        self.assertEqual(u.verify_install(self.root)["version"], "3.0.1")

    def test_modified_and_unknown_files_are_not_overwritten(self):
        data, digest = package(); u.install(self.root, data, digest)
        user_file = self.root / u.SKILLS[0] / "my-note.md"
        user_file.write_text("keep me")
        newer, newhash = package("3.0.2")
        with self.assertRaises(u.UpdateError):
            u.install(self.root, newer, newhash)
        self.assertEqual(user_file.read_text(), "keep me")

    def test_active_analysis_and_update_lock(self):
        self.root.mkdir()
        for lock_name in (u.ANALYSIS_LOCK, u.UPDATE_LOCK):
            lock = self.root / lock_name; lock.write_text("active")
            with self.assertRaises(u.UpdateError):
                u.install(self.root, *package())
            self.assertEqual(lock.read_text(), "active")
            lock.unlink()

    def test_unmanaged_v2_not_replaced(self):
        folder = self.root / u.SKILLS[0]; folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("local v2 changes")
        with self.assertRaises(u.UpdateError):
            u.install(self.root, *package())
        self.assertEqual((folder / "SKILL.md").read_text(), "local v2 changes")

    def test_register_only_exact_source(self):
        data, digest = package(); manifest, files = u.validate_archive(data, digest)
        for p, content in files.items():
            dest = self.root / Path(p).relative_to("skills")
            dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(content)
        self.assertEqual(u.install(self.root, data, digest, register=True)["status"], "registered")
        self.assertEqual(u.verify_install(self.root)["files"], manifest["files"])

    def test_rollback_if_second_skill_placement_fails(self):
        u.install(self.root, *package())
        original_replace = u.os.replace
        def failing_replace(source, dest):
            if Path(source).parent.name == "new" and Path(source).name == u.SKILLS[1]:
                raise OSError("simulated second swap failure")
            return original_replace(source, dest)
        with patch.object(u.os, "replace", side_effect=failing_replace):
            with self.assertRaises(OSError):
                u.install(self.root, *package("3.0.2"))
        self.assertEqual(u.verify_install(self.root)["version"], "3.0.1")

    def test_path_traversal_windows_case_collision_reserved(self):
        for path in ("../escape.py", "skills/teklif-degerlendirme/../../escape", "skills/teklif-degerlendirme/C:bad", "skills/teklif-degerlendirme/NUL.txt", "skills/teklif-degerlendirme/file. "):
            with self.subTest(path=path), self.assertRaises(u.UpdateError):
                u.validate_archive(*package(additions={path: b"bad"}))
        with self.assertRaises(u.UpdateError):
            u.validate_archive(*package(additions={"skills/teklif-degerlendirme/version": b"3.0.1"}))

    def test_symlink_and_manifest_mismatch_rejected(self):
        link = zipfile.ZipInfo("skills/teklif-degerlendirme/link")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaises(u.UpdateError):
            u.validate_archive(*package(rewrite=lambda e: e.update({link.filename: link})))
        with self.assertRaises(u.UpdateError):
            u.validate_archive(*package(rewrite=lambda e: e.update({"skills/teklif-degerlendirme/VERSION": b"3.0.2"})))

    def test_semver_and_release_version_consistency(self):
        self.assertGreater(u.version("3.10.0"), u.version("3.9.9"))
        for v in ("3.0.1-beta", "03.0.1", "3.0", "main"):
            with self.assertRaises(u.UpdateError): u.version(v)
        data, digest = package()
        with self.assertRaises(u.UpdateError): u.validate_archive(data, digest, "3.0.2")

    def test_downgrade_and_reinstall_blocked(self):
        u.install(self.root, *package("3.0.2"))
        for v in ("3.0.1", "3.0.2"):
            with self.assertRaises(u.UpdateError): u.install(self.root, *package(v))

    def test_release_api_no_release_not_up_to_date(self):
        with patch.object(u, "latest_release", return_value=None):
            self.assertEqual(u.check(self.root)["status"], "no_release_or_repository_not_accessible")

    def test_release_api_rejects_foreign_asset(self):
        payload = {"draft": False, "prerelease": False, "tag_name": "v3.0.2", "assets": []}
        with patch.object(u, "download", return_value=json.dumps(payload).encode()):
            with self.assertRaises(u.UpdateError): u.latest_release()

    def test_untrusted_and_http_redirect_blocked(self):
        for url in ("http://github.com/", "https://evil.test/x", "https://github.com@evil.test/", "https://github.com:8000/"):
            self.assertFalse(u.allowed_url(url))

    def test_archive_limits(self):
        data, digest = package()
        with patch.object(u, "MAX_EXPANDED", 8):
            with self.assertRaises(u.UpdateError): u.validate_archive(data, digest)

    def test_metadata_and_changelog_must_match_package_version(self):
        for name in ("skills/teklif-degerlendirme/SKILL.md", "skills/teklif-degerlendirme/CHANGELOG.md"):
            original, digest = package()
            manifest, files = u.validate_archive(original, digest)
            changed = files[name].replace(b"3.0.1", b"3.0.0")
            with self.subTest(name=name), self.assertRaises(u.UpdateError):
                u.validate_archive(*package(additions={name: changed}))


    def test_legacy_to_independent_versions_and_obsolete_files_removed(self):
        stale = "skills/teklif-degerlendirme/scripts/obsolete.py"
        u.install(self.root, *package(additions={stale: b"old release code"}))
        versions = {u.SKILLS[0]: "3.1.0", u.SKILLS[1]: "1.0.0"}
        result = u.install(self.root, *package("3.1.0", versions=versions))
        self.assertTrue(result["previous_version_removed"])
        self.assertEqual(u.component_versions(u.verify_install(self.root)), versions)
        self.assertFalse((self.root / u.SKILLS[0] / "scripts/obsolete.py").exists())
        self.assertEqual(list(self.root.glob(".teklif-stage-*")), [])
        self.assertFalse((self.root / u.JOURNAL).exists())

    def test_updater_only_release_does_not_bump_main(self):
        versions = {u.SKILLS[0]: "3.1.0", u.SKILLS[1]: "1.0.0"}
        u.install(self.root, *package("3.1.0", versions=versions))
        versions[u.SKILLS[1]] = "1.0.1"
        u.install(self.root, *package("3.1.1", versions=versions))
        self.assertEqual(u.component_versions(u.verify_install(self.root)), versions)
        versions[u.SKILLS[1]] = "1.0.0"
        with self.assertRaises(u.UpdateError):
            u.install(self.root, *package("3.1.2", versions=versions))

    def test_independent_version_mismatch_rejected(self):
        versions = {u.SKILLS[0]: "3.1.0", u.SKILLS[1]: "1.0.0"}
        bad = {"skills/teklif-degerlendirme-guncelle/VERSION": b"3.1.0\n"}
        with self.assertRaises(u.UpdateError):
            u.validate_archive(*package("3.1.0", versions=versions, additions=bad))

    def test_independent_upgrade_rolls_back_complete_old_tree(self):
        u.install(self.root, *package())
        replace = u.os.replace
        def fail_second(source, target):
            if Path(source).parent.name == "new" and Path(source).name == u.SKILLS[1]:
                raise OSError("fixture placement failed")
            return replace(source, target)
        with patch.object(u.os, "replace", side_effect=fail_second):
            with self.assertRaises(OSError):
                u.install(self.root, *package("3.1.0", versions={u.SKILLS[0]: "3.1.0", u.SKILLS[1]: "1.0.0"}))
        self.assertEqual(u.verify_install(self.root)["version"], "3.0.1")


if __name__ == "__main__":
    unittest.main()
