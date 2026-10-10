#requires -Version 5.1
# Isolated native regression test; no plugin bootstrap/installation is invoked.
Set-StrictMode -Version 2
$ErrorActionPreference='Stop'
$pluginRoot=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$temporary=Join-Path ([IO.Path]::GetTempPath()) ('kilic-log-test-'+[guid]::NewGuid().ToString('N'))
$previousLocal=$env:LOCALAPPDATA
try{
    [void][IO.Directory]::CreateDirectory($temporary)
    $env:LOCALAPPDATA=$temporary
    . (Join-Path $pluginRoot 'scripts\hata-kaydi.ps1')
    $output=@(Write-KilicErrorLog -Stage 'prepare' -Code 'DEPENDENCIES_REQUIRED' -SkillId 'K01')
    if($output.Count -ne 0){throw 'Logger emitted output'}
    $files=@(Get-ChildItem -LiteralPath (Join-Path $temporary 'KilicSozlesme\logs') -Filter '*.jsonl')
    if($files.Count -ne 1){throw 'StrictMode first call did not create one log'}
    $first=Get-Content -LiteralPath $files[0].FullName -Encoding UTF8 | ConvertFrom-Json
    if($first.error_code -ne 'DEPENDENCIES_REQUIRED' -or $first.skill_id -ne 'K01'){throw 'Wrong first event'}
    $script:KilicLogPluginRoot=$temporary
    try{throw 'secret=abc C:\private\contract.docx'}catch{
        Write-KilicErrorLog -Stage 'run' -Code 'ENTRY_BLOCKED' -ErrorRecord $_ -SkillId 'K01'
    }
    $raw=Get-Content -LiteralPath $files[0].FullName -Raw -Encoding UTF8
    $rows=@(Get-Content -LiteralPath $files[0].FullName -Encoding UTF8 | ForEach-Object {$_|ConvertFrom-Json})
    if($rows.Count -ne 2 -or $rows[1].package_version -ne 'UNKNOWN'){throw 'Metadata fallback failed'}
    if($raw -match 'secret|private|contract.docx'){throw 'Raw error leaked'}
    $blocked=Join-Path $temporary 'file-not-directory'
    [IO.File]::WriteAllText($blocked,'x')
    $env:LOCALAPPDATA=$blocked
    $output=@(Write-KilicErrorLog -Stage 'run' -Code 'TEST')
    if($output.Count -ne 0){throw 'Failed destination emitted output'}
    $env:LOCALAPPDATA=$temporary
    $script:KilicLogCount=100
    Write-KilicErrorLog -Stage 'run' -Code 'OVER_LIMIT'
    if((Get-Content -LiteralPath $files[0].FullName -Raw -Encoding UTF8) -cne $raw){throw 'Event cap failed'}
    'PASS: StrictMode, JSONL, metadata fallback, privacy, failed destination, event cap'
}finally{
    $env:LOCALAPPDATA=$previousLocal
    if(Test-Path -LiteralPath $temporary){Remove-Item -LiteralPath $temporary -Recurse -Force}
}
