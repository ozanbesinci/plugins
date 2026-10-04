#requires -Version 5.1
param([switch]$YalnizBul,[switch]$LocalOnly,[switch]$TestOnly,[string]$TargetFile,[string]$TargetSha256)
. (Join-Path $PSScriptRoot 'program-ortak.ps1')
Assert-SupportedPlatform
$KURULUM_KLASORU = Join-Path $env:LOCALAPPDATA 'Programs\nodejs'
function NodeDogrula([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        $r=Invoke-Native $Path @('-p','JSON.stringify({version:process.versions.node,path:process.execPath,arch:process.arch})') 20
        if ($r.ExitCode -ne 0) { return $null }
        $v=$r.Output.Trim() | ConvertFrom-Json
        $null=Stable-Version $v.version
        return $v
    } catch { return $null }
}
function Find-Node {
    foreach ($folder in @(Get-PathFolders)) {
        $v=NodeDogrula (Join-Path $folder 'node.exe'); if ($v) { $v|Add-Member -NotePropertyName path_visible -NotePropertyValue $true -Force;return $v }
    }
    $fallback=NodeDogrula (Join-Path $KURULUM_KLASORU 'node.exe')
    if($fallback){$fallback|Add-Member -NotePropertyName path_visible -NotePropertyValue $false -Force}
    return $fallback
}
function NodeTarget {
    $releases=Get-RemoteJson 'https://nodejs.org/dist/index.json'
    $lts=@($releases | Where-Object { $_.lts -and @($_.files) -contains 'win-x64-zip' } | Sort-Object {[version]($_.version -replace '^v','')} -Descending | Select-Object -First 1)
    if (-not $lts.Count) { throw 'Node.js LTS hedefi doğrulanamadı.' }
    $v=$lts[0].version -replace '^v',''; $null=Stable-Version $v
    $name="node-v$v-win-x64.zip"
    $sums=(Invoke-WebRequest -Uri "https://nodejs.org/dist/v$v/SHASUMS256.txt" -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop).Content
    $match=[regex]::Match([string]$sums,'(?m)^([a-fA-F0-9]{64})\s+'+[regex]::Escape($name)+'\s*$')
    if (-not $match.Success) { throw 'Node.js paket SHA-256 kaydı yok.' }
    return [pscustomobject]@{version=$v;url="https://nodejs.org/dist/v$v/$name";sha256=$match.Groups[1].Value.ToLower();source='nodejs.org';architecture='x64'}
}
function Test-NodeRuntime([string]$Exe,[string]$Expected) {
    $actual=NodeDogrula $Exe
    if (-not $actual -or $actual.version -cne $Expected -or $actual.arch -ne 'x64') { throw 'Node.js son konum sürümü/mimarisi doğrulanamadı.' }
    $cli=Join-Path (Split-Path $Exe -Parent) 'node_modules\npm\bin\npm-cli.js'
    if (-not (Test-Path -LiteralPath $cli)) { throw 'npm-cli.js eksik.' }
    $npm=Invoke-Native $Exe @($cli,'--version') 30
    if ($npm.ExitCode -ne 0 -or $npm.Output.Trim() -notmatch '^\d+\.\d+\.\d+$') { throw 'npm işlev testi başarısız.' }
    $test=Invoke-Native $Exe @('-p',"require('crypto').createHash('sha256').update('guncelleyici').digest('hex')") 30
    if ($test.ExitCode -ne 0 -or $test.Output.Trim() -cne (Text-Sha256 'guncelleyici')) { throw 'Node.js işlev testi başarısız.' }
    return $actual
}
try {
    $installed=Find-Node
    $local=[pscustomobject]@{version=(Read-Field $installed 'version');path=(Read-Field $installed 'path');arch=(Read-Field $installed 'arch');path_visible=[bool](Read-Field $installed 'path_visible' $false)}
    if($TestOnly){
        if(-not $installed){throw 'Doğrulanacak Node.js yok.'}
        $actual=Test-NodeRuntime $installed.path $installed.version
        Emit-Result ([pscustomobject]@{key='node';ozet=$(if($local.path_visible){'GEÇTİ'}else{'UYARI'});health=$(if($local.path_visible){'PASS'}else{'WARNING'});neden=$(if($local.path_visible){''}else{'İkili çalışıyor fakat kayıtlı PATH üzerinde değil.'});local=$local;surum=$actual.version;node=$actual.path;test_scope='runtime/npm/hash; PATH write not performed'})
    }
    if ($YalnizBul -or $LocalOnly) {
        $target=$null;$note='';if(-not $LocalOnly){try{$target=NodeTarget}catch{$note=Hide-Secrets $_.Exception.Message}}
        Emit-Result ([pscustomobject]@{key='node';local=$local;surum=$local.version;node=$local.path;target=$target;hedef_surum=(Read-Field $target 'version');hedef_kaynagi=$(if($target){'nodejs.org'}else{$null});neden=$note;health='NOT_RUN'})
    }
    $target=Read-Target 'node' $TargetFile $TargetSha256
    $v=[string]$target.version;$null=Stable-Version $v
    if ($target.url -cne "https://nodejs.org/dist/v$v/node-v$v-win-x64.zip") { throw 'Node.js hedef adresi geçersiz.' }
    Assert-MaintenanceWindow
    if ($installed -and -not (Test-UserScope $installed.path)) { throw 'Makine geneli Node.js için BT işlemi gerekli.' }
    if ($installed -and ([version]$installed.version -gt [version]$v -or ([version]$installed.version -eq [version]$v -and -not [bool](Read-Field $target 'repair' $false)))) { throw 'Node.js yerel durumu değişti; yeniden tarayın.' }
    Assert-PlainPath $KURULUM_KLASORU
    $programs=Split-Path $KURULUM_KLASORU -Parent
    [void][IO.Directory]::CreateDirectory($programs)
    $stage=Join-Path $programs ('nodejs.yeni-'+[guid]::NewGuid().ToString('N'))
    $zip=Join-Path $env:TEMP ('guncelleyici-node-'+[guid]::NewGuid().ToString('N')+'.zip')
    $backup=$null;$placed=$false;$committed=$false;$restoreFailed=$false
    try {
        Download-VerifiedSource $target.url $zip 268435456
        if ((File-Sha256 $zip) -cne $target.sha256) { throw 'Node.js SHA-256 doğrulaması başarısız.' }
        Expand-SafeZip $zip $stage "node-v$v-win-x64/"
        $exe=Join-Path $stage 'node.exe'; $sig=Get-AuthenticodeSignature $exe
        if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notlike '*OpenJS Foundation*') { throw 'Node.js imzası doğrulanamadı.' }
        $null=Test-NodeRuntime $exe $v
        if (Test-Path -LiteralPath $KURULUM_KLASORU) {
            $backup=$KURULUM_KLASORU+'.eski-'+[guid]::NewGuid().ToString('N')
            Move-Item -LiteralPath $KURULUM_KLASORU -Destination $backup -ErrorAction Stop
        }
        Move-Item -LiteralPath $stage -Destination $KURULUM_KLASORU -ErrorAction Stop;$placed=$true
        $actual=Test-NodeRuntime (Join-Path $KURULUM_KLASORU 'node.exe') $v
        $committed=$true
        $pathWarning=''
        try { Add-UserPath $KURULUM_KLASORU; Add-UserPath (Join-Path $env:APPDATA 'npm') }
        catch { $pathWarning='Yeni Node.js doğrulandı; PATH kaydı tamamlanamadı: '+(Hide-Secrets $_.Exception.Message) }
        Emit-Result ([pscustomobject]@{key='node';durum='KURULDU';surum=$actual.version;node=$actual.path;ozet=$(if($pathWarning){'UYARI'}else{'GEÇTİ'});neden=$pathWarning;backup=$backup;restart_required=$true;health='PASS'})
    } catch {
        $why=Hide-Secrets $_.Exception.Message
        if (-not $committed) {
            try {
                if ($placed -and (Test-Path -LiteralPath $KURULUM_KLASORU)) { Move-Item -LiteralPath $KURULUM_KLASORU -Destination ($KURULUM_KLASORU+'.basarisiz-'+[guid]::NewGuid().ToString('N')) -ErrorAction Stop }
                if ($backup) { Move-Item -LiteralPath $backup -Destination $KURULUM_KLASORU -ErrorAction Stop }
            } catch { $restoreFailed=$true;$why+='; geri dönüş tamamlanamadı, yedek: '+$backup }
        }
        $now=Find-Node
        Emit-Result ([pscustomobject]@{key='node';durum='BASARISIZ';ozet='ENGEL';surum=(Read-Field $now 'version');node=(Read-Field $now 'path');neden=$why;backup=$backup;recovery_required=$restoreFailed;health='FAIL'}) 2
    } finally {
        if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue }
        if (-not $restoreFailed -and (Test-Path -LiteralPath $stage)) { Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue }
    }
} catch { Emit-Result ([pscustomobject]@{key='node';durum='BASARISIZ';ozet='ENGEL';neden=(Hide-Secrets $_.Exception.Message)}) 2 }
