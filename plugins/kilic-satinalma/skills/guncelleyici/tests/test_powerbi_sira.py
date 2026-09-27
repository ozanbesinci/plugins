"""Power BI ana akışında çalışan sunucuyu sınamadan ayar yazılmadığını doğrular."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[3] / 'skills/guncelleyici/scripts/powerbi-mcp-kur.ps1'
MOCK = r'''
function TumKurulumlar { return [pscustomobject]@{Surum='1.0.0';Exe=(Join-Path $KOK '1.0.0\extension\server\powerbi-modeling-mcp.exe')} }
function SonSurumuOgren { if ($env:PG_PBI_CASE -eq 'network-fail') { return $null }; return [pscustomobject]@{Surum='1.0.0';OnSurum=$false;Kaynak='test'} }
function McpTest([string]$Exe) {
    [IO.File]::AppendAllText((Join-Path $env:LOCALAPPDATA 'order.txt'), 'test;')
    $ok = $env:PG_PBI_CASE -eq 'pass'
    $testler.Add(@{ad='mock';durum=$(if($ok){'GEÇTİ'}else{'ENGEL'});ayrinti='fixture'})
    return $ok
}
function Bagla([string]$Exe) { [IO.File]::AppendAllText((Join-Path $env:LOCALAPPDATA 'order.txt'), 'bind;'); return $true }
function EskileriTemizle([string]$Tut) { return }
'''


class PowerBiSira(unittest.TestCase):
    def test_main_paths(self):
        for case in ('pass','fail','network-fail'):
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix='pg-pbi-order-') as tmp:
                root=Path(tmp)
                script=root/'pbi.ps1'
                text=SOURCE.read_text(encoding='utf-8-sig').replace('$kurulumlar = @(TumKurulumlar)', MOCK+'\n$kurulumlar = @(TumKurulumlar)',1)
                script.write_text(text,encoding='utf-8-sig')
                report=root/'report.txt'; report.touch()
                env=dict(os.environ, LOCALAPPDATA=str(root), PG_PBI_CASE=case)
                r=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-Rapor',str(report)],env=env,capture_output=True,encoding='utf-8',timeout=30)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertEqual((root/'order.txt').read_text(),'test;bind;' if case=='pass' else 'test;')


if __name__=='__main__':
    unittest.main()
