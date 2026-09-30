$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot '..\scripts\sohbet.ps1'
$null = . $scriptPath -LibraryOnly

function Assert([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

$script:InstallCalls = New-Object Collections.ArrayList
$script:LegacyCleanupCalls = 0
function Remove-LegacySkill { $script:LegacyCleanupCalls++; return @() }
function Scan-Inventory {
    $script:Inventory.Clear()
    $script:Inventory['python'] = New-Entry 'python' 'Python' '3.14.6' '3.14.7' ''
    $script:Inventory['node'] = New-Entry 'node' 'Node.js' '24.1.0' '24.2.0' ''
    $script:Inventory['pnpm'] = New-Entry 'pnpm' 'pnpm' '12.0.0' '12.1.0' ''
    $script:Inventory['offer'] = New-Entry 'offer' 'Teklif' '4.0.0' $null 'Ağ kapalı'
}
function Install-Selected([string]$Key) {
    [void]$script:InstallCalls.Add($Key)
    if ($Key -eq 'python') { throw 'Örnek kurulum hatası' }
    return [pscustomobject]@{durum='KURULDU';surum='12.1.0'}
}

$Action = 'scan'
$scan = Invoke-ChatAction
Assert ($scan.status -eq 'selection_required') 'Sohbet seçimi dönmedi.'
Assert ($scan.rows.Count -eq 4 -and $scan.rows[0].key -eq 'python') 'Satır sırası yanlış.'
Assert ($scan.rows[0].secili -and -not $scan.rows[3].secilebilir) 'Varsayılan seçim yanlış.'
Assert ($scan.rows[3].durum -like 'Kontrol edilemedi*') 'Ağ uyarısı kayboldu.'
Assert ($script:InstallCalls.Count -eq 0) 'Tarama kurulum başlattı.'
Assert ($script:LegacyCleanupCalls -eq 0) 'Tarama eski skill temizliğini başlattı.'

$Action = 'apply'; $Keys = 'python,pnpm'; $Fingerprint = ('0' * 64)
$stale = Invoke-ChatAction
Assert ($stale.status -eq 'stale' -and $script:InstallCalls.Count -eq 0) 'Eski seçim kuruluma geçti.'
Assert ($script:LegacyCleanupCalls -eq 0) 'Eski seçim temizliği başlattı.'

$Fingerprint = $scan.fingerprint
$Keys = 'offer'
$rejected = $false
try { $null = Invoke-ChatAction } catch { $rejected = $true }
Assert ($rejected -and $script:InstallCalls.Count -eq 0) 'Seçilemeyen satır kabul edildi.'
Assert ($script:LegacyCleanupCalls -eq 0) 'Geçersiz seçim temizliği başlattı.'

$Keys = ''
$cancel = Invoke-ChatAction
Assert ($cancel.status -eq 'cancelled' -and $script:InstallCalls.Count -eq 0) 'Boş seçim kurulum başlattı.'
Assert ($script:LegacyCleanupCalls -eq 0) 'Boş seçim temizliği başlattı.'

$Keys = 'python,pnpm'
$result = Invoke-ChatAction
Assert ($result.status -eq 'error') 'Kurulum hatası genel durumda görünmedi.'
Assert (($script:InstallCalls -join ',') -eq 'python,pnpm') 'Kurulum sırası veya seçim yanlış.'
Assert ($script:LegacyCleanupCalls -eq 1) 'Temizlik yalnız açık uygulamada çalışmalı.'
Assert ($result.results.Count -eq 2 -and $result.results[0].sonuc -eq 'Hata') 'Hata kaydı eksik.'
Assert ($result.rows[1].durum -eq 'Atlandı · seçilmedi') 'Seçilmeyen satır raporlanmadı.'
Assert ($result.rows[3].durum -like 'Kontrol edilemedi*') 'Ağ uyarısı sonuçta kayboldu.'

'SOHBET_TEST_OK'
