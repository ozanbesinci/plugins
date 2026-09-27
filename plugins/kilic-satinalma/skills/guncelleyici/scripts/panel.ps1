param([switch]$TestMode, [switch]$LayoutTest)

# Windows PowerShell 5.1 is sufficient; Python is installed only when selected.
Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
# Use this PowerShell runtime's modules even when launched from another shell.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
$script:UiActive = $false
$script:Busy = $false
$script:SelectionAccepted = $false
try { [Console]::OutputEncoding = New-Object Text.UTF8Encoding $false } catch {}
$script:Skill = Split-Path $PSScriptRoot -Parent
$skillItem = Get-Item -LiteralPath $script:Skill -Force
if ($skillItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    $linkTarget = $skillItem.PSObject.Properties['Target']
    if ($linkTarget -and $linkTarget.Value) {
        $script:Skill = [IO.Path]::GetFullPath([string]@($linkTarget.Value)[0])
    }
}
$script:SkillsRoot = Split-Path $script:Skill -Parent
$script:Python = $null
$script:Node = $null
$script:Inventory = [ordered]@{}
$script:Results = New-Object System.Collections.ArrayList

function Quote-NativeArgument([string]$Argument) {
    # Windows CommandLineToArgvW escaping, including trailing backslashes.
    $escaped = [regex]::Replace($Argument, '(\\*)"', '$1$1\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '$1$1')
    return '"' + $escaped + '"'
}

function Invoke-Native([string]$Exe, [string[]]$Arguments, [int]$TimeoutSeconds = 0) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $Exe
    $info.Arguments = (@($Arguments | ForEach-Object { Quote-NativeArgument $_ }) -join ' ')
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = New-Object Text.UTF8Encoding $false
    $info.StandardErrorEncoding = New-Object Text.UTF8Encoding $false
    $info.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
    $process = [Diagnostics.Process]::Start($info)
    try {
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $clock = [Diagnostics.Stopwatch]::StartNew()
        while (-not $process.WaitForExit(100)) {
            if ($script:UiActive) { [Windows.Forms.Application]::DoEvents() }
            if ($TimeoutSeconds -gt 0 -and $clock.Elapsed.TotalSeconds -gt $TimeoutSeconds) {
                $process.Kill()
                throw "İşlem zaman aşımına uğradı: $Exe"
            }
        }
        return [pscustomobject]@{ ExitCode=$process.ExitCode; Output=$stdout.Result; Error=$stderr.Result }
    } finally { $process.Dispose() }
}

function Invoke-JsonTool([string]$Exe, [string[]]$Arguments, [string]$Prefix = '@@SONUC ') {
    $run = Invoke-Native $Exe $Arguments
    if ($run.ExitCode -ne 0) { throw "İşlem başarısız (çıkış kodu $($run.ExitCode)): $Exe`n$($run.Error)`n$($run.Output)" }
    $output = @($run.Output -split '\r?\n')
    if (-not $Prefix) {
        $line = @($output | Where-Object { $_.Trim() } | Select-Object -Last 1)
    } else {
        $line = @($output | Where-Object { $_.StartsWith($Prefix) } | Select-Object -Last 1)
        if ($line.Count) { $line[0] = $line[0].Substring($Prefix.Length) }
    }
    if (-not $line.Count) { throw "Sonuç kaydı bulunamadı: $Exe $($Arguments -join ' ')" }
    try {
        $result = $line[0] | ConvertFrom-Json
        if ($null -eq $result -or $result -isnot [pscustomobject]) { throw 'Sonuç nesne değil.' }
        return $result
    }
    catch { throw "Sonuç kaydı okunamadı: $Exe" }
}

function Invoke-Tool([string]$Exe, [string[]]$Arguments) { return Invoke-JsonTool $Exe $Arguments }

