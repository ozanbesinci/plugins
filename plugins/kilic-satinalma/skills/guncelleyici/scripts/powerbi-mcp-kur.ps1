#requires -Version 5.1
<#
  program-guncelle — Aşama 8: Power BI Modeling MCP

  DuckDB işleri bittikten sonra çalışır. Microsoft'un "Power BI Modeling MCP" sunucusu
  (VS Marketplace: analysis-services.powerbi-modeling-mcp, win32-x64):
  1) Yüklü mü bakar; yüklü değilse en yeni sürümü kullanıcı alanına kurar.
  2) Yüklüyse sürümüne bakar: en yeninin gerisindeyse günceller, güncelse sonraki aşamaya geçer.
     "En yeni" = Marketplace'teki en yeni KARARLI win32-x64 sürümü; ön sürümler kurulmaz (Ortak'ın
     kuralı, 2026-09-24: "skill her zaman kararlı olanı yüklesin"; bugün 0.4.0). Daha yeni bir ön sürüm
     zaten kuruluysa (ör. 0.5.x) geri düşürülmez, olduğu gibi kullanılır.
  3) Codex'e (config.toml), bilgisayarda varsa Claude masaüstüne (claude_desktop_config.json) ve Claude
     Code'a (`claude mcp add -s user`) "powerbi-modeling" adıyla bağlar. Mevcut ayarlar korunur; değiştirmeden önce yedek alınır.
  4) Sunucuyu çalıştırıp MCP el sıkışması yapar, araç listesini alır, kapatır.

  Kurulum: %LOCALAPPDATA%\Programs\PowerBIModelingMCP\<sürüm>\ — her sürüm kendi klasöründe, çünkü
  Codex/Claude açıkken çalışan sunucu dosyaları kilitler. Eski sürüm klasörü boşaldığında silinir.
  Doğrulama: paket kimliği (yayıncı, ad, sürüm, platform) ve powerbi-modeling-mcp.exe'nin Microsoft
  Corporation imzası. Marketplace dosya özeti yayımlamıyor; imza doğrulanmadan kurulmaz.
  Yönetici yetkisi istemez.

  Çıktı: son satır "@@SONUC {json}"; aynı JSON %LOCALAPPDATA%\program-guncelle\powerbi-mcp-kur-sonuc.json
  durum: MEVCUT | KURULDU | GUNCELLENDI | ESKI (güncellenemedi, eski sürüm çalışıyor) | BASARISIZ | YOK (-YalnizBul)
  Parametreler: -YalnizBul → hiçbir şey kurmaz ve ayarlara dokunmaz, yalnız bakar.
                -Rapor <dosya> → sonucu kurulum testi raporunun sonuna ekler.
#>
param([switch]$YalnizBul, [string]$Rapor)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
# Çıktıyı okuyan ajan (Codex) UTF-8 bekler; konsolun OEM kod sayfası Türkçeyi ve · — işaretlerini bozar.
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch {}
# Git Bash farklı PowerShell sürümünün modül yolunu taşıyabilir; çalışan kabuğun modüllerini kullan.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -ErrorAction Stop

$YAYINCI = 'analysis-services'
$UZANTI = 'powerbi-modeling-mcp'
$PLATFORM = 'win32-x64'
$SUNUCU_ADI = 'powerbi-modeling'
$IMZA_YAYINCI = 'Microsoft Corporation'
$EXE_YOLU = 'extension\server\powerbi-modeling-mcp.exe'
$KOK = Join-Path $env:LOCALAPPDATA 'Programs\PowerBIModelingMCP'
$BILINEN_KLASORLER = @('C:\MCPServers\PowerBIModelingMCP')   # elle kurulum (Ortak'ın ilk kurulumu bu düzende)
$CODEX_AYAR = Join-Path $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }) 'config.toml'
$CLAUDE_AYAR = Join-Path $env:APPDATA 'Claude\claude_desktop_config.json'

$durumKlasoru = Join-Path $env:LOCALAPPDATA 'program-guncelle'
New-Item -ItemType Directory -Path $durumKlasoru -Force | Out-Null
$testler = New-Object System.Collections.Generic.List[object]
$ayarlar = New-Object System.Collections.Generic.List[object]
$ilkKurulumlar = @()
$hedef = $null

function Yaz([string]$Metin) { Write-Host "  $Metin" }

function Kisalt([string]$Metin, [int]$Uzunluk = 400) {
    if (-not $Metin) { return '' }
    $t = ($Metin -replace '\s+', ' ').Trim()
    if ($t.Length -gt $Uzunluk) { return $t.Substring($t.Length - $Uzunluk) }
    return $t
}

# 0.5.15 ve 0.5.0-beta.13 gibi metinleri karşılaştırılabilir yapar (ön sürüm eki atılır).
function SurumNesnesi([string]$Metin) { try { return [version](($Metin -split '[-+]')[0]) } catch { return [version]'0.0' } }

# Antivirüs yeni yazılan/çalıştırılan dosyayı birkaç saniye kilitli tutar (node-kur.ps1'de ölçüldü).
function Israrla([scriptblock]$Is, [int]$Deneme = 20) {
    for ($i = 1; ; $i++) {
        try { & $Is; return } catch { if ($i -ge $Deneme) { throw }; Start-Sleep -Milliseconds 750 }
    }
}

# Bir exe yolundan kurulumun sürümünü okur: extension\package.json → "version".
function KurulumBilgisi([string]$Exe) {
    if (-not $Exe -or -not (Test-Path -LiteralPath $Exe)) { return $null }
    $paket = Join-Path (Split-Path (Split-Path $Exe -Parent) -Parent) 'package.json'
    $surum = $null
    try { $p = Get-Content -LiteralPath $paket -Raw -Encoding UTF8 | ConvertFrom-Json; if ($p.name -eq $UZANTI) { $surum = "$($p.version)" } } catch {}
    if (-not $surum) { try { $surum = (Get-Item -LiteralPath $Exe).VersionInfo.ProductVersion } catch {} }
    if (-not $surum) { return $null }
    return [pscustomobject]@{ Surum = $surum; Exe = (Resolve-Path -LiteralPath $Exe).Path }
}

