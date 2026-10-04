#requires -Version 5.1
param([switch]$YalnizBul,[switch]$LocalOnly,[switch]$TestOnly,[string]$TargetFile,[string]$TargetSha256,
      [string]$CacheRoot,[string]$PythonYolu,[switch]$BindOnly,[string]$ExePath)
. (Join-Path $PSScriptRoot 'program-ortak.ps1')
Assert-SupportedPlatform
$KOK=Join-Path $env:LOCALAPPDATA 'Programs\PowerBIModelingMCP'
$NAME='powerbi-modeling'
$EXE_REL='extension\server\powerbi-modeling-mcp.exe'
function PbiLocal {
    $roots=@('C:\MCPServers\PowerBIModelingMCP')
    if(Test-Path -LiteralPath $KOK){$roots+=@(Get-ChildItem -LiteralPath $KOK -Directory | Where-Object {$_.Name -match '^\d+\.\d+\.\d+$' -or (Test-Path -LiteralPath (Join-Path $_.FullName '.guncelleyici-verified.json'))} | ForEach-Object {$_.FullName})}
    $found=@()
    foreach($root in $roots){
        $exe=Join-Path $root $EXE_REL;$meta=Join-Path $root 'extension\package.json'
        if(-not (Test-Path -LiteralPath $exe) -or -not (Test-Path -LiteralPath $meta)){continue}
        try{$p=Get-Content -LiteralPath $meta -Raw -Encoding UTF8 | ConvertFrom-Json
            if($p.name -eq 'powerbi-modeling-mcp'){$found+=[pscustomobject]@{version=[string]$p.version;path=$exe;metadata_sha256=(File-Sha256 $meta);binary_sha256=(File-Sha256 $exe)}}
        }catch{}
    }
    $stable=@($found | Where-Object {$_.version -match '^\d+\.\d+\.\d+$'} | Sort-Object {[version]$_.version} -Descending | Select-Object -First 1)
    $chosen=if($stable.Count){$stable[0]}else{$null}
    $receipt=Join-Path $KOK 'active-install.json'
    if(Test-Path -LiteralPath $receipt){
        try{
            $saved=Get-Content -LiteralPath $receipt -Raw -Encoding UTF8|ConvertFrom-Json
            $match=@($found|Where-Object {$_.path -ieq $saved.path -and $_.version -eq $saved.version -and $_.binary_sha256 -ceq $saved.sha256})
            if($match.Count -eq 1 -and (-not $chosen -or [version]$match[0].version -ge [version]$chosen.version)){$chosen=$match[0]}
        }catch{}
    }
    $codexHome=if($env:CODEX_HOME){$env:CODEX_HOME}else{Join-Path $env:USERPROFILE '.codex'}
    $cc=if($env:CLAUDE_CONFIG_DIR){Join-Path $env:CLAUDE_CONFIG_DIR '.claude.json'}else{Join-Path $env:USERPROFILE '.claude.json'}
    $configs=[ordered]@{}
    foreach($f in @((Join-Path $codexHome 'config.toml'),(Join-Path $env:APPDATA 'Claude\claude_desktop_config.json'),$cc)){
        $configs[$f]=if(Test-Path -LiteralPath $f){File-Sha256 $f}else{$null}
    }
    return [pscustomobject]@{version=(Read-Field $chosen 'version');path=(Read-Field $chosen 'path');installations=$found;config_hashes=$configs}

}
function PbiTarget {
    $body=@{filters=@(@{criteria=@(@{filterType=7;value='analysis-services.powerbi-modeling-mcp'})});flags=19} | ConvertTo-Json -Depth 6
    $r=Get-RemoteJson 'https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery' 'POST' $body
    $versions=@($r.results[0].extensions[0].versions | Where-Object {
        $_.targetPlatform -eq 'win32-x64' -and $_.version -match '^\d+\.\d+\.\d+$' -and
        @($_.properties | Where-Object {$_.key -eq 'Microsoft.VisualStudio.Code.PreRelease' -and $_.value -eq 'true'}).Count -eq 0
    } | Sort-Object {[version]$_.version} -Descending | Select-Object -First 1)
    if(-not $versions.Count){throw 'Power BI MCP kararlı win32-x64 yayını doğrulanamadı.'}
    $v=$versions[0];$asset=@($v.files | Where-Object {$_.assetType -eq 'Microsoft.VisualStudio.Services.VSIXPackage'} | Select-Object -First 1)
    if(-not $asset.Count){throw 'VSIX indirme kaynağı yok.'}
    Assert-TrustedUri $asset[0].source
    if(-not $CacheRoot){$script:CacheRoot=Join-Path $env:TEMP ('guncelleyici-pbi-plan-'+[guid]::NewGuid().ToString('N'))}
    Assert-PlainPath $CacheRoot;[void][IO.Directory]::CreateDirectory($CacheRoot)
    $archive=Join-Path $CacheRoot ('powerbi-'+[guid]::NewGuid().ToString('N')+'.vsix')
    Download-VerifiedSource $asset[0].source $archive 268435456
    return [pscustomobject]@{version=[string]$v.version;archive=$archive;sha256=(File-Sha256 $archive);url=$asset[0].source;source='Microsoft Marketplace';architecture='win32-x64'}
}
function McpTest([string]$Exe) {
    $p=$null;$writer=$null
    try{
        $psi=New-Object Diagnostics.ProcessStartInfo
        $psi.FileName=$Exe;$psi.Arguments='--start';$psi.UseShellExecute=$false;$psi.CreateNoWindow=$true
        $psi.RedirectStandardInput=$true;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true
        $psi.StandardOutputEncoding=New-Object Text.UTF8Encoding $false
        $p=[Diagnostics.Process]::Start($psi);$err=$p.StandardError.ReadToEndAsync()
        $writer=New-Object IO.StreamWriter($p.StandardInput.BaseStream,(New-Object Text.UTF8Encoding $false));$writer.AutoFlush=$true
        function Request-Mcp($Id,$Method,$Parameters){
            $writer.WriteLine((@{jsonrpc='2.0';id=$Id;method=$Method;params=$Parameters}|ConvertTo-Json -Compress -Depth 10))
            $deadline=[DateTime]::UtcNow.AddSeconds(60)
            while([DateTime]::UtcNow -lt $deadline){
                $read=$p.StandardOutput.ReadLineAsync()
                $ms=[int][Math]::Max(1,($deadline-[DateTime]::UtcNow).TotalMilliseconds)
                if(-not $read.Wait($ms) -or $null -eq $read.Result){return $null}
                try{$msg=$read.Result|ConvertFrom-Json}catch{continue}
                if((Read-Field $msg 'id') -eq $Id){return $msg}
            }
            return $null
        }
        $init=Request-Mcp 1 'initialize' @{protocolVersion='2025-06-18';capabilities=@{};clientInfo=@{name='guncelleyici';version='2.2.0'}}
        $ir=Read-Field $init 'result'
        if(-not $ir -or (Read-Field $init 'error') -or -not (Read-Field $ir 'protocolVersion')){throw 'MCP initialize cevabı geçersiz.'}
        $writer.WriteLine('{"jsonrpc":"2.0","method":"notifications/initialized"}')
        $response=Request-Mcp 2 'tools/list' @{}
        if(-not $response -or (Read-Field $response 'error')){throw 'MCP tools/list hata cevabı.'}
        $result=Read-Field $response 'result';$tools=Read-Field $result 'tools'
        if($null -eq $tools -or $tools -isnot [array] -or $tools.Count -eq 0){throw 'MCP boş/geçersiz araç listesi.'}
        $names=@()
        foreach($tool in $tools){
            $name=Read-Field $tool 'name';$schema=Read-Field $tool 'inputSchema'
            if(-not ($name -is [string]) -or -not $name.Trim() -or $null -eq $schema -or $schema -isnot [pscustomobject] -or $name -in $names){throw 'MCP araç şeması geçersiz.'}
            $names+=$name
        }
        return [pscustomobject]@{name='MCP initialize/tools/list';status='PASS';tool_count=$names.Count;eula_not_accepted=($names -contains 'accept_eula')}
    }finally{
        if($writer){$writer.Dispose()}
        if($p){if(-not $p.HasExited){$p.Kill();$null=$p.WaitForExit(5000)};$p.Dispose()}
    }
}
function Bind-Clients([string]$Exe){
    $results=@()
    if(-not $PythonYolu -or -not (Test-Path -LiteralPath $PythonYolu)){
        return @([pscustomobject]@{client='MCP ayarları';status='deferred';detail='Ayar koruma yardımcısı için Python 3.11+ gerekli; mevcut ayarlar değiştirilmedi.'})
    }
    # Binding from the same active desktop client is deferred instead of forcing it closed.
    $running=@(Get-Process -ErrorAction Stop | Where-Object {$_.ProcessName -match '^(?i:codex|chatgpt|claude)(?:$|[ -])'})
    if($running.Count){
        return @([pscustomobject]@{client='Codex/Claude';status='deferred';detail='İstemci çalışıyor. Sunucu kuruldu; ayarlar korunuyor. İstemcileri kapatın ve sohbette bağlamayı yeniden isteyin; Work/Codex bakım adımını yerel olarak çalıştırır.'})
    }
    $codexHome=if($env:CODEX_HOME){$env:CODEX_HOME}else{Join-Path $env:USERPROFILE '.codex'}
    $clients=@(@{name='Codex';kind='codex';path=(Join-Path $codexHome 'config.toml')},
               @{name='Claude Desktop';kind='desktop';path=(Join-Path $env:APPDATA 'Claude\claude_desktop_config.json')})
    foreach($client in $clients){
        if(-not (Test-Path -LiteralPath (Split-Path $client.path -Parent))){$results+=[pscustomobject]@{client=$client.name;status='skipped';detail='İstemci klasörü yok.'};continue}
        try{
            $r=Invoke-Json $PythonYolu @('-B',(Join-Path $PSScriptRoot 'mcp_ayar.py'),$client.kind,'--path',$client.path,'--exe',$Exe,'--clients-closed') 60
            $results+=[pscustomobject]@{client=$client.name;status=$r.status;detail=$r}
        }catch{$results+=[pscustomobject]@{client=$client.name;status='error';detail=(Hide-Secrets $_.Exception.Message)}}
    }
    # Claude Code's live JSON is never rewritten directly. Preserve custom entries.
    $claudeConfig=if($env:CLAUDE_CONFIG_DIR){Join-Path $env:CLAUDE_CONFIG_DIR '.claude.json'}else{Join-Path $env:USERPROFILE '.claude.json'}
    $cli=@(Get-Command claude.exe -CommandType Application -ErrorAction SilentlyContinue|Select-Object -First 1)
    if($cli.Count){
        try{
            $r=Invoke-Json $PythonYolu @('-B',(Join-Path $PSScriptRoot 'claude_bagla.py'),'--path',$claudeConfig,'--cli',$cli[0].Source,'--exe',$Exe,'--clients-closed') 240
            $results+=[pscustomobject]@{client='Claude Code';status=$r.status;detail=$r}
        }catch{$results+=[pscustomobject]@{client='Claude Code';status='error';detail=(Hide-Secrets $_.Exception.Message)}}
    }elseif(Test-Path -LiteralPath $claudeConfig){
        $results+=[pscustomobject]@{client='Claude Code';status='deferred';detail='Yerel claude.exe yok; eski .cmd/özel kayıt değiştirilmedi.'}
    }
    return $results
}
$bindingGuard=$null
try{
    if($BindOnly){
        $state=Join-Path $env:LOCALAPPDATA 'guncelleyici';Assert-PlainPath $state;[void][IO.Directory]::CreateDirectory($state)
        $guardPath=Join-Path $state 'update.guard';Assert-PlainPath $guardPath
        $bindingGuard=New-Object IO.FileStream($guardPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
        if(Test-Path -LiteralPath (Join-Path $state 'active-transaction.json')){throw 'Yarım işlem kaydı var; önce BT incelemesi gerekli.'}

        if(-not $ExePath){throw '-BindOnly için imzalı yerel sunucu yolu gerekli.'}
        Assert-PlainPath $ExePath;$sig=Get-AuthenticodeSignature -LiteralPath $ExePath
        if($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notlike '*O=Microsoft Corporation*'){throw 'Sunucu Microsoft imzası doğrulanamadı.'}
        $test=McpTest $ExePath;$bindings=@(Bind-Clients $ExePath)
        $warn=@($bindings|Where-Object {$_.status -in 'error','deferred'}).Count -gt 0
        $observed=PbiLocal
        $fingerprint=Text-Sha256 ($observed|ConvertTo-Json -Depth 30 -Compress)
        Write-AtomicJson (Join-Path $state 'health\powerbi.json') @{checked_at=[DateTime]::UtcNow.ToString('o');local_fingerprint=$fingerprint;health='PASS';pending=$warn;result=@{bindings=$bindings;test=$test}}
        Emit-Result ([pscustomobject]@{key='powerbi';durum='MEVCUT';ozet=$(if($warn){'UYARI'}else{'GEÇTİ'});ayarlar=$bindings;testler=@($test);health='PASS';exe=$ExePath})
    }
    $local=PbiLocal
    if($TestOnly){
        if(-not $local.path){throw 'Test edilecek Power BI MCP bulunamadı.'}
        $sig=Get-AuthenticodeSignature -LiteralPath $local.path
        if($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notlike '*O=Microsoft Corporation*'){throw 'Sunucu imzası doğrulanamadı.'}
        $test=McpTest $local.path
        Emit-Result ([pscustomobject]@{key='powerbi';local=$local;surum=$local.version;ozet='GEÇTİ';health='PASS';testler=@($test);test_scope='server only; client bindings not modified or certified'})
    }
    if($YalnizBul -or $LocalOnly){
        $target=$null;$why='';if(-not $LocalOnly){try{$target=PbiTarget}catch{$why=Hide-Secrets $_.Exception.Message}}
        Emit-Result ([pscustomobject]@{key='powerbi';local=$local;surum=$local.version;target=$target;hedef_surum=(Read-Field $target 'version');neden=$why;health='NOT_RUN'})
    }
    $target=Read-Target 'powerbi' $TargetFile $TargetSha256;$v=[string]$target.version;$null=Stable-Version $v
    Assert-PlainPath $target.archive
    if((File-Sha256 $target.archive) -cne $target.sha256){throw 'VSIX onaylanan SHA-256 ile eşleşmiyor.'}
    $destination=Join-Path $KOK ($v+'-'+[guid]::NewGuid().ToString('N'))
    try{
        Expand-SafeZip $target.archive $destination
        $manifest=Join-Path $destination 'extension.vsixmanifest'
        $xml=Read-SafeXml (Get-Content -LiteralPath $manifest -Raw -Encoding UTF8)
        $id=$xml.PackageManifest.Metadata.Identity
        if($id.Publisher -ne 'analysis-services' -or $id.Id -ne 'powerbi-modeling-mcp' -or $id.Version -ne $v -or $id.TargetPlatform -ne 'win32-x64'){throw 'VSIX yayıncı/sürüm/platform kimliği farklı.'}
        $exe=Join-Path $destination $EXE_REL;$sig=Get-AuthenticodeSignature -LiteralPath $exe
        if($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notlike '*O=Microsoft Corporation*'){throw 'Microsoft yayıncı imzası doğrulanamadı.'}
        $test=McpTest $exe
    }catch{
        $quarantine=Join-Path $KOK '_karantina';[void][IO.Directory]::CreateDirectory($quarantine)
        if(Test-Path -LiteralPath $destination){Move-Item -LiteralPath $destination -Destination $quarantine -ErrorAction SilentlyContinue}
        throw
    }
    Write-AtomicJson (Join-Path $destination '.guncelleyici-verified.json') @{version=$v;sha256=(File-Sha256 $exe);tested_at=[DateTime]::UtcNow.ToString('o')}
    Write-AtomicJson (Join-Path $KOK 'active-install.json') @{path=$exe;version=$v;sha256=(File-Sha256 $exe)}
    $bindings=@(Bind-Clients $exe)
    $warn=@($bindings|Where-Object {$_.status -in 'error','deferred'}).Count -gt 0
    $recovery=@($bindings|Where-Object {[bool](Read-Field (Read-Field $_ 'detail') 'recovery_required' $false)}).Count -gt 0
    Emit-Result ([pscustomobject]@{key='powerbi';durum='KURULDU';surum=$v;exe=$exe;ozet=$(if($warn){'UYARI'}else{'GEÇTİ'});health='PASS';
        ayarlar=$bindings;testler=@($test);previous_path=$local.path;restart_required=$true;recovery_required=$recovery;
        neden=$(if($warn){'Sunucu doğrulandı; istemci bağlantılarının bir bölümü tamamlanmadı. Mevcut ayarlar/eski sürümler korundu.'}else{''})})
}catch{Emit-Result ([pscustomobject]@{key='powerbi';durum='BASARISIZ';ozet='ENGEL';health='FAIL';neden=(Hide-Secrets $_.Exception.Message)}) 2}finally{if($bindingGuard){$bindingGuard.Dispose()}}