function Invoke-PS([string]$Name, [string[]]$Extra) {
    $path = Join-Path (Join-Path $script:Skill 'scripts') $Name
    return Invoke-Tool 'powershell.exe' (@('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $path) + $Extra)
}

function Find-Python {
    if ($script:Python -and (Test-Path -LiteralPath $script:Python)) { return $script:Python }
    foreach ($command in @('py.exe', 'python.exe')) {
        $found = Get-Command $command -ErrorAction SilentlyContinue
        if (-not $found) { continue }
        try {
            $args = if ($command -eq 'py.exe') { @('-3', '-c', 'import sys;print(sys.executable)') } else { @('-c', 'import sys;print(sys.executable)') }
            $run = Invoke-Native $found.Source $args 30
            if ($run.ExitCode -ne 0) { continue }
            $path = $run.Output.Trim()
            if ($path -and (Test-Path -LiteralPath $path)) { return [string]$path }
        } catch { }
    }
    return $null
}

function Version-Compare([string]$Installed, [string]$Latest) {
    if (-not $Installed -or -not $Latest) { return $false }
    try { return [version]$Installed -ge [version]$Latest } catch { return $false }
}

function New-Entry([string]$Key, [string]$Name, $Installed, $Latest, [string]$Note) {
    $installedText = if ($Installed) { [string]$Installed } else { 'Yüklü değil' }
    $latestText = if ($Latest) { [string]$Latest } else { 'Kontrol edilemedi' }
    $ready = [bool]$Latest -and -not (Version-Compare $Installed $Latest)
    return [pscustomobject]@{ Key=$Key; Name=$Name; Installed=$installedText; Latest=$latestText;
        Note=$Note; Ready=$ready; RawInstalled=$Installed; RawLatest=$Latest }
}

function Check-FailureText([string]$Note) {
    if ($Note -match 'Erişim izinlerince|access permissions|SocketException.*10013') {
        return 'Kontrol edilemedi · ağ erişimi engellendi'
    }
    return 'Kontrol edilemedi · ayrıntı için satırın üzerine gelin'
}

function New-FailedEntry([string]$Key, [string]$Name, [string]$Note) {
    $entry = New-Entry $Key $Name $null $null $Note
    $entry.Installed = 'Tespit edilemedi'
    return $entry
}

function Value-Of($Object, [string]$Name) {
    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Collections.IDictionary]) { return $Object[$Name] }
    $property = $Object.PSObject.Properties[$Name]
    if ($property) { return $property.Value }
    return $null
}

