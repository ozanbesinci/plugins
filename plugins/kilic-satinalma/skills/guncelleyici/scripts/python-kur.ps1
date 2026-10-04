#requires -Version 5.1
param([switch]$YalnizBul,[switch]$LocalOnly,[switch]$TestOnly,[string]$TargetFile,[string]$TargetSha256)
. (Join-Path $PSScriptRoot 'program-ortak.ps1')
Assert-SupportedPlatform
$DESTEK_SERI = '3.14'
$script:MutationStarted=$false

function Find-SupportedPython {
    $candidates = @((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'))
    foreach ($root in 'HKCU:\SOFTWARE\Python\PythonCore','HKLM:\SOFTWARE\Python\PythonCore') {
        if (Test-Path $root) {
            foreach ($item in Get-ChildItem $root) {
                $ip = Get-ItemProperty (Join-Path $item.PSPath 'InstallPath') -ErrorAction SilentlyContinue
                $v = Read-Field $ip 'ExecutablePath'
                if ($v) { $candidates += [string]$v }
            }
        }
    }
    foreach ($command in @(Get-Command python.exe -All -ErrorAction SilentlyContinue)) { $candidates += $command.Source }
    $found = @(); $other = @()
    foreach ($path in @($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $path) -or $path -like '*\WindowsApps\*') { continue }
        try {
            $r = Invoke-Native $path @('-I','-B','-c','import json,sys,struct; print(json.dumps(dict(version=sys.version.split()[0],path=sys.executable,bits=struct.calcsize("P")*8)))') 20
            if ($r.ExitCode -ne 0) { continue }
            $v = $r.Output.Trim() | ConvertFrom-Json
            if ($v.version -like "$DESTEK_SERI.*" -and $v.bits -eq 64) { $found += $v } else { $other += $v }
        } catch {}
    }
    $chosen = @($found | Sort-Object { [version]$_.version } -Descending | Select-Object -First 1)
    return [pscustomobject]@{chosen=$(if($chosen.Count){$chosen[0]}else{$null});other=$other}
}
function Python-Target {
    $list = Get-RemoteJson 'https://www.python.org/api/v2/downloads/release/?is_published=true&pre_release=false'
    $candidate = @($list | Where-Object { $_.name -match '^Python 3\.14\.\d+$' } | Sort-Object { [version]($_.name -replace '^Python ','') } -Descending | Select-Object -First 1)
    if (-not $candidate.Count) { throw 'Desteklenen Python serisinin kararlı yayını doğrulanamadı.' }
    $v = $candidate[0].name -replace '^Python ',''
    $rid = ($candidate[0].resource_uri.TrimEnd('/') -split '/')[-1]
    $files = Get-RemoteJson "https://www.python.org/api/v2/downloads/release_file/?release=$rid"
    $file = @($files | Where-Object { $_.url -eq "https://www.python.org/ftp/python/$v/python-$v-amd64.exe" } | Select-Object -First 1)
    if (-not $file.Count -or $file[0].sha256_sum -notmatch '^[a-fA-F0-9]{64}$') { throw 'Python kurucu özeti doğrulanamadı.' }
    return [pscustomobject]@{version=$v;url=$file[0].url;sha256=$file[0].sha256_sum.ToLower();size=[long]$file[0].filesize;source='python.org';architecture='amd64'}
}
try {
    $info = Find-SupportedPython; $installed = $info.chosen
    $local = [pscustomobject]@{version=$(if($installed){$installed.version}else{$null});path=$(if($installed){$installed.path}else{$null});bits=$(if($installed){$installed.bits}else{$null});other=$info.other}
    if($TestOnly){
        if(-not $installed){throw 'Desteklenen Python bulunamadı.'}
        $pip=Invoke-Native $installed.path @('-I','-B','-m','pip','--version') 30
        Emit-Result ([pscustomobject]@{key='python';local=$local;surum=$installed.version;python=$installed.path;ozet=$(if($pip.ExitCode -eq 0){'GEÇTİ'}else{'ENGEL'});health=$(if($pip.ExitCode -eq 0){'PASS'}else{'FAIL'});test_scope='runtime/version/pip'}) $(if($pip.ExitCode -eq 0){0}else{2})
    }
    if ($YalnizBul -or $LocalOnly) {
        $target = $null; $note = ''
        if (-not $LocalOnly) { try { $target = Python-Target } catch { $note=Hide-Secrets $_.Exception.Message } }
        Emit-Result ([pscustomobject]@{key='python';python=$local.path;surum=$local.version;local=$local;target=$target;hedef_surum=(Read-Field $target 'version');hedef_kaynagi=$(if($target){'python.org'}else{$null});durum=$(if($installed){'MEVCUT'}else{'YOK'});neden=$note;health='NOT_RUN'})
    }
    $target = Read-Target 'python' $TargetFile $TargetSha256
    $v = [string]$target.version; $null = Stable-Version $v
    if ($v -notlike '3.14.*' -or $target.url -cne "https://www.python.org/ftp/python/$v/python-$v-amd64.exe") { throw 'Python hedef serisi/kaynağı geçersiz.' }
    Assert-MaintenanceWindow
    if ($installed -and [version]$installed.version -ge [version]$v) { throw 'Yerel Python plan sonrasında değişmiş veya hedef artık gerekli değil; yeniden tarayın.' }
    if ($installed -and -not (Test-UserScope $installed.path)) { throw 'Makine geneli Python güncellemesi BT tarafından yapılmalı; ikinci kopya kurulmadı.' }
    $tmp = Join-Path $env:TEMP ('guncelleyici-python-' + [guid]::NewGuid().ToString('N'))
    [void][IO.Directory]::CreateDirectory($tmp)
    try {
        $exe = Join-Path $tmp 'python-setup.exe'
        Download-VerifiedSource $target.url $exe 134217728
        if ((File-Sha256 $exe) -cne $target.sha256 -or (Get-Item $exe).Length -ne [long]$target.size) { throw 'Python boyut/hash doğrulaması başarısız.' }
        $sig = Get-AuthenticodeSignature -LiteralPath $exe
        if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notlike '*Python Software Foundation*') { throw 'Python yayıncı imzası doğrulanamadı.' }
        $script:MutationStarted=$true
        $run = Invoke-Native $exe @('/quiet','InstallAllUsers=0','PrependPath=1','Include_launcher=1','InstallLauncherAllUsers=0','Include_test=0','Include_doc=0') 1200
        $after = (Find-SupportedPython).chosen
        if ($run.ExitCode -notin @(0,3010) -or -not $after -or $after.version -ne $v) { throw 'Python kurulum sonucu hedefle doğrulanamadı; yeniden kurmayı denemeden önce yerel durumu inceleyin.' }
        $pip = Invoke-Native $after.path @('-I','-B','-m','pip','--version') 30
        Emit-Result ([pscustomobject]@{key='python';durum='KURULDU';ozet=$(if($pip.ExitCode -eq 0){'GEÇTİ'}else{'UYARI'});surum=$after.version;python=$after.path;restart_required=($run.ExitCode -eq 3010);health=$(if($pip.ExitCode -eq 0){'PASS'}else{'WARNING'});testler=@(@{ad='pip';durum=$(if($pip.ExitCode -eq 0){'GEÇTİ'}else{'UYARI'})});neden=$(if($pip.ExitCode -ne 0){'Python kuruldu; pip işlevi doğrulanamadı.'}else{''})})
    } finally { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }
} catch {
    Emit-Result ([pscustomobject]@{key='python';durum='BASARISIZ';ozet='ENGEL';neden=(Hide-Secrets $_.Exception.Message);health='FAIL';recovery_required=$script:MutationStarted}) 2
}