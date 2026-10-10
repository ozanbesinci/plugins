#requires -Version 5.1
# Explicit release acceptance only; installs into an owned temporary prefix, never the live runtime.
param([Parameter(Mandatory=$true)][string]$InputFile)
$ErrorActionPreference='Stop'
$skill=Split-Path $PSScriptRoot -Parent
. (Join-Path $skill 'scripts\program-ortak.ps1')
Assert-SupportedPlatform
$inputData=Get-Content -LiteralPath $InputFile -Raw -Encoding UTF8|ConvertFrom-Json
function Load-Function([string]$Name){
    $tokens=$null;$errors=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $skill 'scripts\pnpm-kur.ps1'),[ref]$tokens,[ref]$errors)
    $matches=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $Name},$false))
    if($errors.Count -or $matches.Count -ne 1){throw ('Unexpected function: '+$Name)}
    return $matches[0].Extent.Text
}
foreach($name in 'Test-NativePnpm','ProbePnpm','Get-Sha512Integrity','Read-Block','Save-TgzMember','Install-NativePnpm'){
    . ([scriptblock]::Create((Load-Function $name)))
}
$NATIVE_PAKET='@pnpm/exe.win32-x64'
$NodeYolu=[string]$inputData.node
$version=[string]$inputData.version
$null=Stable-Version $version
if($inputData.url -cne "https://registry.npmjs.org/pnpm/-/pnpm-$version.tgz" -or
   $inputData.native_url -cne "https://registry.npmjs.org/@pnpm/exe.win32-x64/-/exe.win32-x64-$version.tgz"){throw 'Untrusted input package URL.'}
if((Get-Sha512Integrity $inputData.archive) -cne $inputData.integrity -or
   (Get-Sha512Integrity $inputData.native_archive) -cne $inputData.native_integrity){throw 'Input SHA-512 mismatch.'}
$tempBase=(Get-Item -LiteralPath $env:TEMP).FullName
$taskRoot=Join-Path $tempBase ('gp-'+[guid]::NewGuid().ToString('N').Substring(0,12))
# A short owned root keeps npm's long SHA-512 cache paths inside the PS5.1 limit.
$null=New-Item -ItemType Directory -Path $taskRoot -ErrorAction Stop
$stage=Join-Path $taskRoot 'stage'
$exe=Join-Path $taskRoot 'verified-pnpm.exe'
$checks=New-Object System.Collections.Generic.List[string]
$passed=$false
try{
    $config=Join-Path $taskRoot 'user.npmrc';[IO.File]::WriteAllText($config,'')
    $globalConfig=Join-Path $taskRoot 'global.npmrc';[IO.File]::WriteAllText($globalConfig,'')
    $npm=Join-Path (Split-Path $NodeYolu -Parent) 'node_modules\npm\bin\npm-cli.js'
    $r=Invoke-Native $NodeYolu @($npm,'install','--global','--prefix',$stage,$inputData.archive,
       '--offline','--ignore-scripts','--omit=optional','--engine-strict','--no-audit','--no-fund',
       '--registry=https://registry.npmjs.org','--cache',(Join-Path $taskRoot 'cache'),
       '--userconfig',$config,'--globalconfig',$globalConfig) 600
    if($r.ExitCode -ne 0){throw ('Offline staging failed: '+(Hide-Secrets ($r.Error+$r.Output)))}
    $checks.Add('Real npm offline/ignore-scripts/omit-optional installation')
    if(ProbePnpm $stage){throw 'Unverified placeholder launcher accepted.'}
    $checks.Add('Placeholder rejected without executing the launcher')
    Save-TgzMember $inputData.native_archive 'package/pnpm.exe' $exe
    Install-NativePnpm $stage $exe
    $probe=ProbePnpm $stage
    if(-not $probe -or $probe.version -cne $version -or -not $probe.native){throw 'Native pnpm version mismatch.'}
    $checks.Add('Real verified native executable version')
    foreach($name in 'pn','pnx','pnpm','pnpx'){
        if(-not (Test-Path -LiteralPath (Join-Path $stage ($name+'.cmd'))) -or
           -not (Test-Path -LiteralPath (Join-Path $stage ($name+'.ps1')))){throw ('Missing shim: '+$name)}
    }
    $checks.Add('All four native command shims present')
    $cmd=Join-Path $stage 'pnpm.cmd'
    $cmdOutput=(& $cmd --version 2>&1|Out-String).Trim()
    if($LASTEXITCODE -ne 0 -or $cmdOutput -cne $version){throw 'CMD shim failed.'}
    $checks.Add('Real pnpm.cmd --version')
    $ps=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $r=Invoke-Native $ps @('-NoProfile','-File',(Join-Path $stage 'pnpm.ps1'),'--version') 60
    if($r.ExitCode -ne 0 -or $r.Output.Trim() -cne $version){throw 'PowerShell shim failed.'}
    $checks.Add('Real pnpm.ps1 --version with inherited execution policy')
    $passed=$true
    $result=@{status='PASS';version=$version;assertions=$checks.Count;checks=$checks.ToArray();
       live_installation='NOT_RUN';staging='real temporary prefix';network_installation=$false;
       integrity='both npm tarballs SHA-512 verified'}
}finally{
    $absolute=[IO.Path]::GetFullPath($taskRoot)
    $allowed=[IO.Path]::GetFullPath($tempBase).TrimEnd('\')+'\'
    if(-not $absolute.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase) -or
       (Split-Path $absolute -Leaf) -notmatch '^gp-[a-f0-9]{12}$'){throw 'Cleanup escaped owned TEMP prefix.'}
    if($passed){Remove-Item -LiteralPath $absolute -Recurse -Force}
}
'@@NATIVE_PNPM '+($result|ConvertTo-Json -Compress)