function Remove-LegacySkill {
    $notes = New-Object System.Collections.ArrayList
    foreach ($base in @((Join-Path $env:USERPROFILE '.codex\skills'),
                       (Join-Path $env:USERPROFILE '.claude\skills'),
                       (Join-Path $env:USERPROFILE '.agents\skills'))) {
        foreach ($name in @('program-guncelle', 'program-guncelleme')) {
            $candidate = Join-Path $base $name
            $parent = Split-Path $candidate -Parent
            if (-not [IO.Directory]::Exists($base) -or
                [IO.Path]::GetFullPath($parent).TrimEnd('\') -ne [IO.Path]::GetFullPath($base).TrimEnd('\') -or
                -not (Test-Path -LiteralPath $candidate)) { continue }
            try {
                $item = Get-Item -LiteralPath $candidate -Force
                if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                    [IO.Directory]::Delete($candidate)
                    [void]$notes.Add("$candidate bağlantısı kaldırıldı")
                    continue
                }
                $definition = Join-Path $candidate 'SKILL.md'
                if (-not (Test-Path -LiteralPath $definition) -or
                    -not (Select-String -LiteralPath $definition -Pattern '^name:\s*program-guncelle(me)?\s*$' -Quiet)) {
                    [void]$notes.Add("$candidate kimliği doğrulanamadı; dokunulmadı")
                    continue
                }
                $quarantine = Join-Path $env:LOCALAPPDATA 'guncelleyici\kaldirilan-eski-skill'
                New-Item -ItemType Directory -Path $quarantine -Force | Out-Null
                $target = Join-Path $quarantine ("$name-" + [guid]::NewGuid().ToString('N'))
                $allowedTarget = [IO.Path]::GetFullPath($quarantine).TrimEnd('\') + '\'
                if (-not [IO.Path]::GetFullPath($target).StartsWith($allowedTarget,[StringComparison]::OrdinalIgnoreCase)) {
                    throw 'Karantina hedefi doğrulanamadı.'
                }
                Move-Item -LiteralPath $candidate -Destination $target
                [void]$notes.Add("$candidate kaldırıldı")
            } catch { [void]$notes.Add("$candidate kaldırılamadı: $($_.Exception.Message)") }
        }
    }
    return @($notes)
}

function Read-OfferRelease([string]$Uri) {
    $headers = @{ 'User-Agent'='guncelleyici'; 'Accept'='application/vnd.github+json' }
    try { return Invoke-RestMethod -Uri $Uri -Headers $headers -TimeoutSec 30 }
    catch {
        Start-Sleep -Milliseconds 800
        return Invoke-RestMethod -Uri $Uri -Headers $headers -TimeoutSec 30
    }
}

function Download-OfferAsset([string]$Uri, [string]$OutputFile, [int]$Timeout) {
    try { Invoke-WebRequest -Uri $Uri -OutFile $OutputFile -TimeoutSec $Timeout -UseBasicParsing | Out-Null }
    catch {
        Start-Sleep -Milliseconds 800
        Invoke-WebRequest -Uri $Uri -OutFile $OutputFile -TimeoutSec $Timeout -UseBasicParsing | Out-Null
    }
}

function Get-FileSha256([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}

function Get-OfferLatest {
    $uri = 'https://api.github.com/repos/ozanbesinci/teklif-degerlendirme/releases/latest'
    $release = Read-OfferRelease $uri
    if ($release.draft -or $release.prerelease -or $release.tag_name -notmatch '^v\d+\.\d+\.\d+$') { throw 'Kararlı sürüm doğrulanamadı.' }
    $file = 'teklif-degerlendirme-' + $release.tag_name + '.zip'
    $base = 'https://github.com/ozanbesinci/teklif-degerlendirme/releases/download/' + $release.tag_name + '/'
    foreach ($required in @($file, "$file.sha256")) {
        if (@($release.assets | Where-Object { $_.name -eq $required -and $_.browser_download_url -eq "$base$required" }).Count -ne 1) { throw 'Yayın dosyaları doğrulanamadı.' }
    }
    $temp = Join-Path ([IO.Path]::GetTempPath()) ('guncelleyici-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $temp | Out-Null
    try {
        $archive = Join-Path $temp $file
        $shaFile = "$archive.sha256"
        Download-OfferAsset "$base$file" $archive 40
        Download-OfferAsset "$base$file.sha256" $shaFile 30
        if ((Get-Item -LiteralPath $archive).Length -gt 32MB) { throw 'Paket boyutu sınırı aşıldı.' }
        $record = (Get-Content -LiteralPath $shaFile -Raw).Trim()
        $checksum = [regex]::Match($record, '^([a-fA-F0-9]{64})\s+\*?(.+)$')
        if (-not $checksum.Success -or $checksum.Groups[2].Value -ne $file -or
            (Get-FileSha256 $archive) -ne $checksum.Groups[1].Value) { throw 'Paket SHA-256 doğrulaması başarısız.' }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [IO.Compression.ZipFile]::OpenRead($archive)
        try {
            $manifests = @($zip.Entries | Where-Object { $_.FullName -eq 'release-manifest.json' })
            if ($manifests.Count -ne 1) { throw 'Tek bir sürüm manifesti bulunmalıdır.' }
            $manifestEntry = $manifests[0]
            if ($manifestEntry.Length -gt 1MB) { throw 'Sürüm manifesti boyut sınırı aşıldı.' }
            $reader = New-Object IO.StreamReader($manifestEntry.Open(), [Text.Encoding]::UTF8)
            try { $manifest = $reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
            if ((Value-Of $manifest 'repository') -ne 'ozanbesinci/teklif-degerlendirme' -or
                (Value-Of $manifest 'schema') -notin @(1,2,3)) { throw 'Manifest kaynağı veya şeması geçersiz.' }
            if ((Value-Of $manifest 'version') -ne $release.tag_name.Substring(1)) { throw 'Yayın ve manifest sürümü farklı.' }
            $versions = Value-Of $manifest 'skill_versions'
            if ($manifest.schema -in @(2,3)) {
                if ((Value-Of $manifest 'versioning') -ne 'independent/v1' -or -not (Value-Of $versions 'teklif-degerlendirme')) {
                    throw 'Bileşen sürüm kaydı eksik veya geçersiz.'
                }
                $componentVersion = [string](Value-Of $versions 'teklif-degerlendirme')
                if ($componentVersion -notmatch '^\d+\.\d+\.\d+$') { throw 'Bileşen sürümü geçersiz.' }
                return $componentVersion
            }
            return [string]$manifest.version
        } finally { $zip.Dispose() }
    } finally {
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
        $checked = [IO.Path]::GetFullPath($temp)
        if ($checked.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase) -and
            (Split-Path $checked -Leaf) -match '^guncelleyici-[a-f0-9]{32}$') {
            Remove-Item -LiteralPath $checked -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-Libraries($Python) {
    $code = @'
import importlib.metadata as m
import importlib.util as u
import json
import sys
sys.dont_write_bytecode = True
s = u.spec_from_file_location('kt', sys.argv[1])
k = u.module_from_spec(s)
s.loader.exec_module(k)
out = {}
for name, target, _ in k.PAKETLER:
    try:
        installed = m.version(name)
    except m.PackageNotFoundError:
        installed = None
    out[name] = {'installed': installed, 'target': target}
print(json.dumps(out))
'@
    return Invoke-JsonTool $Python @('-c', $code, (Join-Path $PSScriptRoot 'kurulum-testi.py')) ''
}

function Get-RegistryLatest([string]$Uri) {
    $record = Invoke-RestMethod -Uri $Uri -TimeoutSec 25
    $latest = if ($Uri -like '*pypi.org*') { $record.info.version } else { $record.version }
    if ($latest -notmatch '^\d+\.\d+(\.\d+)?$') { throw 'Kararlı sürüm doğrulanamadı.' }
    return [string]$latest
}

function Scan-Inventory {
    $script:Inventory.Clear()
    $script:Python = $null
    $script:Node = $null
    try {
        $pythonResult = Invoke-PS 'python-kur.ps1' @('-YalnizBul')
        $script:Python = $pythonResult.python
        $latestPython = if ($pythonResult.hedef_kaynagi -eq 'python.org') { $pythonResult.hedef_surum } else { $null }
        $script:Inventory['python'] = New-Entry 'python' 'Python' $pythonResult.surum $latestPython $pythonResult.hedef_kaynagi
    } catch {
        $script:Python = Find-Python
        $script:Inventory['python'] = New-FailedEntry 'python' 'Python' $_.Exception.Message
    }
    if ($script:Python) {
        try {
            $lib = Get-Libraries $script:Python
            $packages = @($lib.PSObject.Properties)
            $have = @($packages | Where-Object { $_.Value.installed -eq $_.Value.target }).Count
            $installedCount = @($packages | Where-Object { $_.Value.installed }).Count
            $details = @($packages | ForEach-Object { "$($_.Name): $($_.Value.installed) → $($_.Value.target)" }) -join '; '
            $installedSet = if ($installedCount) { "$have/12 hedefte" } else { $null }
            $entry = New-Entry 'libraries' 'Python kütüphaneleri (12)' $installedSet '12 paket · sabit set' ('Doğrulanmış paket seti; internetin son sürümleri değildir. ' + $details)
            $entry.Ready = $have -lt $packages.Count
            $script:Inventory['libraries'] = $entry
        } catch { $script:Inventory['libraries'] = New-FailedEntry 'libraries' 'Python kütüphaneleri (12)' $_.Exception.Message }
    } else { $script:Inventory['libraries'] = New-Entry 'libraries' 'Python kütüphaneleri (12)' $null '12/12' 'Önce Python seçilmelidir' }
    try {
        $nodeResult = Invoke-PS 'node-kur.ps1' @('-YalnizBul')
        $script:Node = $nodeResult.node
        $latestNode = if ($nodeResult.hedef_kaynagi -eq 'nodejs.org') { $nodeResult.hedef_surum } else { $null }
        $script:Inventory['node'] = New-Entry 'node' 'Node.js LTS' $nodeResult.surum $latestNode $nodeResult.hedef_kaynagi
    } catch { $script:Inventory['node'] = New-FailedEntry 'node' 'Node.js LTS' $_.Exception.Message }
    $pnpmArgs = @('-YalnizBul'); if ($script:Node) { $pnpmArgs += @('-NodeYolu', $script:Node) }
    try {
        $pnpmResult = Invoke-PS 'pnpm-kur.ps1' $pnpmArgs
        $pnpmLatest = $pnpmResult.hedef_surum
        $pnpmNote = if ($pnpmLatest) { 'npm latest / kararlı' } else { [string](Value-Of $pnpmResult 'neden') }
        if (-not $pnpmLatest -and -not $script:Node) {
            try { $pnpmLatest = Get-RegistryLatest 'https://registry.npmjs.org/pnpm/latest'; $pnpmNote = 'npm latest / kararlı; önce Node.js seçilmelidir' }
            catch { $pnpmNote = $_.Exception.Message }
        }
        $script:Inventory['pnpm'] = New-Entry 'pnpm' 'pnpm' $pnpmResult.surum $pnpmLatest $pnpmNote
    } catch { $script:Inventory['pnpm'] = New-FailedEntry 'pnpm' 'pnpm' $_.Exception.Message }
    if ($script:Python) {
        try {
            $duck = Invoke-Tool $script:Python @((Join-Path $PSScriptRoot 'python-paket-kur.py'), 'duckdb', '--yalniz-bul')
            $duckNote = if ($duck.hedef_surum) { 'PyPI / bu Python ile uyumlu' } else { [string](Value-Of $duck 'neden') }
            $script:Inventory['duckdb'] = New-Entry 'duckdb' 'DuckDB' $duck.surum $duck.hedef_surum $duckNote
        } catch { $script:Inventory['duckdb'] = New-FailedEntry 'duckdb' 'DuckDB' $_.Exception.Message }
    } else {
        try { $duckLatest = Get-RegistryLatest 'https://pypi.org/pypi/duckdb/json' }
        catch { $duckLatest = $null }
        $script:Inventory['duckdb'] = New-Entry 'duckdb' 'DuckDB' $null $duckLatest 'PyPI / uyumluluk kurulumda doğrulanır; Python gerekli'
    }
    try {
        $power = Invoke-PS 'powerbi-mcp-kur.ps1' @('-YalnizBul')
        $powerNote = if ($power.hedef_surum) { 'Microsoft Marketplace / kararlı' } else { [string](Value-Of $power 'neden') }
        $script:Inventory['powerbi'] = New-Entry 'powerbi' 'Power BI Modeling MCP' $power.surum $power.hedef_surum $powerNote
    } catch { $script:Inventory['powerbi'] = New-FailedEntry 'powerbi' 'Power BI Modeling MCP' $_.Exception.Message }
    $localOffer = Join-Path (Join-Path $script:SkillsRoot 'teklif-degerlendirme') 'VERSION'
    try {
        $installedOffer = if (Test-Path -LiteralPath $localOffer) { (Get-Content -LiteralPath $localOffer -Raw).Trim() } else { $null }
        if ($installedOffer -and $installedOffer -notmatch '^\d+\.\d+\.\d+$') { throw 'Yerel teklif VERSION kaydı geçersiz.' }
    } catch {
        $script:Inventory['offer'] = New-FailedEntry 'offer' 'teklif-degerlendirme skill' $_.Exception.Message
        return
    }
    try { $latestOffer = Get-OfferLatest; $offerNote = 'GitHub kararlı yayın / doğrulanmış paket' }
    catch { $latestOffer = $null; $offerNote = $_.Exception.Message }
    $script:Inventory['offer'] = New-Entry 'offer' 'teklif-degerlendirme skill' $installedOffer $latestOffer $offerNote
}

function Install-Selected([string]$Key) {
    switch ($Key) {
        'python' {
            $result = Invoke-PS 'python-kur.ps1' @()
            if ($result.python) { $script:Python = $result.python }
            return $result
        }
        'libraries' {
            if (-not $script:Python) { throw 'Python kurulu değil; Python satırını da seçin.' }
            return Invoke-Tool $script:Python @((Join-Path $PSScriptRoot 'kurulum-testi.py'))
        }
        'node' {
            $result = Invoke-PS 'node-kur.ps1' @()
            if ($result.node) { $script:Node = $result.node }
            return $result
        }
        'pnpm' {
            if (-not $script:Node) { throw 'Node.js kurulu değil; Node.js satırını da seçin.' }
            return Invoke-PS 'pnpm-kur.ps1' @('-NodeYolu', $script:Node)
        }
        'duckdb' {
            if (-not $script:Python) { throw 'Python kurulu değil; Python satırını da seçin.' }
            return Invoke-Tool $script:Python @((Join-Path $PSScriptRoot 'python-paket-kur.py'), 'duckdb')
        }
        'powerbi' { return Invoke-PS 'powerbi-mcp-kur.ps1' @() }
        'offer' {
            $python = Find-Python
            if (-not $python) { throw 'Teklif skill güncellemesi için Python gerekli; Python satırını da seçin.' }
            $result = Invoke-JsonTool $python @((Join-Path $PSScriptRoot 'teklif-guncelle.py'), 'update', '--root', $script:SkillsRoot) ''
            if ($result.status -eq 'error') { throw $result.error }
            if ($result.status -notin @('installed','up_to_date')) { throw 'Teklif için doğrulanmış kararlı yayın bulunamadı.' }
            $verify = Invoke-JsonTool $python @((Join-Path $PSScriptRoot 'teklif-guncelle.py'), 'verify', '--root', $script:SkillsRoot) ''
            if ($verify.status -ne 'verified' -or -not $verify.version) { throw 'Teklif skill doğrulaması başarısız.' }
            $result | Add-Member -NotePropertyName version -NotePropertyValue $verify.version -Force
            return $result
        }
    }
    throw "Bilinmeyen satır: $Key"
}

function Result-State($Result) {
    $summary = Value-Of $Result 'ozet'
    $values = @(if ($summary -is [string]) { @($summary) }
              elseif ($summary -is [Collections.IDictionary]) { @($summary.Values) }
              elseif ($summary) { @($summary.PSObject.Properties | ForEach-Object { $_.Value }) }
              else { @() })
    $state = Value-Of $Result 'durum'
    $offerStatus = Value-Of $Result 'status'
    if ($offerStatus -eq 'error' -or $state -in @('BASARISIZ','YOK') -or $values -contains 'ENGEL') { return 'Hata' }
    if ($values -contains 'UYARI' -or $state -in @('ESKI','ESKI_SURUM','ESKI_YAMA','KONTROL_EDILEMEDI') -or
        (Value-Of $Result 'it_isi') -or (Value-Of $Result 'warning')) { return 'Uyarı' }
    if ($offerStatus -in @('installed','up_to_date') -or $state -in @('MEVCUT','KURULDU','GUNCELLENDI') -or
        ($values -contains 'GEÇTİ' -and @($values | Where-Object { $_ -notin @('GEÇTİ','BİLGİ') }).Count -eq 0)) { return 'Tamamlandı' }
    return 'Hata'
}

function Test-InventoryCurrent {
    $keys = @('python','libraries','node','pnpm','duckdb','powerbi','offer')
    if ($script:Inventory.Count -ne $keys.Count) { return $false }
    foreach ($key in $keys) {
        if (-not $script:Inventory.Contains($key)) { return $false }
        $entry = $script:Inventory[$key]
        if ($entry.Ready -or -not $entry.RawInstalled -or -not $entry.RawLatest) { return $false }
    }
    return $true
}

function Get-PanelOutcome {
    $rows = @($grid.Rows | ForEach-Object {
        [pscustomobject]@{ad=$_.Cells['Ad'].Value; yuklu=$_.Cells['Yuklu'].Value;
            guncel=$_.Cells['Guncel'].Value; durum=$_.Cells['Durum'].Value}
    })
    $states = @($script:Results | ForEach-Object { $_.sonuc })
    $status = if (-not $script:SelectionAccepted) { 'cancelled' }
              elseif ($states -contains 'Hata') { 'error' }
              elseif ($states -contains 'Uyarı') { 'warning' }
              else { 'completed' }
    return [pscustomobject]@{status=$status; results=@($script:Results.ToArray()); rows=$rows}
}

if ($TestMode) { 'PANEL_TEST_MODE_OK'; return }

# Complete discovery before creating any window: a current machine needs no table.
if (-not $LayoutTest) {
    $null = Remove-LegacySkill
    Scan-Inventory
    if (Test-InventoryCurrent) {
        'Güncelsiniz.'
        '@@SONUC {"status":"up_to_date","message":"Güncelsiniz."}'
        return
    }
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$form = New-Object Windows.Forms.Form
$form.Text = 'Güncelleyici'
$form.Size = New-Object Drawing.Size(1110, 720)
$form.MinimumSize = New-Object Drawing.Size(860, 600)
$form.StartPosition = 'CenterScreen'
$form.BackColor = [Drawing.Color]::FromArgb(244,247,251)
$form.Font = New-Object Drawing.Font('Segoe UI', 10)

$heading = New-Object Windows.Forms.Label
$heading.Text = 'GÜNCELLEYİCİ'
$heading.Font = New-Object Drawing.Font('Segoe UI Semibold', 22)
$heading.ForeColor = [Drawing.Color]::FromArgb(21,40,68)
$heading.SetBounds(28,20,820,48)
$form.Controls.Add($heading)
$subtitle = New-Object Windows.Forms.Label
$subtitle.Text = 'Yükleme ve güncelleme gerekenler seçili · Seçimleri değiştirebilirsiniz'
$subtitle.ForeColor = [Drawing.Color]::FromArgb(84,101,124)
$subtitle.SetBounds(30,74,1020,26)
$form.Controls.Add($subtitle)

$grid = New-Object Windows.Forms.DataGridView
$grid.SetBounds(28,116,1035,455)
$grid.Anchor = 'Top,Bottom,Left,Right'
$grid.BackgroundColor = [Drawing.Color]::White
$grid.BorderStyle = 'None'
$grid.RowHeadersVisible = $false
$grid.AllowUserToAddRows = $false
$grid.AllowUserToDeleteRows = $false
$grid.AllowUserToResizeRows = $false
$grid.SelectionMode = 'FullRowSelect'
$grid.MultiSelect = $false
$grid.RowTemplate.Height = 47
$grid.EnableHeadersVisualStyles = $false
$grid.ColumnHeadersHeight = 43
$grid.ColumnHeadersDefaultCellStyle.BackColor = [Drawing.Color]::FromArgb(21,40,68)
$grid.ColumnHeadersDefaultCellStyle.ForeColor = [Drawing.Color]::White
$grid.ColumnHeadersDefaultCellStyle.Font = New-Object Drawing.Font('Segoe UI Semibold', 10)
$grid.DefaultCellStyle.BackColor = [Drawing.Color]::White
$grid.AlternatingRowsDefaultCellStyle.BackColor = [Drawing.Color]::FromArgb(248,250,253)
$grid.DefaultCellStyle.SelectionBackColor = [Drawing.Color]::FromArgb(218,240,238)
$grid.DefaultCellStyle.SelectionForeColor = [Drawing.Color]::FromArgb(21,40,68)
$choice = New-Object Windows.Forms.DataGridViewCheckBoxColumn
$choice.Name='Sec'; $choice.HeaderText='Seç'; $choice.Width=70
[void]$grid.Columns.Add($choice)
foreach ($spec in @(@('Ad','Skill / program',270),@('Yuklu','Yüklü sürüm',145),@('Guncel','Güncel sürüm',145),@('Durum','Durum',370))) {
    $col = New-Object Windows.Forms.DataGridViewTextBoxColumn
    $col.Name=$spec[0]; $col.HeaderText=$spec[1]; $col.Width=[int]$spec[2]; $col.ReadOnly=$true
    $col.SortMode = 'NotSortable'
    [void]$grid.Columns.Add($col)
}
$grid.Columns['Durum'].AutoSizeMode = 'Fill'
$form.Controls.Add($grid)

$button = New-Object Windows.Forms.Button
$button.Text = 'Güncelle'
$button.BackColor = [Drawing.Color]::FromArgb(8,128,122)
$button.ForeColor = [Drawing.Color]::White
$button.FlatStyle = 'Flat'
$button.FlatAppearance.BorderSize = 0
$button.Font = New-Object Drawing.Font('Segoe UI Semibold', 12)
$button.SetBounds(825,595,238,56)
$button.Anchor = 'Bottom,Right'
$button.Enabled = $false
$form.Controls.Add($button)
$footer = New-Object Windows.Forms.Label
$footer.Text = 'Güncelle tıklanınca pencere kapanır; seçili işlemler devam eder.'
$footer.ForeColor = [Drawing.Color]::FromArgb(84,101,124)
$footer.SetBounds(28,606,780,38)
$footer.Anchor = 'Bottom,Left,Right'
$form.Controls.Add($footer)

$grid.Add_CurrentCellDirtyStateChanged({
    if ($grid.IsCurrentCellDirty) { [void]$grid.CommitEdit([Windows.Forms.DataGridViewDataErrorContexts]::Commit) }
})
$grid.Add_CellValueChanged({
    if (-not $script:Busy) {
        $button.Enabled = @($grid.Rows | Where-Object {
            $_.Tag -and $_.Cells['Sec'].Value -eq $true -and $script:Inventory[$_.Tag].Ready
        }).Count -gt 0
    }
})

function Render-Inventory {
    $grid.Rows.Clear()
    foreach ($entry in $script:Inventory.Values) {
        $index = $grid.Rows.Add([bool]$entry.Ready, $entry.Name, $entry.Installed, $entry.Latest,
            $(if ($entry.Ready -and -not $entry.RawInstalled) { 'Güncel sürüm yüklenecek' }
              elseif ($entry.Ready) { 'Güncelleme seçilebilir' }
              elseif ($entry.Key -eq 'libraries' -and $entry.RawLatest) { 'Doğrulanmış set hazır' }
              elseif ($entry.RawLatest -and (Version-Compare $entry.RawInstalled $entry.RawLatest)) {
                  if ([version]$entry.RawInstalled -gt [version]$entry.RawLatest) { 'Yüklü sürüm yayından yeni' } else { 'Güncel' }
              }
              elseif (-not $entry.RawLatest) { Check-FailureText $entry.Note }
              else { $entry.Note }))
        $grid.Rows[$index].Tag = $entry.Key
        foreach ($cell in $grid.Rows[$index].Cells) { $cell.ToolTipText = $entry.Note }
        $grid.Rows[$index].Cells['Sec'].ReadOnly = -not $entry.Ready
        if (-not $entry.Ready) { $grid.Rows[$index].Cells['Sec'].Style.BackColor = [Drawing.Color]::FromArgb(238,241,245) }
    }
    $button.Enabled = @($script:Inventory.Values | Where-Object { $_.Ready }).Count -gt 0
}

$form.Add_FormClosing({
    param($sender, $eventArgs)
    if ($script:Busy) {
        $eventArgs.Cancel = $true
        $footer.Text = 'İşlem sürüyor; tamamlandıktan sonra pencereyi kapatabilirsiniz.'
    }
})

function Run-SelectedUpdates {
    if ($script:Busy) { return }
    [void]$grid.EndEdit()
    $selected = @($grid.Rows | Where-Object { $_.Cells['Sec'].Value -eq $true -and $script:Inventory[$_.Tag].Ready })
    if (-not $selected.Count) { return }
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $mutex = New-Object Threading.Mutex($false, ('Local\guncelleyici-update-' + $sid))
    try { $ownsMutex = $mutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $ownsMutex = $true }
    if (-not $ownsMutex) {
        $mutex.Dispose()
        $footer.Text = 'Başka bir Güncelleyici penceresinde işlem sürüyor; tamamlanmasını bekleyin.'
        return
    }
    $script:Busy = $true
    $script:SelectionAccepted = $true
    $form.Hide()
    $button.Enabled = $false
    $grid.Enabled = $false
    $grid.Columns['Sec'].Visible = $false
    $script:Results.Clear()
    $step = 0
    try {
    foreach ($row in $grid.Rows) {
        if ($row -notin $selected) {
            if ($script:Inventory[$row.Tag].RawLatest -and $script:Inventory[$row.Tag].Ready) { $row.Cells['Durum'].Value = 'Atlandı · seçilmedi' }
            continue
        }
        $step++
        $row.Cells['Durum'].Value = "$step/$($selected.Count) · İşleniyor…"
        $subtitle.Text = "$step/$($selected.Count) · $($row.Cells['Ad'].Value)"
        [Windows.Forms.Application]::DoEvents()
        try {
            $result = Install-Selected $row.Tag
            $newVersion = if ($row.Tag -eq 'offer') { Value-Of $result 'version' } else { Value-Of $result 'surum' }
            $status = Result-State $result
            if ($row.Tag -eq 'libraries') {
                $after = Get-Libraries $script:Python
                $items = @($after.PSObject.Properties)
                $matched = @($items | Where-Object { $_.Value.installed -eq $_.Value.target }).Count
                $newVersion = "$matched/$($items.Count) hedefte"
                if ($matched -ne $items.Count -and $status -eq 'Tamamlandı') { $status = 'Uyarı' }
            }
            if ($status -eq 'Tamamlandı' -and -not $newVersion) { throw 'Kurulum sonrası sürüm doğrulanamadı.' }
            $targetMissed = $row.Tag -ne 'libraries' -and $status -eq 'Tamamlandı' -and
                -not (Version-Compare $newVersion $script:Inventory[$row.Tag].RawLatest)
            if ($targetMissed) { $status = 'Uyarı' }
            if ($newVersion) { $row.Cells['Yuklu'].Value = [string]$newVersion }
            $details = @('neden','warning','it_isi' | ForEach-Object { Value-Of $result $_ } | Where-Object { $_ })
            if ($targetMissed) { $details += 'Seçilen hedef sürüme ulaşılamadı.' }
            if (Value-Of $result 'rapor') { $details += 'Rapor: ' + [string](Value-Of $result 'rapor') }
            $detail = $details -join ' · '
            if ($status -eq 'Hata' -and -not $detail) { $detail = 'Başarılı kurulum doğrulanamadı.' }
            $row.Cells['Durum'].Value = "$step. $status $detail".Trim()
            $row.Cells['Durum'].ToolTipText = $row.Cells['Durum'].Value
            [void]$script:Results.Add([pscustomobject]@{sira=$step; ad=$row.Cells['Ad'].Value; sonuc=$status; ayrinti=$detail})
        } catch {
            $row.Cells['Durum'].Value = "$step. Hata · $($_.Exception.Message)"
            $row.Cells['Durum'].ToolTipText = $row.Cells['Durum'].Value
            [void]$script:Results.Add([pscustomobject]@{sira=$step; ad=$row.Cells['Ad'].Value; sonuc='Hata'; ayrinti=$_.Exception.Message})
        }
        [Windows.Forms.Application]::DoEvents()
    }
    $subtitle.Text = 'Son durum · İşlemler tamamlandı'
    $footer.Text = "Sıralı sonuç: $($script:Results.Count) seçim işlendi. Pencereyi kapatabilirsiniz."
    } finally {
        $script:Busy = $false; $grid.Enabled = $true
        $mutex.ReleaseMutex(); $mutex.Dispose()
        if ($form.Modal) { $form.DialogResult = [Windows.Forms.DialogResult]::OK }
    }
}

$button.Add_Click({ Run-SelectedUpdates })

if ($LayoutTest) {
    $script:Inventory['python'] = New-Entry 'python' 'Python' '3.14.6' '3.14.7' 'python.org'
    $script:Inventory['offer'] = New-Entry 'offer' 'teklif-degerlendirme skill' '4.0.0' '3.1.1' 'GitHub Release'
    Render-Inventory
    if ($grid.Rows.Count -ne 2 -or -not $button.Enabled) { throw 'Panel satırları oluşturulamadı.' }
    if ($grid.Rows[1].Cells['Durum'].Value -ne 'Yüklü sürüm yayından yeni') { throw 'Yayın önündeki yerel sürüm doğru gösterilmedi.' }
    'LAYOUT_TEST_OK'
    return
}
$script:UiActive = $true
Render-Inventory
try {
    [void]$form.ShowDialog()
    '@@SONUC ' + ((Get-PanelOutcome) | ConvertTo-Json -Compress -Depth 6)
} finally { $script:UiActive = $false; $form.Dispose() }
