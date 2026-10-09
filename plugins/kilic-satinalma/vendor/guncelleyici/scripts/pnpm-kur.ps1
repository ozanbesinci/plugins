#requires -Version 5.1
param([switch]$YalnizBul,[switch]$LocalOnly,[switch]$TestOnly,[string]$NodeYolu,[string]$TargetFile,[string]$TargetSha256)
. (Join-Path $PSScriptRoot 'program-ortak.ps1')
Assert-SupportedPlatform
$KURULUM_KLASORU=Join-Path $env:LOCALAPPDATA 'Programs\pnpm'
$NATIVE_PAKET='@pnpm/exe.win32-x64'
function Test-NativePnpm($Manifest) {
    # pnpm 12+ npm package ships a JS launcher placeholder; install.js normally swaps in the native
    # binary from @pnpm/exe.<platform>. bin.pnpm is pnpm.exe after that swap.
    return ([string](Read-Field (Read-Field $Manifest 'bin') 'pnpm') -like '*.exe') -or [bool](Read-Field (Read-Field $Manifest 'optionalDependencies') $NATIVE_PAKET)
}
function ProbePnpm([string]$Root) {
    $manifest=Join-Path $Root 'node_modules\pnpm\package.json'
    if (-not (Test-Path -LiteralPath $manifest)) { return $null }
    try {
        $p=Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
        $entry=[string]$p.bin.pnpm
        if (Test-NativePnpm $p) { $entry='pnpm.exe' }
        if (-not $entry -or $entry -match '(^|[\\/])\.\.([\\/]|$)|[:]' -or [IO.Path]::IsPathRooted($entry)) { return $null }
        $bin=Join-Path (Split-Path $manifest -Parent) $entry
        if (-not [IO.File]::Exists($bin)) { return $null }
        if ($entry -like '*.exe') { $r=Invoke-Native $bin @('--version') 30 }
        elseif ($NodeYolu) { $r=Invoke-Native $NodeYolu @($bin,'--version') 30 }
        else { return $null }
        if ($r.ExitCode -ne 0 -or $r.Output.Trim() -notmatch '^\d+\.\d+\.\d+(?:[-+][\w.-]+)?$') { return $null }
        return [pscustomobject]@{version=$r.Output.Trim();path=(Join-Path $Root 'pnpm.cmd');root=$Root;native=($entry -like '*.exe')}
    } catch { return $null }
}
function Find-Pnpm {
    $visible=@(Get-PathFolders)
    foreach ($root in @($visible+@($KURULUM_KLASORU) | Select-Object -Unique)) {
        $v=ProbePnpm $root;if($v){$v|Add-Member -NotePropertyName path_visible -NotePropertyValue ($root -in $visible) -Force;return $v}
        # Unknown shims/standalone binaries are not overwritten based on guessed metadata.
        if ((Test-Path (Join-Path $root 'pnpm.cmd')) -or (Test-Path (Join-Path $root 'pnpm.exe'))) {
            $claimed=$null;try{$claimed=[string](Get-Content -LiteralPath (Join-Path $root 'node_modules\pnpm\package.json') -Raw -Encoding UTF8 | ConvertFrom-Json).version}catch{}
            return [pscustomobject]@{version=$null;path=$root;root=$root;unmanaged=$true;path_visible=($root -in $visible);manifest_version=$claimed}
        }
    }
    return $null
}
function Get-Sha512Integrity([string]$Path) {
    $hash=[Security.Cryptography.SHA512]::Create();$stream=[IO.File]::OpenRead($Path)
    try{return 'sha512-'+[Convert]::ToBase64String($hash.ComputeHash($stream))}finally{$hash.Dispose();$stream.Dispose()}
}
function Read-Block($Stream,[byte[]]$Buffer,[int]$Count) {
    $read=0;while($read -lt $Count){$n=$Stream.Read($Buffer,$read,$Count-$read);if($n -le 0){break};$read+=$n};return $read
}
function Save-TgzMember([string]$Archive,[string]$Member,[string]$Destination,[long]$Limit=268435456) {
    # Minimal ustar reader for an already hash-verified npm tarball: copies exactly one regular file.
    # Links/special entries, PAX-overridden names, duplicates and truncated data are rejected.
    Assert-PlainPath $Destination
    $file=[IO.File]::OpenRead($Archive);$gz=New-Object IO.Compression.GZipStream($file,[IO.Compression.CompressionMode]::Decompress)
    $header=New-Object byte[] 512;$buffer=New-Object byte[] 65536;$found=$false;$pax=$false;$ascii=[Text.Encoding]::ASCII
    try {
        while ($true) {
            if ((Read-Block $gz $header 512) -ne 512) { throw 'pnpm arşivi beklenmedik biçimde bitti.' }
            if (@($header -ne 0).Count -eq 0) { break }
            $name=$ascii.GetString($header,0,100).TrimEnd([char]0)
            if ($ascii.GetString($header,257,5) -ceq 'ustar') { $prefix=$ascii.GetString($header,345,155).TrimEnd([char]0);if($prefix){$name=$prefix+'/'+$name} }
            if ($header[124] -band 0x80) { throw 'pnpm arşivinde desteklenmeyen boyut alanı.' }
            $sizeText=$ascii.GetString($header,124,12).Trim([char]0,' ')
            if ($sizeText -notmatch '^[0-7]+$') { throw 'pnpm arşiv başlığı geçersiz.' }
            [long]$size=[Convert]::ToInt64($sizeText,8);$type=[char]$header[156]
            [long]$padded=[Math]::Ceiling($size/512)*512
            if ($name -ceq $Member) {
                if ($type -notin [char]'0',[char]0) { throw 'pnpm ikilisi düz dosya değil.' }
                if ($found -or $pax) { throw 'pnpm arşivinde yinelenmiş/PAX ile değiştirilmiş ikili kaydı.' }
                if ($size -le 0 -or $size -gt $Limit) { throw 'pnpm ikili boyutu sınır dışında.' }
                $out=New-Object IO.FileStream($Destination,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
                try {
                    [long]$left=$size
                    while ($left -gt 0) { $n=Read-Block $gz $buffer ([int][Math]::Min($left,$buffer.Length));if($n -le 0){throw 'pnpm ikilisi eksik.'};$out.Write($buffer,0,$n);$left-=$n }
                    $out.Flush($true)
                } finally { $out.Dispose() }
                [long]$left=$padded-$size;$found=$true
            } else { [long]$left=$padded }
            while ($left -gt 0) { $n=Read-Block $gz $buffer ([int][Math]::Min($left,$buffer.Length));if($n -le 0){throw 'pnpm arşivi beklenmedik biçimde bitti.'};$left-=$n }
            $pax=($type -ceq [char]'x')
        }
    } finally { $gz.Dispose();$file.Dispose() }
    if (-not $found) { throw 'Doğrulanmış paket içinde yerel pnpm ikilisi bulunamadı.' }
}
function Install-NativePnpm([string]$Root,[string]$Exe) {
    # Reproduce the install.js result (evidence: npm-installed 12.6.0 layout) without running scripts:
    # every declared bin gets the verified native binary and shims call it directly, never the JS launcher.
    $pkg=Join-Path $Root 'node_modules\pnpm'
    $p=Get-Content -LiteralPath (Join-Path $pkg 'package.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $names=@($p.bin.PSObject.Properties | ForEach-Object { $_.Name })
    if ('pnpm' -notin $names) { throw 'pnpm paket bin kaydı eksik.' }
    $utf8=New-Object Text.UTF8Encoding $false
    foreach ($name in $names) {
        if ($name -cnotmatch '^[a-z]+$') { throw 'pnpm paket bin adı geçersiz.' }
        Copy-Item -LiteralPath $Exe -Destination (Join-Path $pkg ($name+'.exe')) -Force -ErrorAction Stop
        [IO.File]::WriteAllText((Join-Path $Root ($name+'.cmd')),("@ECHO off`r`n""%~dp0node_modules\pnpm\$name.exe"" %*`r`n"),$utf8)
        [IO.File]::WriteAllText((Join-Path $Root ($name+'.ps1')),("`$basedir=Split-Path `$MyInvocation.MyCommand.Definition -Parent`r`nif (`$MyInvocation.ExpectingInput) {`r`n  `$input | & ""`$basedir/node_modules/pnpm/$name.exe"" `$args`r`n} else {`r`n  & ""`$basedir/node_modules/pnpm/$name.exe"" `$args`r`n}`r`nexit `$LASTEXITCODE`r`n"),$utf8)
        [IO.File]::WriteAllText((Join-Path $Root $name),("#!/bin/sh`nbasedir=`$(dirname ""`$(echo ""`$0"" | sed -e 's,\\,/,g')"")`nexec ""`$basedir/node_modules/pnpm/$name.exe"" ""`$@""`n"),$utf8)
    }
}
try {
    $installed=Find-Pnpm
    $local=[pscustomobject]@{version=(Read-Field $installed 'version');path=(Read-Field $installed 'path');node=$NodeYolu;unmanaged=[bool](Read-Field $installed 'unmanaged' $false);path_visible=[bool](Read-Field $installed 'path_visible' $false);manifest_version=(Read-Field $installed 'manifest_version')}
    if($TestOnly){
        if(-not $installed -or $local.unmanaged -or -not $local.version){throw 'Doğrulanmış pnpm yerel kurulumu yok.'}
        Emit-Result ([pscustomobject]@{key='pnpm';local=$local;surum=$local.version;ozet=$(if($local.path_visible){'GEÇTİ'}else{'UYARI'});health=$(if($local.path_visible){'PASS'}else{'WARNING'});test_scope='explicit Node + pnpm executable version'})
    }
    if ($YalnizBul -or $LocalOnly) {
        $target=$null;$why=''
        if($local.unmanaged){$why='pnpm komutu bulundu ('+$local.path+$(if($local.manifest_version){'; paket kaydı '+$local.manifest_version}else{''})+') fakat sürümü çalıştırılarak doğrulanamadı; yönetilmeyen kurulum korunuyor, otomatik değişiklik yapılmaz.'}
        if(-not $LocalOnly){try{
            $m=Get-RemoteJson 'https://registry.npmjs.org/pnpm/latest'
            $null=Stable-Version $m.version
            if($m.name -ne 'pnpm' -or $m.dist.integrity -cnotmatch '^sha512-[A-Za-z0-9+/=]+$'){throw 'pnpm metadata geçersiz.'}
            $native=$null
            if(Test-NativePnpm $m){
                # The approved plan pins the platform binary package too; apply never resolves it on its own.
                if([string](Read-Field (Read-Field $m 'optionalDependencies') $NATIVE_PAKET) -cne $m.version){throw 'pnpm yerel ikili paket kaydı sürümle eşleşmiyor.'}
                $e=Get-RemoteJson ('https://registry.npmjs.org/'+$NATIVE_PAKET+'/'+$m.version)
                if($e.name -cne $NATIVE_PAKET -or $e.version -cne $m.version -or $e.dist.tarball -cne "https://registry.npmjs.org/$NATIVE_PAKET/-/exe.win32-x64-$($m.version).tgz" -or $e.dist.integrity -cnotmatch '^sha512-[A-Za-z0-9+/=]+$'){throw 'pnpm yerel ikili metadata geçersiz.'}
                $native=[pscustomobject]@{package=$NATIVE_PAKET;version=$e.version;url=$e.dist.tarball;integrity=$e.dist.integrity}
            }
            $target=[pscustomobject]@{version=$m.version;url=$m.dist.tarball;integrity=$m.dist.integrity;engine=$m.engines.node;source='npm';node=$NodeYolu;native=$native}
            if(-not $NodeYolu){$why=(($why+' Node.js gerekli; önce Node.js kurulup yeniden taranmalı.').Trim())}
        }catch{$target=$null;$why=(($why+' '+(Hide-Secrets $_.Exception.Message)).Trim())}}
        Emit-Result ([pscustomobject]@{key='pnpm';local=$local;surum=$local.version;target=$target;hedef_surum=(Read-Field $target 'version');neden=$why;blocked=($local.unmanaged -or -not $NodeYolu);health='NOT_RUN'})
    }
    $target=Read-Target 'pnpm' $TargetFile $TargetSha256
    $v=[string]$target.version;$null=Stable-Version $v
    if($target.url -cne "https://registry.npmjs.org/pnpm/-/pnpm-$v.tgz"){throw 'pnpm paket adresi geçersiz.'}
    $native=Read-Field $target 'native'
    if($native -and ([string]$native.package -cne $NATIVE_PAKET -or [string]$native.version -cne $v -or [string]$native.url -cne "https://registry.npmjs.org/$NATIVE_PAKET/-/exe.win32-x64-$v.tgz" -or [string]$native.integrity -cnotmatch '^sha512-[A-Za-z0-9+/=]+$')){throw 'pnpm yerel ikili hedefi geçersiz.'}
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
    $temp=Join-Path $env:TEMP ('guncelleyici-pnpm-'+[guid]::NewGuid().ToString('N'))
    $tgz=$temp+'.tgz';$exeTgz=$temp+'-exe.tgz';$exeFile=$temp+'.exe'
    $backup=$null;$placed=$false;$committed=$false;$recovery=$false
    try {
        Download-VerifiedSource $target.url $tgz 134217728
        if((Get-Sha512Integrity $tgz) -cne $target.integrity){throw 'pnpm onaylanan SHA-512 özetiyle eşleşmiyor.'}
        if($native){
            Download-VerifiedSource $native.url $exeTgz 134217728
            if((Get-Sha512Integrity $exeTgz) -cne $native.integrity){throw 'pnpm yerel ikili paketi onaylanan SHA-512 özetiyle eşleşmiyor.'}
        }
        $cli=Join-Path $nodeRoot 'node_modules\npm\bin\npm-cli.js'
        $r=Invoke-Native $NodeYolu @($cli,'install','--global','--prefix',$stage,$tgz,'--offline','--ignore-scripts','--omit=optional','--engine-strict','--no-audit','--no-fund','--registry=https://registry.npmjs.org') 600
        if($r.ExitCode -ne 0){throw 'Hash doğrulanmış yerel pnpm paketinin çevrimdışı kurulumu başarısız.'}
        $staged=Get-Content -LiteralPath (Join-Path $stage 'node_modules\pnpm\package.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        if(Test-NativePnpm $staged){
            # Scripts stay disabled: the launcher would otherwise fetch an unpinned binary at first run.
            if(-not $native){throw 'Plan pnpm yerel ikili paket kaydı içermiyor; yeniden tarayın.'}
            Save-TgzMember $exeTgz 'package/pnpm.exe' $exeFile
            Install-NativePnpm $stage $exeFile
        }
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
        foreach($f in @($tgz,$exeTgz,$exeFile)){Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue}
        if(-not $recovery){Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue}
    }
}catch{Emit-Result ([pscustomobject]@{key='pnpm';durum='BASARISIZ';ozet='ENGEL';neden=(Hide-Secrets $_.Exception.Message)}) 2}