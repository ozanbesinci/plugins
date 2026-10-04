#requires -Version 5.1
# Production function/branch regressions using offline responses and temporary files.
param()
$ErrorActionPreference='Stop'
$skill=Split-Path $PSScriptRoot -Parent
$results=New-Object System.Collections.Generic.List[object]
function Check([bool]$Condition,[string]$Name){
    if(-not $Condition){throw "FAIL: $Name"}
    $results.Add([pscustomobject]@{name=$Name;status='PASS'})
}
function Function-Source([string]$File,[string]$Name){
    $tokens=$null;$errors=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $skill ('scripts\'+$File)),[ref]$tokens,[ref]$errors)
    $matches=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $Name},$false))
    if($errors.Count -or $matches.Count -ne 1){throw ('Unexpected function: '+$Name)}
    return $matches[0].Extent.Text
}
. (Join-Path $skill 'scripts\core.ps1')
. ([scriptblock]::Create((Function-Source 'python-kur.ps1' 'Python-Target')))
. ([scriptblock]::Create((Function-Source 'node-kur.ps1' 'NodeTarget')))
. ([scriptblock]::Create((Function-Source 'powerbi-mcp-kur.ps1' 'PbiLocal')))
. ([scriptblock]::Create((Function-Source 'pnpm-kur.ps1' 'Find-Pnpm')))
# Retain the production HTTP helper. Replace only HTTP transport with JSON-shaped fixtures.
function Invoke-RestMethod {
    param($Uri,$Method,$MaximumRedirection,$TimeoutSec,$Headers,[switch]$UseBasicParsing,$ErrorAction)
    if($Uri -like '*release_file/*'){return ,$script:Files}
    if($Uri -like '*downloads/release/*'){return ,$script:Releases}
    if($Uri -eq 'https://nodejs.org/dist/index.json'){return ,$script:NodeReleases}
    if($Uri -eq 'https://registry.npmjs.org/pnpm/latest'){return $script:PnpmMetadata}
    throw ('Unexpected offline request: '+$Uri)
}
function Invoke-WebRequest {
    param($Uri,[switch]$UseBasicParsing,$TimeoutSec,$ErrorAction)
    if($Uri -notlike 'https://nodejs.org/dist/v*/SHASUMS256.txt'){throw 'Unexpected checksum request.'}
    return [pscustomobject]@{Content=$script:NodeSums}
}
$hash='a'*64
$script:Releases=@([pscustomobject]@{name='Python 3.14.8';resource_uri='/api/v2/downloads/release/8/'})
$script:Files=@([pscustomobject]@{url='https://www.python.org/ftp/python/3.14.8/python-3.14.8-amd64.exe';sha256_sum=$hash;filesize=12345})
$p=Python-Target
Check ($p.version -ceq '3.14.8' -and $p.size -eq 12345 -and $p.sha256 -ceq $hash) 'Python single release and file arrays select scalar target'
$script:Releases=@([pscustomobject]@{name='Python 3.15.0';resource_uri='/release/9/'},$script:Releases[0],[pscustomobject]@{name='Python 3.14.7';resource_uri='/release/7/'})
$script:Files=@([pscustomobject]@{url='https://www.python.org/ftp/python/3.14.8/python-3.14.8-arm64.exe';sha256_sum=$hash;filesize=88},$script:Files[0])
Check ((Python-Target).version -ceq '3.14.8') 'Python multiple releases/files retain supported amd64 selection'
$savedFiles=$script:Files;$script:Files=@();$rejected=$false
try{$null=Python-Target}catch{$rejected=$true}
Check $rejected 'Python empty file array rejected'
$script:Files=$savedFiles;$script:Files[1].sha256_sum='bad';$rejected=$false
try{$null=Python-Target}catch{$rejected=$true}
Check $rejected 'Python invalid checksum rejected'
$script:Releases=@();$rejected=$false
try{$null=Python-Target}catch{$rejected=$true}
Check $rejected 'Python empty release array rejected'
$script:NodeReleases=@([pscustomobject]@{version='v24.21.0';lts='Krypton';files=@('win-x64-zip')})
$script:NodeSums=$hash+'  node-v24.21.0-win-x64.zip'
Check ((NodeTarget).version -ceq '24.21.0') 'Node single release array selects scalar LTS target'
$script:NodeReleases=@([pscustomobject]@{version='v25.9.0';lts=$false;files=@('win-x64-zip')},$script:NodeReleases[0],[pscustomobject]@{version='v24.20.0';lts='Krypton';files=@('win-x64-zip')})
Check ((NodeTarget).version -ceq '24.21.0') 'Node multiple releases select newest compatible LTS'
$script:NodeSums='bad checksum';$rejected=$false
try{$null=NodeTarget}catch{$rejected=$true}
Check $rejected 'Node missing checksum rejected'
$script:NodeReleases=@();$rejected=$false
try{$null=NodeTarget}catch{$rejected=$true}
Check $rejected 'Node empty release array rejected'
$packages=@(1..12 | ForEach-Object {[pscustomobject]@{name=('package'+$_);version='2.0.0'}})
$locals=[ordered]@{};foreach($pkg in $packages){$locals[$pkg.name]=@{version=$pkg.version}}
$before=[pscustomobject]@{packages=$locals};$target=[pscustomobject]@{packages=$packages}
Check (@(Get-LibraryEffects $before $target $false).Count -eq 0) 'Twelve matching libraries produce no changes'
$effects=@(Get-LibraryEffects $before $target $true)
Check ($effects.Count -eq 12 -and @($effects.package|Select-Object -Unique).Count -eq 12 -and @($effects|Where-Object {$_.action -ne 'reinstall' -or $_.from -cne $_.to}).Count -eq 0) 'Repair produces twelve separate equal-version reinstall effects'
$locals.package1.version='1.0.0';$locals.package2.version='3.0.0';$locals.Remove('package3')
$effects=@(Get-LibraryEffects $before $target $false)
Check ($effects.Count -eq 3) 'Only changed or missing libraries produce effects'
Check ($effects[0].package -ceq 'package1' -and $effects[0].action -ceq 'upgrade') 'Library upgrade preserves individual name'
Check ($effects[1].package -ceq 'package2' -and $effects[1].action -ceq 'downgrade') 'Library downgrade preserves individual name'
Check ($effects[2].package -ceq 'package3' -and $effects[2].action -ceq 'install' -and $null -eq $effects[2].from) 'Missing library produces install effect'
Check (@(Get-LibraryEffects $before ([pscustomobject]@{packages=@()}) $false).Count -eq 0) 'Empty library list produces no effects'
$single=@(Get-LibraryEffects ([pscustomobject]@{packages=@{}}) ([pscustomobject]@{packages=@($packages[0])}) $false)
Check ($single.Count -eq 1 -and $single[0].package -ceq 'package1') 'Single library array retains package identity'
$testRoot=Join-Path $env:TEMP ('s-'+[guid]::NewGuid().ToString('N').Substring(0,8))
[void][IO.Directory]::CreateDirectory($testRoot)
$oldEnv=@{};foreach($key in @('USERPROFILE','APPDATA','LOCALAPPDATA','CODEX_HOME','CLAUDE_CONFIG_DIR')){$oldEnv[$key]=[Environment]::GetEnvironmentVariable($key,'Process')}
$oldCulture=[Threading.Thread]::CurrentThread.CurrentCulture
$oldHome=$HOME
try{
    $env:USERPROFILE=Join-Path $testRoot 'profile';$env:APPDATA=Join-Path $testRoot 'roaming';$env:LOCALAPPDATA=Join-Path $testRoot 'local'
    $env:CODEX_HOME=$null;$env:CLAUDE_CONFIG_DIR=$null
    $KOK=Join-Path $env:LOCALAPPDATA 'Programs\PowerBIModelingMCP';$EXE_REL='extension\server\powerbi-modeling-mcp.exe'
    # Keep discovery wholly inside the fixture, including the fixed machine location.
    function Test-Path {
        param([string]$LiteralPath,[string]$Path)
        $candidate=if($LiteralPath){$LiteralPath}else{$Path}
        if($candidate -like 'C:\MCPServers\PowerBIModelingMCP*'){return $false}
        return Microsoft.PowerShell.Management\Test-Path -LiteralPath $candidate
    }
    $missing=PbiLocal
    Check ($null -eq $missing.version -and $HOME -ceq $oldHome) 'Power BI absent fixture succeeds without HOME collision'
    $server=Join-Path $KOK '1.0.0\extension\server';[void][IO.Directory]::CreateDirectory($server)
    $exe=Join-Path $server 'powerbi-modeling-mcp.exe';[IO.File]::WriteAllText($exe,'fixture bytes; never executed')
    [IO.File]::WriteAllText((Join-Path (Split-Path $server -Parent) 'package.json'),'{"name":"powerbi-modeling-mcp","version":"1.0.0"}')
    $codex=Join-Path $env:USERPROFILE '.codex';[void][IO.Directory]::CreateDirectory($codex)
    $config=Join-Path $codex 'config.toml';[IO.File]::WriteAllText($config,'fixture-config')
    $configHash=File-Sha256 $config
    $pbi=PbiLocal
    Check ($pbi.version -ceq '1.0.0' -and $pbi.path -ceq $exe) 'Power BI fixture metadata and binary discovered without server launch'
    Check ($pbi.config_hashes[$config] -ceq $configHash -and (File-Sha256 $config) -ceq $configHash -and $HOME -ceq $oldHome) 'Power BI default config discovery preserves config and HOME'
    $env:CODEX_HOME=Join-Path $testRoot 'custom codex';[void][IO.Directory]::CreateDirectory($env:CODEX_HOME)
    $custom=Join-Path $env:CODEX_HOME 'config.toml';[IO.File]::WriteAllText($custom,'custom-fixture')
    Check ((PbiLocal).config_hashes.Contains($custom)) 'Power BI honors explicit CODEX_HOME in fixture'
    $script:PnpmRoot=Join-Path $testRoot 'pnpm';[void][IO.Directory]::CreateDirectory($script:PnpmRoot)
    [IO.File]::WriteAllText((Join-Path $script:PnpmRoot 'pnpm.cmd'),'fixture shim; never executed')
    function Get-PathFolders {return @($script:PnpmRoot)}
    function ProbePnpm {return $null}
    $KURULUM_KLASORU=$script:PnpmRoot;$NodeYolu='fixture-node'
    $installed=Find-Pnpm
    Check ([bool]$installed.unmanaged) 'pnpm unknown fixture shim remains unmanaged'
    $local=[pscustomobject]@{version=$null;path=$installed.path;node=$NodeYolu;unmanaged=[bool]$installed.unmanaged;path_visible=$false}
    function Emit-Result($Object){$script:PnpmResult=$Object}
    $tokens=$null;$errors=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $skill 'scripts\pnpm-kur.ps1'),[ref]$tokens,[ref]$errors)
    $branches=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.IfStatementAst] -and $n.Clauses[0].Item1.Extent.Text -eq '$YalnizBul -or $LocalOnly'},$true))
    if($errors.Count -or $branches.Count -ne 1){throw 'Unexpected pnpm scan branch.'}
    $scanBranch=[scriptblock]::Create($branches[0].Extent.Text);$YalnizBul=$true;$LocalOnly=$false
    [Threading.Thread]::CurrentThread.CurrentCulture=[Globalization.CultureInfo]::GetCultureInfo('tr-TR')
    $integrity='sha512-'+[Convert]::ToBase64String([byte[]](0..63))
    Check ($integrity.Contains('I') -and [Convert]::FromBase64String($integrity.Substring(7)).Length -eq 64) 'SHA512 fixture includes Turkish case-sensitive ASCII I'
    $script:PnpmMetadata=[pscustomobject]@{name='pnpm';version='12.9.1';dist=@{tarball='https://registry.npmjs.org/pnpm/-/pnpm-12.9.1.tgz';integrity=$integrity};engines=@{node='>=18'}}
    . $scanBranch
    Check ($script:PnpmResult.target.integrity -ceq $integrity -and $script:PnpmResult.blocked -and $script:PnpmResult.health -ceq 'NOT_RUN') 'pnpm valid SHA512 accepted in tr-TR while unmanaged guard remains blocked'
    foreach($bad in @('sha512-!','SHA512-AAAA','sha512-ıAAA','sha512-İAAA')){
        $script:PnpmMetadata.dist.integrity=$bad;. $scanBranch
        Check ($null -eq $script:PnpmResult.target -and $script:PnpmResult.blocked) ('pnpm invalid integrity rejected: '+$bad)
    }
}finally{
    [Threading.Thread]::CurrentThread.CurrentCulture=$oldCulture
    foreach($key in $oldEnv.Keys){[Environment]::SetEnvironmentVariable($key,$oldEnv[$key],'Process')}
    $resolved=[IO.Path]::GetFullPath($testRoot)
    $tempPrefix=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\'
    if(-not $resolved.StartsWith($tempPrefix,[StringComparison]::OrdinalIgnoreCase)){throw 'Fixture cleanup path escaped TEMP.'}
    if(Microsoft.PowerShell.Management\Test-Path -LiteralPath $resolved){Remove-Item -LiteralPath $resolved -Recurse -Force}
}
Check ([Threading.Thread]::CurrentThread.CurrentCulture.Name -ceq $oldCulture.Name) 'Scan regressions restore process culture'
$summary=[ordered]@{suite='Windows PowerShell 5.1 offline scan regressions';status='PASS';assertions=$results.Count;results=$results.ToArray();installations='NOT_RUN';server_launch='NOT_RUN'}
'@@SCAN_TEST '+($summary|ConvertTo-Json -Depth 8 -Compress)