# --- Codex config.toml -----------------------------------------------------------------------------
$TOML_BASLIK = '^\s*\[\s*mcp_servers\.(?:"powerbi-modeling"|''powerbi-modeling''|powerbi-modeling)\s*\]\s*(#.*)?$'
$TOML_ALT = '^\s*\[\s*mcp_servers\.(?:"powerbi-modeling"|''powerbi-modeling''|powerbi-modeling)\.'

function MetinOku([string]$Yol) {
    $b = [IO.File]::ReadAllBytes($Yol)
    $bom = $b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF
    $t = (New-Object Text.UTF8Encoding $false).GetString($b, $(if ($bom) { 3 } else { 0 }), $b.Length - $(if ($bom) { 3 } else { 0 }))
    return [pscustomobject]@{ Metin = $t; Bom = $bom; Satir = $(if ($t -match "`r`n") { "`r`n" } else { "`n" }) }
}

function MetinYaz([string]$Yol, [string]$Metin, [bool]$Bom) {
    [IO.File]::WriteAllText($Yol, $Metin, (New-Object Text.UTF8Encoding $Bom))
}

function Yedekle([string]$Yol) {
    $y = "$Yol.program-guncelle-$((Get-Date).ToString('yyyyMMdd-HHmmss')).bak"
    Copy-Item -LiteralPath $Yol -Destination $y -Force
    return $y
}

