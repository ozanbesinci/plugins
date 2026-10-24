#requires -Version 5.1
# First-use setup for Work; fixed published installer, then the normal native gate.
param([ValidatePattern('^K(0[0-9]|1[0-9]|2[0-9])$')][string]$SkillId='K00',[switch]$LibraryOnly)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding $false
$OutputEncoding=New-Object Text.UTF8Encoding $false
$script:SetupPluginRoot=Split-Path $PSScriptRoot -Parent
$script:SetupInstallerName='KilicSozlesmeKurulum-0.1.1.exe'
$script:SetupInstallerUrl='https://github.com/ozanbesinci/plugins/releases/download/kilic-sozlesme-yonetimi-v0.1.1/KilicSozlesmeKurulum-0.1.1.exe'
$script:SetupInstallerSha='6cf9231a568b9551a42e0d0863e2ab620be73e606ac36e296e2693e02bc5bf3a'
$script:SetupInstallerBytes=44002816L

function Get-SetupSha([string]$Path) {
    $hash=[Security.Cryptography.SHA256]::Create();$stream=[IO.File]::OpenRead($Path)
    try{return ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}
    finally{$stream.Dispose();$hash.Dispose()}
}
function Assert-SetupPlainPath([string]$Path) {
    $node=[IO.Path]::GetFullPath($Path)
    while($node){
        if(Test-Path -LiteralPath $node){
            if((Get-Item -LiteralPath $node -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'REPARSE_PATH_REJECTED'}
        }
        $node=Split-Path $node -Parent
    }
}
function Assert-SetupPackage {
    Assert-SetupPlainPath $script:SetupPluginRoot
    $manifest=Get-Content -LiteralPath (Join-Path $script:SetupPluginRoot 'references\bootstrap-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if($manifest.schema -cne 'contract-bootstrap/v1'){throw 'PAKET_BUTUNLUK'}
    foreach($entry in $manifest.files.PSObject.Properties){
        if($entry.Name -match '(^/|\\|:|(^|/)\.\.(/|$))' -or $entry.Value -cnotmatch '^[a-f0-9]{64}$'){throw 'PAKET_BUTUNLUK'}
        $path=Join-Path $script:SetupPluginRoot $entry.Name
        Assert-SetupPlainPath $path
        if(-not [IO.File]::Exists($path) -or (Get-SetupSha $path) -cne $entry.Value){throw 'PAKET_BUTUNLUK'}
    }
}
function Receive-SetupInstaller([string]$Path) {
    Invoke-WebRequest -UseBasicParsing -Uri $script:SetupInstallerUrl -OutFile $Path -MaximumRedirection 5 -TimeoutSec 180 | Out-Null
}
function Assert-SetupInstaller([string]$Path) {
    Assert-SetupPlainPath $Path
    if(-not [IO.File]::Exists($Path) -or (Get-Item -LiteralPath $Path).Length -ne $script:SetupInstallerBytes -or (Get-SetupSha $Path) -cne $script:SetupInstallerSha){throw 'INSTALLER_HASH_MISMATCH'}
}
function Start-SetupInstaller([string]$Path) {
    # No elevation, shell policy changes, SmartScreen bypass or shared Python changes.
    $logBase=Join-Path (Split-Path $Path -Parent) ('kurulum-'+[guid]::NewGuid().ToString('N'))
    $process=Start-Process -FilePath $Path -ArgumentList '--quiet' -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput ($logBase+'.out.log') -RedirectStandardError ($logBase+'.err.log')
    try {
        $exitCode=$process.ExitCode
        if($null -eq $exitCode){throw 'INSTALLER_EXIT_CODE_UNAVAILABLE'}
        if($exitCode -ne 0){
            $detail=Get-Content -LiteralPath ($logBase+'.err.log') -Raw -Encoding UTF8
            throw ('INSTALLER_FAILED_EXIT_'+$exitCode+': '+$detail)
        }
    } finally {$process.Dispose()}
}
function Read-SetupReady([string]$Launcher,[string]$Id) {
    $lines=@(& $Launcher '--plugin-root' $script:SetupPluginRoot 'prepare' '--skill' $Id)
    $exitCode=$LASTEXITCODE
    $records=@($lines | Where-Object {$_ -like '@@SONUC *'})
    if($records.Count -ne 1){throw 'NATIVE_PREPARE_RESULT_INVALID'}
    $value=$records[0].Substring(8) | ConvertFrom-Json
    if($exitCode -ne 0 -or $value.status -cne 'READY' -or $value.resume_allowed -ne $true){
        $reason=if($value.error){[string]$value.error}else{'NATIVE_PREPARE_NOT_READY'}
        throw $reason
    }
    return $value
}
function Invoke-ContractAutomaticSetup([string]$Id) {
    Assert-SetupPackage
    if(-not $env:USERPROFILE -or -not [IO.Path]::IsPathRooted($env:USERPROFILE)){throw 'LOCAL_ACCESS_REQUIRED'}
    $homePath=Join-Path $env:USERPROFILE 'KilicPython'
    $launcher=Join-Path $homePath 'launcher\sozlesme.exe'
    Assert-SetupPlainPath $launcher
    if([IO.File]::Exists($launcher)){
        # A broken or unfinished existing environment is not an automatic repair.
        try {
            $ready=Read-SetupReady $launcher $Id
            $ready | Add-Member -NotePropertyName automatic_setup -NotePropertyValue 'NOT_NEEDED' -Force
            return $ready
        } catch {if($_.Exception.Message -cne 'SETUP_REQUIRED'){throw}}
    }
    if((Test-Path -LiteralPath (Join-Path $homePath 'sozlesme-runtime.json')) -or (Test-Path -LiteralPath (Join-Path $homePath 'sozlesme-setup'))){throw 'RECOVERY_REQUIRED'}
    $cache=Join-Path $env:USERPROFILE 'Downloads\KilicSozlesme'
    Assert-SetupPlainPath $cache
    [IO.Directory]::CreateDirectory($cache) | Out-Null
    $lockPath=Join-Path $cache 'kurulum-indirme.lock'
    Assert-SetupPlainPath $lockPath
    $lock=New-Object IO.FileStream($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    $partial=$null;$guard=$null
    try {
        $installer=Join-Path $cache $script:SetupInstallerName
        if(-not [IO.File]::Exists($installer)){
            $partial=Join-Path $cache ($script:SetupInstallerName+'.'+[guid]::NewGuid().ToString('N')+'.partial')
            Receive-SetupInstaller $partial
            Assert-SetupInstaller $partial
            [IO.File]::Move($partial,$installer)
            $partial=$null
        }
        Assert-SetupInstaller $installer
        # Keep the verified executable read-locked until installation terminates.
        $guard=[IO.File]::Open($installer,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
        if($guard.Length -ne $script:SetupInstallerBytes -or (Get-SetupSha $installer) -cne $script:SetupInstallerSha){throw 'INSTALLER_HASH_MISMATCH'}
        Start-SetupInstaller $installer
        $ready=Read-SetupReady $launcher $Id
        $ready | Add-Member -NotePropertyName automatic_setup -NotePropertyValue 'INSTALLED_AND_VERIFIED' -Force
        $ready | Add-Member -NotePropertyName installer_sha256 -NotePropertyValue $script:SetupInstallerSha -Force
        return $ready
    } finally {
        if($guard){$guard.Dispose()}
        if($partial -and [IO.File]::Exists($partial)){[IO.File]::Delete($partial)}
        $lock.Dispose()
    }
}
if($LibraryOnly){return}
try {
    $result=Invoke-ContractAutomaticSetup $SkillId
    '@@SONUC '+($result | ConvertTo-Json -Depth 30 -Compress)
    exit 0
} catch {
    '@@SONUC '+(@{status='BLOCKED';error='AUTOMATIC_SETUP_FAILED';message=$_.Exception.Message;resume_allowed=$false;business_acceptance='NOT_GRANTED'} | ConvertTo-Json -Compress)
    exit 2
}
