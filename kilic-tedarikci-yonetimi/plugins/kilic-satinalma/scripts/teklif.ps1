#requires -Version 5.1
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$CommandArgs)
$ErrorActionPreference = 'Stop'
try {
    $registry = Join-Path $env:USERPROFILE 'KilicPython\teklif-runtime.json'
    if (-not (Test-Path -LiteralPath $registry -PathType Leaf)) {
        throw 'Hazır teklif ortamı yok. Eklenti dışındaki kurulum\Kur.cmd dosyasını çalıştırın.'
    }
    $record = Get-Content -LiteralPath $registry -Raw -Encoding UTF8 | ConvertFrom-Json
    $profile = Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\config\runtime-profile.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($record.schema -ne 'kilic-offer-runtime/v1' -or $record.profile_id -ne $profile.id -or $record.lock_sha256 -ne $profile.lock_sha256) {
        throw 'Ortam kaydı bu eklentinin paket kilidiyle uyuşmuyor.'
    }
    $userRoot = [IO.Path]::GetFullPath((Join-Path $env:USERPROFILE 'KilicPython')).TrimEnd('\') + '\'
    $environment = [IO.Path]::GetFullPath([string]$record.environment_root).TrimEnd('\') + '\'
    $python = [IO.Path]::GetFullPath([string]$record.python)
    if (-not $environment.StartsWith($userRoot,[StringComparison]::OrdinalIgnoreCase) -or -not $python.StartsWith($environment,[StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw 'Kayıtlı Python kullanıcı ortamı içinde bulunamadı.'
    }
    # Resolve junctions before execution too; a registry path is not an executable authority.
    $probe = Get-Item -LiteralPath $python
    while ($probe -and $probe.FullName.Length -ge $userRoot.Length) {
        if (($probe.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Ortam yolunda yeniden yönlendirme bulundu.' }
        $probe = $probe.Parent
        if (-not $probe) { $probe = (Get-Item -LiteralPath $python).Directory }
    }
    & $python -X utf8 -I -B (Join-Path $PSScriptRoot 'runtime_launcher.py') @CommandArgs
    exit $LASTEXITCODE
} catch {
    Write-Error $_.Exception.Message -ErrorAction Continue
    exit 3
}

