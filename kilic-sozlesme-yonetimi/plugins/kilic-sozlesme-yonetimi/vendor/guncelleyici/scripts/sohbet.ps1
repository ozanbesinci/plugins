#requires -Version 5.1
param([ValidateSet('scan','apply','verify')][string]$Action='scan',[string]$Keys='',
      [string]$Fingerprint='', [string]$PlanFile='', [switch]$IncludePdf,
      [switch]$MaintenanceWindow, [switch]$ConfirmApply, [string]$RepairKeys='', [switch]$LibraryOnly)
. (Join-Path $PSScriptRoot 'core.ps1')
Assert-SupportedPlatform
if($LibraryOnly){return}
try{
    if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){throw 'Bu giriş Windows PowerShell 5.1 içindir.'}
    $selected=@($Keys.Split(',')|ForEach-Object {$_.Trim().ToLowerInvariant()}|Where-Object {$_}|Select-Object -Unique)
    $repair=@($RepairKeys.Split(',')|ForEach-Object {$_.Trim().ToLowerInvariant()}|Where-Object {$_}|Select-Object -Unique)
    foreach($key in $repair){if($key -notin @('libraries','duckdb','node','pnpm','powerbi')){throw 'Bu bileşen için otomatik aynı sürüm onarımı desteklenmiyor.'}}
    if($Action -eq 'scan'){$out=Build-Plan ([bool]$IncludePdf) $repair}
    elseif($Action -eq 'apply'){$out=Apply-Plan $PlanFile $Fingerprint $selected ([bool]$MaintenanceWindow) ([bool]$ConfirmApply)}
    else{$out=Verify-Selected $selected}
    '@@SONUC '+(Hide-Secrets ($out|ConvertTo-Json -Depth 30 -Compress))
    if($out.status -in 'error','busy','stale'){exit 2}
    exit 0
}catch{
    '@@SONUC '+(@{status='error';message=(Hide-Secrets $_.Exception.Message)}|ConvertTo-Json -Compress)
    exit 2
}
