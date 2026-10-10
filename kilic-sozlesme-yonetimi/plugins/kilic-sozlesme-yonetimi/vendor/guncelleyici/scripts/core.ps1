# Shared orchestration; definitions only. No GUI and no installation on import.
. (Join-Path $PSScriptRoot 'program-ortak.ps1')
$script:Skill=Split-Path $PSScriptRoot -Parent
$skillItem=Get-Item -LiteralPath $script:Skill -Force
if($skillItem.Attributes -band [IO.FileAttributes]::ReparsePoint){
    $targets=Read-Field $skillItem 'Target'
    if(-not $targets){throw 'Skill fiziksel kökü çözülemedi.'}
    $resolved=[string]@($targets)[0]
    if(-not [IO.Path]::IsPathRooted($resolved)){$resolved=Join-Path (Split-Path $script:Skill -Parent) $resolved}
    $script:Skill=[IO.Path]::GetFullPath($resolved)
}
$script:Python=$null;$script:Node=$null
$script:StateRoot=Join-Path $env:LOCALAPPDATA 'guncelleyici'
$script:Names=[ordered]@{python='Python';libraries='Python kütüphaneleri (12)';node='Node.js LTS';pnpm='pnpm';duckdb='DuckDB';powerbi='Power BI Modeling MCP';pdf='DuckDB PDF eklentisi (isteğe bağlı)'}
function Invoke-PS([string]$Name,[string[]]$Extra,[int]$Timeout=1800){
    return Invoke-Json "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" (@('-NoProfile','-File',(Join-Path $PSScriptRoot $Name))+$Extra) $Timeout
}
function Get-Identity {
    return [ordered]@{computer=$env:COMPUTERNAME;sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;skill_root=[IO.Path]::GetFullPath($script:Skill)}
}
function Get-CodeFingerprint {
    # Bind approval to every operational instruction/config/script, not only executable code.
    # Test artifacts and generated reports are intentionally excluded so test reruns do not stale a plan.
    $files=@(Get-ChildItem -LiteralPath $script:Skill -File -Recurse | Where-Object {
        $rel=$_.FullName.Substring($script:Skill.Length).TrimStart('\')
        if($rel -like 'tests\*' -or $rel -eq 'CHANGELOG.md' -or $rel -eq 'MANIFEST.sha256.json' -or
           $rel -eq 'references\TEST_RAPORU.md' -or $rel -eq 'references\tests-python.json' -or
           $rel -like '*\__pycache__\*' -or $_.Extension -eq '.pyc'){return $false}
        return ($rel -in @('SKILL.md','VERSION','BUILD.json','agents\openai.yaml') -or
                $rel -like 'scripts\*' -or $rel -like 'config\*' -or $rel -like 'references\*')
    } | Sort-Object FullName)
    $entries=@($files | ForEach-Object { $_.FullName.Substring($script:Skill.Length)+(File-Sha256 $_.FullName) })
    return Text-Sha256 ($entries -join "`n")
}
function Object-Fingerprint($Object){return Text-Sha256 ($Object|ConvertTo-Json -Depth 30 -Compress)}
function Discover-Runtimes {
    $p=Invoke-PS 'python-kur.ps1' @('-LocalOnly') 180
    $script:Python=Read-Field $p 'python'
    $n=Invoke-PS 'node-kur.ps1' @('-LocalOnly') 180
    $script:Node=Read-Field $n 'node'
}
function Get-Observation([string]$Key,[switch]$LocalOnly,[string]$Cache,[bool]$Repair=$false){
    $psMode=if($LocalOnly){'-LocalOnly'}else{'-YalnizBul'}
    $pyMode=if($LocalOnly){'--local-only'}else{'--yalniz-bul'}
    switch($Key){
        'python'{$r=Invoke-PS 'python-kur.ps1' @($psMode) 180;$script:Python=Read-Field $r 'python';return $r}
        'node'{$r=Invoke-PS 'node-kur.ps1' @($psMode) 180;$script:Node=Read-Field $r 'node';return $r}
        'libraries'{
            if(-not $script:Python){return [pscustomobject]@{local=@{python=$null};target=$null;blocked=$true;neden='Önce desteklenen Python kurulmalı; ardından yeniden tarayın.'}}
            $r=Invoke-Json $script:Python @('-B',(Join-Path $PSScriptRoot 'kurulum-testi.py'),$pyMode) 180
            if(-not $LocalOnly -and $r.target){$r.target.repair=$Repair};return $r
        }
        'pnpm'{return Invoke-PS 'pnpm-kur.ps1' @($psMode,'-NodeYolu',([string]$script:Node)) 240}
        'duckdb'{
            if(-not $script:Python){return [pscustomobject]@{local=@{python=$null};target=$null;blocked=$true;neden='Önce Python kurulmalı; uyumlu DuckDB planı sonraki taramada oluşturulur.'}}
            $args=@('-B',(Join-Path $PSScriptRoot 'python-paket-kur.py'),'duckdb',$pyMode);if($Repair){$args+='--repair'}
            return Invoke-Json $script:Python $args 420
        }
        'powerbi'{
            $args=@($psMode,'-PythonYolu',([string]$script:Python));if($Cache){$args+=@('-CacheRoot',$Cache)}
            return Invoke-PS 'powerbi-mcp-kur.ps1' $args 600
        }
        'pdf'{
            if(-not $script:Python){return [pscustomobject]@{local=@{python=$null};target=$null;blocked=$true;neden='Önce Python ve DuckDB kurulmalı.'}}
            $action=if($LocalOnly){'probe'}else{'scan'}
            $args=@('-B',(Join-Path $PSScriptRoot 'duckdb_pdf.py'),$action);if(-not $LocalOnly){$args+=@('--cache',$Cache)}
            return Invoke-Json $script:Python $args 420
        }
    }
    throw 'Bilinmeyen bileşen.'
}
function Read-Health([string]$Key,$Local){
    $file=Join-Path $script:StateRoot ('health\'+$Key+'.json')
    if(-not (Test-Path -LiteralPath $file)){return $null}
    try{
        $state=Get-Content -LiteralPath $file -Raw -Encoding UTF8|ConvertFrom-Json
        if($state.local_fingerprint -ceq (Object-Fingerprint $Local)){return $state}
    }catch{}
    return $null
}
function Get-DisplayVersion([string]$Key,$Observation){
    $v=Read-Field $Observation 'surum'
    if(-not $v){$v=Read-Field (Read-Field $Observation 'local') 'version'}
    if($v){return [string]$v}
    # A found-but-unverifiable install must never be reported as absent.
    if([bool](Read-Field (Read-Field $Observation 'local') 'unmanaged' $false)){return 'Yüklü · sürüm doğrulanamadı'}
    return 'Yüklü değil / doğrulanamadı'
}
function Get-LibraryEffects($Before,$Target,[bool]$Repair){
    $effects=@();$locals=Read-Field $Before 'packages'
    $packages=Read-Field $Target 'packages' @()
    foreach($pkg in $packages){
        $row=Read-Field $locals ([string]$pkg.name);$from=[string](Read-Field $row 'version');$to=[string]$pkg.version
        if(-not $from){$action='install'}elseif($from -ceq $to){if($Repair){$action='reinstall'}else{continue}}else{
            $action='change';try{if([version]$from -gt [version]$to){$action='downgrade'}elseif([version]$from -lt [version]$to){$action='upgrade'}}catch{}
        }
        $effects+=[pscustomobject]@{type='python_package';package=[string]$pkg.name;from=$(if($from){$from}else{$null});to=$to;action=$action}
    }
    return @($effects)
}
function Get-ComponentEffects([string]$Key,$Before,$Target,[bool]$Repair){
    if(-not $Target){return @()}
    switch($Key){
        'python'{return @([pscustomobject]@{type='shared_runtime';action='install_or_upgrade';target=[string]$Target.version;source='python.org';user_path_change=$true;rollback='manual_if_installer_mutates'})}
        'libraries'{return @(Get-LibraryEffects $Before $Target $Repair)}
        'node'{return @([pscustomobject]@{type='shared_runtime';action=$(if($Repair){'reinstall'}else{'install_or_upgrade'});target=[string]$Target.version;user_path_change=$true;previous_tree_backup=$true})}
        'pnpm'{return @([pscustomobject]@{type='shared_runtime';action=$(if($Repair){'reinstall'}else{'install_or_upgrade'});target=[string]$Target.version;user_path_change=$true;previous_tree_backup=$true})}
        'duckdb'{return @([pscustomobject]@{type='shared_python_environment';action=$(if($Repair){'force_reinstall'}else{'install_or_upgrade'});target=[string]$Target.version;pip_user_possible=$true;transactional_rollback=$false})}
        'powerbi'{return @([pscustomobject]@{type='mcp_server';action=$(if($Repair){'reinstall'}else{'install_or_upgrade'});target=[string]$Target.version;client_binding='Codex/Claude only when clients are closed; unknown fields preserved';restart_required=$true})}
        'pdf'{return @([pscustomobject]@{type='community_extension';action=$(if($Repair){'reinstall'}else{'install_or_upgrade'});engine=[string]$Target.engine;sha256=[string]$Target.sha256;optional=$true;native_test_required=$true})}
    }
    return @()
}
function Build-Plan([bool]$IncludePdf,[string[]]$RepairKeys){
    $cache=Join-Path $env:TEMP ('guncelleyici-plan-'+[guid]::NewGuid().ToString('N'))
    [void][IO.Directory]::CreateDirectory($cache)
    $components=@();$rows=@()
    foreach($key in $script:Names.Keys){
        $repair=$key -in $RepairKeys
        try{
            if($key -eq 'pdf' -and -not $IncludePdf){
                $o=[pscustomobject]@{local=@{};target=$null;neden='İsteğe bağlı. PDF seçimi için -IncludePdf ile plan hazırlayın.';blocked=$true}
            }else{$o=Get-Observation $key -Cache $cache -Repair $repair}
            $before=Read-Field $o 'local';$target=Read-Field $o 'target';$blocked=[bool](Read-Field $o 'blocked' $false)
            $note=[string](Read-Field $o 'neden' (Read-Field $o 'warning' ''))
            $ready=$false;$status='Kontrol edilemedi';$current=Get-DisplayVersion $key $o
            if($target -and -not $blocked){
                if($key -eq 'libraries'){
                    $ready=([int](Read-Field $o 'matched' 0) -ne 12) -or $repair
                    $status=if($ready){'Sabit sete eşitleme; bazı sürümler düşebilir'}else{'Paket sürümleri hedef sette'}
                }elseif($key -eq 'pdf'){
                    $ready=(Read-Field $before 'sha256') -cne $target.sha256 -or $repair
                    $status=if($ready){'Community paket; imza/işlev testi uygulamada'}else{'Paket hash bilgisi güncel'}
                }else{
                    $installedVersion=[string](Read-Field $before 'version')
                    if(-not $installedVersion){$ready=$true;$status='Kurulum seçilebilir'}
                    elseif($installedVersion -notmatch '^\d+\.\d+\.\d+$'){$blocked=$true;$status='Özel/ön sürüm kurulum; otomatik değişiklik yok'}
                    elseif([version]$installedVersion -lt [version]$target.version){$ready=$true;$status='Güncelleme seçilebilir'}
                    elseif([version]$installedVersion -eq [version]$target.version){$ready=$repair;$status=if($ready){'Açık onarım seçimi'}else{'Sürüm güncel'}}
                    else{$status='Yüklü sürüm yayından yeni; değiştirilmez'}
                }
            }elseif($blocked){$status='Bağımlılık/bütünlük nedeniyle uygulanamaz';if(-not $note){$note='Bileşen engel nedeni bildirmedi; otomatik değişiklik yapılmaz, yeniden tarayın.'}}
            $health=Read-Health $key $before
            $pending=$health -and ((Read-Field $health 'health') -eq 'FAIL' -or [bool](Read-Field $health 'pending' $false))
            if($pending){$status+=' · önceki kontrol/bağlantı eksikliği sürüyor'}
            if($target){$target|Add-Member -NotePropertyName repair -NotePropertyValue $repair -Force}
            $effects=@(Get-ComponentEffects $key $before $target $repair)
            if($key -eq 'libraries' -and @($effects|Where-Object {$_.action -eq 'downgrade'}).Count){
                $downs=@($effects|Where-Object {$_.action -eq 'downgrade'}|ForEach-Object {$_.package+' '+$_.from+'→'+$_.to})
                $note=(($note+'; olası düşürme: '+($downs -join ', ')).Trim('; '))
            }
            $selected=$ready -and $key -ne 'pdf'
            $components+=[pscustomobject]@{key=$key;name=$script:Names[$key];before=$before;before_fingerprint=(Object-Fingerprint $before);target=$target;selectable=$ready;selected=$selected;repair=$repair;reason=$note;effects=$effects}
            $latest=if($key -eq 'libraries' -and $target){'12 paket · sabit set'}elseif($key -eq 'pdf' -and $target){$target.engine+' / SHA '+$target.sha256.Substring(0,12)}elseif($target){[string]$target.version}else{'Kontrol edilemedi'}
            $rows+=[pscustomobject]@{key=$key;ad=$script:Names[$key];yuklu=$current;guncel=$latest;durum=$status;ayrinti=$note;secili=$selected;secilebilir=$ready;blocked=$blocked;pending=[bool]$pending;health=$(if($health){$health.health}else{'NOT_RUN'});effects=$effects}
        }catch{
            $note=Hide-Secrets $_.Exception.Message
            $components+=[pscustomobject]@{key=$key;name=$script:Names[$key];before=$null;before_fingerprint='';target=$null;selectable=$false;selected=$false;repair=$repair;reason=$note;effects=@()}
            $rows+=[pscustomobject]@{key=$key;ad=$script:Names[$key];yuklu='Tespit edilemedi';guncel='Kontrol edilemedi';durum='Kontrol edilemedi';ayrinti=$note;secili=$false;secilebilir=$false;blocked=$true;pending=$true;health='NOT_RUN';effects=@()}
        }
    }
    $globalEffects=@([pscustomobject]@{type='legacy_skill_cleanup';when='any non-empty apply';scope='standard user skill paths';junction_target_preserved=$true;verified_physical_tree_quarantined=$true})
    $plan=[ordered]@{schema='guncelleyici-plan/v1';id=[guid]::NewGuid().ToString('N');created_at=[DateTime]::UtcNow.ToString('o');expires_at=[DateTime]::UtcNow.AddHours(1).ToString('o');identity=(Get-Identity);code_fingerprint=(Get-CodeFingerprint);global_effects=$globalEffects;components=$components;rows=$rows}
    $path=Join-Path $cache 'plan.json';Write-AtomicJson $path $plan;$fingerprint=File-Sha256 $path
    $required=@($rows|Where-Object {$_.key -ne 'pdf' -or $IncludePdf})
    $current=@($required|Where-Object {$_.secilebilir -or $_.pending -or $_.blocked -or $_.guncel -eq 'Kontrol edilemedi'}).Count -eq 0
    return [pscustomobject]@{status=$(if($current){'up_to_date'}else{'selection_required'});message=$(if($current){'Sürüm kontrolü güncel; bu taramada işlev testi çalıştırılmadı.'}else{'Seçimleri kontrol edin; yalnız açık Güncelle onayı uygulama yetkisi verir.'});plan_file=$path;fingerprint=$fingerprint;rows=$rows;global_effects=$globalEffects}
}
function Enter-Guard {
    Assert-PlainPath $script:StateRoot;[void][IO.Directory]::CreateDirectory($script:StateRoot)
    $path=Join-Path $script:StateRoot 'update.guard';Assert-PlainPath $path
    try{$handle=New-Object IO.FileStream($path,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)}catch{throw 'Başka bir Güncelleyici işlemi çalışıyor.'}
    return $handle
}
function Invoke-Selected([string]$Key,$Component,[string]$SessionPath){
    $path=Join-Path $SessionPath ($Key+'-target.json')
    Write-AtomicJson $path ([ordered]@{key=$Key;run_token=$env:GUNCELLEYICI_RUN_TOKEN;target=$Component.target})
    $hash=File-Sha256 $path;$ps=@('-TargetFile',$path,'-TargetSha256',$hash);$py=@('--target-file',$path,'--target-sha256',$hash)
    switch($Key){
        'python'{$r=Invoke-PS 'python-kur.ps1' $ps 1800;if(Read-Field $r 'python'){$script:Python=$r.python};return $r}
        'node'{$r=Invoke-PS 'node-kur.ps1' $ps 1800;if(Read-Field $r 'node'){$script:Node=$r.node};return $r}
        'pnpm'{return Invoke-PS 'pnpm-kur.ps1' ($ps+@('-NodeYolu',([string]$script:Node))) 1200}
        'libraries'{if(-not $script:Python){throw 'Python yok.'};return Invoke-Json $script:Python (@('-B',(Join-Path $PSScriptRoot 'kurulum-testi.py'))+$py) 1800}
        'duckdb'{if(-not $script:Python){throw 'Python yok.'};return Invoke-Json $script:Python (@('-B',(Join-Path $PSScriptRoot 'python-paket-kur.py'),'duckdb')+$py) 1800}
        'powerbi'{return Invoke-PS 'powerbi-mcp-kur.ps1' ($ps+@('-PythonYolu',([string]$script:Python))) 900}
        'pdf'{return Invoke-Json $script:Python (@('-B',(Join-Path $PSScriptRoot 'duckdb_pdf.py'),'apply')+$py) 600}
    }
    throw 'Bilinmeyen bileşen.'
}
function Remove-LegacySkill {
    $notes=@()
    foreach($root in @((Join-Path $env:USERPROFILE '.codex\skills'),(Join-Path $env:USERPROFILE '.claude\skills'),(Join-Path $env:USERPROFILE '.agents\skills'))){
        foreach($name in 'program-guncelle','program-guncelleme'){
            $candidate=Join-Path $root $name;if(-not (Test-Path -LiteralPath $candidate)){continue}
            try{
                $item=Get-Item -LiteralPath $candidate -Force
                if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){[IO.Directory]::Delete($candidate);$notes+=@{path=$candidate;action='link_removed';target_preserved=$true};continue}
                $definition=Join-Path $candidate 'SKILL.md'
                if(-not (Test-Path -LiteralPath $definition) -or -not (Select-String -LiteralPath $definition -Pattern '^name:\s*program-guncelle(me)?\s*$' -Quiet)){$notes+=@{path=$candidate;action='unchanged';reason='identity_unknown'};continue}
                Assert-PlainPath $candidate
                $quarantine=Join-Path $script:StateRoot 'kaldirilan-eski-skill';Assert-PlainPath $quarantine;[void][IO.Directory]::CreateDirectory($quarantine)
                $dest=Join-Path $quarantine ($name+'-'+[guid]::NewGuid().ToString('N'))
                Move-Item -LiteralPath $candidate -Destination $dest -ErrorAction Stop
                $notes+=@{path=$candidate;action='quarantined';destination=$dest}
            }catch{$notes+=@{path=$candidate;action='error';reason=(Hide-Secrets $_.Exception.Message)}}
        }
    }
    return $notes
}
function Apply-Plan([string]$PlanFile,[string]$Fingerprint,[string[]]$Keys,[bool]$MaintenanceWindow,[bool]$Confirmed){
    if(-not $Keys.Count){return [pscustomobject]@{status='cancelled';rows=@();results=@()}}
    if(-not $Confirmed){throw 'Açık uygulama teyidi gerekli; seçim değişikliği kurulum yetkisi değildir.'}
    Assert-PlainPath $PlanFile
    if($Fingerprint -notmatch '^[a-f0-9]{64}$' -or (File-Sha256 $PlanFile) -cne $Fingerprint){throw 'Plan/parmak izi değişti; yeniden tarayın.'}
    $plan=Get-Content -LiteralPath $PlanFile -Raw -Encoding UTF8|ConvertFrom-Json
    if($plan.schema -ne 'guncelleyici-plan/v1' -or [DateTimeOffset]::Parse($plan.expires_at).UtcDateTime -le [DateTime]::UtcNow){throw 'Plan geçersiz veya süresi dolmuş.'}
    if((Object-Fingerprint $plan.identity) -cne (Object-Fingerprint (Get-Identity)) -or $plan.code_fingerprint -cne (Get-CodeFingerprint)){throw 'Bilgisayar/kullanıcı/skill kodu değişti; yeniden tarayın.'}
    $selected=@($plan.components|Where-Object {$_.key -in $Keys})
    if($selected.Count -ne $Keys.Count -or @($selected|Where-Object {-not $_.selectable}).Count){throw 'Bilinmeyen/seçilemeyen bileşen.'}
    $shared=@($Keys|Where-Object {$_ -in 'python','libraries','node','pnpm','duckdb'})
    if($shared.Count -and -not $MaintenanceWindow){throw 'Paylaşılan çalışma ortamı bakım penceresi onayı gerekli.'}
    $guard=Enter-Guard
    $journal=Join-Path $script:StateRoot 'active-transaction.json'
    $previousToken=$env:GUNCELLEYICI_RUN_TOKEN;$previousMaintenance=$env:GUNCELLEYICI_MAINTENANCE
    try{
        if(Test-Path -LiteralPath $journal){throw 'Yarım kalmış işlem kaydı var; otomatik silinmez. BT kaydı incelemeli.'}
        # Revalidate AFTER acquiring the installation lock; do not resolve new online targets.
        if((File-Sha256 $PlanFile) -cne $Fingerprint -or $plan.code_fingerprint -cne (Get-CodeFingerprint)){throw 'Kilit alınırken plan/kod değişti.'}
        Discover-Runtimes
        foreach($component in $selected){
            $current=Get-Observation $component.key -LocalOnly
            if((Object-Fingerprint (Read-Field $current 'local')) -cne $component.before_fingerprint){
                return [pscustomobject]@{status='stale';message='Yerel durum değişti; yeni tarama ve seçim gerekli.';rows=$plan.rows;results=@()}
            }
        }
        if($shared.Count){$env:GUNCELLEYICI_MAINTENANCE='confirmed';Assert-MaintenanceWindow}
        $env:GUNCELLEYICI_RUN_TOKEN=[guid]::NewGuid().ToString('N')
        $session=Join-Path $script:StateRoot ('sessions\'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmss')+'-'+$env:GUNCELLEYICI_RUN_TOKEN)
        [void][IO.Directory]::CreateDirectory($session)
        Write-AtomicJson (Join-Path $session 'approved-plan.json') $plan
        $approvedEffects=@()
        foreach($component in $selected){foreach($effect in @($component.effects)){$approvedEffects+=@([pscustomobject]@{key=$component.key;effect=$effect})}}
        $record=[ordered]@{schema='guncelleyici-result/v1';run_id=$env:GUNCELLEYICI_RUN_TOKEN;plan_fingerprint=$Fingerprint;confirmation='explicit';selected_keys=$Keys;approved_effects=$approvedEffects;global_effects=$plan.global_effects;started_at=[DateTime]::UtcNow.ToString('o');results=@();maintenance=@();status='running'}
        Write-AtomicJson $journal @{session=$session;phase='STARTED';selected_keys=$Keys}
        $cleanup=@(Remove-LegacySkill);$record.maintenance=$cleanup
        $rows=@($plan.rows);$uncertain=$false
        foreach($row in $rows){$row.secili=$row.key -in $Keys;if(-not $row.secili -and $row.secilebilir){$row.durum='Atlandı · seçilmedi'}}
        foreach($component in $selected){
            if($uncertain){
                $row=@($rows|Where-Object {$_.key -eq $component.key})[0]
                $row.durum='Atlandı · önceki işlemde kurtarma incelemesi gerekli';$row.pending=$true
                $record.results+=@([pscustomobject]@{key=$component.key;ad=$component.name;sonuc='Atlandı';details=@{reason='recovery_required'}})
                continue
            }
            Write-AtomicJson $journal @{session=$session;phase='APPLYING';component=$component.key}
            try{
                $r=Invoke-Selected $component.key $component $session
                $after=Get-Observation $component.key -LocalOnly
                $state=Read-Field $r 'ozet' ''
                if(-not $state){$state=if((Read-Field $r 'status') -in 'installed','up_to_date'){'GEÇTİ'}else{'ENGEL'}}
                $actual=Read-Field (Read-Field $after 'local') 'version'
                if($component.key -in 'python','node','pnpm','duckdb','powerbi' -and $state -eq 'GEÇTİ' -and $actual -cne $component.target.version){$state='ENGEL';$r|Add-Member -NotePropertyName neden -NotePropertyValue 'Yerel son durum onaylanan hedefle aynı değil.' -Force}
                if($component.key -eq 'pdf' -and (Read-Field (Read-Field $after 'local') 'sha256') -cne $component.target.sha256){$state='ENGEL'}
                $health=Read-Field $r 'health' 'NOT_RUN';if($state -eq 'ENGEL'){$health='FAIL'}
                $receipt=@{checked_at=[DateTime]::UtcNow.ToString('o');local_fingerprint=(Object-Fingerprint (Read-Field $after 'local'));health=$health;pending=($state -ne 'GEÇTİ');result=$r}
                Write-AtomicJson (Join-Path $script:StateRoot ('health\'+$component.key+'.json')) $receipt
                $result=[pscustomobject]@{key=$component.key;ad=$component.name;sonuc=$(if($state -eq 'GEÇTİ'){'Tamamlandı'}elseif($state -eq 'UYARI'){'Uyarı'}else{'Hata'});details=$r;after=(Read-Field $after 'local')}
                $row=@($rows|Where-Object {$_.key -eq $component.key})[0]
                $row.yuklu=Get-DisplayVersion $component.key $after;$row.durum=$result.sonuc;$row.ayrinti=[string](Read-Field $r 'neden' (Read-Field $r 'warning' ''));$row.health=$health;$row.pending=($state -ne 'GEÇTİ')
                $uncertain=[bool](Read-Field $r 'recovery_required' $false)
                if($state -eq 'ENGEL' -and $component.key -in 'libraries','duckdb'){$uncertain=$true}
            }catch{
                $uncertain=$true
                $row=@($rows|Where-Object {$_.key -eq $component.key})[0]
                $row.durum='Hata · yerel durum doğrulanamadı';$row.pending=$true;$row.health='FAIL';$row.ayrinti=Hide-Secrets $_.Exception.Message
                $result=[pscustomobject]@{key=$component.key;ad=$component.name;sonuc='Hata';details=@{neden=(Hide-Secrets $_.Exception.Message);recovery_required=$true}}
            }
            $record.results+=@($result);Write-AtomicJson (Join-Path $session 'result.json') $record
        }
        $states=@($record.results|ForEach-Object {$_.sonuc})
        $record.status=if($states -contains 'Hata'){'error'}elseif($states -contains 'Uyarı' -or @($cleanup|Where-Object {$_.action -eq 'error'}).Count){'warning'}else{'completed'}
        $record['finished_at']=[DateTime]::UtcNow.ToString('o');$record['rows']=$rows;$record['recovery_required']=$uncertain
        Write-AtomicJson (Join-Path $session 'result.json') $record
        if(-not $uncertain){Remove-Item -LiteralPath $journal -Force}else{Write-AtomicJson $journal @{session=$session;phase='REVIEW_REQUIRED';reason='İşlem durumu/geri dönüş doğrulanmalı.'}}
        return [pscustomobject]@{status=$record.status;results=$record.results;rows=$rows;maintenance=$cleanup;approved_effects=$approvedEffects;global_effects=$plan.global_effects;report=(Join-Path $session 'result.json');recovery_required=$uncertain}
    }finally{$env:GUNCELLEYICI_RUN_TOKEN=$previousToken;$env:GUNCELLEYICI_MAINTENANCE=$previousMaintenance;$guard.Dispose()}
}

function Verify-Selected([string[]]$Keys){
    if(-not $Keys.Count){$Keys=@('python','libraries','node','pnpm','duckdb','powerbi')}
    foreach($key in $Keys){if($key -notin $script:Names.Keys){throw 'Bilinmeyen kontrol bileşeni.'}}
    $guard=Enter-Guard
    try{
        Discover-Runtimes
        $rows=@();$results=@()
        foreach($key in $Keys){
            try{
                $before=Get-Observation $key -LocalOnly
                $prior=Read-Health $key (Read-Field $before 'local')
                switch($key){
                    'python'{$r=Invoke-PS 'python-kur.ps1' @('-TestOnly') 120}
                    'node'{$r=Invoke-PS 'node-kur.ps1' @('-TestOnly') 120}
                    'pnpm'{$r=Invoke-PS 'pnpm-kur.ps1' @('-TestOnly','-NodeYolu',([string]$script:Node)) 120}
                    'powerbi'{$r=Invoke-PS 'powerbi-mcp-kur.ps1' @('-TestOnly') 180}
                    'libraries'{
                        if(-not $script:Python){throw 'Python bulunamadı.'}
                        $r=Invoke-Json $script:Python @('-B',(Join-Path $PSScriptRoot 'kurulum-testi.py'),'--kurma') 420
                    }
                    'duckdb'{
                        if(-not $script:Python){throw 'Python bulunamadı.'}
                        $r=Invoke-Json $script:Python @('-B',(Join-Path $PSScriptRoot 'python-paket-kur.py'),'duckdb','--test-only') 180
                    }
                    'pdf'{
                        if(-not $script:Python){throw 'Python bulunamadı.'}
                        $r=Invoke-Json $script:Python @('-B',(Join-Path $PSScriptRoot 'duckdb_pdf.py'),'test') 240
                        $r|Add-Member -NotePropertyName ozet -NotePropertyValue $(if((Read-Field $r 'status') -eq 'PASS'){'GEÇTİ'}else{'ENGEL'}) -Force
                        $r|Add-Member -NotePropertyName health -NotePropertyValue $(if((Read-Field $r 'status') -eq 'PASS'){'PASS'}else{'FAIL'}) -Force
                    }
                }
                $after=Get-Observation $key -LocalOnly
                $state=[string](Read-Field $r 'ozet' 'ENGEL');$health=Read-Field $r 'health' 'NOT_RUN'
                $pending=$state -ne 'GEÇTİ'
                # A server-only test does not certify or repair client configuration.
                if($key -eq 'powerbi' -and $prior -and [bool](Read-Field $prior 'pending' $false)){$pending=$true;$state='UYARI'}
                $receipt=@{checked_at=[DateTime]::UtcNow.ToString('o');local_fingerprint=(Object-Fingerprint (Read-Field $after 'local'));health=$health;pending=$pending;result=$r}
                Write-AtomicJson (Join-Path $script:StateRoot ('health\'+$key+'.json')) $receipt
                $label=if($state -eq 'GEÇTİ'){'Kontrol geçti'}elseif($state -eq 'UYARI'){'Uyarı / bağlantı eksikliği'}else{'Kontrol başarısız'}
                $rows+=[pscustomobject]@{key=$key;ad=$script:Names[$key];yuklu=(Get-DisplayVersion $key $after);durum=$label;health=$health;pending=$pending;ayrinti=$r}
                $results+=[pscustomobject]@{key=$key;ozet=$state;details=$r}
            }catch{
                $detail=Hide-Secrets $_.Exception.Message
                $rows+=[pscustomobject]@{key=$key;ad=$script:Names[$key];yuklu='Doğrulanamadı';durum='Kontrol başarısız';health='FAIL';pending=$true;ayrinti=$detail}
                $results+=[pscustomobject]@{key=$key;ozet='ENGEL';details=$detail}
                try{
                    $after=Get-Observation $key -LocalOnly
                    Write-AtomicJson (Join-Path $script:StateRoot ('health\'+$key+'.json')) @{checked_at=[DateTime]::UtcNow.ToString('o');local_fingerprint=(Object-Fingerprint (Read-Field $after 'local'));health='FAIL';pending=$true;result=@{neden=$detail}}
                }catch{}
            }
        }
        $states=@($results|ForEach-Object {$_.ozet})
        $status=if($states -contains 'ENGEL'){'error'}elseif($states -contains 'UYARI'){'warning'}else{'completed'}
        $record=[ordered]@{status=$status;mode='verify';created_at=[DateTime]::UtcNow.ToString('o');rows=$rows;results=$results;recovery_journal_preserved=(Test-Path -LiteralPath (Join-Path $script:StateRoot 'active-transaction.json'))}
        $file=Join-Path $script:StateRoot ('sessions\verify-'+[guid]::NewGuid().ToString('N')+'.json')
        Write-AtomicJson $file $record
        return [pscustomobject]@{status=$status;rows=$rows;results=$results;report=$file;message='Yalnız belirtilen işlev/bütünlük kontrolleri yapıldı; hiçbir paket kurulmadı.'}
    }finally{$guard.Dispose()}
}