"""pnpm betiğinin gerçek dosya taşıma/geri dönüş akışı; ağ, npm ve PATH izole taklitler."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

KAYNAK = Path(__file__).resolve().parents[3] / 'skills/guncelleyici/scripts/pnpm-kur.ps1'
TAKLIT = r'''
$testKok = $env:PG_TEST_ROOT
$KURULUM_KLASORU = Join-Path $testKok 'pnpm'
$KARANTINA = Join-Path $testKok '_karantina'
function PathKlasorleri { return @($KURULUM_KLASORU) }
function Israrla([scriptblock]$Is) { & $Is }
function Kapsam([string]$Yol) { if ($env:PG_TEST_CASE -eq 'machine') { return 'makine geneli' }; return 'kullanıcı' }
function Invoke-RestMethod {
    if ($env:PG_TEST_CASE -eq 'network') { throw 'simulated registry failure' }
    return [pscustomobject]@{name='pnpm';version='12.6.0';dist=@{integrity='sha512-YWJj'};engines=@{node='>=20.19 || >=22.12'}}
}
function Calistir([string]$Dosya, [string]$Argumanlar, [int]$SureMs, [string]$EkPath = '') {
    $out = '24.15.0'; $kod = 0
    if ($Argumanlar -like '*process.argv*') { $out = if ($env:PG_TEST_CASE -eq 'engine') { 'false' } else { 'true' } }
    if ($Argumanlar -like '*install --global*') {
        [IO.File]::WriteAllText((Join-Path $testKok 'npm-called.txt'), $Argumanlar)
        if ($env:PG_TEST_CASE -eq 'npm-fail') { $kod=17 }
        else {
            New-Item -ItemType Directory -Path $hazirlik -Force | Out-Null
            [IO.File]::WriteAllText((Join-Path $hazirlik 'pnpm.cmd'), '12.6.0')
        }
    }
    return [pscustomobject]@{Kod=$kod;Cikti=$out;Hata=''}
}
function PnpmDogrula([string]$Dosya) {
    if (-not (Test-Path -LiteralPath $Dosya)) { return $null }
    $v = [IO.File]::ReadAllText($Dosya)
    if ($env:PG_TEST_CASE -eq 'final-fail' -and $Dosya -eq (Join-Path $KURULUM_KLASORU 'pnpm.cmd') -and $v -eq '12.6.0') { return $null }
    return [pscustomobject]@{Surum=$v;Yol=$Dosya}
}
function KullaniciPathEkle {
    if ($env:PG_TEST_CASE -eq 'path-fail') { throw 'simulated PATH failure' }
    [IO.File]::WriteAllText((Join-Path $testKok 'path-called.txt'), $KURULUM_KLASORU)
}
function Move-Item {
    param($LiteralPath, $Destination, $ErrorAction)
    if ($env:PG_TEST_CASE -eq 'move-fail' -and $LiteralPath -like '*pnpm.yeni-*') { throw 'simulated move failure' }
    Microsoft.PowerShell.Management\Move-Item -LiteralPath $LiteralPath -Destination $Destination -ErrorAction Stop
}
function Rename-Item {
    param($LiteralPath, $NewName, $ErrorAction)
    if ($env:PG_TEST_CASE -eq 'move-fail') { throw 'simulated rename failure' }
    Microsoft.PowerShell.Management\Rename-Item -LiteralPath $LiteralPath -NewName $NewName -ErrorAction Stop
}
'''


class PnpmAkis(unittest.TestCase):
    def kos(self, senaryo, eski=None, yalniz=False, exe=False):
        # Gerçek betik farklı bir alt süreçte çalışır; Bitir/exit akışı da sınanır.
        with tempfile.TemporaryDirectory(prefix='pg-pnpm-test-') as tmp:
            root = Path(tmp)
            script = root / 'pnpm-kur.ps1'
            source = KAYNAK.read_text(encoding='utf-8-sig')
            source = source.replace("Write-Host ''\nYaz", TAKLIT + "\nWrite-Host ''\nYaz", 1)
            script.write_text(source, encoding='utf-8-sig')
            node = root / 'node/node.exe'
            node.parent.mkdir()
            node.write_text('test')
            (node.parent / 'node_modules/npm/bin').mkdir(parents=True)
            (node.parent / 'node_modules/npm/bin/npm-cli.js').write_text('test')
            (node.parent / 'node_modules/npm/node_modules/semver').mkdir(parents=True)
            if eski:
                (root / 'pnpm').mkdir()
                (root / 'pnpm' / ('pnpm.exe' if exe else 'pnpm.cmd')).write_text(eski)
            report = root / 'report.txt'
            report.touch()
            cmd = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
                   '-NodeYolu', str(node if senaryo != 'bad-node' else root / 'missing.exe'), '-Rapor', str(report)]
            if yalniz:
                cmd += ['-YalnizBul']
            env = dict(os.environ, PG_TEST_ROOT=str(root), PG_TEST_CASE=senaryo)
            r = subprocess.run(cmd, env=env, capture_output=True, encoding='utf-8', timeout=40)
            self.assertEqual(r.returncode, 0, r.stderr)
            lines = [s for s in r.stdout.splitlines() if s.startswith('@@SONUC ')]
            self.assertEqual(len(lines), 1, r.stdout + r.stderr)
            result = json.loads(lines[0][8:])
            files = {str(p.relative_to(root)).replace('\\', '/'): p.read_text(encoding='utf-8-sig')
                     for p in root.rglob('*') if p.is_file() and p.name != 'pnpm-kur.ps1'}
            return result, files

    def test_new_install(self):
        r, f = self.kos('install')
        self.assertEqual(r['durum'], 'KURULDU')
        self.assertEqual(f['pnpm/pnpm.cmd'], '12.6.0')
        self.assertIn('path-called.txt', f)
        for flag in ('--registry=https://registry.npmjs.org', '--engine-strict'):
            self.assertIn(flag, f['npm-called.txt'])

    def test_upgrade_preserves_old(self):
        r, f = self.kos('upgrade', '11.8.0')
        self.assertEqual(r['durum'], 'GUNCELLENDI')
        self.assertTrue(any(k.startswith('_karantina/') and v == '11.8.0' for k, v in f.items()))

    def test_failure_restores_old(self):
        for case in ('final-fail', 'move-fail', 'npm-fail'):
            with self.subTest(case=case):
                r, f = self.kos(case, '11.8.0')
                self.assertEqual(r['durum'], 'ESKI_SURUM')
                self.assertEqual(r['surum'], '11.8.0')
                self.assertEqual(f['pnpm/pnpm.cmd'], '11.8.0')
                self.assertNotIn('path-called.txt', f)

    def test_new_failure_does_not_claim_old(self):
        r, f = self.kos('final-fail')
        self.assertEqual(r['durum'], 'BASARISIZ')
        self.assertNotIn('pnpm/pnpm.cmd', f)

    def test_path_failure_is_warning(self):
        r, f = self.kos('path-fail', '11.8.0')
        self.assertEqual(r['ozet'], 'UYARI')
        self.assertEqual(r['surum'], '12.6.0')
        self.assertEqual(f['pnpm/pnpm.cmd'], '12.6.0')

    def test_read_only_machine_current_and_network(self):
        cases = [('read', '11.8.0', True, 'ESKI_SURUM'), ('machine', '11.8.0', False, 'ESKI_SURUM'),
                 ('current', '12.6.0', False, 'MEVCUT'), ('network', None, False, 'KONTROL_EDILEMEDI'),
                 ('engine', '11.8.0', False, 'BASARISIZ'), ('bad-node', None, False, 'BASARISIZ')]
        for case, old, readonly, expected in cases:
            with self.subTest(case=case):
                r, f = self.kos(case, old, readonly)
                self.assertEqual(r['durum'], expected)
                self.assertNotIn('npm-called.txt', f)
                if case == 'current':
                    self.assertIn('path-called.txt', f)
                else:
                    self.assertNotIn('path-called.txt', f)

    def test_executable_and_same_version_prerelease(self):
        r, f = self.kos('current', '12.6.0', exe=True)
        self.assertEqual(r['durum'], 'MEVCUT')
        self.assertNotIn('npm-called.txt', f)
        r, _ = self.kos('upgrade', '12.6.0-beta.1')
        self.assertEqual(r['durum'], 'GUNCELLENDI')


if __name__ == '__main__':
    unittest.main()
