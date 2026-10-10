#requires -Version 5.1
# Explicit preflight only. No installation, no security-policy changes, no Excel launch.
param([string]$ReportDirectory='',[switch]$Sessiz)
. (Join-Path $PSScriptRoot 'program-ortak.ps1')
$checks=@()
function Add-Check($Name,$Status,$Detail){$script:checks+=@([pscustomobject]@{name=$Name;status=$Status;detail=$Detail})}
try{
    if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){throw 'Windows gerekli.'}
    Add-Check 'PowerShell' $(if($PSVersionTable.PSVersion.Major -eq 5){'PASS'}else{'WARNING'}) $PSVersionTable.PSVersion.ToString()
    Add-Check '64-bit process' $(if([Environment]::Is64BitProcess){'PASS'}else{'FAIL'}) ([Environment]::Is64BitProcess)
    Add-Check 'OS architecture' $(if($env:PROCESSOR_ARCHITECTURE -eq 'AMD64'){'PASS'}else{'FAIL'}) ([string]$env:PROCESSOR_ARCHITECTURE)
    Add-Check 'Language mode' $(if($ExecutionContext.SessionState.LanguageMode -eq 'FullLanguage'){'PASS'}else{'WARNING'}) ([string]$ExecutionContext.SessionState.LanguageMode)
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $principal=New-Object Security.Principal.WindowsPrincipal($identity)
    Add-Check 'Administrator session' 'INFO' ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
    Add-Check 'Execution policies' 'INFO' (@(Get-ExecutionPolicy -List|ForEach-Object {$_.Scope.ToString()+'='+$_.ExecutionPolicy.ToString()}) -join '; ')
    Add-Check 'Excel COM registration' $(if(Test-Path 'Registry::HKEY_CLASSES_ROOT\Excel.Application'){'PASS'}else{'WARNING'}) 'Registry only; real COM test requires an explicit verify request.'
    Add-Check 'Active workloads' 'INFO' (@(Get-CimInstance Win32_Process|Where-Object {$_.Name -match '^(pythonw?|node|pnpm)\.exe$'}).Count)
    Add-Check 'Network / installers' 'NOT_RUN' 'This preflight does not download or install packages.'
    $result=[ordered]@{status='completed';mode='preflight';timestamp=[DateTime]::UtcNow.ToString('o');checks=$checks;security_settings_changed=$false}
    if($ReportDirectory){
        Assert-PlainPath $ReportDirectory;$path=Join-Path $ReportDirectory ('on-kontrol-'+[guid]::NewGuid().ToString('N')+'.json')
        Write-AtomicJson $path $result;$result['report']=$path
    }
    '@@SONUC '+($result|ConvertTo-Json -Depth 8 -Compress)
}catch{
    '@@SONUC '+(@{status='error';message=(Hide-Secrets $_.Exception.Message)}|ConvertTo-Json -Compress);exit 2
}
