#requires -Version 5.1
param([switch]$YalnizBul,[switch]$LocalOnly,[switch]$TestOnly,[string]$NodeYolu,[string]$TargetFile,[string]$TargetSha256)
. (Join-Path $PSScriptRoot 'program-ortak.ps1')
Assert-SupportedPlatform
$KURULUM_KLASORU=Join-Path $env:LOCALAPPDATA 'Programs\pnpm'
function ProbePnpm([string]$Root) {
    $manifest=Join-Path $Root 'node_modules\pnpm\package.json'
    if (-not (Test-Path -LiteralPath $manifest)) { return $null }
    try {
        $p=Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
        $entry=[string]$p.bin.pnpm
        if ($entry -match '(^|[\\/])\.\.([\\/]|$)|[:]' -or [IO.Path]::IsPathRooted($entry)) { return $null }
        $bin=Join-Path (Split-Path $manifest -Parent) $entry
        $r=Invoke-Native $NodeYolu @($bin,'--version') 30
        if ($r.ExitCode -ne 0 -or $r.Output.Trim() -notmatch '^\d+\.\d+\.\d+(?:[-+][\w.-]+)?$') { return $null }
        return [pscustomobject]@{version=$r.Output.Trim();path=(Join-Path $Root 'pnpm.cmd');root=$Root}
    } catch { return $null }
}
function Find-Pnpm {
    if (-not $NodeYolu) { return $null }
    foreach ($root in @(@(Get-PathFolders)+@($KURULUM_KLASORU) | Select-Object -Unique)) {
        $v=ProbePnpm $root;if($v){$v|Add-Member -NotePropertyName path_visible -NotePropertyValue ($root -in @(Get-PathFolders)) -Force;return $v}
        # Unknown shims/standalone binaries are not overwritten based on guessed metadata.
        if ((Test-Path (Join-Path $root 'pnpm.cmd')) -or (Test-Path (Join-Path $root 'pnpm.exe'))) {
            return [pscustomobject]@{version=$null;path=$root;root=$root;unmanaged=$true}
        }
    }
    return $null
}
try {
    $installed=Find-Pnpm
    $local=[pscustomobject]@{version=(Read-Field $installed 'version');path=(Read-Field $installed 'path');node=$NodeYolu;unmanaged=[bool](Read-Field $installed 'unmanaged' $false);path_visible=[bool](Read-Field $installed 'path_visible' $false)}
    if($TestOnly){
        if(-not $installed -or $local.unmanaged -or -not $local.version){throw 'Doğrulanmış pnpm yerel kurulumu yok.'}
        Emit-Result ([pscustomobject]@{key='pnpm';local=$local;surum=$local.version;ozet=$(if($local.path_visible){'GEÇTİ'}else{'UYARI'});health=$(if($local.path_visible){'PASS'}else{'WARNING'});test_scope='explicit Node + pnpm executable version'})
    }
    if ($YalnizBul -or $LocalOnly) {
        $target=$null;$why=''
        if(-not $LocalOnly){try{
            $m=Get-RemoteJson 'https://registry.npmjs.org/pnpm/latest'
            $null=Stable-Version $m.version
            if($m.name -ne 'pnpm' -or $m.dist.integrity -cnotmatch '^sha512-[A-Za-z0-9+/=]+$'){throw 'pnpm metadata geçersiz.'}
            $target=[pscustomobject]@{version=$m.version;url=$m.dist.tarball;integrity=$m.dist.integrity;engine=$m.engines.node;source='npm';node=$NodeYolu}
            if(-not $NodeYolu){$why='Node.js gerekli; önce Node.js kurulup yeniden taranmalı.'}
        }catch{$why=Hide-Secrets $_.Exception.Message}}
        Emit-Result ([pscustomobject]@{key='pnpm';local=$local;surum=$local.version;target=$target;hedef_surum=(Read-Field $target 'version');neden=$why;blocked=($local.unmanaged -or -not $NodeYolu);health='NOT_RUN'})
    }
    $target=Read-Target 'pnpm' $TargetFile $TargetSha256
    $v=[string]$target.version;$null=Stable-Version $v
    if($target.url -cne "https://registry.npmjs.org/pnpm/-/pnpm-$v.tgz"){throw 'pnpm paket adresi geçersiz.'}
    if(-not $NodeYolu -or $NodeYolu -cne $target.node){throw 'Seçilen Node.js yolu değişmiş/eksik.'}
    Assert-MaintenanceWindow
    if($local.version -and [version]($local.version -split '[-+]')[0] -gt [version]$v){throw 'Daha yeni pnpm sürümü düşürülmez.'}
    if($local.unmanaged){throw 'Yönetilmeyen pnpm/Corepack kurulumu korunuyor; BT incelemesi gerekli.'}
    if($installed -and -not (Test-UserScope $installed.path)){throw 'Makine geneli pnpm için BT işlemi gerekli.'}
    $nodeRoot=Split-Path $NodeYolu -Parent
    $semver=Join-Path $nodeRoot 'node_modules\npm\node_modules\semver'
    $nodeVersion=Invoke-Native $NodeYolu @('-p','process.versions.node') 20
    $engineTest=Invoke-Native $NodeYolu @('-e','process.stdout.write(String(require(process.argv[1]).satisfies(process.argv[2],process.argv[3])))',$semver,$nodeVersion.Output.Trim(),[string]$target.engine) 30
    if($engineTest.ExitCode -ne 0 -or $engineTest.Output.Trim() -ne 'true'){throw 'Onaylanan pnpm sürümü Node.js ile uyumlu değil.'}
    $programs=Split-Path $KURULUM_KLASORU -Parent;[void][IO.Directory]::CreateDirectory($programs)
    $stage=Join-Path $programs ('pnpm.yeni-'+[guid]::NewGuid().ToString('N'))
    $tgz=Join-Path $env:TEMP ('guncelleyici-pnpm-'+[guid]::NewGuid().ToString('N')+'.tgz')
    $backup=$null;$placed=$false;$committed=$false;$recovery=$false
    try {
        Download-VerifiedSource $target.url $tgz 134217728
        $hash=[Security.Cryptography.SHA512]::Create();$stream=[IO.File]::OpenRead($tgz)
        try{$actual='sha512-'+[Convert]::ToBase64String($hash.ComputeHash($stream))}finally{$hash.Dispose();$stream.Dispose()}
        if($actual -cne $target.integrity){throw 'pnpm onaylanan SHA-512 özetiyle eşleşmiyor.'}
        $cli=Join-Path $nodeRoot 'node_modules\npm\bin\npm-cli.js'
        $r=Invoke-Native $NodeYolu @($cli,'install','--global','--prefix',$stage,$tgz,'--offline','--ignore-scripts','--engine-strict','--no-audit','--no-fund','--registry=https://registry.npmjs.org') 600
        if($r.ExitCode -ne 0){throw 'Hash doğrulanmış yerel pnpm paketinin çevrimdışı kurulumu başarısız.'}
        $before=ProbePnpm $stage;if(-not $before -or $before.version -ne $v){throw 'pnpm hazırlık testi başarısız.'}
        Assert-PlainPath $KURULUM_KLASORU
        if(Test-Path -LiteralPath $KURULUM_KLASORU){$backup=$KURULUM_KLASORU+'.eski-'+[guid]::NewGuid().ToString('N');Move-Item -LiteralPath $KURULUM_KLASORU -Destination $backup -ErrorAction Stop}
        Move-Item -LiteralPath $stage -Destination $KURULUM_KLASORU -ErrorAction Stop;$placed=$true
        $after=ProbePnpm $KURULUM_KLASORU;if(-not $after -or $after.version -ne $v){throw 'pnpm son konum testi başarısız.'}
        $committed=$true;$warning=''
        try{Add-UserPath $KURULUM_KLASORU}catch{$warning='pnpm çalışıyor; PATH kaydı tamamlanamadı.'}
        Emit-Result ([pscustomobject]@{key='pnpm';durum='KURULDU';surum=$after.version;pnpm=$after.path;ozet=$(if($warning){'UYARI'}else{'GEÇTİ'});neden=$warning;backup=$backup;restart_required=$true;health='PASS'})
    } catch {
        $why=Hide-Secrets $_.Exception.Message
        if(-not $committed){try{
            if($placed){Move-Item -LiteralPath $KURULUM_KLASORU -Destination ($KURULUM_KLASORU+'.basarisiz-'+[guid]::NewGuid().ToString('N')) -ErrorAction Stop}
            if($backup){Move-Item -LiteralPath $backup -Destination $KURULUM_KLASORU -ErrorAction Stop}
        }catch{$recovery=$true;$why+='; geri dönüş tamamlanamadı, yedek: '+$backup}}
        $after=Find-Pnpm
        Emit-Result ([pscustomobject]@{key='pnpm';durum='BASARISIZ';ozet='ENGEL';surum=(Read-Field $after 'version');neden=$why;backup=$backup;recovery_required=$recovery;health='FAIL'}) 2
    } finally {
        Remove-Item -LiteralPath $tgz -Force -ErrorAction SilentlyContinue
        if(-not $recovery){Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue}
    }
}catch{Emit-Result ([pscustomobject]@{key='pnpm';durum='BASARISIZ';ozet='ENGEL';neden=(Hide-Secrets $_.Exception.Message)}) 2}