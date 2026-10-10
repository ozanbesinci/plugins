#requires -Version 5.1
# pnpm detection/staging regressions on production functions; offline fixtures only.
# No real pnpm/node binary is executed: Invoke-Native is replaced by a fixture process model.
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
    $found=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $Name},$false))
    if($errors.Count -or $found.Count -ne 1){throw ('Unexpected function: '+$Name)}
    return $found[0].Extent.Text
}
. (Join-Path $skill 'scripts\core.ps1')
foreach($name in 'Test-NativePnpm','ProbePnpm','Find-Pnpm','Read-Block','Save-TgzMember','Install-NativePnpm'){
    . ([scriptblock]::Create((Function-Source 'pnpm-kur.ps1' $name)))
}
$NATIVE_PAKET='@pnpm/exe.win32-x64'
function New-TarGz([string]$Path,[object[]]$Entries,[int]$Cut=0){
    # Builds a minimal ustar .tgz fixture; never contains executable code.
    $ms=New-Object IO.MemoryStream
    foreach($e in $Entries){
        $data=[byte[]]$e.data;$h=New-Object byte[] 512
        $n=[Text.Encoding]::ASCII.GetBytes($e.name);[Array]::Copy($n,$h,$n.Length)
        $s=[Text.Encoding]::ASCII.GetBytes([Convert]::ToString($data.Length,8).PadLeft(11,'0'));[Array]::Copy($s,0,$h,124,11)
        $h[156]=[byte][char]$e.type
        $m=[Text.Encoding]::ASCII.GetBytes('ustar');[Array]::Copy($m,0,$h,257,5)
        $ms.Write($h,0,512);$ms.Write($data,0,$data.Length)
        $pad=(512-($data.Length%512))%512;if($pad){$ms.Write((New-Object byte[] $pad),0,$pad)}
    }
    $ms.Write((New-Object byte[] 1024),0,1024)
    $bytes=$ms.ToArray();if($Cut){$bytes=[byte[]]$bytes[0..($Cut-1)]}
    $out=[IO.File]::Create($Path);$gz=New-Object IO.Compression.GZipStream($out,[IO.Compression.CompressionMode]::Compress)
    try{$gz.Write($bytes,0,$bytes.Length)}finally{$gz.Dispose();$out.Dispose()}
}
function Tar-Entry([string]$Name,[string]$Text,[string]$Type='0'){return [pscustomobject]@{name=$Name;data=[Text.Encoding]::ASCII.GetBytes($Text);type=$Type}}
function Rejects([scriptblock]$Block){try{& $Block;return $false}catch{return $true}}
# Retain the production HTTP helper. Replace only HTTP transport with JSON-shaped fixtures.
function Invoke-RestMethod {
    param($Uri,$Method,$MaximumRedirection,$TimeoutSec,$Headers,[switch]$UseBasicParsing,$ErrorAction)
    if($Uri -eq 'https://registry.npmjs.org/pnpm/latest'){return $script:PnpmMetadata}
    if($Uri -eq 'https://registry.npmjs.org/@pnpm/exe.win32-x64/12.9.1'){return $script:PnpmExeMetadata}
    throw ('Unexpected offline request: '+$Uri)
}
$rawRoot=Join-Path $env:TEMP ('p-'+[guid]::NewGuid().ToString('N').Substring(0,8))
[void][IO.Directory]::CreateDirectory($rawRoot)
# Canonical (long) root: TEMP can be an 8.3 short path on real user profiles.
$testRoot=(Get-Item -LiteralPath $rawRoot -Force).FullName
$utf8=New-Object Text.UTF8Encoding $false
function Write-Fixture([string]$Path,[string]$Text){[void][IO.Directory]::CreateDirectory((Split-Path $Path -Parent));[IO.File]::WriteAllText($Path,$Text,$utf8)}
$oldCulture=[Threading.Thread]::CurrentThread.CurrentCulture
$savedInvokeNative=${function:Invoke-Native}
try{
    # Layout copied from real 2.2.1 evidence: Local\Programs\pnpm 12.6.0 native, Roaming\npm 11.8.0 JS entry.
    $nativeManifest='{"name":"pnpm","version":"12.6.0","bin":{"pnpm":"pnpm.exe","pn":"pn.exe","pnpx":"pnpx.exe","pnx":"pnx.exe"},"optionalDependencies":{"@pnpm/exe.win32-x64":"12.6.0"}}'
    $localRoot=Join-Path $testRoot 'Local\Programs\pnpm';$roamingRoot=Join-Path $testRoot 'Roaming\npm'
    Write-Fixture (Join-Path $localRoot 'node_modules\pnpm\package.json') $nativeManifest
    Write-Fixture (Join-Path $localRoot 'node_modules\pnpm\pnpm.exe') 'native-12.6.0'
    Write-Fixture (Join-Path $localRoot 'pnpm.cmd') 'fixture shim; never executed'
    Write-Fixture (Join-Path $roamingRoot 'node_modules\pnpm\package.json') '{"name":"pnpm","version":"11.8.0","bin":{"pnpm":"bin/pnpm.mjs"}}'
    Write-Fixture (Join-Path $roamingRoot 'node_modules\pnpm\bin\pnpm.mjs') 'js-11.8.0'
    $script:NativeCalls=New-Object System.Collections.Generic.List[string]
    # Fixture process model: node runs only js-* files, native-* files run only directly (node pnpm.exe fails like real Windows).
    function Invoke-Native([string]$Exe,[string[]]$Arguments,[int]$TimeoutSeconds=120){
        $script:NativeCalls.Add(($Exe+'|'+($Arguments -join '|')))
        $file=if($Exe -ceq 'fixture-node'){$Arguments[0]}else{$Exe}
        $text=[IO.File]::ReadAllText($file)
        if($text -match '^(?:native|js)-(\d+\.\d+\.\d+)$' -and (($Exe -ceq 'fixture-node') -eq ($text -like 'js-*'))){return [pscustomobject]@{ExitCode=0;Output=($Matches[1]+"`r`n");Error=''}}
        return [pscustomobject]@{ExitCode=1;Output='';Error='fixture launcher would download a binary'}
    }
    function Get-PathFolders {return @($localRoot,$roamingRoot)}
    $KURULUM_KLASORU=$localRoot;$NodeYolu='fixture-node'
    $found=Find-Pnpm
    Check ($found.version -ceq '12.6.0' -and $found.native -and $found.path_visible -and -not (Read-Field $found 'unmanaged' $false)) 'pnpm 12 native install (2.2.1 evidence layout) detected with version, not unmanaged'
    Check (@($script:NativeCalls|Where-Object {$_ -like 'fixture-node|*pnpm.exe*'}).Count -eq 0) 'pnpm native binary is never passed to node as a script'
    $NodeYolu=$null
    Check ((Find-Pnpm).version -ceq '12.6.0') 'pnpm native probe does not require Node.js'
    $NodeYolu='fixture-node'
    function Get-PathFolders {return @($roamingRoot)}
    Check ((Find-Pnpm).version -ceq '11.8.0') 'pnpm JS-entry install still probed through explicit Node'
    # Staging after npm --ignore-scripts: published 12.9.1 bin map (registry evidence) points at JS launcher placeholders.
    $stageFixture=Join-Path $testRoot 'stage';$bins=@('pn','pnx','pnpm','pnpx')
    Write-Fixture (Join-Path $stageFixture 'node_modules\pnpm\package.json') '{"name":"pnpm","version":"12.9.1","bin":{"pn":"pn","pnx":"pnx","pnpm":"pnpm","pnpx":"pnpx"},"optionalDependencies":{"@pnpm/exe.win32-x64":"12.9.1"}}'
    foreach($b in $bins){
        Write-Fixture (Join-Path $stageFixture ('node_modules\pnpm\'+$b)) 'js-12.9.1'
        Write-Fixture (Join-Path $stageFixture ($b+'.cmd')) ('@"%~dp0\node.exe" "%~dp0\node_modules\pnpm\'+$b+'" %*')
    }
    $script:NativeCalls.Clear()
    Check ($null -eq (ProbePnpm $stageFixture) -and $script:NativeCalls.Count -eq 0) 'pnpm ignore-scripts placeholder launcher is never executed and cannot pass staging'
    $nativeExe=Join-Path $testRoot 'pnpm-native.exe';Write-Fixture $nativeExe 'native-12.9.1'
    Install-NativePnpm $stageFixture $nativeExe
    $staged=ProbePnpm $stageFixture
    Check ($staged.version -ceq '12.9.1' -and $staged.native) 'pnpm staging passes after verified native binary placement'
    $shimsOk=$true
    foreach($b in $bins){
        $cmd=[IO.File]::ReadAllText((Join-Path $stageFixture ($b+'.cmd')))
        $ps1=[IO.File]::ReadAllText((Join-Path $stageFixture ($b+'.ps1')))
        $sh=[IO.File]::ReadAllText((Join-Path $stageFixture $b))
        $exeText=[IO.File]::ReadAllText((Join-Path $stageFixture ('node_modules\pnpm\'+$b+'.exe')))
        if(-not $cmd.Contains('node_modules\pnpm\'+$b+'.exe') -or $cmd.ToLowerInvariant().Contains('node.exe') -or
           -not $ps1.Contains('/node_modules/pnpm/'+$b+'.exe') -or -not $sh.Contains('/node_modules/pnpm/'+$b+'.exe') -or $exeText -cne 'native-12.9.1'){$shimsOk=$false}
    }
    Check $shimsOk 'pnpm npm launcher shims are replaced by direct native shims for all four published bins'
    $badBin=Join-Path $testRoot 'badbin';Write-Fixture (Join-Path $badBin 'node_modules\pnpm\package.json') '{"name":"pnpm","bin":{"pnpm":"pnpm","..\\x":"x"}}'
    Check (Rejects {Install-NativePnpm $badBin $nativeExe}) 'pnpm native shim generation rejects unsafe bin names'
    # Member order and types mirror the verified exe.win32-x64-12.9.1.tgz listing.
    $exeTgz=Join-Path $testRoot 'exe.tgz';$payload='native-12.9.1'+('x'*700)
    New-TarGz $exeTgz @((Tar-Entry 'package/LICENSE' 'MIT'),(Tar-Entry 'package/pnpm.exe' $payload),(Tar-Entry 'package/package.json' '{}'),(Tar-Entry 'package/THIRD-PARTY-NOTICES.md' 'n'))
    $outExe=Join-Path $testRoot 'out.exe';Save-TgzMember $exeTgz 'package/pnpm.exe' $outExe
    Check ([IO.File]::ReadAllText($outExe) -ceq $payload) 'pnpm native binary extracted byte-exact from verified tgz'
    $tgzCases=@(
        @{name='link entry';entries=@((Tar-Entry 'package/pnpm.exe' '' '2'))},
        @{name='duplicate entry';entries=@((Tar-Entry 'package/pnpm.exe' 'a'),(Tar-Entry 'package/pnpm.exe' 'b'))},
        @{name='PAX path override';entries=@((Tar-Entry 'PaxHeader' "30 path=package/other.exe`n" 'x'),(Tar-Entry 'package/pnpm.exe' 'a'))},
        @{name='missing binary';entries=@((Tar-Entry 'package/pnpm' 'a'))}
    )
    foreach($case in $tgzCases){
        $badTgz=Join-Path $testRoot ('bad-'+[guid]::NewGuid().ToString('N')+'.tgz');New-TarGz $badTgz $case.entries
        Check (Rejects {Save-TgzMember $badTgz 'package/pnpm.exe' ($badTgz+'.exe')}) ('pnpm tgz rejects '+$case.name)
    }
    $badTgz=Join-Path $testRoot 'truncated.tgz';New-TarGz $badTgz @((Tar-Entry 'package/pnpm.exe' ('y'*2000))) 1024
    Check (Rejects {Save-TgzMember $badTgz 'package/pnpm.exe' ($badTgz+'.exe')}) 'pnpm tgz rejects truncated binary'
    $broken=Join-Path $testRoot 'broken'
    Write-Fixture (Join-Path $broken 'node_modules\pnpm\package.json') $nativeManifest
    Write-Fixture (Join-Path $broken 'node_modules\pnpm\pnpm.exe') 'corrupt'
    Write-Fixture (Join-Path $broken 'pnpm.cmd') 'fixture shim; never executed'
    function Get-PathFolders {return @($broken)}
    $u=Find-Pnpm
    Check ($u.unmanaged -and $u.path_visible -and $u.manifest_version -ceq '12.6.0' -and $null -eq $u.version) 'pnpm unverifiable install stays unmanaged but keeps PATH visibility and claimed version'
    Check ((Get-DisplayVersion 'pnpm' ([pscustomobject]@{surum=$null;local=[pscustomobject]@{version=$null;unmanaged=$true}})) -ceq 'Yüklü · sürüm doğrulanamadı') 'Found but unverifiable pnpm is not reported as not installed'
    Check ((Get-DisplayVersion 'pnpm' ([pscustomobject]@{surum=$null;local=[pscustomobject]@{version=$null;unmanaged=$false}})) -ceq 'Yüklü değil / doğrulanamadı') 'Absent pnpm is still reported as not installed'
    ${function:Invoke-Native}=$savedInvokeNative
    # Production scan branch, executed from its AST with an unknown shim that must stay unmanaged.
    $script:PnpmRoot=Join-Path $testRoot 'pnpm';[void][IO.Directory]::CreateDirectory($script:PnpmRoot)
    [IO.File]::WriteAllText((Join-Path $script:PnpmRoot 'pnpm.cmd'),'fixture shim; never executed')
    function Get-PathFolders {return @($script:PnpmRoot)}
    function ProbePnpm {return $null}
    $KURULUM_KLASORU=$script:PnpmRoot;$NodeYolu='fixture-node'
    $installed=Find-Pnpm
    Check ([bool]$installed.unmanaged) 'pnpm unknown fixture shim remains unmanaged'
    $local=[pscustomobject]@{version=$null;path=$installed.path;node=$NodeYolu;unmanaged=[bool]$installed.unmanaged;path_visible=$false;manifest_version=$null}
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
    Check ([string]$script:PnpmResult.neden -like '*doğrulanamadı*' -and [string]$script:PnpmResult.neden -like ('*'+$installed.path+'*')) 'pnpm unmanaged block always carries a visible reason'
    foreach($bad in @('sha512-!','SHA512-AAAA','sha512-ıAAA','sha512-İAAA')){
        $script:PnpmMetadata.dist.integrity=$bad;. $scanBranch
        Check ($null -eq $script:PnpmResult.target -and $script:PnpmResult.blocked) ('pnpm invalid integrity rejected: '+$bad)
    }
    # Shape of the real 12.9.1 registry metadata (registry-package-evidence.json).
    $exeUrl='https://registry.npmjs.org/@pnpm/exe.win32-x64/-/exe.win32-x64-12.9.1.tgz'
    $script:PnpmMetadata=[pscustomobject]@{name='pnpm';version='12.9.1';bin=[pscustomobject]@{pn='pn';pnx='pnx';pnpm='pnpm';pnpx='pnpx'};optionalDependencies=[pscustomobject]@{'@pnpm/exe.win32-x64'='12.9.1'};dist=@{tarball='https://registry.npmjs.org/pnpm/-/pnpm-12.9.1.tgz';integrity=$integrity};engines=@{node='>=18.*'}}
    $script:PnpmExeMetadata=[pscustomobject]@{name='@pnpm/exe.win32-x64';version='12.9.1';dist=@{tarball=$exeUrl;integrity=$integrity}}
    . $scanBranch
    Check ($script:PnpmResult.target.native.url -ceq $exeUrl -and $script:PnpmResult.target.native.integrity -ceq $integrity -and $script:PnpmResult.target.native.version -ceq '12.9.1') 'pnpm 12 plan pins native binary package URL and SHA-512'
    $script:PnpmExeMetadata.dist.tarball='https://registry.npmjs.org/@pnpm/exe.win32-x64/-/exe.win32-x64-12.9.0.tgz';. $scanBranch
    Check ($null -eq $script:PnpmResult.target -and [string]$script:PnpmResult.neden -like '*metadata*') 'pnpm native tarball URL mismatch rejected with reason'
    $script:PnpmExeMetadata.dist.tarball=$exeUrl;$script:PnpmMetadata.optionalDependencies.'@pnpm/exe.win32-x64'='12.9.0';. $scanBranch
    Check ($null -eq $script:PnpmResult.target) 'pnpm native optional dependency version mismatch rejected'
}finally{
    [Threading.Thread]::CurrentThread.CurrentCulture=$oldCulture
    ${function:Invoke-Native}=$savedInvokeNative
    $resolved=[IO.Path]::GetFullPath($rawRoot)
    $tempPrefix=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\'
    if(-not $resolved.StartsWith($tempPrefix,[StringComparison]::OrdinalIgnoreCase)){throw 'Fixture cleanup path escaped TEMP.'}
    if(Test-Path -LiteralPath $resolved){Remove-Item -LiteralPath $resolved -Recurse -Force}
}
Check ([Threading.Thread]::CurrentThread.CurrentCulture.Name -ceq $oldCulture.Name) 'pnpm regressions restore process culture'
$summary=[ordered]@{suite='Windows PowerShell 5.1 offline pnpm regressions';status='PASS';assertions=$results.Count;results=$results.ToArray();installations='NOT_RUN';binary_execution='NOT_RUN';network='NOT_RUN'}
'@@PNPM_TEST '+($summary|ConvertTo-Json -Depth 8 -Compress)
