"""Actual local subprocess entrypoint checks plus configuration edge cases."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'scripts';sys.path.insert(0,str(S))
import mcp_ayar as m
import islem_guvencesi as g

class CliTests(unittest.TestCase):
    def call(self,name,*args,env=None):
        return subprocess.run([sys.executable,'-B',str(S/name),*args],capture_output=True,text=True,encoding='utf-8',timeout=30,env=env)
    def test_package_local_scan_has_no_state_writes(self):
        with tempfile.TemporaryDirectory() as td:
            state=Path(td)/'state';env=dict(os.environ,LOCALAPPDATA=str(state),PYTHONDONTWRITEBYTECODE='1')
            r=self.call('kurulum-testi.py','--local-only',env=env)
            self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout.split('@@SONUC ')[-1])['health'],'NOT_RUN')
            self.assertFalse(state.exists())
    def test_duckdb_local_scan_has_no_state_writes(self):
        with tempfile.TemporaryDirectory() as td:
            state=Path(td)/'state';env=dict(os.environ,LOCALAPPDATA=str(state),PYTHONDONTWRITEBYTECODE='1')
            r=self.call('python-paket-kur.py','duckdb','--local-only',env=env)
            self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout.split('@@SONUC ')[-1])['health'],'NOT_RUN')
            self.assertFalse(state.exists())
    def test_config_cli_requires_closed_clients(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'config.toml';p.write_bytes(b'model="keep"\n')
            r=self.call('mcp_ayar.py','codex','--path',str(p),'--exe','fixture.exe')
            self.assertEqual(r.returncode,2);self.assertEqual(p.read_bytes(),b'model="keep"\n')

class ConfigEdgeTests(unittest.TestCase):
    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(g.SafetyError):m.validate_desktop(b'{"x":1,"x":2}')
    def test_codex_command_comment_preserved(self):
        old=b'[mcp_servers.powerbi-modeling]\ncommand = "old" # user note\nargs = ["--start"]\n'
        self.assertIn(b'# user note',m.update_codex(old,'new'))
    def test_toml_date_type_preserved(self):
        old=b'published=2026-01-02\n[mcp_servers.powerbi-modeling]\ncommand="old"\nargs=["--start"]\n'
        self.assertEqual(m.validate_codex(old)['published'],m.validate_codex(m.update_codex(old,'new'))['published'])
    def test_readback_validation_failure_restores_old(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'config';p.write_bytes(b'old');counter=0
            def validate(data):
                nonlocal counter
                counter+=1
                if counter==2:raise g.SafetyError('fixture readback validator failure')
            with self.assertRaises(g.SafetyError):g.config_transaction(p,lambda _:b'new',validate)
            self.assertEqual(p.read_bytes(),b'old')
    def test_concurrent_config_change_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'config';p.write_bytes(b'old')
            def change_and_transform(_):p.write_bytes(b'other edit');return b'new'
            with self.assertRaises(g.SafetyError):g.config_transaction(p,change_and_transform,lambda _:None)
            self.assertEqual(p.read_bytes(),b'other edit')

if __name__=='__main__':unittest.main()