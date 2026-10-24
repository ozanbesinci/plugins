#requires -Version 5.1
# Compatibility entry; normal Work uses the native sozlesme.exe launcher.
param([ValidateSet('prepare','run')][string]$Action='prepare',
 [Parameter(Mandatory=$true)][string]$SkillId,
 [string]$RequestFile='', [string]$Workspace='', [string]$OutputRoot='',
 [string[]]$SourceRoot=@(),[string]$RuntimeStateRoot='',[switch]$LibraryOnly)
$ErrorActionPreference='Stop'
$contractRoot=Split-Path $PSScriptRoot -Parent
[Console]::OutputEncoding=New-Object Text.UTF8Encoding $false
$OutputEncoding=New-Object Text.UTF8Encoding $false
try {
 $manifest=Get-Content -LiteralPath (Join-Path $contractRoot 'references\bootstrap-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
 $helper=Join-Path $PSScriptRoot 'runtime_common.ps1'
 $h=[Security.Cryptography.SHA256]::Create();$f=[IO.File]::OpenRead($helper)
 try{$digest=([BitConverter]::ToString($h.ComputeHash($f))).Replace('-','').ToLowerInvariant()}finally{$f.Dispose();$h.Dispose()}
 if($manifest.schema -cne 'contract-bootstrap/v1' -or $digest -cne $manifest.files.'scripts/runtime_common.ps1'){throw 'PAKET_BUTUNLUK'}
 . $helper
} catch { '@@SONUC '+(@{status='BLOCKED';error='PAKET_BUTUNLUK';resume_allowed=$false}|ConvertTo-Json -Compress);exit 2 }
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
    if((File-Sha256 $Frozen.path) -cne $Frozen.sha256){throw 'Original request changed before execution'}
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
function Assert-ContractResult($Result) {
    if((Read-Field $Result 'process_exit_code' 0) -ne 0 -or (Read-Field $Result 'status') -eq 'ERROR' -or (Read-Field $Result 'ozet') -eq 'ENGEL'){
        throw [string](Read-Field $Result 'message' (Read-Field $Result 'neden' (Read-Field $Result 'error' 'Dependency process failed')))
    }
}

if($LibraryOnly){return}
try {
 $entry=Join-Path $env:USERPROFILE 'KilicPython\launcher\sozlesme.exe'
 Assert-PlainPath $entry
 if(-not (Test-Path -LiteralPath $entry)){throw 'SETUP_REQUIRED: Ayrı Kılıç Sözleşme kurucusu gerekli'}
 $params=@('--plugin-root',$contractRoot,$Action,'--skill',$SkillId)
 if($RuntimeStateRoot){$params+=@('--state-root',$RuntimeStateRoot)}
 if($Action -eq 'run'){
   $params+=@('--request',$RequestFile,'--workspace',$Workspace,'--output-root',$OutputRoot)
   foreach($source in $SourceRoot){$params+=@('--source-root',$source)}
 }
 & $entry @params
 exit $LASTEXITCODE
} catch { '@@SONUC '+(@{status='BLOCKED';error='SETUP_REQUIRED';message=$_.Exception.Message;resume_allowed=$false}|ConvertTo-Json -Compress);exit 2 }
