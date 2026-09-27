$ErrorActionPreference = 'Stop'
$panel = Join-Path (Split-Path $PSScriptRoot -Parent) 'scripts\panel.ps1'
. $panel -TestMode | Out-Null
$realOffer = (Get-Command Get-OfferLatest).ScriptBlock

function Assert([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

$script:Calls = New-Object System.Collections.ArrayList
function Invoke-PS([string]$Name, [string[]]$Extra) {
    [void]$script:Calls.Add([pscustomobject]@{ name=$Name; args=@($Extra) })
    switch ($Name) {
        'python-kur.ps1' { return [pscustomobject]@{ surum='3.14.6'; hedef_surum='3.14.7'; hedef_kaynagi='python.org'; python='C:\test\python.exe' } }
        'node-kur.ps1' { return [pscustomobject]@{ surum='24.0.0'; hedef_surum='24.1.0'; hedef_kaynagi='nodejs.org'; node='C:\test\node.exe' } }
        'pnpm-kur.ps1' { return [pscustomobject]@{ surum=$null; hedef_surum='10.0.0'; hedef_kaynagi='npm latest' } }
        'powerbi-mcp-kur.ps1' { return [pscustomobject]@{ surum='0.4.0'; hedef_surum='1.0.0' } }
    }
    throw "Beklenmeyen betik: $Name"
}
function Invoke-Tool([string]$Exe, [string[]]$Arguments) {
    [void]$script:Calls.Add([pscustomobject]@{ name='duckdb'; args=@($Arguments) })
    return [pscustomobject]@{ surum='1.0.0'; hedef_surum='1.1.0' }
}
function Get-Libraries($Python) {
    return [pscustomobject]@{ openpyxl=[pscustomobject]@{ installed='3.0.0'; target='3.1.5' } }
}
function Get-OfferLatest { return '3.0.0' }

Scan-Inventory
Assert ($script:Inventory.Count -eq 7) 'Yedi seçim satırı oluşmadı.'
Assert ($script:Inventory['python'].Ready) 'Eski Python seçilemedi.'
Assert (-not $script:Inventory['offer'].Ready) 'Daha eski teklif yayını seçilebilir olmamalı.'
Assert ((Check-FailureText 'System.Net.Sockets.SocketException: Erişim izinlerince izin verilmeyen bir şekilde') -eq 'Kontrol edilemedi · ağ erişimi engellendi') 'Ağ erişimi engeli panelde açıklanmadı.'
Assert (@($script:Calls | Where-Object { $_.name -eq 'duckdb' -and $_.args -contains '--yalniz-bul' }).Count -eq 1) 'DuckDB taraması salt okuma değil.'
Assert (@($script:Calls | Where-Object { $_.name -ne 'duckdb' -and $_.args -notcontains '-YalnizBul' }).Count -eq 0) 'İlk taramada kurulum komutu çağrıldı.'
$before = $script:Calls.Count
$null = Install-Selected 'node'
Assert ($script:Calls.Count -eq ($before + 1)) 'Tek seçim birden çok kurulum çalıştırdı.'
Assert ($script:Calls[$before].name -eq 'node-kur.ps1' -and $script:Calls[$before].args -notcontains '-YalnizBul') 'Seçilen Node.js kurulumu çalışmadı.'
function Invoke-PS([string]$Name, [string[]]$Extra) {
    switch ($Name) {
        'python-kur.ps1' { return [pscustomobject]@{surum='3.14.7';hedef_surum='3.14.7';hedef_kaynagi='python.org';python='C:\test\python.exe'} }
        'node-kur.ps1' { throw 'Yerel tespit başarısız' }
        'pnpm-kur.ps1' { return [pscustomobject]@{surum='12.6.0';hedef_surum=$null;neden='Ağ kapalı'} }
        'powerbi-mcp-kur.ps1' { return [pscustomobject]@{surum='1.0.0';hedef_surum=$null;neden='Marketplace kapalı'} }
    }
}
function Get-RegistryLatest { throw 'Ağ kapalı' }
function Invoke-Tool { return [pscustomobject]@{surum='1.5.5';hedef_surum=$null;neden='PyPI kapalı'} }
Scan-Inventory
Assert ($script:Inventory['node'].Installed -eq 'Tespit edilemedi') 'Tespit hatası kurulum yokluğu sayıldı.'
foreach ($key in @('pnpm','duckdb','powerbi')) {
    Assert ($script:Inventory[$key].Installed -ne 'Yüklü değil' -and -not $script:Inventory[$key].Ready) "Ağ hatasında $key yerel sürümü kayboldu veya güncellenebilir sayıldı."
}
$layout = & powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File $panel -LayoutTest
Assert ($layout -contains 'LAYOUT_TEST_OK') 'Seçim tablosu oluşturulamadı.'

$testRoot = Join-Path $PSScriptRoot ('.panel-test-' + [guid]::NewGuid().ToString('N'))
$resolved = [IO.Path]::GetFullPath($testRoot)
$allowed = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
Assert ($resolved.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)) 'Test yolu çalışma alanı dışında.'
$previousProfile = $env:USERPROFILE
$previousLocal = $env:LOCALAPPDATA
try {
    $env:USERPROFILE = Join-Path $testRoot 'profile'
    $env:LOCALAPPDATA = Join-Path $testRoot 'local'
    $old = Join-Path $env:USERPROFILE '.codex\skills\program-guncelle'
    $new = Join-Path $env:USERPROFILE '.codex\skills\guncelleyici'
    New-Item -ItemType Directory -Path $old,$new,$env:LOCALAPPDATA -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $old 'SKILL.md') -Value "---`nname: program-guncelle`n---"
    Set-Content -LiteralPath (Join-Path $new 'SKILL.md') -Value "---`nname: guncelleyici`n---"
    $null = Remove-LegacySkill
    Assert (-not (Test-Path -LiteralPath $old)) 'Eski skill kurulumdan kaldırılmadı.'
    Assert (Test-Path -LiteralPath $new) 'Yeni skill yanlışlıkla kaldırıldı.'
    $moved = @(Get-ChildItem -LiteralPath (Join-Path $env:LOCALAPPDATA 'guncelleyici\kaldirilan-eski-skill'))
    Assert ($moved.Count -eq 1) 'Eski skill karantinada bulunamadı.'

    $shared = Join-Path $testRoot 'shared-skill'
    New-Item -ItemType Directory -Path $shared | Out-Null
    Set-Content -LiteralPath (Join-Path $shared 'keep.txt') -Value 'preserve shared target'
    New-Item -ItemType Junction -Path $old -Target $shared | Out-Null
    $null = Remove-LegacySkill
    Assert (-not (Test-Path -LiteralPath $old)) 'Eski junction kaldırılmadı.'
    Assert (Test-Path -LiteralPath (Join-Path $shared 'keep.txt')) 'Junction hedefi silindi.'
    New-Item -ItemType Directory -Path $old | Out-Null
    Set-Content -LiteralPath (Join-Path $old 'SKILL.md') -Value "---`nname: unrelated`n---"
    $null = Remove-LegacySkill
    Assert (Test-Path -LiteralPath $old) 'Kimliği eşleşmeyen klasör taşındı.'

    # The displayed offer version must come from a checksum-verified Release manifest.
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $fixture = Join-Path $testRoot 'release.zip'
    $fileStream = [IO.File]::Open($fixture,[IO.FileMode]::Create)
    $archive = New-Object IO.Compression.ZipArchive($fileStream,[IO.Compression.ZipArchiveMode]::Create)
    $entry = $archive.CreateEntry('release-manifest.json')
    $writer = New-Object IO.StreamWriter($entry.Open(),[Text.Encoding]::UTF8)
    $writer.Write('{"repository":"ozanbesinci/teklif-degerlendirme","version":"3.1.1","schema":3,"versioning":"independent/v1","skill_versions":{"teklif-degerlendirme":"4.0.0"}}')
    $writer.Dispose(); $archive.Dispose(); $fileStream.Dispose()
    $fixtureHash = (Get-FileHash -LiteralPath $fixture -Algorithm SHA256).Hash
    Assert ((Get-FileSha256 $fixture) -eq $fixtureHash) 'SHA-256 doğrulaması cmdlet bağımlılığı olmadan çalışmadı.'
    $checksum = Join-Path $testRoot 'release.sha256'
    Set-Content -LiteralPath $checksum -Value "$fixtureHash  teklif-degerlendirme-v3.1.1.zip"
    $script:FixtureArchive = $fixture
    $script:FixtureChecksum = $checksum
    $script:RestCalls = 0
    $script:AssetCalls = 0
    function Invoke-RestMethod {
        $script:RestCalls++
        if ($script:RestCalls -eq 1) { throw 'Geçici bağlantı hatası' }
        return [pscustomobject]@{draft=$false; prerelease=$false; tag_name='v3.1.1'; assets=@(
            [pscustomobject]@{name='teklif-degerlendirme-v3.1.1.zip';browser_download_url='https://github.com/ozanbesinci/teklif-degerlendirme/releases/download/v3.1.1/teklif-degerlendirme-v3.1.1.zip'},
            [pscustomobject]@{name='teklif-degerlendirme-v3.1.1.zip.sha256';browser_download_url='https://github.com/ozanbesinci/teklif-degerlendirme/releases/download/v3.1.1/teklif-degerlendirme-v3.1.1.zip.sha256'})}
    }
    function Invoke-WebRequest {
        param([string]$Uri,[string]$OutFile,[int]$TimeoutSec,[switch]$UseBasicParsing)
        $script:AssetCalls++
        if ($script:AssetCalls -eq 1) { throw 'Geçici indirme hatası' }
        $source = if ($Uri.EndsWith('.sha256')) { $script:FixtureChecksum } else { $script:FixtureArchive }
        Copy-Item -LiteralPath $source -Destination $OutFile
    }
    Assert ((& $realOffer) -eq '4.0.0') 'Doğrulanmış bileşen sürümü okunamadı.'
    Assert ($script:RestCalls -eq 2 -and $script:AssetCalls -eq 3) 'Geçici ağ hatası yeniden denenmedi.'
    Set-Content -LiteralPath $checksum -Value "$('0' * 64)  teklif-degerlendirme-v3.1.1.zip"
    $rejected = $false
    try { $null = & $realOffer } catch { $rejected = $true }
    Assert $rejected 'SHA-256 uyuşmazlığı kabul edildi.'
} finally {
    $env:USERPROFILE = $previousProfile
    $env:LOCALAPPDATA = $previousLocal
    if ($resolved.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolved)) {
        Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
    }
}
'PANEL_TEST_OK'
