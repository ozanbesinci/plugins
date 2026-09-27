param()
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -Force
$kaynak = Join-Path $PSScriptRoot '..\..\..\skills\guncelleyici\scripts\node-kur.ps1'
$tok=$null; $err=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Resolve-Path $kaynak).Path,[ref]$tok,[ref]$err)
if ($err.Count) { throw $err[0] }
foreach ($f in $ast.FindAll({ param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -in 'ZipKur','Kisalt','Yaz' },$true)) { Invoke-Expression $f.Extent.Text }
function Israrla([scriptblock]$Is) { & $Is }
function Get-AuthenticodeSignature { param($LiteralPath) return @{Status='Valid';SignerCertificate=@{Subject='OpenJS Foundation'}} }
function NodeDogrula { param($Dosya) return @{Surum='24.21.0';Yol=$Dosya} }
function KullaniciPathEkle { param($BasaKlasorler,$Klasorler) return $true }
function Invoke-WebRequest { param($Uri,$OutFile,[switch]$UseBasicParsing,$TimeoutSec,$ErrorAction) Copy-Item -LiteralPath $script:fixtureZip -Destination $OutFile }
function Rename-Item {
    param($LiteralPath,$NewName,$ErrorAction)
    if ($script:senaryo -eq 'rollback' -and $LiteralPath -like '*nodejs.yeni-*') { throw 'simulated replacement failure' }
    Microsoft.PowerShell.Management\Rename-Item -LiteralPath $LiteralPath -NewName $NewName -ErrorAction Stop
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$testRoot=Join-Path $env:TEMP ('pg-node-preserve-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
$IMZA_YAYINCI='OpenJS Foundation'
foreach ($script:senaryo in 'success','rollback') {
    $caseRoot=Join-Path $testRoot $senaryo
    $KURULUM_KLASORU=Join-Path $caseRoot 'nodejs'
    $NPM_KLASORU=Join-Path $caseRoot 'npm'
    New-Item -ItemType Directory -Path $KURULUM_KLASORU | Out-Null
    [IO.File]::WriteAllText((Join-Path $KURULUM_KLASORU 'old.txt'),'preserve')
    $script:fixtureZip=Join-Path $caseRoot 'fixture.zip'
    $zip=[IO.Compression.ZipFile]::Open($fixtureZip,'Create')
    $entry=$zip.CreateEntry('node-v24.21.0-win-x64/node.exe')
    $writer=[IO.StreamWriter]::new($entry.Open()); $writer.Write('test fixture'); $writer.Dispose(); $zip.Dispose()
    $hedef=@{Surum='24.21.0';Url='https://fixture.invalid/node.zip';Sha256=(Get-FileHash $fixtureZip -Algorithm SHA256).Hash.ToLower()}
    $r=ZipKur
    if ($senaryo -eq 'success') {
        if ($r.Kod -ne 0) { throw $r.Neden }
        if (-not @(Get-ChildItem -LiteralPath (Join-Path $caseRoot '_karantina') -Filter 'old.txt' -Recurse).Count) { throw 'old installation was deleted' }
    } else {
        if ($r.Kod -eq 0 -or -not (Test-Path -LiteralPath (Join-Path $KURULUM_KLASORU 'old.txt'))) { throw 'rollback did not preserve original' }
    }
    Write-Output "PASS Node.js $senaryo"
}
Write-Output "Temporary fixtures: $testRoot"