function CodexKomutu {
    if (-not (Test-Path -LiteralPath $CODEX_AYAR)) { return $null }
    $d = MetinOku $CODEX_AYAR
    $satirlar = $d.Metin -split "`r?`n"; $icinde = $false
    foreach ($s in $satirlar) {
        if ($s -match $TOML_BASLIK) { $icinde = $true; continue }
        if ($icinde -and $s -match '^\s*\[') { break }
        if ($icinde -and $s -match '^\s*command\s*=\s*(?:"((?:[^"\\]|\\.)*)"|''([^'']*)'')') {
            if ($Matches[1]) { return ($Matches[1] -replace '\\\\', '\' -replace '\\"', '"') } else { return $Matches[2] }
        }
    }
    return $null
}

function CodexBagla([string]$Exe) {
    $klasor = Split-Path $CODEX_AYAR -Parent
    if (-not (Test-Path -LiteralPath $klasor)) { return [ordered]@{ uygulama = 'Codex'; sonuc = 'atlandı'; ayrinti = "Codex ayar klasörü yok ($klasor)" } }
    $komut = $Exe -replace '\\', '\\' -replace '"', '\"'
    $blok = @("[mcp_servers.$SUNUCU_ADI]", "command = `"$komut`"", 'args = ["--start"]', 'startup_timeout_sec = 60')
    try {
        if (-not (Test-Path -LiteralPath $CODEX_AYAR)) {
            MetinYaz $CODEX_AYAR (($blok -join "`n") + "`n") $false
            return [ordered]@{ uygulama = 'Codex'; sonuc = 'eklendi'; ayrinti = "$CODEX_AYAR oluşturuldu" }
        }
        $d = MetinOku $CODEX_AYAR
        $satirlar = New-Object System.Collections.Generic.List[string]; foreach ($s in ($d.Metin -split "`r?`n")) { $satirlar.Add($s) }
        $bas = -1
        for ($i = 0; $i -lt $satirlar.Count; $i++) { if ($satirlar[$i] -match $TOML_BASLIK) { $bas = $i; break } }
        if ($bas -lt 0) {
            if ($d.Metin -match 'powerbi-modeling') {
                return [ordered]@{ uygulama = 'Codex'; sonuc = 'dokunulmadı'; ayrinti = "config.toml'da 'powerbi-modeling' farklı biçimde tanımlı; elle bakılmalı" }
            }
            $yedek = Yedekle $CODEX_AYAR
            $metin = $d.Metin.TrimEnd("`r", "`n") + $d.Satir + $d.Satir + ($blok -join $d.Satir) + $d.Satir
            MetinYaz $CODEX_AYAR $metin $d.Bom
            return [ordered]@{ uygulama = 'Codex'; sonuc = 'eklendi'; ayrinti = "yedek: $yedek" }
        }
        $son = $satirlar.Count
        for ($i = $bas + 1; $i -lt $satirlar.Count; $i++) {
            if ($satirlar[$i] -match '^\s*\[' -and $satirlar[$i] -notmatch $TOML_ALT) { $son = $i; break }
        }
        $eski = @($satirlar[$bas..($son - 1)] | Where-Object { $_.Trim() }) -join "`n"
        if ($eski -eq ($blok -join "`n")) { return [ordered]@{ uygulama = 'Codex'; sonuc = 'zaten doğru'; ayrinti = '' } }
        $yedek = Yedekle $CODEX_AYAR
        $yeni = @($blok) + @('')
        $satirlar.RemoveRange($bas, $son - $bas); $satirlar.InsertRange($bas, [string[]]$yeni)
        MetinYaz $CODEX_AYAR (($satirlar -join $d.Satir).TrimEnd("`r", "`n") + $d.Satir) $d.Bom
        return [ordered]@{ uygulama = 'Codex'; sonuc = 'güncellendi'; ayrinti = "yedek: $yedek" }
    } catch {
        return [ordered]@{ uygulama = 'Codex'; sonuc = 'hata'; ayrinti = (Kisalt $_.Exception.Message 200) }
    }
}

# --- Claude masaüstü claude_desktop_config.json ----------------------------------------------------
function ClaudeKomutu {
    if (-not (Test-Path -LiteralPath $CLAUDE_AYAR)) { return $null }
    try { $j = (MetinOku $CLAUDE_AYAR).Metin | ConvertFrom-Json; return "$($j.mcpServers.$SUNUCU_ADI.command)" } catch { return $null }
}

function ClaudeBagla([string]$Exe) {
    $klasor = Split-Path $CLAUDE_AYAR -Parent
    if (-not (Test-Path -LiteralPath $klasor)) { return [ordered]@{ uygulama = 'Claude masaüstü'; sonuc = 'atlandı'; ayrinti = 'Claude masaüstü bu bilgisayarda kullanılmamış' } }
    try {
        $d = $null; $j = $null
        if (Test-Path -LiteralPath $CLAUDE_AYAR) {
            $d = MetinOku $CLAUDE_AYAR
            if ($d.Metin.Trim()) {
                try { $j = $d.Metin | ConvertFrom-Json } catch { return [ordered]@{ uygulama = 'Claude masaüstü'; sonuc = 'dokunulmadı'; ayrinti = 'claude_desktop_config.json okunamadı (geçersiz JSON); elle bakılmalı' } }
            }
        }
        if (-not $j) { $j = New-Object psobject }
        $mevcut = $j.mcpServers.$SUNUCU_ADI
        if ($mevcut -and "$($mevcut.command)" -eq $Exe -and (@($mevcut.args) -join ' ') -eq '--start') {
            return [ordered]@{ uygulama = 'Claude masaüstü'; sonuc = 'zaten doğru'; ayrinti = '' }
        }
        if (-not $j.mcpServers) { $j | Add-Member -NotePropertyName mcpServers -NotePropertyValue (New-Object psobject) -Force }
        $giris = [pscustomobject]@{ command = $Exe; args = @('--start'); env = (New-Object psobject) }
        $j.mcpServers | Add-Member -NotePropertyName $SUNUCU_ADI -NotePropertyValue $giris -Force
        $yedek = if ($d) { Yedekle $CLAUDE_AYAR } else { '' }
        MetinYaz $CLAUDE_AYAR ($j | ConvertTo-Json -Depth 50) $false
        # Yazılanı geri oku: bozuk JSON bırakma.
        try { $null = (MetinOku $CLAUDE_AYAR).Metin | ConvertFrom-Json } catch {
            if ($yedek) { Copy-Item -LiteralPath $yedek -Destination $CLAUDE_AYAR -Force }
            return [ordered]@{ uygulama = 'Claude masaüstü'; sonuc = 'hata'; ayrinti = 'yazılan ayar doğrulanamadı; yedek geri kondu' }
        }
        return [ordered]@{ uygulama = 'Claude masaüstü'; sonuc = $(if ($mevcut) { 'güncellendi' } else { 'eklendi' }); ayrinti = $(if ($yedek) { "yedek: $yedek" } else { "$CLAUDE_AYAR oluşturuldu" }) }
    } catch {
        return [ordered]@{ uygulama = 'Claude masaüstü'; sonuc = 'hata'; ayrinti = (Kisalt $_.Exception.Message 200) }
    }
}

# --- Claude Code (komut satırı), kullanıcı kapsamı -------------------------------------------------
# ~/.claude.json Claude Code açıkken sürekli yeniden yazılır; betik onu yalnız OKUR, yazmayı Claude Code'un
# kendi `claude mcp add/remove` komutuna bırakır. CLAUDE_CONFIG_DIR tanımlıysa ayar dosyası oradadır.
function ClaudeCodeAyarDosyasi {
    if ($env:CLAUDE_CONFIG_DIR) { return (Join-Path $env:CLAUDE_CONFIG_DIR '.claude.json') }
    return (Join-Path $env:USERPROFILE '.claude.json')
}

function ClaudeCodeKaydi {
    $f = ClaudeCodeAyarDosyasi
    if (-not (Test-Path -LiteralPath $f)) { return $null }
    try { return ((MetinOku $f).Metin | ConvertFrom-Json).mcpServers.$SUNUCU_ADI } catch { return $null }
}

function ClaudeCodeKomutu { $k = ClaudeCodeKaydi; if ($k) { return "$($k.command)" } else { return $null } }

function KomutCalistir([string]$Dosya, [string]$Argumanlar, [int]$SureMs = 60000) {
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $env:ComSpec; $psi.Arguments = "/d /c `"`"$Dosya`" $Argumanlar`""
        $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        $o = $p.StandardOutput.ReadToEndAsync(); $e = $p.StandardError.ReadToEndAsync()
        if (-not $p.WaitForExit($SureMs)) { try { $p.Kill() } catch {}; return [pscustomobject]@{ Kod = -1; Cikti = 'zaman aşımı' } }
        return [pscustomobject]@{ Kod = $p.ExitCode; Cikti = (Kisalt "$($o.Result) $($e.Result)" 200) }
    } catch { return [pscustomobject]@{ Kod = -2; Cikti = (Kisalt $_.Exception.Message 200) } }
}

function ClaudeCodeBagla([string]$Exe) {
    $cli = Get-Command claude -CommandType Application -ErrorAction SilentlyContinue | Where-Object { $_.Source -match '\.(cmd|exe)$' } | Select-Object -First 1
    if (-not $cli) {
        $durum = if (Test-Path -LiteralPath (ClaudeCodeAyarDosyasi)) { 'dokunulmadı' } else { 'atlandı' }
        return [ordered]@{ uygulama = 'Claude Code'; sonuc = $durum; ayrinti = "Claude Code komut satırı ('claude') bulunamadı; mevcut ayar varsa eski sürümler korunur" }
    }
    $mevcut = ClaudeCodeKaydi
    if ($mevcut -and "$($mevcut.command)" -eq $Exe -and (@($mevcut.args) -join ' ') -eq '--start') {
        return [ordered]@{ uygulama = 'Claude Code'; sonuc = 'zaten doğru'; ayrinti = '' }
    }
    if ($mevcut) {
        # CLI eski kaydı kaldırmadan aynı adı güncellemiyor. Yalnız geri kurulabilecek düz stdio
        # kaydını değiştir; özel argüman/ortam/alan varsa mevcut kullanıcı ayarını koru.
        $alanlar = @($mevcut.PSObject.Properties | Where-Object { $_.Name -notin 'type', 'command', 'args', 'env' })
        $ortam = @($mevcut.env.PSObject.Properties)
        if (-not $mevcut.command -or @($mevcut.args).Count -ne 1 -or @($mevcut.args)[0] -ne '--start' -or
            ($mevcut.type -and $mevcut.type -ne 'stdio') -or $alanlar.Count -or $ortam.Count -or
            "$($mevcut.command)" -match '["%!]') {
            return [ordered]@{ uygulama = 'Claude Code'; sonuc = 'dokunulmadı'; ayrinti = 'mevcut kayıt özel ayar içeriyor; güvenli geri dönüş için değiştirilmedi' }
        }
    }
    if ($mevcut) {
        $r = KomutCalistir $cli.Source "mcp remove $SUNUCU_ADI -s user"
        if ($r.Kod -ne 0) { return [ordered]@{ uygulama = 'Claude Code'; sonuc = 'hata'; ayrinti = "eski kayıt kaldırılamadı: $($r.Cikti)" } }
    }
    $r = KomutCalistir $cli.Source "mcp add -s user $SUNUCU_ADI -- `"$Exe`" --start"
    $yeni = ClaudeCodeKaydi
    if ($r.Kod -ne 0 -or -not $yeni -or "$($yeni.command)" -ne $Exe -or (@($yeni.args) -join ' ') -ne '--start') {
        $hata = "claude mcp add başarısız (kod $($r.Kod)): $($r.Cikti)"
        if ($mevcut) {
            if ($yeni) {
                $sil = KomutCalistir $cli.Source "mcp remove $SUNUCU_ADI -s user"
                if ($sil.Kod -ne 0) { return [ordered]@{ uygulama = 'Claude Code'; sonuc = 'hata'; ayrinti = "$hata; kısmi kayıt kaldırılamadı, eski sunucu dosyası korundu" } }
            }
            $geri = KomutCalistir $cli.Source "mcp add -s user $SUNUCU_ADI -- `"$($mevcut.command)`" --start"
            $geriKayit = ClaudeCodeKaydi
            $geriDondu = $geri.Kod -eq 0 -and $geriKayit -and "$($geriKayit.command)" -eq "$($mevcut.command)" -and
                (@($geriKayit.args) -join ' ') -eq '--start'
            $hata += $(if ($geriDondu) { '; eski kayıt geri kondu' } else { "; eski kayıt geri konamadı: $($geri.Cikti)" })
        }
        return [ordered]@{ uygulama = 'Claude Code'; sonuc = 'hata'; ayrinti = $hata }
    }
    return [ordered]@{ uygulama = 'Claude Code'; sonuc = $(if ($mevcut) { 'güncellendi' } else { 'eklendi' }); ayrinti = "kullanıcı kapsamı ($(ClaudeCodeAyarDosyasi))" }
}

