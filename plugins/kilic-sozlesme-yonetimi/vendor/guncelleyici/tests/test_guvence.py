"""Offline safety regression tests. Never change a real user configuration."""
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import islem_guvencesi as g
import mcp_ayar as m


class SafetyTests(unittest.TestCase):
    def plan(self):
        return {"schema": g.SCHEMA, "identity": {"user": "fixture"},
                "expires_at": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat(),
                "components": [{"key": "node", "selectable": True,
                                "target": {"version": "1.2.3", "sha256": "a" * 64},
                                "before": {"version": "1.0.0", "path": "fixture"}}]}

    def test_plan_binds_target_hash(self):
        p = self.plan(); digest = g.fingerprint(p)
        self.assertEqual(g.check_plan(p, digest, ["node"])[0]["key"], "node")
        p["components"][0]["target"]["sha256"] = "b" * 64
        with self.assertRaises(g.SafetyError): g.check_plan(p, digest, ["node"])

    def test_plan_rejects_unknown_and_empty_selection(self):
        p = self.plan()
        for keys in ([], ["bad"]):
            with self.assertRaises(g.SafetyError): g.check_plan(p, g.fingerprint(p), keys)

    def test_expired_plan(self):
        p = self.plan(); p["expires_at"] = "2020-01-01T00:00:00+00:00"
        with self.assertRaises(g.SafetyError): g.check_plan(p, g.fingerprint(p), ["node"])

    def test_wrong_identity(self):
        p = self.plan()
        with self.assertRaises(g.SafetyError):
            g.check_plan(p, g.fingerprint(p), ["node"], identity={"user": "other"})

    def test_no_checks_is_not_pass(self):
        self.assertEqual(g.aggregate_checks([]), "NOT_RUN")
        self.assertEqual(g.aggregate_checks([{"status": "INFO"}]), "NOT_RUN")
        self.assertEqual(g.aggregate_checks([{"status": "PASS"}, {"status": "NOT_RUN"}]), "WARNING")

    def test_mcp_invalid_responses(self):
        for value in (None, {}, {"error": {"message": "bad"}}, {"result": {"tools": [None]}},
                      {"result": {"tools": [{"name": "x"}]}}, {"result": {"tools": []}}):
            with self.subTest(value=value), self.assertRaises(g.SafetyError): g.validate_mcp_tools(value)

    def test_mcp_valid_response(self):
        self.assertEqual(g.validate_mcp_tools({"result": {"tools": [{"name": "x", "inputSchema": {"type": "object"}}]}}), {"x"})

    def test_lock_excludes_and_releases(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "lock"
            with g.exclusive_lock(p):
                with self.assertRaises(g.SafetyError):
                    with g.exclusive_lock(p): pass
            self.assertFalse(p.exists())

    def test_existing_lock_not_removed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "lock"; p.write_text("stale")
            with self.assertRaises(g.SafetyError):
                with g.exclusive_lock(p): pass
            self.assertEqual(p.read_text(), "stale")

    def test_atomic_write_refuses_concurrent_change(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config"; p.write_bytes(b"new user edit")
            with self.assertRaises(g.SafetyError): g.atomic_bytes(p, b"replacement", expected_hash=g.digest_bytes(b"old"))
            self.assertEqual(p.read_bytes(), b"new user edit")

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); target = root / "target"; target.write_bytes(b"keep")
            link = root / "link"
            try: link.symlink_to(target)
            except OSError: self.skipTest("symlink privilege unavailable")
            with self.assertRaises(g.SafetyError): g.atomic_bytes(link, b"bad")
            self.assertEqual(target.read_bytes(), b"keep")

    def test_proxy_redaction(self):
        text = g.redact("https://name:secret@proxy.invalid/x?token=private&ok=1")
        self.assertNotIn("secret", text); self.assertNotIn("private", text)


class ConfigTests(unittest.TestCase):
    def test_codex_preserves_environment_and_unknown_fields(self):
        old = b'[mcp_servers.powerbi-modeling]\ncommand = "old.exe"\nargs = ["--start"]\nstartup_timeout_sec = 95\nenabled = false\n[mcp_servers.powerbi-modeling.env]\nA = "keep"\n[mcp_servers.other]\ncommand = "else.exe"\n'
        out = m.update_codex(old, r'C:\new path\server.exe')
        obj = m.validate_codex(out)
        self.assertEqual(obj["mcp_servers"][m.NAME]["env"], {"A": "keep"})
        self.assertEqual(obj["mcp_servers"][m.NAME]["startup_timeout_sec"], 95)
        self.assertFalse(obj["mcp_servers"][m.NAME]["enabled"])
        self.assertEqual(obj["mcp_servers"]["other"]["command"], "else.exe")

    def test_codex_bom_crlf(self):
        old = b'\xef\xbb\xbf[mcp_servers."powerbi-modeling"]\r\ncommand = "old"\r\nargs = ["--start"]\r\n'
        out = m.update_codex(old, "new")
        self.assertTrue(out.startswith(b'\xef\xbb\xbf'))
        self.assertIn(b'\r\n', out)

    def test_codex_custom_args_rejected(self):
        old = b'[mcp_servers.powerbi-modeling]\ncommand = "old"\nargs = ["--other"]\n'
        with self.assertRaises(g.SafetyError): m.update_codex(old, "new")

    def test_codex_multiline_rejected(self):
        old = b'[mcp_servers.powerbi-modeling]\ncommand = """old\nvalue"""\nargs = ["--start"]\n'
        with self.assertRaises(g.SafetyError): m.update_codex(old, "new")

    def test_codex_new_entry(self):
        obj = m.validate_codex(m.update_codex(b'model = "fixture"\n', "new"))
        self.assertEqual(obj["model"], "fixture")
        self.assertEqual(obj["mcp_servers"][m.NAME]["command"], "new")

    def test_desktop_preserves_fields(self):
        old = {"theme": "keep", "mcpServers": {m.NAME: {"command": "old", "args": ["--start"], "env": {"A": "secret"}, "custom": 8}}}
        obj = m.validate_desktop(m.update_desktop(json.dumps(old).encode(), "new"))
        self.assertEqual(obj["theme"], "keep")
        self.assertEqual(obj["mcpServers"][m.NAME]["env"], {"A": "secret"})
        self.assertEqual(obj["mcpServers"][m.NAME]["custom"], 8)

    def test_invalid_json_does_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.json"; p.write_bytes(b"{bad")
            with self.assertRaises(ValueError):
                g.config_transaction(p, lambda x: m.update_desktop(x, "new"), m.validate_desktop)
            self.assertEqual(p.read_bytes(), b"{bad")

    def test_backup_and_idempotence(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.toml"; before = b'model = "keep"\n'; p.write_bytes(before)
            result = g.config_transaction(p, lambda x: m.update_codex(x, "new"), m.validate_codex)
            self.assertEqual(Path(result["backup"]).read_bytes(), before)
            after = p.read_bytes()
            result2 = g.config_transaction(p, lambda x: m.update_codex(x, "new"), m.validate_codex)
            self.assertEqual(result2["status"], "unchanged")
            self.assertEqual(p.read_bytes(), after)

    def test_atomic_replace_failure_keeps_original(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config"; p.write_bytes(b"old")
            with patch.object(g.os, "replace", side_effect=OSError("fixture")):
                with self.assertRaises(OSError): g.atomic_bytes(p, b"new")
            self.assertEqual(p.read_bytes(), b"old")


if __name__ == "__main__": unittest.main()