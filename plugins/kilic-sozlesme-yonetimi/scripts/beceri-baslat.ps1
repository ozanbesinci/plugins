#requires -Version 5.1
# Agent entry point. No execution-policy changes, elevation or end-user terminal.
param(
    [ValidateSet('prepare','run')][string]$Action='prepare',
    [Parameter(Mandatory=$true)][string]$SkillId,
    [switch]$AutoInstallMissing,
    [string]$RequestFile='', [string]$Workspace='', [string]$OutputRoot='',
    [string[]]$SourceRoot=@(),
    [string]$RuntimeStateRoot='',
    [switch]$LibraryOnly
)
$contractRoot=Split-Path $PSScriptRoot -Parent
$engineRoot=Join-Path $contractRoot 'vendor\guncelleyici'
. (Join-Path $engineRoot 'scripts\core.ps1')
[Console]::OutputEncoding=New-Object Text.UTF8Encoding $false
$OutputEncoding=New-Object Text.UTF8Encoding $false

function Get-ContractMeta([string]$Id) {
    $registry=Get-Content -LiteralPath (Join-Path $contractRoot 'references\skill-versions.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $meta=Read-Field $registry $Id
    if(-not $meta){throw 'Unknown skill id'}
    $version=(Get-Content -LiteralPath (Join-Path $contractRoot ('skills\'+$meta.slug+'\VERSION')) -Raw -Encoding UTF8).Trim()
    if($version -cne $meta.version){throw 'Skill VERSION mismatch'}
    return $meta
}
function Get-ContractRequest([string]$File,[string[]]$Roots,[string]$Id) {
    Assert-PlainPath $File
    $full=[IO.Path]::GetFullPath($File)
    $allowed=$false
    foreach($root in $Roots){
        Assert-PlainPath $root
        $prefix=[IO.Path]::GetFullPath($root).TrimEnd('\')+'\'
        if($full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){$allowed=$true}
    }
    if(-not $allowed -or [IO.Path]::GetExtension($full) -ine '.json' -or -not (Test-Path -LiteralPath $full -PathType Leaf)) {throw 'Request outside allowed source roots'}
    if((Get-Item -LiteralPath $full).Length -gt 65536){throw 'Request exceeds 64 KiB'}
    $request=Get-Content -LiteralPath $full -Raw -Encoding UTF8 | ConvertFrom-Json
    $uuid=[guid]::Empty
    if(-not [guid]::TryParse([string](Read-Field $request 'request_id'),[ref]$uuid) -or (Read-Field $request 'skill_id') -cne $Id){throw 'Request id/skill mismatch'}
    return [pscustomobject]@{path=$full;sha256=(File-Sha256 $full);request_id=$uuid.ToString();request=$request}
}
function Test-ContractRequestCurrent($Frozen) {
    Assert-PlainPath $Frozen.path
    if((File-Sha256 $Frozen.path) -cne $Frozen.sha256){throw 'Original request changed during dependency installation'}
}
function Invoke-ContractProbe([string]$Python) {
    $result=Invoke-Json $Python @('-B','-X','utf8',(Join-Path $PSScriptRoot 'runtime_kontrol.py'),'--action','probe') 240
    Assert-ContractResult $result
    return $result
}
function Assert-ContractResult($Result) {
    if((Read-Field $Result 'process_exit_code' 0) -ne 0 -or (Read-Field $Result 'status') -eq 'ERROR' -or (Read-Field $Result 'ozet') -eq 'ENGEL'){
        throw [string](Read-Field $Result 'message' (Read-Field $Result 'neden' (Read-Field $Result 'error' 'Dependency process failed')))
    }
}
function Install-ContractPython([string]$State) {
    # Explicit plugin missing-install policy authorizes NEW Python only. An
    # existing supported interpreter is never upgraded by this adapter.
    $guard=Enter-Guard
    $oldToken=$env:GUNCELLEYICI_RUN_TOKEN;$oldMaintenance=$env:GUNCELLEYICI_MAINTENANCE
    $journal=Join-Path $State 'bootstrap-active.json'
    try{
        if((Test-Path -LiteralPath $journal) -or (Test-Path -LiteralPath (Join-Path $script:StateRoot 'active-transaction.json'))){throw 'Unfinished updater transaction; no blind retry'}
        $local=Get-Observation 'python' -LocalOnly
        if(Read-Field $local 'python'){return [string]$local.python}
        $observation=Get-Observation 'python'
        if(-not $observation.target -or (Read-Field $observation 'python')){throw 'Missing-only Python target unavailable or local state changed'}
        $plan=[ordered]@{schema='sozlesme-missing-python/v1';identity=(Get-Identity);code_fingerprint=(Get-CodeFingerprint);
            target=$observation.target;before_fingerprint=(Object-Fingerprint $local.local);policy='EXPLICIT_PLUGIN_MISSING_INSTALL';updater_version='2.3.0'}
        $session=Join-Path $State ('bootstrap\'+[guid]::NewGuid().ToString('N'))
        [void][IO.Directory]::CreateDirectory($session)
        $planPath=Join-Path $session 'plan.json';Write-AtomicJson $planPath $plan;$hash=File-Sha256 $planPath
        $current=Get-Observation 'python' -LocalOnly
        if(Read-Field $current 'python'){throw 'Python appeared after scan; prepare a new request'}
        if((Object-Fingerprint $current.local) -cne $plan.before_fingerprint -or (Get-CodeFingerprint) -cne $plan.code_fingerprint -or (File-Sha256 $planPath) -cne $hash){throw 'Python target/context changed'}
        # Only fresh interpreter installation; native process test still runs.
        $env:GUNCELLEYICI_MAINTENANCE='confirmed'
        Assert-MaintenanceWindow
        $env:GUNCELLEYICI_RUN_TOKEN=[guid]::NewGuid().ToString('N')
        Write-AtomicJson $journal @{phase='STARTED';plan=$planPath;sha256=$hash}
        $result=Invoke-Selected 'python' ([pscustomobject]@{target=$plan.target}) $session
        Write-AtomicJson (Join-Path $session 'result.json') $result
        if((Read-Field $result 'health') -ne 'PASS' -or (Read-Field $result 'recovery_required' $false) -or (Read-Field $result 'restart_required' $false)){throw 'Python installation not verified or restart required'}
        $after=Get-Observation 'python' -LocalOnly
        if(-not $after.python -or $after.surum -cne $plan.target.version){throw 'Python installed state differs from plan'}
        Remove-Item -LiteralPath $journal -ErrorAction Stop
        return [string]$after.python
    }finally{$env:GUNCELLEYICI_RUN_TOKEN=$oldToken;$env:GUNCELLEYICI_MAINTENANCE=$oldMaintenance;$guard.Dispose()}
}
if($LibraryOnly){return}

try{
    $meta=Get-ContractMeta $SkillId
    $meta.startup_message
    Assert-SupportedPlatform
    if((Get-Content -LiteralPath (Join-Path $engineRoot 'VERSION') -Raw).Trim() -cne '2.3.0'){throw 'Updater 2.3.0 required'}
    $frozen=$null
    if($Action -eq 'run'){
        if($SkillId -eq 'guncelleyici'){throw 'Use the direct updater chat entry for general update requests'}
        if(-not $Workspace -or -not $OutputRoot -or -not $SourceRoot.Count){throw 'Case/output/source roots required'}
        Assert-PlainPath $Workspace;Assert-PlainPath $OutputRoot
        $frozen=Get-ContractRequest $RequestFile $SourceRoot $SkillId
    }
    if(-not $RuntimeStateRoot){$RuntimeStateRoot=Join-Path $env:LOCALAPPDATA 'KilicSozlesme\runtime'}
    Assert-PlainPath $RuntimeStateRoot
    $RuntimeStateRoot=[IO.Path]::GetFullPath($RuntimeStateRoot)
    foreach($name in @('bootstrap-active.json','active-install.json')){
        if(Test-Path -LiteralPath (Join-Path $RuntimeStateRoot $name)){throw 'Unfinished runtime transaction; no automatic retry'}
    }
    $observed=Invoke-PS 'python-kur.ps1' @('-LocalOnly') 180
    $python=[string](Read-Field $observed 'python')
    $active=Join-Path $RuntimeStateRoot 'active-runtime.json'
    if(Test-Path -LiteralPath $active){
        Assert-PlainPath $active
        $record=Get-Content -LiteralPath $active -Raw -Encoding UTF8 | ConvertFrom-Json
        $candidate=[string]$record.python;Assert-PlainPath $candidate
        $prefix=$RuntimeStateRoot.TrimEnd('\')+'\environments\'
        $private=[IO.Path]::GetFullPath($candidate).StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)
        $registered=(Read-Field $record 'mode') -eq 'REGISTERED_RUNTIME' -and $candidate -ieq $python
        if((-not $private -and -not $registered) -or -not (Test-Path -LiteralPath $candidate -PathType Leaf)){throw 'Managed runtime pointer invalid'}
        $extension=[string](Read-Field $record 'extension_root')
        if($extension){
            Assert-PlainPath $extension
            if(-not ([IO.Path]::GetFullPath($extension).StartsWith($RuntimeStateRoot.TrimEnd('\')+'\extensions\',[StringComparison]::OrdinalIgnoreCase))){throw 'PDF extension pointer invalid'}
            $env:SOZLESME_PDF_EXTENSION_ROOT=$extension
        }
        $python=$candidate
    }
    $probe=$null
    if($python){$probe=Invoke-ContractProbe $python}
    $needed=-not $probe -or $probe.status -ne 'READY'
    if($needed -and -not $AutoInstallMissing){
        '@@SONUC '+(@{status='DEPENDENCIES_REQUIRED';resume_allowed=$false;runtime=$probe;startup_message=$meta.startup_message}|ConvertTo-Json -Depth 25 -Compress)
        exit 2
    }
    if($needed){
        if($SkillId -ne 'guncelleyici'){(Get-ContractMeta 'guncelleyici').startup_message}
        [void][IO.Directory]::CreateDirectory($RuntimeStateRoot)
        if(-not $python){$python=Install-ContractPython $RuntimeStateRoot}
        $installed=Invoke-Json $python @('-B','-X','utf8',(Join-Path $PSScriptRoot 'runtime_kontrol.py'),'--action','install','--state-root',$RuntimeStateRoot,'--auto-install-missing') 2400
        Assert-ContractResult $installed
        $python=[string]$installed.python
        if(Read-Field $installed 'extension_root'){$env:SOZLESME_PDF_EXTENSION_ROOT=[string]$installed.extension_root}
        $probe=Invoke-ContractProbe $python
        if($probe.status -ne 'READY'){throw 'Dependencies not verified; original skill not resumed'}
    }
    if($frozen){Test-ContractRequestCurrent $frozen}
    if($Action -eq 'prepare'){
        '@@SONUC '+(@{status='READY';resume_allowed=$true;python=$python;runtime=$probe;startup_message=$meta.startup_message;updater_version='2.3.0'}|ConvertTo-Json -Depth 25 -Compress)
        exit 0
    }
    # Same request bytes, skill id and roots. Store rechecks source hashes and CAS
    # AFTER installation. Request id is consumed before launch, never blindly replayed.
    $requests=Join-Path $RuntimeStateRoot 'requests';Assert-PlainPath $requests
    [void][IO.Directory]::CreateDirectory($requests)
    $receipt=Join-Path $requests ($frozen.request_id+'.json')
    $lock=New-Object IO.FileStream($receipt,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{
        $claim=@{status='STARTED';request_sha256=$frozen.sha256;request_id=$frozen.request_id;skill_id=$SkillId;workspace=$Workspace;output_root=$OutputRoot;source_roots=$SourceRoot}
        $bytes=[Text.Encoding]::UTF8.GetBytes(($claim|ConvertTo-Json -Depth 10 -Compress));$lock.Write($bytes,0,$bytes.Length);$lock.Flush($true)
        Test-ContractRequestCurrent $frozen
        $args=@('-B','-X','utf8','-m','sozlesme_cekirdek','--workspace',$Workspace,'--output-root',$OutputRoot)
        foreach($root in $SourceRoot){$args+=@('--source-root',$root)}
        $args+=@('skill-evaluate','--request',$frozen.path)
        $run=Invoke-Native $python $args 240 @{PYTHONPATH=(Join-Path $contractRoot 'src')}
        $result=$run.Output.Trim()|ConvertFrom-Json
        if($run.ExitCode -ne 0 -or $result.status -ne 'SUCCEEDED'){throw 'Original skill blocked after dependency check; no automatic replay'}
        $claim.status='COMPLETED';$claim.result=$result
        $lock.SetLength(0);$lock.Position=0;$bytes=[Text.Encoding]::UTF8.GetBytes(($claim|ConvertTo-Json -Depth 30 -Compress));$lock.Write($bytes,0,$bytes.Length);$lock.Flush($true)
        '@@SONUC '+(@{status='COMPLETED';resume_allowed=$false;request_sha256=$frozen.sha256;result=$result;startup_message=$meta.startup_message}|ConvertTo-Json -Depth 30 -Compress)
    }finally{$lock.Dispose()}
    exit 0
}catch{
    '@@SONUC '+(@{status='BLOCKED';message=(Hide-Secrets $_.Exception.Message);resume_allowed=$false;retry_safety='NO_BLIND_RETRY'}|ConvertTo-Json -Compress)
    exit 2
}