# --- Kurulumlar --------------------------------------------------------------------------------------
function TumKurulumlar {
    $adaylar = New-Object System.Collections.Generic.List[string]
    if (Test-Path -LiteralPath $KOK) { Get-ChildItem -LiteralPath $KOK -Directory | ForEach-Object { $adaylar.Add((Join-Path $_.FullName $EXE_YOLU)) } }
    foreach ($k in $BILINEN_KLASORLER) { $adaylar.Add((Join-Path $k $EXE_YOLU)) }
    foreach ($c in @((CodexKomutu), (ClaudeKomutu), (ClaudeCodeKomutu))) { if ($c) { $adaylar.Add($c) } }
    $bulunan = @(); $gorulen = @{}
    $fso = New-Object -ComObject Scripting.FileSystemObject
    foreach ($a in $adaylar) {
        $b = KurulumBilgisi $a
        if (-not $b) { continue }
        # Aynı dosya kısa ve uzun Windows adıyla gelebilir: kısa ada çevirip karşılaştır.
        $anahtar = try { $fso.GetFile($b.Exe).ShortPath.ToLower() } catch { $b.Exe.ToLower() }
        if (-not $gorulen.ContainsKey($anahtar)) { $gorulen[$anahtar] = $true; $bulunan += $b }
    }
    return @($bulunan | Sort-Object { SurumNesnesi $_.Surum } -Descending)
}

