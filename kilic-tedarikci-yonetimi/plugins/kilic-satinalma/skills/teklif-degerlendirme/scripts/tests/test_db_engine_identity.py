import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import db
from run_tests import assert_engine
from test_engine_support import EXPECTED_ENGINE

class EngineIdentityTests(unittest.TestCase):
    def test_wrong_connection_rejected_independently_of_environment(self):
        con = sqlite3.connect(":memory:")
        try:
            with patch.dict(os.environ, {"TEKLIF_TEST_SQLITE": "1"}):
                with self.assertRaisesRegex(AssertionError, "requested=duckdb, actual=sqlite"):
                    assert_engine(con, "duckdb")
        finally:
            con.close()

    def test_environment_override_cannot_hide_wrong_engine(self):
        if EXPECTED_ENGINE == "duckdb":
            with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"TEKLIF_TEST_SQLITE": "1"}):
                with self.assertRaisesRegex(AssertionError, "DB engine mismatch"):
                    db.connect(Path(td))
        else:
            con = sqlite3.connect(":memory:")
            try:
                with self.assertRaises(AssertionError):
                    assert_engine(con, "duckdb")
            finally:
                con.close()

    def test_real_connection_and_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            db.init_db(path)
            con = db.connect(path)
            try:
                actual = assert_engine(con, EXPECTED_ENGINE or "sqlite")
                engine = con.execute("SELECT value FROM run_meta WHERE key='db_engine'").fetchone()[0]
                self.assertEqual(engine, "sqlite-test" if actual == "sqlite" else "duckdb")
            finally:
                con.close()
