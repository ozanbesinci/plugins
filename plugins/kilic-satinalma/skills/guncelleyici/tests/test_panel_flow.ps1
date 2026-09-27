$ErrorActionPreference = 'Stop'
$panel = Join-Path $PSScriptRoot '..\scripts\panel.ps1'
. $panel -LayoutTest | Out-Null
$realInstall = (Get-Command Install-Selected).ScriptBlock
function Assert([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }

$testRoot = Join-Path $PSScriptRoot ('.flow-test-' + [guid]::NewGuid().ToString('N'))
$checked = [IO.Path]::GetFullPath($testRoot)
$allowed = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
Assert ($checked.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)) 'Test yolu sınır dışında.'
New-Item -ItemType Directory -Path $testRoot | Out-Null
try {
    $fixture = Join-Path $testRoot 'Türkçe boşluk.ps1'
    $code = @'
param([string]$Value, [int]$Code = 0)
[Console]::OutputEncoding = New-Object Text.UTF8Encoding $false
[Console]::Error.WriteLine('Tanı: güncelleme sırasında bilgi')
Write-Output ('@@SONUC ' + (@{durum='KURULDU';neden=$Value} | ConvertTo-Json -Compress))
exit $Code
'@
    [IO.File]::WriteAllText($fixture,$code,(New-Object Text.UTF8Encoding $true))
    $value = 'Türkçe güncelleme "alıntı" C:\boşluk yol\'
    $got = Invoke-Tool 'powershell.exe' @('-NoProfile','-File',$fixture,'-Value',$value)
    Assert ($got.neden -ceq $value) 'Türkçe, tırnak veya yol argümanı bozuldu.'
    $empty = Invoke-Tool 'powershell.exe' @('-NoProfile','-File',$fixture,'-Value','')
    Assert ($empty.neden -eq '') 'Boş argüman bozuldu.'
    $rejected = $false
    try { $null = Invoke-Tool 'powershell.exe' @('-NoProfile','-File',$fixture,'-Code','7') } catch { $rejected = $true }
    Assert $rejected 'Sıfır olmayan çıkış kodu başarı sayıldı.'

    Assert ((Result-State ([pscustomobject]@{})) -eq 'Hata') 'Boş sonuç başarı sayıldı.'
    Assert ((Result-State ([pscustomobject]@{status='no_release'})) -eq 'Hata') 'Yayın yokluğu başarı sayıldı.'
    Assert ((Result-State ([pscustomobject]@{durum='KONTROL_EDILEMEDI'})) -eq 'Uyarı') 'Kontrol hatası başarı sayıldı.'
    Assert ((Result-State ([pscustomobject]@{ozet=@{paket='ENGEL'}})) -eq 'Hata') 'Paket hatası başarı sayıldı.'
    Assert ((Result-State ([pscustomobject]@{ozet=@{paket='GEÇTİ';excel='UYARI'}})) -eq 'Uyarı') 'İşlev uyarısı kayboldu.'
    $script:Python = $null; $script:Node = $null
    foreach ($key in @('libraries','duckdb','pnpm')) {
        $blocked = $false
        try { $null = & $realInstall $key } catch { $blocked = $true }
        Assert $blocked "Eksik bağımlılıkla $key kurulumu başlatıldı."
    }
    $script:Busy = $true
    $closing = New-Object Windows.Forms.FormClosingEventArgs([Windows.Forms.CloseReason]::UserClosing,$false)
    $method = [Windows.Forms.Form].GetMethod('OnFormClosing',[Reflection.BindingFlags]'NonPublic,Instance')
    $closingArgs = New-Object object[] 1
    $closingArgs.SetValue($closing.PSObject.BaseObject,0)
    [void]$method.Invoke($form,$closingArgs)
    Assert $closing.Cancel 'Devam eden işlem pencere kapanışıyla kesilebiliyor.'
    $script:Busy = $false

    # Exercise the real grid/selection/result flow with isolated installer substitutes.
    $script:Inventory.Clear()
    $script:Inventory['python'] = New-Entry 'python' 'Python' '3.14.6' '3.14.7' ''
    $script:Inventory['node'] = New-Entry 'node' 'Node.js' '24.1.0' '24.2.0' ''
    $script:Inventory['pnpm'] = New-Entry 'pnpm' 'pnpm' '12.0.0' '12.6.0' ''
    $script:Inventory['offer'] = New-Entry 'offer' 'Teklif' '4.0.0' '3.1.1' ''
    $script:Inventory['duckdb'] = New-Entry 'duckdb' 'DuckDB' '1.5.4' $null 'Bağlantı başarısız'
    Render-Inventory
    Assert (@($grid.Rows | Where-Object { $_.Cells['Sec'].Value }).Count -eq 3) 'Güncelleme gerekenler seçili başlamadı.'
    Assert ($grid.Rows[3].Cells['Sec'].ReadOnly -and $grid.Rows[4].Cells['Sec'].ReadOnly) 'Yeni/bilinmeyen sürüm seçilebilir.'
    Assert (@($grid.Columns | Where-Object { $_.SortMode -eq 'Automatic' }).Count -eq 0) 'Sıralama bağımlılık sırasını değiştirebilir.'
    $script:Calls = New-Object Collections.ArrayList
    function Install-Selected([string]$Key) {
        Assert (-not $form.Visible) 'Kurulum başladığında seçim penceresi hâlâ açık.'
        Run-SelectedUpdates # Reentrant UI events must not launch another batch.
        [void]$script:Calls.Add($Key)
        if ($Key -eq 'python') { throw 'Örnek kurulum hatası' }
        return [pscustomobject]@{durum='KURULDU';surum='12.6.0';ozet='UYARI';it_isi='Türkçe uyarı'}
    }
    foreach($row in $grid.Rows){$row.Cells['Sec'].Value=$false}
    Run-SelectedUpdates
    Assert ($script:Calls.Count -eq 0) 'Boş seçim kurulum başlattı.'
    $grid.Rows[0].Cells['Sec'].Value = $true
    $grid.Rows[2].Cells['Sec'].Value = $true
    $grid.Rows[3].Cells['Sec'].Value = $true # A programmatic stale checkbox must still be rejected.
    $form.ShowInTaskbar=$false; $form.Opacity=0; $form.Show()
    $mutexScript = Join-Path $testRoot 'hold-mutex.ps1'
    $mutexCode = @'
param([string]$Name,[string]$Ready,[string]$Release)
$m=New-Object Threading.Mutex($false,$Name)
[void]$m.WaitOne()
try {
    [IO.File]::WriteAllText($Ready,'ready')
    $timer=[Diagnostics.Stopwatch]::StartNew()
    while(-not [IO.File]::Exists($Release) -and $timer.Elapsed.TotalSeconds -lt 15){Start-Sleep -Milliseconds 50}
} finally {$m.ReleaseMutex();$m.Dispose()}
'@
    [IO.File]::WriteAllText($mutexScript,$mutexCode,(New-Object Text.UTF8Encoding $true))
    $mutexName = 'Local\guncelleyici-update-' + [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $readyFile = Join-Path $testRoot 'ready'; $releaseFile = Join-Path $testRoot 'release'
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = 'powershell.exe'; $info.UseShellExecute=$false; $info.CreateNoWindow=$true
    $info.Arguments = (@('-NoProfile','-File',$mutexScript,$mutexName,$readyFile,$releaseFile) | ForEach-Object {Quote-NativeArgument $_}) -join ' '
    $holder = [Diagnostics.Process]::Start($info)
    try {
        $timer=[Diagnostics.Stopwatch]::StartNew()
        while(-not [IO.File]::Exists($readyFile) -and $timer.Elapsed.TotalSeconds -lt 5){Start-Sleep -Milliseconds 50}
        Assert ([IO.File]::Exists($readyFile)) 'İkinci süreç kilidi hazırlanamadı.'
        Run-SelectedUpdates
        Assert ($script:Calls.Count -eq 0 -and $footer.Text -like 'Başka bir*') 'Eşzamanlı ikinci güncelleme başladı.'
    } finally {
        [IO.File]::WriteAllText($releaseFile,'release')
        if(-not $holder.WaitForExit(5000)){$holder.Kill()}
        $holder.Dispose()
    }
    Run-SelectedUpdates
    Assert (($script:Calls -join ',') -eq 'python,pnpm') 'Seçilmeyen veya uygun olmayan satır çalıştırıldı.'
    Assert ($script:Results.Count -eq 2 -and $script:Results[0].sonuc -eq 'Hata' -and $script:Results[1].sonuc -eq 'Uyarı') 'Sıralı hata/uyarı sonuçları yanlış.'
    Assert ($grid.Rows[1].Cells['Durum'].Value -eq 'Atlandı · seçilmedi') 'Seçilmeyen uygun satır yanlış raporlandı.'
    Assert ($grid.Rows[3].Cells['Durum'].Value -eq 'Yüklü sürüm yayından yeni') 'Yayın önündeki sürüm bilgisi silindi.'
    Assert ($grid.Rows[4].Cells['Durum'].Value -like 'Kontrol edilemedi*') 'Tarama hatası sonuçta silindi.'
    Assert (-not $script:Busy -and -not $button.Enabled) 'İşlem son durumu yanlış.'
    $script:Inventory.Clear()
    $script:Inventory['node'] = New-Entry 'node' 'Node.js' '24.1.0' '24.2.0' ''
    Render-Inventory
    $grid.Rows[0].Cells['Sec'].Value=$true
    function Install-Selected { return [pscustomobject]@{durum='KURULDU'} }
    Run-SelectedUpdates
    Assert ($script:Results[0].sonuc -eq 'Hata') 'Sürümü olmayan kurulum tamamlandı sayıldı.'
    Render-Inventory
    $grid.Rows[0].Cells['Sec'].Value=$true
    function Install-Selected { return [pscustomobject]@{durum='MEVCUT';surum='24.1.0'} }
    Run-SelectedUpdates
    Assert ($script:Results[0].sonuc -eq 'Uyarı') 'Hedefe ulaşılmadan güncelleme tamamlandı sayıldı.'

    # Missing software is offered as a preselected fresh installation.
    $script:Inventory.Clear()
    $script:Inventory['offer'] = New-Entry 'offer' 'Teklif' $null '4.0.0' ''
    Render-Inventory
    Assert ($grid.Rows[0].Cells['Yuklu'].Value -eq 'Yüklü değil' -and $grid.Rows[0].Cells['Sec'].Value) 'Eksik skill seçili kurulum adayı olmadı.'
    function Install-Selected {
        Assert (-not $form.Visible) 'Modal seçim penceresi kurulumdan önce kapanmadı.'
        return [pscustomobject]@{status='installed';version='4.0.0'}
    }
    $form.DialogResult=[Windows.Forms.DialogResult]::None
    $timer=New-Object Windows.Forms.Timer
    $timer.Interval=50
    $timer.Add_Tick({$timer.Stop(); Run-SelectedUpdates})
    try { $timer.Start(); [void]$form.ShowDialog() } finally { $timer.Dispose() }
    $outcome = Get-PanelOutcome
    Assert ($outcome.status -eq 'completed' -and $outcome.rows[0].yuklu -eq '4.0.0') 'Kapalı panelin kurulum sonucu kayboldu.'

    # All known components must be current; missing/unknown rows cannot take this path.
    $script:Inventory.Clear()
    foreach($key in @('python','libraries','node','pnpm','duckdb','powerbi','offer')) {
        $script:Inventory[$key] = New-Entry $key $key '2.0.0' '1.0.0' ''
    }
    Assert (Test-InventoryCurrent) 'Yeni veya güncel kurulumlar güncel sayılmadı.'
    $script:Inventory['offer'] = New-Entry 'offer' 'Teklif' '2.0.0' $null 'Ağ yok'
    Assert (-not (Test-InventoryCurrent)) 'Bilinmeyen güncel sürümde Güncelsiniz denildi.'
    $script:Inventory['offer'] = New-Entry 'offer' 'Teklif' $null '2.0.0' ''
    Assert (-not (Test-InventoryCurrent)) 'Eksik skill varken Güncelsiniz denildi.'

    # Exercise the script entry point; opening the UI on this path is a test failure.
    $source=[IO.File]::ReadAllText((Resolve-Path $panel).Path,[Text.Encoding]::UTF8)
    $tokens=$null;$errors=$null
    $ast=[Management.Automation.Language.Parser]::ParseInput($source,[ref]$tokens,[ref]$errors)
    $functions=$ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -in @('Scan-Inventory','Remove-LegacySkill')},$true) | Sort-Object { $_.Extent.StartOffset } -Descending
    foreach($fn in $functions){
        $replacement = if($fn.Name -eq 'Remove-LegacySkill'){'function Remove-LegacySkill { return @() }'}else{
            'function Scan-Inventory { $script:Inventory.Clear(); foreach($key in @("python","libraries","node","pnpm","duckdb","powerbi","offer")){ $script:Inventory[$key]=New-Entry $key $key "1.0.0" "1.0.0" "" } }'
        }
        $source=$source.Remove($fn.Extent.StartOffset,$fn.Extent.Text.Length).Insert($fn.Extent.StartOffset,$replacement)
    }
    $source=$source.Replace('Add-Type -AssemblyName System.Windows.Forms',"throw 'Güncel makinede tablo açıldı'")
    $currentScript=Join-Path $testRoot 'current-machine.ps1'
    [IO.File]::WriteAllText($currentScript,$source,(New-Object Text.UTF8Encoding $true))
    $run=Invoke-Native 'powershell.exe' @('-NoProfile','-File',$currentScript) 15
    Assert ($run.ExitCode -eq 0 -and $run.Output -match 'Güncelsiniz' -and $run.Output -match 'up_to_date') 'Güncel makine penceresiz bitmedi.'
    'PANEL_FLOW_TEST_OK'
} finally {
    $form.Dispose()
    if ($checked.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $checked)) {
        Remove-Item -LiteralPath $checked -Recurse -Force
    }
}