function SonSurumuOgren {
    try {
        try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
        try { [Net.WebRequest]::DefaultWebProxy.Credentials = [Net.CredentialCache]::DefaultNetworkCredentials } catch {}
        $govde = @{ filters = @(@{ criteria = @(@{ filterType = 7; value = "$YAYINCI.$UZANTI" }) }); flags = (0x1 -bor 0x2 -bor 0x10) } | ConvertTo-Json -Depth 6
        $r = Invoke-RestMethod -Method Post -Uri 'https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery' -Body $govde `
            -ContentType 'application/json' -Headers @{ Accept = 'application/json;api-version=7.2-preview.1' } -UseBasicParsing -TimeoutSec 30
        # Yalnız kararlı sürümler (Ortak'ın kuralı, 2026-09-24: "skill her zaman kararlı olanı yüklesin").
        $surumler = @($r.results[0].extensions[0].versions | Where-Object {
                $_.targetPlatform -eq $PLATFORM -and
                (($_.properties | Where-Object { $_.key -eq 'Microsoft.VisualStudio.Code.PreRelease' }).value -ne 'true') } |
            Sort-Object { SurumNesnesi $_.version } -Descending)
        if (-not $surumler.Count) { throw "Marketplace'te $PLATFORM için kararlı sürüm bulunamadı" }
        $v = $surumler[0]
        $url = ($v.files | Where-Object { $_.assetType -eq 'Microsoft.VisualStudio.Services.VSIXPackage' }).source
        if (-not $url) { $url = "https://marketplace.visualstudio.com/_apis/public/gallery/publishers/$YAYINCI/vsextensions/$UZANTI/$($v.version)/vspackage?targetPlatform=$PLATFORM" }
        $on = (($v.properties | Where-Object { $_.key -eq 'Microsoft.VisualStudio.Code.PreRelease' }).value -eq 'true')
        return [pscustomobject]@{ Surum = "$($v.version)"; Url = $url; OnSurum = $on; Kaynak = 'VS Marketplace' }
    } catch {
        Yaz "Marketplace'ten en yeni sürüm öğrenilemedi ($(Kisalt $_.Exception.Message 150))."
        return $null
    }
}

# Paketi indirir, kimliğini ve imzasını doğrular, <kök>\<sürüm>\ altına açar.
function PaketKur {
    $gecici = Join-Path $env:TEMP ('program-guncelle-pbi-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    $hedefKlasor = Join-Path $KOK $hedef.Surum
    $hazirlik = Join-Path $KOK ('.yeni-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    New-Item -ItemType Directory -Path $gecici, $KOK -Force | Out-Null
    $dosya = Join-Path $gecici "$UZANTI-$($hedef.Surum).vsix"
    try {
        Yaz "Marketplace'ten Power BI Modeling MCP $($hedef.Surum) indiriliyor (yaklaşık 40 MB)..."
        Invoke-WebRequest -Uri $hedef.Url -OutFile $dosya -UseBasicParsing -TimeoutSec 600 -ErrorAction Stop
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $arsiv = [IO.Compression.ZipFile]::OpenRead($dosya)
        try {
            $mf = $arsiv.Entries | Where-Object { $_.FullName -eq 'extension.vsixmanifest' } | Select-Object -First 1
            if (-not $mf) { throw 'paket VSIX değil (extension.vsixmanifest yok); kurulmadı' }
            $okuyucu = New-Object IO.StreamReader($mf.Open()); $x = [xml]$okuyucu.ReadToEnd(); $okuyucu.Close()
            $id = $x.PackageManifest.Metadata.Identity
            if ($id.Publisher -ne $YAYINCI -or $id.Id -ne $UZANTI -or $id.Version -ne $hedef.Surum -or $id.TargetPlatform -ne $PLATFORM) {
                throw "paket kimliği beklenen değil ($($id.Publisher).$($id.Id) $($id.Version) $($id.TargetPlatform)); kurulmadı"
            }
            foreach ($g in $arsiv.Entries) {
                $ic = $g.FullName
                if ($ic -match '(^|/)\.\.(/|$)' -or $ic -match '[:\\]') { throw "paket içinde geçersiz yol ($ic); kurulmadı" }
                $yol = Join-Path $hazirlik ($ic -replace '/', '\')
                if ($ic.EndsWith('/')) { [void][IO.Directory]::CreateDirectory($yol); continue }
                [void][IO.Directory]::CreateDirectory((Split-Path $yol -Parent))
                [IO.Compression.ZipFileExtensions]::ExtractToFile($g, $yol, $true)
            }
        } finally { $arsiv.Dispose() }
        $exe = Join-Path $hazirlik $EXE_YOLU
        if (-not (Test-Path -LiteralPath $exe)) { throw "paket içinde powerbi-modeling-mcp.exe yok; kurulmadı" }
        $imza = Get-AuthenticodeSignature -LiteralPath $exe
        if ($imza.Status -ne 'Valid' -or $imza.SignerCertificate.Subject -notlike "*O=$IMZA_YAYINCI*") {
            throw "powerbi-modeling-mcp.exe dijital imzası doğrulanamadı (durum $($imza.Status), imzalayan $($imza.SignerCertificate.Subject)); kurulmadı"
        }
        Yaz 'Paket doğrulandı (yayıncı, ad, sürüm, platform; Microsoft Corporation imzası). Kuruluyor...'
        if (Test-Path -LiteralPath $hedefKlasor) {
            $karantina = Join-Path $KOK '_karantina'
            New-Item -ItemType Directory -Path $karantina -Force | Out-Null
            $oncekiHedef = Join-Path $karantina ($hedef.Surum + '-onceki-' + [guid]::NewGuid().ToString('N'))
            Israrla { Move-Item -LiteralPath $hedefKlasor -Destination $oncekiHedef -ErrorAction Stop }
        }
        Israrla { Rename-Item -LiteralPath $hazirlik -NewName (Split-Path $hedefKlasor -Leaf) -ErrorAction Stop }
        return [pscustomobject]@{ Kod = 0; Neden = ''; Exe = (Join-Path $hedefKlasor $EXE_YOLU) }
    } catch {
        return [pscustomobject]@{ Kod = -3; Neden = (Kisalt $_.Exception.Message); Exe = $null }
    } finally {
        foreach ($k in @($hazirlik, $gecici)) {
            if ($k -and (Test-Path -LiteralPath $k)) { try { Israrla { Remove-Item -LiteralPath $k -Recurse -Force -ErrorAction Stop } } catch {} }
        }
    }
}

# Kullanılmayan eski sürümleri karantinaya taşır; ayarlarda kullanılan klasöre dokunmaz.
function EskileriTemizle([string]$Tut) {
    if (-not (Test-Path -LiteralPath $KOK)) { return }
    $korunan = @()
    foreach ($komut in @((CodexKomutu), (ClaudeKomutu), (ClaudeCodeKomutu))) {
        if (-not $komut) { continue }
        try {
            # Aynı Windows yolu /, \\ veya .. ile yazılabilir. Kısa adlarda ve
            # çözülemeyen yollarda hangi sürümün kullanıldığını varsayma.
            if (-not [IO.Path]::IsPathRooted($komut) -or $komut -match '~\d') { throw 'belirsiz komut yolu' }
            $tamKomut = [IO.Path]::GetFullPath($komut)
            if (-not (Test-Path -LiteralPath $tamKomut -PathType Leaf)) { throw 'komut dosyası çözülemedi' }
            $korunan += (Resolve-Path -LiteralPath $tamKomut -ErrorAction Stop).ProviderPath
        } catch {
            Yaz 'Bir istemcinin sunucu yolu doğrulanamadı; eski sürümler korunuyor.'
            return
        }
    }
    $karantina = Join-Path $KOK '_karantina'
    $kokTam = [IO.Path]::GetFullPath($KOK).TrimEnd('\') + '\'
    foreach ($k in Get-ChildItem -LiteralPath $KOK -Directory) {
        if ($k.Name -eq $Tut -or $k.Name -notmatch '^\d+\.\d+\.\d+$') { continue }
        $kaynak = [IO.Path]::GetFullPath($k.FullName)
        if (-not $kaynak.StartsWith($kokTam, [StringComparison]::OrdinalIgnoreCase)) { continue }
        $kaynakOnEk = $kaynak.TrimEnd('\') + '\'
        if (@($korunan | Where-Object { $_.StartsWith($kaynakOnEk, [StringComparison]::OrdinalIgnoreCase) }).Count) {
            Yaz "Eski sürüm ayarda kullanılıyor, korundu: $($k.Name)"
            continue
        }
        try {
            [void][IO.Directory]::CreateDirectory($karantina)
            $hedefYol = [IO.Path]::GetFullPath((Join-Path $karantina ($k.Name + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))))
            if (-not $hedefYol.StartsWith(([IO.Path]::GetFullPath($karantina).TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)) { throw 'karantina yolu beklenen kökte değil' }
            Move-Item -LiteralPath $kaynak -Destination $hedefYol -ErrorAction Stop
            Yaz "Eski sürüm karantinaya taşındı: $($k.Name)"
        } catch { Yaz "Eski sürüm korunuyor: $($k.Name) ($($_.Exception.Message))" }
    }
}

# Sunucuyu çalıştırıp MCP el sıkışması yapar ve araç listesini ister; sonra kapatır. Çalıştıysa $true döner.
# Marketplace ön sürümleri bozuk çıkabiliyor (0.5.14 açılırken çöküyordu, 2026-09-24): yeni sürüm ayarlara
# bağlanmadan ÖNCE bununla sınanır.
function McpTest([string]$Exe) {
    $p = $null; $hataAkisi = $null; $calisti = $false
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $Exe; $psi.Arguments = '--start'; $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
        $psi.RedirectStandardInput = $true; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
        $psi.StandardOutputEncoding = New-Object Text.UTF8Encoding $false
        $p = [System.Diagnostics.Process]::Start($psi)
        $hataAkisi = $p.StandardError.ReadToEndAsync()
        $giris = New-Object IO.StreamWriter($p.StandardInput.BaseStream, (New-Object Text.UTF8Encoding $false)); $giris.AutoFlush = $true
        function Iste($Id, $Yontem, $Param) {
            $giris.WriteLine((@{ jsonrpc = '2.0'; id = $Id; method = $Yontem; params = $Param } | ConvertTo-Json -Compress -Depth 6))
            $bitis = (Get-Date).AddSeconds(60)
            while ((Get-Date) -lt $bitis) {
                $satir = $p.StandardOutput.ReadLineAsync()
                if (-not $satir.Wait([int][Math]::Max(1000, ($bitis - (Get-Date)).TotalMilliseconds))) { break }
                if ($null -eq $satir.Result) { break }
                try { $m = $satir.Result | ConvertFrom-Json } catch { continue }
                if ($m.id -eq $Id) { return $m }
            }
            return $null
        }
        $ilk = Iste 1 'initialize' @{ protocolVersion = '2025-06-18'; capabilities = @{}; clientInfo = @{ name = 'program-guncelle'; version = '1' } }
        if (-not $ilk -or -not $ilk.result) { throw "sunucu el sıkışmaya cevap vermedi$(if ($ilk.error) { ": $($ilk.error.message)" })" }
        $giris.WriteLine('{"jsonrpc":"2.0","method":"notifications/initialized"}')
        $araclar = Iste 2 'tools/list' @{}
        $sayi = @($araclar.result.tools).Count
        if (-not $sayi) { throw 'sunucu araç listesi vermedi' }
        $testler.Add([ordered]@{ ad = 'MCP el sıkışması'; durum = 'GEÇTİ'; ayrinti = "$($ilk.result.serverInfo.name) $($ilk.result.serverInfo.version) çalıştı, $sayi araç sunuyor" })
        if (@($araclar.result.tools.name) -contains 'accept_eula') {
            $testler.Add([ordered]@{ ad = 'Kullanım sözleşmesi'; durum = 'BİLGİ'; ayrinti = "sunucu ilk kullanımda Microsoft sözleşmesinin onayını isteyebilir; skill onayı personel adına vermez" })
        }
        $calisti = $true
    } catch {
        $neden = Kisalt $_.Exception.Message 200
        if ($p) { try { $p.WaitForExit(3000) | Out-Null } catch {} }
        if ($hataAkisi -and $hataAkisi.Wait(3000)) {
            $satir = @($hataAkisi.Result -split "`r?`n" | Where-Object { $_ -match 'Exception:' -and $_ -notmatch '^\s+at ' }) | Select-Object -First 1
            if ($satir) { $t = ($satir -replace '\s+', ' ').Trim(); $neden += " — $($t.Substring(0, [Math]::Min(300, $t.Length)))" }
        }
        $testler.Add([ordered]@{ ad = 'MCP el sıkışması'; durum = 'ENGEL'; ayrinti = "sunucu çalışmadı ($Exe): $neden" })
    } finally {
        if ($p -and -not $p.HasExited) { try { $p.Kill(); $p.WaitForExit(5000) | Out-Null } catch {} }
    }
    $pbi = @((Join-Path $env:ProgramFiles 'Microsoft Power BI Desktop\bin\PBIDesktop.exe')) | Where-Object { Test-Path -LiteralPath $_ }
    $pbiStore = Get-AppxPackage -Name 'Microsoft.MicrosoftPowerBIDesktop' -ErrorAction SilentlyContinue
    if (-not @($testler | Where-Object { $_.ad -eq 'Power BI Desktop' }).Count) { $testler.Add([ordered]@{ ad = 'Power BI Desktop'; durum = 'BİLGİ'; ayrinti = $(if ($pbi -or $pbiStore) { 'kurulu' } else { 'bulunamadı — MCP yerel modellerle çalışmak için Power BI Desktop ister' }) }) }
    foreach ($t in $testler) { Yaz "[$($t.durum)] $($t.ad): $($t.ayrinti)" }
    return $calisti
}

function Bagla([string]$Exe) {
    foreach ($s in @((CodexBagla $Exe), (ClaudeBagla $Exe), (ClaudeCodeBagla $Exe))) { $ayarlar.Add($s); Yaz "Ayar — $($s.uygulama): $($s.sonuc)$(if ($s.ayrinti) { " ($($s.ayrinti))" })" }
    if (@($ayarlar | Where-Object { $_.sonuc -in 'eklendi', 'güncellendi' }).Count) {
        Yaz "Codex, Claude masaüstü ve Claude Code yeniden başlatılınca 'powerbi-modeling' araçları görünür."
    }
    return -not @($ayarlar | Where-Object { $_.sonuc -in 'hata', 'dokunulmadı' }).Count
}

function Bitir([string]$Durum, $Bulunan, [string]$Yontem, [string]$Neden, [string]$ItIsi) {
    $sonuc = [ordered]@{
        durum         = $Durum
        exe           = $(if ($Bulunan) { $Bulunan.Exe } else { $null })
        surum         = $(if ($Bulunan) { $Bulunan.Surum } else { $null })
        hedef_surum   = $(if ($hedef) { $hedef.Surum } else { $null })
        hedef_on_surum = $(if ($hedef) { $hedef.OnSurum } else { $null })
        mevcut        = @($ilkKurulumlar | ForEach-Object { "$($_.Surum) — $($_.Exe)" })
        yontem        = $Yontem
        neden         = $Neden
        it_isi        = $ItIsi
        ayarlar       = $ayarlar
        testler       = $testler
        bilgisayar    = $env:COMPUTERNAME
        zaman         = (Get-Date).ToString('s')
    }
    $d = @($testler | ForEach-Object { $_.durum }) + @($ayarlar | Where-Object { $_.sonuc -in 'hata', 'dokunulmadı' } | ForEach-Object { 'UYARI' })
    $ozet = if ($Durum -eq 'BASARISIZ' -or $d -contains 'ENGEL') { 'ENGEL' } elseif ($Durum -eq 'ESKI' -or $d -contains 'UYARI') { 'UYARI' } elseif ($Durum -eq 'YOK') { 'BİLGİ' } else { 'GEÇTİ' }
    $sonuc['ozet'] = $ozet

    $satirlar = @('', 'AŞAMA 8 — POWER BI MODELING MCP', '--------------------------------',
        "[BİLGİ] Yüklü (kurulumdan önce): $(if ($sonuc.mevcut.Count) { $sonuc.mevcut -join '; ' } else { 'yoktu' })",
        "[BİLGİ] En yeni kararlı sürüm: $($sonuc.hedef_surum)",
        "[$($ozet.PadRight(5))] Durum: $Durum$(if ($Bulunan) { " — kullanılan $($Bulunan.Surum), $($Bulunan.Exe)" })$(if ($Yontem) { "; $Yontem" })$(if ($Neden) { "; $Neden" })")
    foreach ($a in $ayarlar) { $satirlar += "[BİLGİ] Ayar — $($a.uygulama): $($a.sonuc)$(if ($a.ayrinti) { " ($($a.ayrinti))" })" }
    foreach ($t in $testler) { $satirlar += "[$($t.durum.PadRight(5))] $($t.ad): $($t.ayrinti)" }
    if ($ItIsi) { $satirlar += "IT'den gereken: $ItIsi" }

    if ($Rapor -and (Test-Path -LiteralPath $Rapor)) {
        [IO.File]::AppendAllText($Rapor, (($satirlar -join "`r`n") + "`r`n"), (New-Object Text.UTF8Encoding $false))
        $sonuc['rapor'] = $Rapor
    } elseif ($ozet -eq 'ENGEL') {
        $masaustu = [Environment]::GetFolderPath('Desktop')
        if (-not $masaustu -or -not (Test-Path $masaustu)) { $masaustu = $durumKlasoru }
        $dosya = Join-Path $masaustu ("powerbi-mcp-kurulumu-{0}-{1}.txt" -f $env:COMPUTERNAME, (Get-Date).ToString('yyyyMMdd-HHmm'))
        $bas = @("GÜNCELLEYİCİ · sürüm $skillSurum — POWER BI MODELING MCP KURULUMU", $AMAC, "Bilgisayar: $env:COMPUTERNAME  Kullanıcı: $env:USERDOMAIN\$env:USERNAME", "Tarih: $((Get-Date).ToString('dd.MM.yyyy HH:mm'))")
        ($bas + $satirlar) | Out-File -FilePath $dosya -Encoding utf8
        $sonuc['rapor'] = $dosya
    }
    $json = $sonuc | ConvertTo-Json -Compress -Depth 5
    [IO.File]::WriteAllText((Join-Path $durumKlasoru 'powerbi-mcp-kur-sonuc.json'), $json, (New-Object Text.UTF8Encoding $false))
    Write-Output "@@SONUC $json"
    exit 0
}

# SKILL.md başlangıç mesajı ve diğer betiklerle aynı cümle; birini değiştiren hepsini değiştirir.
$AMAC = 'Satınalma Departmanının kullandığı yapay zekâ projelerinde gerekli olan programların personel bilgisayarına yüklenmesini sağlar.'
$skillSurum = '?'
try { $skillSurum = (Get-Content -LiteralPath (Join-Path (Split-Path $PSScriptRoot -Parent) 'VERSION') -TotalCount 1 -ErrorAction Stop).Trim() } catch {}

Write-Host ''
Yaz "Güncelleyici · sürüm $skillSurum — Power BI Modeling MCP"
Yaz $AMAC
Write-Host ''
Yaz 'Aşama 8 — Power BI Modeling MCP'

$kurulumlar = @(TumKurulumlar)
$ilkKurulumlar = $kurulumlar
if ($kurulumlar.Count -eq 0) { Yaz 'Power BI Modeling MCP yüklü değil; kurulacak.' }
else { foreach ($k in $kurulumlar) { Yaz "Power BI Modeling MCP yüklü: $($k.Surum) — $($k.Exe)" } }
$etkin = $kurulumlar | Select-Object -First 1

$hedef = SonSurumuOgren
if ($hedef) { Yaz "En yeni kararlı sürüm: $($hedef.Surum) ($($hedef.Kaynak))" }

if (-not $hedef) {
    if ($etkin) {
        if (-not $YalnizBul) { if (McpTest $etkin.Exe) { $null = Bagla $etkin.Exe } }
        Bitir 'ESKI' $etkin 'zaten kurulu' 'en yeni sürüm öğrenilemedi (Marketplace erişimi yok); kurulu sürümle devam' ''
    }
    Bitir 'BASARISIZ' $null '' "Marketplace'e erişilemedi" 'marketplace.visualstudio.com ve *.gallerycdn.vsassets.io erişiminin açılması (yalnız HTTPS, yalnız okuma).'
}
$hedefV = SurumNesnesi $hedef.Surum

if ($etkin -and (SurumNesnesi $etkin.Surum) -ge $hedefV) {
    Yaz "Power BI Modeling MCP güncel, sonraki aşamaya geçiliyor: $($etkin.Surum)"
    if (-not $YalnizBul) {
        $testGecti = McpTest $etkin.Exe
        $baglantiTam = if ($testGecti) { Bagla $etkin.Exe } else { $false }
        if ($baglantiTam -and $testGecti -and $etkin.Exe -like "$KOK\*") { EskileriTemizle (Split-Path (Split-Path (Split-Path (Split-Path $etkin.Exe -Parent) -Parent) -Parent) -Leaf) }
    }
    Bitir 'MEVCUT' $etkin 'zaten kurulu' '' ''
}
if ($YalnizBul) {
    Bitir $(if ($etkin) { 'ESKI' } else { 'YOK' }) $etkin $(if ($etkin) { 'zaten kurulu' } else { '' }) "en yeni $($hedef.Surum) (yalnız bakıldı)" ''
}

Yaz "$(if ($etkin) { "Power BI Modeling MCP $($etkin.Surum) kurulu ama en yeni değil; $($hedef.Surum) sürümüne güncelleniyor." } else { "Power BI Modeling MCP $($hedef.Surum) kullanıcı alanınıza kurulacak (yönetici yetkisi gerekmez)." })"
$s = PaketKur
$yeni = if ($s.Kod -eq 0) { KurulumBilgisi $s.Exe }
if ($yeni) {
    # Önce sına, sonra bağla: bozuk bir ön sürüm çalışan kurulumun yerine geçmesin.
    if (McpTest $yeni.Exe) {
        Yaz "$(if ($etkin) { 'Güncellendi' } else { 'Kuruldu' }): $($yeni.Surum) — $($yeni.Exe)"
        $baglantiTam = Bagla $yeni.Exe
        if ($baglantiTam) { EskileriTemizle $hedef.Surum }
        Bitir $(if ($etkin) { 'GUNCELLENDI' } else { 'KURULDU' }) $yeni "VS Marketplace paketi (kullanıcı kapsamı)$(if ($etkin) { ", $($etkin.Surum) sürümünden" })" '' ''
    }
    $bozuk = Split-Path (Split-Path (Split-Path $yeni.Exe -Parent) -Parent) -Parent
    try {
        $karantina = Join-Path $KOK '_karantina'
        New-Item -ItemType Directory -Path $karantina -Force | Out-Null
        $bozukHedef = Join-Path $karantina ($hedef.Surum + '-basarisiz-' + [guid]::NewGuid().ToString('N'))
        Israrla { Move-Item -LiteralPath $bozuk -Destination $bozukHedef -ErrorAction Stop }
    } catch { Yaz "Başarısız sürüm silinmedi; bulunduğu klasör: $bozuk" }
    if ($etkin) {
        Yaz "Yeni sürüm $($hedef.Surum) bu bilgisayarda çalışmadı, kaldırıldı; kurulu $($etkin.Surum) ile devam ediliyor."
        $testler.Clear()
        if (McpTest $etkin.Exe) {
            $null = Bagla $etkin.Exe
            Bitir 'ESKI' $etkin 'zaten kurulu' "en yeni sürüm $($hedef.Surum) açılmadı (eski sürüm çalışıyor: büyük olasılıkla Microsoft'un paket hatası, sonraki sürümde yeniden denenir)" ''
        }
        Bitir 'ESKI' $etkin 'zaten kurulu' "ne en yeni $($hedef.Surum) ne kurulu $($etkin.Surum) açıldı" 'powerbi-modeling-mcp.exe (Microsoft imzalı) kullanıcı klasöründen çalışamıyor; güvenlik yazılımı engelliyor olabilir.'
    }
    Bitir 'BASARISIZ' $null '' "Power BI Modeling MCP $($hedef.Surum) kuruldu ama açılmadı, kaldırıldı" 'powerbi-modeling-mcp.exe (Microsoft imzalı) kullanıcı klasöründen çalışamıyor olabilir (güvenlik yazılımı); hata Microsoft paketindeyse sonraki sürümde düzelir — rapordaki hata satırına bakın.'
}
if ($etkin) {
    Yaz "Güncellenemedi ($($s.Neden)); kurulu $($etkin.Surum) ile devam ediliyor."
    if (McpTest $etkin.Exe) { $null = Bagla $etkin.Exe }
    Bitir 'ESKI' $etkin 'zaten kurulu' "en yeni $($hedef.Surum) kurulamadı: $($s.Neden)" ''
}
Yaz 'Power BI Modeling MCP kurulamadı. IT desteği gerekiyor.'
Bitir 'BASARISIZ' $null '' $s.Neden "marketplace.visualstudio.com ve *.gallerycdn.vsassets.io erişiminin açılması ve kullanıcı klasöründen powerbi-modeling-mcp.exe çalıştırılmasına izin (Microsoft imzalı)."
