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
# Some hosts (Codex sandbox) start PowerShell without PROCESSOR_ARCHITECTURE; the vendored platform
# check then rejects a real amd64 machine. Fill it from the OS only when missing; never override.
if(-not $env:PROCESSOR_ARCHITECTURE){
    $osArch=$null
    try{$osArch=[string](Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment' -Name PROCESSOR_ARCHITECTURE -ErrorAction Stop).PROCESSOR_ARCHITECTURE}catch{}
    if(-not $osArch){
        try{$osArch=switch([string][Runtime.InteropServices.RuntimeInformation]::OSArchitecture){'X64'{'AMD64'}'Arm64'{'ARM64'}'X86'{'x86'}default{$_}}}catch{}
    }
    if($osArch){$env:PROCESSOR_ARCHITECTURE=$osArch}
}
function Get-ContractBootstrapSha([string]$Path) {
    $algorithm=[Security.Cryptography.SHA256]::Create()
    $stream=[IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try { return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose();$algorithm.Dispose() }
}
function Assert-ContractVendorIntegrity {
    # Built-in PowerShell/IO/crypto only; no vendor function is loaded yet.
    $ErrorActionPreference='Stop'
    $root=[IO.Path]::GetFullPath($engineRoot)
    $rootItem=Get-Item -LiteralPath $root -Force
    if($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Vendor reparse root rejected'}
    $manifestPath=Join-Path $root 'MANIFEST.sha256.json'
    if((Get-Item -LiteralPath $manifestPath).Length -gt 65536){throw 'Vendor manifest exceeds bound'}
    $manifestHash=Get-ContractBootstrapSha $manifestPath
    if($env:SOZLESME_VENDOR_MANIFEST_SHA256 -and $manifestHash -cne $env:SOZLESME_VENDOR_MANIFEST_SHA256){throw 'External vendor manifest digest mismatch'}
    $manifest=Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if($manifest.schema -cne 'guncelleyici-source-manifest/v1' -or $manifest.version -cne '2.3.0'){throw 'Vendor schema/version mismatch'}
    $entries=@($manifest.files.PSObject.Properties)
    if($entries.Count -ne 42){throw 'Closed vendor manifest requires 42 files'}
    $expected=New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach($entry in $entries){
        $name=[string]$entry.Name
        if(-not $name -or $name.Contains('\') -or $name.Contains(':') -or $name.StartsWith('/') -or @($name.Split('/')|Where-Object {$_ -eq '.' -or $_ -eq '..' -or $_ -eq ''}).Count){throw 'Invalid vendor manifest path'}
        if(-not $expected.Add($name)){throw 'Vendor path collision'}
        if([string]$entry.Value -cnotmatch '^[a-f0-9]{64}$'){throw 'Invalid vendor digest'}
        $path=[IO.Path]::GetFullPath((Join-Path $root $name))
        if(-not $path.StartsWith($root.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Vendor path outside root'}
        $node=$path
        while($node -and $node.Length -ge $root.Length){
            $item=Get-Item -LiteralPath $node -Force
            if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Vendor reparse path rejected'}
            if($node -eq $root){break};$node=Split-Path $node -Parent
        }
        if((Get-ContractBootstrapSha $path) -cne [string]$entry.Value){throw 'Vendor bytes mismatch'}
    }
    $actual=@(Get-ChildItem -LiteralPath $root -Recurse -File -Force | Where-Object {$_.Name -ne 'MANIFEST.sha256.json' -and $_.FullName -notmatch '[\\/]__pycache__[\\/]'})
    if($actual.Count -ne 42){throw 'Extra or missing vendor file'}
    foreach($file in $actual){$relative=$file.FullName.Substring($root.Length+1).Replace('\','/');if(-not $expected.Contains($relative)){throw 'Unexpected vendor file'}}
}
try { Assert-ContractVendorIntegrity }
catch {
    '@@SONUC '+(@{status='ERROR';error='PAKET_BUTUNLUK';message=$_.Exception.Message;resume_allowed=$false}|ConvertTo-Json -Compress)
    exit 2
}
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
function Write-ContractReceiptBytes([IO.FileStream]$Stream,[byte[]]$Bytes) {
    $Stream.Write($Bytes,0,$Bytes.Length)
}
function Flush-ContractReceiptStream([IO.FileStream]$Stream) {
    $Stream.Flush($true)
}
function Move-ContractFinalReceipt([string]$Temporary,[string]$Path) {
    [IO.File]::Move($Temporary,$Path) # Same directory, atomic publication, no overwrite.
}
function New-ContractRequestClaim([string]$Path,$Claim) {
    Assert-PlainPath $Path
    $bytes=[Text.Encoding]::UTF8.GetBytes(($Claim|ConvertTo-Json -Depth 20 -Compress))
    $stream=New-Object IO.FileStream($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try {Write-ContractReceiptBytes $stream $bytes;Flush-ContractReceiptStream $stream;return $stream}
    catch {$stream.Dispose();throw}
}
function Write-ContractFinalReceipt([string]$Path,$Final) {
    Assert-PlainPath $Path
    $bytes=[Text.Encoding]::UTF8.GetBytes(($Final|ConvertTo-Json -Depth 40 -Compress))
    $temporary=$Path+'.'+[guid]::NewGuid().ToString('N')+'.tmp'
    $created=$false
    try {
        $stream=New-Object IO.FileStream($temporary,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        $created=$true
        try {Write-ContractReceiptBytes $stream $bytes;Flush-ContractReceiptStream $stream}finally{$stream.Dispose()}
        Move-ContractFinalReceipt $temporary $Path
    }finally{if($created -and [IO.File]::Exists($temporary)){[IO.File]::Delete($temporary)}}
}
function Read-ContractReceiptRecord([string]$Path) {
    Assert-PlainPath $Path
    $stream=[IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    $reader=$null
    try {
        if($stream.Length -gt 16777216){throw 'Receipt exceeds read budget'}
        $reader=[IO.StreamReader]::new($stream,[Text.UTF8Encoding]::new($false,$true),$false,4096,$true)
        return ($reader.ReadToEnd() | ConvertFrom-Json -ErrorAction Stop)
    }finally{if($reader){$reader.Dispose()};$stream.Dispose()}
}
function Get-ContractRequestReceiptState([string]$Root,[string]$RequestId,[string]$Sha256,[string]$SkillId) {
    # Read-only record correlation. No HMAC, host identity, QA or business approval.
    $result=@{state='RECOVERY_REQUIRED';reason='UNVERIFIED_RECORD';record_format='UNKNOWN';resume_allowed=$false;
        repair_performed=$false;authority='NOT_VERIFIED';business_acceptance='NOT_GRANTED';scope='REQUEST_RECORD_CORRELATION_ONLY'}
    try {
        Assert-PlainPath $Root
        $id=[Guid]::Empty
        if(-not [Guid]::TryParse($RequestId,[ref]$id) -or $Sha256 -cnotmatch '^[a-f0-9]{64}$' -or -not $SkillId){throw 'Explicit request binding required'}
        $claimPath=Join-Path $Root ($id.ToString('D')+'.json')
        $finalPath=Join-Path $Root ($id.ToString('D')+'.final.json')
        Assert-PlainPath $claimPath;Assert-PlainPath $finalPath
        if(-not [IO.File]::Exists($claimPath)){
            $result.state=if([IO.File]::Exists($finalPath)){'ORPHAN_FINAL_UNVERIFIED'}else{'UNCLAIMED'}
            $result.reason='NO_CLAIM';return $result
        }
        $claim=Read-ContractReceiptRecord $claimPath
        if((Read-Field $claim 'request_id') -cne $RequestId -or (Read-Field $claim 'request_sha256') -cne $Sha256 -or (Read-Field $claim 'skill_id') -cne $SkillId){throw 'Claim binding differs'}
        $schema=Read-Field $claim 'schema' ''
        if(-not $schema){
            $result.record_format='LEGACY_SINGLE_FILE'
            $status=Read-Field $claim 'status'
            if($status -notin @('STARTED','COMPLETED','FAILED')){throw 'Legacy state unknown'}
            if([IO.File]::Exists($finalPath)){throw 'Legacy/new record mixture'}
            $result.state=if($status -eq 'STARTED'){'RECOVERY_REQUIRED'}else{'LEGACY_TERMINAL_RECORD'}
            $result.reason=[string]$status;return $result
        }
        if($schema -cne 'contract-request-claim/v1' -or (Read-Field $claim 'status') -cne 'STARTED'){throw 'Claim schema/state unknown'}
        $result.record_format='IMMUTABLE_CLAIM_SEPARATE_FINAL'
        if(-not [IO.File]::Exists($finalPath)){$result.reason='FINAL_MISSING';return $result}
        $final=Read-ContractReceiptRecord $finalPath
        if((Read-Field $final 'schema') -cne 'contract-request-final/v1' -or (Read-Field $final 'request_id') -cne $RequestId -or (Read-Field $final 'request_sha256') -cne $Sha256){throw 'Final binding differs'}
        if((Read-Field $final 'status') -notin @('COMPLETED','FAILED') -or (Read-Field $final 'business_acceptance') -cne 'NOT_GRANTED'){throw 'Final state/authority differs'}
        $result.state='TERMINAL_RECORD';$result.reason=[string]$final.status
        return $result
    }catch{$result.reason='CORRUPT_OR_MISMATCHED_RECORD';return $result}
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
    $claim=@{schema='contract-request-claim/v1';status='STARTED';request_sha256=$frozen.sha256;request_id=$frozen.request_id;skill_id=$SkillId;workspace=$Workspace;output_root=$OutputRoot;source_roots=$SourceRoot;started_utc=[DateTime]::UtcNow.ToString('o');retry_safety='NO_BLIND_RETRY'}
    $lock=New-ContractRequestClaim $receipt $claim
    $finalReceipt=Join-Path $requests ($frozen.request_id+'.final.json')
    try{
        Test-ContractRequestCurrent $frozen
        $args=@('-B','-X','utf8',(Join-Path $PSScriptRoot 'contract_cli.py'),'--workspace',$Workspace,'--output-root',$OutputRoot)
        foreach($root in $SourceRoot){$args+=@('--source-root',$root)}
        $args+=@('skill-evaluate','--request',$frozen.path)
        $run=Invoke-Native $python $args 240 @{PYTHONPATH=(Join-Path $contractRoot 'src')}
        $result=$run.Output.Trim()|ConvertFrom-Json
        if($run.ExitCode -ne 0 -or $result.status -ne 'SUCCEEDED'){throw 'Original skill blocked after dependency check; no automatic replay'}
        $final=@{schema='contract-request-final/v1';status='COMPLETED';technical_status='SUCCEEDED';business_status=[string]$result.result.status;business_acceptance='NOT_GRANTED';request_id=$frozen.request_id;request_sha256=$frozen.sha256;ended_utc=[DateTime]::UtcNow.ToString('o');result=$result;retry_safety='NO_BLIND_RETRY'}
        Write-ContractFinalReceipt $finalReceipt $final
        '@@SONUC '+(@{status='COMPLETED';technical_status='SUCCEEDED';business_status=$final.business_status;business_acceptance='NOT_GRANTED';resume_allowed=$false;request_sha256=$frozen.sha256;result=$result;startup_message=$meta.startup_message}|ConvertTo-Json -Depth 40 -Compress)
    }catch{
        $failure=$_
        if(-not [IO.File]::Exists($finalReceipt)){
            try{Write-ContractFinalReceipt $finalReceipt @{schema='contract-request-final/v1';status='FAILED';technical_status='BLOCKED';business_status='NOT_RUN';business_acceptance='NOT_GRANTED';request_id=$frozen.request_id;request_sha256=$frozen.sha256;ended_utc=[DateTime]::UtcNow.ToString('o');retry_safety='NO_BLIND_RETRY'}}catch{}
        }
        throw $failure
    }finally{$lock.Dispose()}
    exit 0
}catch{
    '@@SONUC '+(@{status='BLOCKED';message=(Hide-Secrets $_.Exception.Message);resume_allowed=$false;retry_safety='NO_BLIND_RETRY'}|ConvertTo-Json -Compress)
    exit 2
}
