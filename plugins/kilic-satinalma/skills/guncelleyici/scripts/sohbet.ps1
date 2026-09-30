param(
    [ValidateSet('scan','apply')][string]$Action = 'scan',
    [string]$Keys = '',
    [string]$Fingerprint = '',
    [switch]$LibraryOnly
)

# The existing installer and version checks are shared with the former window.
# No Windows Forms object is created on this entry point.
$null = . (Join-Path $PSScriptRoot 'panel.ps1') -TestMode

function Get-EntryStatus($Entry) {
    if ($Entry.Ready -and -not $Entry.RawInstalled) { return 'Güncel sürüm yüklenecek' }
    if ($Entry.Ready) { return 'Güncelleme seçilebilir' }
    if ($Entry.Key -eq 'libraries' -and $Entry.RawLatest) { return 'Doğrulanmış set hazır' }
    if ($Entry.RawLatest -and (Version-Compare $Entry.RawInstalled $Entry.RawLatest)) {
        if ([version]$Entry.RawInstalled -gt [version]$Entry.RawLatest) { return 'Yüklü sürüm yayından yeni' }
        return 'Güncel'
    }
    if (-not $Entry.RawLatest) {
        return (Check-FailureText $Entry.Note).Replace('ayrıntı için satırın üzerine gelin', 'ayrıntı aşağıda')
    }
    return [string]$Entry.Note
}

function Get-ChatRows {
    return @($script:Inventory.Values | ForEach-Object {
        [pscustomobject]@{
            key = $_.Key; ad = $_.Name; yuklu = $_.Installed; guncel = $_.Latest
            durum = Get-EntryStatus $_; ayrinti = $_.Note
            secili = [bool]$_.Ready; secilebilir = [bool]$_.Ready
        }
    })
}

function Get-InventoryFingerprint {
    $data = @($script:Inventory.Values | ForEach-Object {
        [ordered]@{ key=$_.Key; installed=$_.RawInstalled; latest=$_.RawLatest; ready=[bool]$_.Ready }
    }) | ConvertTo-Json -Compress -Depth 4
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($data))).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Get-OutcomeStatus($Results) {
    $states = @($Results | ForEach-Object { $_.sonuc })
    if ($states -contains 'Hata') { return 'error' }
    if ($states -contains 'Uyarı') { return 'warning' }
    return 'completed'
}

function Invoke-SelectedUpdates([string[]]$SelectedKeys) {
    $results = New-Object System.Collections.ArrayList
    $rows = @(Get-ChatRows)
    $step = 0
    foreach ($row in $rows) {
        $row.secili = $row.key -in $SelectedKeys
        if ($row.key -notin $SelectedKeys) {
            if ($row.secilebilir) { $row.durum = 'Atlandı · seçilmedi' }
            continue
        }
        $step++
        try {
            $result = Install-Selected $row.key
            $newVersion = if ($row.key -eq 'offer') { Value-Of $result 'version' } else { Value-Of $result 'surum' }
            $state = Result-State $result
            if ($row.key -eq 'libraries') {
                $after = Get-Libraries $script:Python
                $items = @($after.PSObject.Properties)
                $matched = @($items | Where-Object { $_.Value.installed -eq $_.Value.target }).Count
                $newVersion = "$matched/$($items.Count) hedefte"
                if ($matched -ne $items.Count -and $state -eq 'Tamamlandı') { $state = 'Uyarı' }
            }
            if ($state -eq 'Tamamlandı' -and -not $newVersion) { throw 'Kurulum sonrası sürüm doğrulanamadı.' }
            $targetMissed = $row.key -ne 'libraries' -and $state -eq 'Tamamlandı' -and
                -not (Version-Compare $newVersion $script:Inventory[$row.key].RawLatest)
            if ($targetMissed) { $state = 'Uyarı' }
            if ($newVersion) { $row.yuklu = [string]$newVersion }
            $details = @()
            foreach ($name in @('neden','warning','it_isi')) {
                $value = Value-Of $result $name
                if ($value) { $details += [string]$value }
            }
            if ($targetMissed) { $details += 'Seçilen hedef sürüme ulaşılamadı.' }
            $report = Value-Of $result 'rapor'
            if ($report) { $details += 'Rapor: ' + [string]$report }
            $detail = $details -join ' · '
            if ($state -eq 'Hata' -and -not $detail) { $detail = 'Başarılı kurulum doğrulanamadı.' }
            $row.durum = "$step. $state $detail".Trim()
            [void]$results.Add([pscustomobject]@{sira=$step; ad=$row.ad; sonuc=$state; ayrinti=$detail})
        } catch {
            $row.durum = "$step. Hata · $($_.Exception.Message)"
            [void]$results.Add([pscustomobject]@{sira=$step; ad=$row.ad; sonuc='Hata'; ayrinti=$_.Exception.Message})
        }
    }
    return [pscustomobject]@{status=(Get-OutcomeStatus $results); results=@($results.ToArray()); rows=$rows}
}

function Invoke-ChatAction {
    Scan-Inventory
    $rows = @(Get-ChatRows)
    if ($Action -eq 'scan') {
        if (Test-InventoryCurrent) { return [pscustomobject]@{status='up_to_date'; message='Güncelsiniz.'; rows=$rows} }
        return [pscustomobject]@{status='selection_required'; fingerprint=(Get-InventoryFingerprint); rows=$rows}
    }
    if (-not $Fingerprint -or $Fingerprint -notmatch '^[a-f0-9]{64}$') { throw 'Tarama parmak izi gerekli.' }
    $current = Get-InventoryFingerprint
    if ($Fingerprint -cne $current) {
        return [pscustomobject]@{status='stale'; message='Sürümler değişti; seçim yeniden gösterilmeli.'; fingerprint=$current; rows=$rows}
    }
    $selected = @($Keys.Split(',') | ForEach-Object { $_.Trim().ToLowerInvariant() } | Where-Object { $_ } | Select-Object -Unique)
    if (-not $selected.Count) { return [pscustomobject]@{status='cancelled'; results=@(); rows=$rows} }
    $valid = @($script:Inventory.Values | Where-Object { $_.Ready } | ForEach-Object { $_.Key })
    foreach ($key in $selected) {
        if ($key -notin $valid) { throw "Seçilemeyen veya bilinmeyen satır: $key" }
    }
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $mutex = New-Object Threading.Mutex($false, ('Local\guncelleyici-update-' + $sid))
    $ownsMutex = $false
    try {
        try { $ownsMutex = $mutex.WaitOne(0) }
        catch [Threading.AbandonedMutexException] { $ownsMutex = $true }
        if (-not $ownsMutex) { return [pscustomobject]@{status='busy'; message='Başka bir Güncelleyici işlemi sürüyor.'; rows=$rows} }
        $null = Remove-LegacySkill
        return Invoke-SelectedUpdates $selected
    } finally {
        if ($ownsMutex) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

if ($LibraryOnly) { return }
try {
    $outcome = Invoke-ChatAction
    if ($outcome.status -eq 'up_to_date') { 'Güncelsiniz.' }
    '@@SONUC ' + ($outcome | ConvertTo-Json -Compress -Depth 8)
} catch {
    '@@SONUC ' + ([pscustomobject]@{status='error'; message=$_.Exception.Message} | ConvertTo-Json -Compress -Depth 4)
    exit 1
}
