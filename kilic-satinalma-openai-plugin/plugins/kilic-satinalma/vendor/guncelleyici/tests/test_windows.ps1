#requires -Version 5.1
# Offline syntax + orchestration fixture tests. Never install real applications.
param()
$ErrorActionPreference='Stop'
$skill=Split-Path $PSScriptRoot -Parent
$results=New-Object System.Collections.Generic.List[object]
function Check([bool]$Condition,[string]$Name){
    if(-not $Condition){throw "FAIL: $Name"}
    $results.Add([pscustomobject]@{name=$Name;status='PASS'})
}
foreach($file in Get-ChildItem -LiteralPath $skill -Recurse -File -Filter '*.ps1'){
    $tokens=$null;$errors=$null
    $null=[Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$errors)
    if($errors.Count){throw ($file.Name+': '+($errors|Out-String))}
    Check $true ('syntax:'+ $file.Name)
}
$testRoot=Join-Path $env:TEMP ('guncelleyici-offline-test-'+[guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($testRoot)
$oldLocal=$env:LOCALAPPDATA;$oldProfile=$env:USERPROFILE;$oldTemp=$env:TEMP
try{
    $env:TEMP=$testRoot
    $env:LOCALAPPDATA=Join-Path $testRoot 'local';$env:USERPROFILE=Join-Path $testRoot 'profile'
    . (Join-Path $skill 'scripts\core.ps1')
    $script:StateRoot=Join-Path $testRoot 'state'
    # Execute the production dispatcher definition against temporary probe scripts.
    # Copy only its AST extent so PSScriptRoot cannot select real installers.
    $policyBefore=Get-ExecutionPolicy -List | Select-Object Scope,ExecutionPolicy
    $policyBeforeJson=ConvertTo-Json -InputObject @($policyBefore) -Compress
    $coreTokens=$null;$coreErrors=$null
    $coreAst=[Management.Automation.Language.Parser]::ParseFile((Join-Path $skill 'scripts\core.ps1'),[ref]$coreTokens,[ref]$coreErrors)
    $dispatch=@($coreAst.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Invoke-PS'},$false))
    if($coreErrors.Count -or $dispatch.Count -ne 1){throw 'Unexpected dispatcher definition.'}
    $dispatchPath=Join-Path $testRoot 'dispatcher.ps1'
    [IO.File]::WriteAllText($dispatchPath,$dispatch[0].Extent.Text,(New-Object Text.UTF8Encoding $true))
    $probePath=Join-Path $testRoot 'policy probe.ps1'
    $probe=@'
param([string]$Value)
$policies=Get-ExecutionPolicy -List | Select-Object Scope,ExecutionPolicy
$result=[ordered]@{version=$PSVersionTable.PSVersion.ToString();edition=$PSVersionTable.PSEdition;is64=[Environment]::Is64BitProcess;value=$Value;policy=(Get-ExecutionPolicy).ToString();policies=@($policies)}
"@@SONUC "+($result|ConvertTo-Json -Depth 6 -Compress)
'@
    [IO.File]::WriteAllText($probePath,$probe,(New-Object Text.UTF8Encoding $true))
    try{
        . $dispatchPath
        $observed=Invoke-PS 'policy probe.ps1' @('-Value','argument with spaces') 60
        Check ($observed.edition -eq 'Desktop' -and $observed.version -like '5.1.*' -and $observed.is64) 'Dispatcher uses native Windows PowerShell 5.1 x64'
        Check ($observed.value -ceq 'argument with spaces') 'Dispatcher preserves spaced arguments'
        $childPolicyJson=ConvertTo-Json -InputObject @($observed.policies) -Compress
        Check ($childPolicyJson -ceq $policyBeforeJson) 'Dispatcher child inherits all execution policy scopes'
        if($observed.policy -eq 'RemoteSigned'){
            $blockedPath=Join-Path $testRoot 'unsigned remote probe.ps1'
            $blockedMarker=Join-Path $testRoot 'remote-script-ran.txt'
            $blockedCode="[IO.File]::WriteAllText('"+$blockedMarker.Replace("'","''")+"','unexpected execution')"
            [IO.File]::WriteAllText($blockedPath,$blockedCode,(New-Object Text.UTF8Encoding $true))
            Set-Content -LiteralPath $blockedPath -Stream 'Zone.Identifier' -Value "[ZoneTransfer]`r`nZoneId=3" -Encoding ASCII
            $policyRejected=$false
            try{$null=Invoke-PS 'unsigned remote probe.ps1' @() 60}catch{$policyRejected=$true;$policyError=$_.Exception.Message}
            '@@POLICY '+([ordered]@{policy=$observed.policy;rejected=$policyRejected;error=$policyError;marker_exists=(Test-Path -LiteralPath $blockedMarker)}|ConvertTo-Json -Compress)
            Check $policyRejected 'Dispatcher propagates policy rejection without bypass retry'
            Check (-not (Test-Path -LiteralPath $blockedMarker)) 'RemoteSigned blocks unsigned remote probe before execution'
        }else{
            $results.Add([pscustomobject]@{name='Unsigned remote policy rejection';status='NOT_RUN';reason=('Requires RemoteSigned; observed '+$observed.policy)})
        }
        $policyAfter=Get-ExecutionPolicy -List | Select-Object Scope,ExecutionPolicy
        Check ((ConvertTo-Json -InputObject @($policyAfter) -Compress) -ceq $policyBeforeJson) 'Parent execution policy scopes unchanged'
    }finally{
        # Restore production definitions and fixture state before orchestration checks.
        . (Join-Path $skill 'scripts\core.ps1')
        $script:StateRoot=Join-Path $testRoot 'state'
    }
    $script:Versions=@{python='1.0.0';node='1.0.0';pnpm='1.0.0';duckdb='1.0.0';powerbi='1.0.0';libraries='1.0.0';pdf='1.0.0'}
    $script:InstallCalls=0
    function Get-Observation([string]$Key,[switch]$LocalOnly,[string]$Cache,[bool]$Repair=$false){
        return [pscustomobject]@{local=[ordered]@{version=$script:Versions[$Key];path=('fixture/'+$Key)};surum=$script:Versions[$Key];target=$(if($LocalOnly){$null}else{[pscustomobject]@{version='2.0.0';repair=$Repair}});blocked=$false;matched=0;health='NOT_RUN'}
    }
    function Discover-Runtimes {$script:Python='fixture-python';$script:Node='fixture-node'}
    function Invoke-Selected([string]$Key,$Component,[string]$SessionPath){
        $script:InstallCalls++;$script:Versions[$Key]=$Component.target.version
        return [pscustomobject]@{key=$Key;ozet='GEÇTİ';surum=$Component.target.version;health='PASS'}
    }
    function Remove-LegacySkill {return @([pscustomobject]@{action='fixture-no-mutation'})}
    function Assert-MaintenanceWindow {if($env:GUNCELLEYICI_MAINTENANCE -ne 'confirmed'){throw 'Fixture maintenance guard.'}}
    # Native regression: first creation, repeated atomic replacement, and failure safety.
    $atomicPath=Join-Path $testRoot 'atomic.json'
    Write-AtomicJson $atomicPath @{phase='STARTED'}
    Check ((Get-Content -LiteralPath $atomicPath -Raw -Encoding UTF8|ConvertFrom-Json).phase -eq 'STARTED') 'Atomic JSON first creation'
    Write-AtomicJson $atomicPath @{phase='APPLYING'}
    Check ((Get-Content -LiteralPath $atomicPath -Raw -Encoding UTF8|ConvertFrom-Json).phase -eq 'APPLYING') 'Atomic JSON existing file replacement'
    $atomicBefore=File-Sha256 $atomicPath
    $atomicLock=[IO.File]::Open($atomicPath,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    $atomicRejected=$false
    try{
        try{Write-AtomicJson $atomicPath @{phase='SHOULD_NOT_WRITE'}}catch{$atomicRejected=$true}
    }finally{$atomicLock.Dispose()}
    Check $atomicRejected 'Atomic JSON locked destination rejects replacement'
    Check ((File-Sha256 $atomicPath) -ceq $atomicBefore) 'Atomic JSON failed replacement preserves original'
    Check (@(Get-ChildItem -LiteralPath $testRoot -Filter '.write-*' -File).Count -eq 0) 'Atomic JSON temporary files cleared after failure'
    $scan=Build-Plan $false @()
    Check ($scan.rows.Count -eq 7) 'Seven rows including optional PDF'
    Check (@($scan.rows|Where-Object {$_.key -eq 'offer'}).Count -eq 0) 'Removed offer component absent from scan'
    $removedRejected=$false
    try{$null=Apply-Plan $scan.plan_file $scan.fingerprint @('offer') $true $true}catch{$removedRejected=$true}
    Check ($removedRejected -and $script:InstallCalls -eq 0) 'Former offer selection rejected before installation'
    $removedRejected=$false
    try{$null=Verify-Selected @('offer')}catch{$removedRejected=$true}
    Check $removedRejected 'Former offer verification rejected'
    Check ($scan.status -eq 'selection_required') 'Update candidates returned'
    Check ($script:InstallCalls -eq 0) 'Scan never invokes install'
    Check (-not (Test-Path -LiteralPath $script:StateRoot)) 'Scan does not persist installation state'
    Check (-not @($scan.rows|Where-Object {$_.key -eq 'pdf'})[0].secili) 'PDF is opt-in'
    $rejected=$false
    try{$null=Apply-Plan $scan.plan_file ('0'*64) @('node') $true $true}catch{$rejected=$true}
    Check $rejected 'Changed plan rejected'
    Check ($script:InstallCalls -eq 0) 'Changed plan has no install calls'
    $rejected=$false
    try{$null=Apply-Plan $scan.plan_file $scan.fingerprint @('bad') $true $true}catch{$rejected=$true}
    Check $rejected 'Unknown selection rejected'
    $rejected=$false
    try{$null=Apply-Plan $scan.plan_file $scan.fingerprint @('node') $true $false}catch{$rejected=$true}
    Check $rejected 'Apply without explicit confirmation rejected'
    Check ($script:InstallCalls -eq 0) 'Unconfirmed apply has no install calls'
    $cancel=Apply-Plan $scan.plan_file $scan.fingerprint @() $true $false
    Check ($cancel.status -eq 'cancelled') 'Empty selection cancels'
    $script:Versions.node='1.0.1'
    $stale=Apply-Plan $scan.plan_file $scan.fingerprint @('node') $true $true
    Check ($stale.status -eq 'stale') 'Local change detected under lock'
    Check ($script:InstallCalls -eq 0) 'Stale local state not installed'
    $script:Versions.node='1.0.0'
    $done=Apply-Plan $scan.plan_file $scan.fingerprint @('node') $true $true
    Check ($done.status -eq 'completed') 'Approved fixture installation completes'
    Check ($script:InstallCalls -eq 1) 'Only selected component invoked'
    Check ($done.maintenance.Count -eq 1) 'Maintenance result retained'
    Check ((Get-Content -LiteralPath $done.report -Raw|ConvertFrom-Json).rows.Count -eq 7) 'Audit result contains final rows'
    Check (-not (Test-Path -LiteralPath (Join-Path $script:StateRoot 'active-transaction.json'))) 'Completed transaction journal cleared'
    $guard=Enter-Guard
    try{
        $blocked=$false;try{$second=Enter-Guard;$second.Dispose()}catch{$blocked=$true}
        Check $blocked 'Shared update guard rejects second writer'
    }finally{$guard.Dispose()}
    $sample=[pscustomobject]@{tools=@([pscustomobject]@{name='single'})}
    $value=Read-Field $sample 'tools'
    Check ($value -is [array] -and $value.Count -eq 1) 'Single-item arrays preserved by field reader'
    & (Join-Path $PSScriptRoot 'test_pnpm.ps1')
    & (Join-Path $PSScriptRoot 'test_scan.ps1')
    $summary=[ordered]@{suite='Windows PowerShell 5.1 offline syntax/orchestration';status='PASS';assertions=$results.Count;results=$results.ToArray();live_installations='NOT_RUN';excel_com='NOT_RUN';authenticode_chain='NOT_RUN';pdf_native_extension='NOT_RUN'}
    '@@TEST '+($summary|ConvertTo-Json -Depth 8 -Compress)
}finally{
    $env:LOCALAPPDATA=$oldLocal;$env:USERPROFILE=$oldProfile;$env:TEMP=$oldTemp
    if(Test-Path -LiteralPath $testRoot){Remove-Item -LiteralPath $testRoot -Recurse -Force}
}
