#requires -Version 5.1
<#
  program-guncelle — Aşama 5: Node.js

  Python ile ilgili aşamalar (1–4) bittikten sonra çalışır, Python'un sonucundan bağımsızdır.
  1) Node.js yüklü mü bakar; yüklü değilse son LTS sürümünü kullanıcı alanına kurar.
  2) Yüklüyse sürümüne bakar: son LTS'in gerisindeyse günceller, değilse sonraki aşamaya geçer.
     "Son sürüm" = nodejs.org'daki en yeni LTS (uzun süreli destek) sürümü; her çalıştırmada
     https://nodejs.org/dist/index.json'dan öğrenilir. LTS'ten yeni bir sürüm (Current) kuruluysa
     dokunulmaz, geri düşürülmez.
  Kurulum: nodejs.org resmi Windows zip'i → %LOCALAPPDATA%\Programs\nodejs. SHA-256 nodejs.org'un
  SHASUMS256.txt'siyle, node.exe'nin OpenJS Foundation imzasıyla doğrulanmadan kurulmaz. Kullanıcı
  PATH'ine eklenir. Yönetici yetkisi istemez; makine geneli eski kurulum IT'ye bildirilir.
  (winget kullanılmaz: kullanıcı kapsamında o da aynı zip'i kurar ve kataloğu geride kalıyor.)

  Çıktı: son satır "@@SONUC {json}"; aynı JSON %LOCALAPPDATA%\program-guncelle\node-kur-sonuc.json
  durum: MEVCUT | KURULDU | ESKI_SURUM (kullanılabilir ama son LTS değil) | BASARISIZ | YOK (-YalnizBul)
  Parametreler: -YalnizBul → hiçbir şey kurmaz, yalnız bakar.
                -Rapor <dosya> → sonucu kurulum-testi.py raporunun sonuna "AŞAMA 5 — NODE.JS" olarak ekler.
#>
param([switch]$YalnizBul, [string]$Rapor)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
# Çıktıyı okuyan ajan (Codex) UTF-8 bekler; konsolun OEM kod sayfası Türkçeyi ve · — işaretlerini bozar.
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch {}
# Git Bash farklı PowerShell sürümünün modül yolunu taşıyabilir; çalışan kabuğun modüllerini kullan.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -ErrorAction Stop

# nodejs.org'a ulaşılamazsa kullanılacak bilinen son LTS (2026-09-24, nodejs.org SHASUMS256.txt'den alındı).
$YEDEK = [pscustomobject]@{
    Surum  = '24.21.0'
    LtsAdi = 'Krypton'
    Url    = 'https://nodejs.org/dist/v24.21.0/node-v24.21.0-win-x64.zip'
    Sha256 = '158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541'
    Kaynak = "skill içindeki bilinen sürüm (nodejs.org'a ulaşılamadı)"
    EnYeni = $null
}
$IMZA_YAYINCI = 'OpenJS Foundation'
$KURULUM_KLASORU = Join-Path $env:LOCALAPPDATA 'Programs\nodejs'
$NPM_KLASORU = Join-Path $env:APPDATA 'npm'

$durumKlasoru = Join-Path $env:LOCALAPPDATA 'program-guncelle'
New-Item -ItemType Directory -Path $durumKlasoru -Force | Out-Null
$denemeler = New-Object System.Collections.Generic.List[object]
$testler = New-Object System.Collections.Generic.List[object]
$ilkNodelar = @()
$hedef = $null

function Yaz([string]$Metin) { Write-Host "  $Metin" }

function Calistir([string]$Dosya, [string]$Argumanlar, [int]$SureMs) {
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $Dosya; $psi.Arguments = $Argumanlar; $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true; $psi.CreateNoWindow = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        $o = $p.StandardOutput.ReadToEndAsync(); $e = $p.StandardError.ReadToEndAsync()
        if (-not $p.WaitForExit($SureMs)) {
            try { $p.Kill() } catch {}
            return [pscustomobject]@{ Kod = -1; Cikti = ''; Hata = "zaman aşımı ($([int]($SureMs/1000)) sn)" }
        }
        return [pscustomobject]@{ Kod = $p.ExitCode; Cikti = $o.Result.Trim(); Hata = $e.Result.Trim() }
    } catch {
        return [pscustomobject]@{ Kod = -2; Cikti = ''; Hata = $_.Exception.Message }
    }
}

function Kisalt([string]$Metin, [int]$Uzunluk = 400) {
    if (-not $Metin) { return '' }
    $t = ($Metin -replace '\s+', ' ').Trim()
    if ($t.Length -gt $Uzunluk) { return $t.Substring($t.Length - $Uzunluk) }
    return $t
}

function SurumNesnesi([string]$Metin) { try { return [version]($Metin -replace '^v', '') } catch { return [version]'0.0' } }

function Kapsam([string]$Yol) {
    if ($Yol -like "$env:LOCALAPPDATA*" -or $Yol -like "$env:APPDATA*") { return 'kullanıcı' }
    return 'makine geneli'
}

# Yeni açılacak bir oturumun PATH'i: önce makine, sonra kullanıcı (kayıt defterinden; bu sürecin PATH'i eskimiş olabilir).
function PathKlasorleri {
    $liste = @()
    foreach ($hedefAd in 'Machine', 'User') {
        $ham = [Environment]::GetEnvironmentVariable('Path', $hedefAd)
        foreach ($k in @("$ham" -split ';')) {
            $k = [Environment]::ExpandEnvironmentVariables($k.Trim()).TrimEnd('\')
            if ($k) { $liste += $k.ToLower() }
        }
    }
    return $liste
}

# Aday node.exe'yi çalıştırarak doğrular.
function NodeDogrula([string]$Dosya) {
    $r = Calistir $Dosya "-p `"process.version.slice(1)+'|'+process.execPath`"" 15000
    if ($r.Kod -ne 0 -or $r.Cikti -notmatch '^(\d+\.\d+\.\d+)\|(.+)$') { return $null }
    return [pscustomobject]@{ Surum = $Matches[1]; Yol = $Matches[2].Trim() }
}

# Bilgisayardaki bütün Node.js kurulumları; Sira = yeni oturumda PATH'teki önceliği (PATH'te değilse 9999).
function TumNodelar {
    $adaylar = New-Object System.Collections.Generic.List[string]
    Get-Command node -All -CommandType Application -ErrorAction SilentlyContinue | ForEach-Object { $adaylar.Add($_.Source) }
    $adaylar.Add((Join-Path $env:ProgramFiles 'nodejs\node.exe'))
    if (${env:ProgramFiles(x86)}) { $adaylar.Add((Join-Path ${env:ProgramFiles(x86)} 'nodejs\node.exe')) }
    $adaylar.Add((Join-Path $KURULUM_KLASORU 'node.exe'))
    if ($env:NVM_SYMLINK) { $adaylar.Add((Join-Path $env:NVM_SYMLINK 'node.exe')) }
    $path = @(PathKlasorleri)
    $bulunanlar = @(); $gorulen = @{}
    foreach ($a in ($adaylar | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $a)) { continue }
        $v = NodeDogrula $a
        if (-not $v -or $gorulen.ContainsKey($v.Yol.ToLower())) { continue }
        $gorulen[$v.Yol.ToLower()] = $true
        $sira = [array]::IndexOf($path, (Split-Path $v.Yol -Parent).TrimEnd('\').ToLower())
        $v | Add-Member -NotePropertyName Sira -NotePropertyValue $(if ($sira -ge 0) { $sira } else { 9999 })
        $bulunanlar += $v
    }
    return @($bulunanlar | Sort-Object Sira, { - (SurumNesnesi $_.Surum).Major })
}

# nodejs.org'dan en yeni LTS'i ve Windows zip'inin özetini öğrenir.
function SonLtsOgren {
    try {
        try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
        try { [Net.WebRequest]::DefaultWebProxy.Credentials = [Net.CredentialCache]::DefaultNetworkCredentials } catch {}
        $dizin = Invoke-RestMethod -Uri 'https://nodejs.org/dist/index.json' -TimeoutSec 20 -UseBasicParsing
        $lts = @($dizin | Where-Object { $_.lts -and @($_.files) -contains 'win-x64-zip' } |
            Sort-Object { SurumNesnesi $_.version } -Descending) | Select-Object -First 1
        if (-not $lts) { throw "nodejs.org'da Windows zip'i olan LTS sürümü bulunamadı" }
        $enYeni = (@($dizin | Sort-Object { SurumNesnesi $_.version } -Descending) | Select-Object -First 1).version -replace '^v', ''
        $v = $lts.version
        $zip = "node-$v-win-x64.zip"
        $ozetler = (Invoke-WebRequest -Uri "https://nodejs.org/dist/$v/SHASUMS256.txt" -TimeoutSec 20 -UseBasicParsing).Content
        $satir = @("$ozetler" -split "`r?`n" | Where-Object { $_ -match "^([0-9a-fA-F]{64})\s+$([regex]::Escape($zip))$" }) | Select-Object -First 1
        if (-not $satir) { throw "SHASUMS256.txt'de $zip özeti yok" }
        return [pscustomobject]@{ Surum = $v -replace '^v', ''; LtsAdi = "$($lts.lts)"; Url = "https://nodejs.org/dist/$v/$zip"
            Sha256 = ($satir -split '\s+')[0].ToLower(); Kaynak = 'nodejs.org'; EnYeni = $enYeni }
    } catch {
        Yaz "nodejs.org'dan son sürüm öğrenilemedi ($(Kisalt $_.Exception.Message 150)); bilinen sürüm kullanılacak."
        return $YEDEK
    }
}

# Kullanıcı PATH'ine klasör ekler (kayıt defterindeki ham değer korunur: %USERPROFILE% gibi değişkenler açılmaz).
function KullaniciPathEkle([string[]]$Klasorler, [string[]]$BasaKlasorler) {
    $anahtar = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
    try {
        $ham = [string]$anahtar.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        $parcalar = @($ham -split ';' | Where-Object { $_.Trim() })
        $acik = @($parcalar | ForEach-Object { [Environment]::ExpandEnvironmentVariables($_).TrimEnd('\').ToLower() })
        $degisti = $false
        foreach ($k in $BasaKlasorler) { if ($acik -notcontains $k.TrimEnd('\').ToLower()) { $parcalar = @($k) + $parcalar; $degisti = $true } }
        foreach ($k in $Klasorler) { if ($acik -notcontains $k.TrimEnd('\').ToLower()) { $parcalar += $k; $degisti = $true } }
        if (-not $degisti) { return $false }
        $anahtar.SetValue('Path', ($parcalar -join ';'), [Microsoft.Win32.RegistryValueKind]::ExpandString)
    } finally { $anahtar.Close() }
    # Açık pencerelere "ortam değişkenleri değişti" haberi: .NET kullanıcı değişkeni yazınca bunu yayınlar.
    [Environment]::SetEnvironmentVariable('PROGRAM_GUNCELLE_YENILE', '1', 'User')
    [Environment]::SetEnvironmentVariable('PROGRAM_GUNCELLE_YENILE', $null, 'User')
    return $true
}

# Antivirüs yeni yazılan/çalıştırılan dosyayı birkaç saniye kilitli tutar (ölçüldü, 2026-09-24):
# klasör işlemi aynı biçimde kısa aralıklarla yeniden denenir (en fazla ~15 sn).
function Israrla([scriptblock]$Is, [int]$Deneme = 20) {
    for ($i = 1; ; $i++) {
        try { & $Is; return } catch { if ($i -ge $Deneme) { throw }; Start-Sleep -Milliseconds 750 }
    }
}

# nodejs.org zip'ini indirir, doğrular, %LOCALAPPDATA%\Programs\nodejs'e koyar (varsa eskisinin yerine).
function ZipKur {
    $gecici = Join-Path $env:TEMP ('program-guncelle-node-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    $programs = Split-Path $KURULUM_KLASORU -Parent
    $hazirlik = Join-Path $programs ('nodejs.yeni-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    $eskiYedek = $null
    New-Item -ItemType Directory -Path $gecici, $programs -Force | Out-Null
    $dosya = Join-Path $gecici ($hedef.Url -split '/')[-1]
    try {
        Yaz "nodejs.org'dan Node.js $($hedef.Surum) indiriliyor (yaklaşık 36 MB)..."
        Invoke-WebRequest -Uri $hedef.Url -OutFile $dosya -UseBasicParsing -TimeoutSec 600 -ErrorAction Stop
        $ozet = (Get-FileHash -LiteralPath $dosya -Algorithm SHA256).Hash.ToLower()
        if ($ozet -ne $hedef.Sha256) {
            throw "indirilen dosya doğrulanamadı (SHA-256 $ozet, beklenen $($hedef.Sha256)) — dosya değişmiş ya da ağda araya giren var; kurulmadı"
        }
        # Zip'in üst klasörü (node-vX-win-x64) atlanarak açılır: npm'in iç içe yolları Windows'un 260 karakter
        # sınırına yaklaşıyor, gereksiz 22 karakter payı eritmesin. Her yol ayrıca denetlenir.
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $ust = "node-v$($hedef.Surum)-win-x64/"
        $arsiv = [IO.Compression.ZipFile]::OpenRead($dosya)
        try {
            foreach ($g in $arsiv.Entries) {
                if (-not $g.FullName.StartsWith($ust)) { throw "zip beklenen klasörle başlamıyor ($($g.FullName)); kurulmadı" }
                $ic = $g.FullName.Substring($ust.Length)
                if (-not $ic) { continue }
                if ($ic -match '(^|/)\.\.(/|$)' -or $ic -match '[:\\]') { throw "zip içinde geçersiz yol ($($g.FullName)); kurulmadı" }
                $yol = Join-Path $hazirlik ($ic -replace '/', '\')
                if ($ic.EndsWith('/')) { [void][IO.Directory]::CreateDirectory($yol); continue }
                [void][IO.Directory]::CreateDirectory((Split-Path $yol -Parent))
                [IO.Compression.ZipFileExtensions]::ExtractToFile($g, $yol, $true)
            }
        } finally { $arsiv.Dispose() }
        $yeniNode = Join-Path $hazirlik 'node.exe'
        if (-not (Test-Path -LiteralPath $yeniNode)) { throw "zip içinde node.exe yok; kurulmadı" }
        $imza = Get-AuthenticodeSignature -LiteralPath $yeniNode
        if ($imza.Status -ne 'Valid' -or $imza.SignerCertificate.Subject -notlike "*$IMZA_YAYINCI*") {
            throw "node.exe dijital imzası doğrulanamadı (durum $($imza.Status), imzalayan $($imza.SignerCertificate.Subject)); kurulmadı"
        }
        $v = NodeDogrula $yeniNode
        if (-not $v -or $v.Surum -ne $hedef.Surum) { throw "indirilen node.exe çalışmadı ya da sürümü beklenen değil (güvenlik yazılımı engellemiş olabilir); kurulmadı" }
        Yaz 'Dosya doğrulandı (SHA-256, OpenJS Foundation imzası, çalıştırma). Kuruluyor...'
        if (Test-Path -LiteralPath $KURULUM_KLASORU) {
            $eskiYedek = "$KURULUM_KLASORU.eski-" + [guid]::NewGuid().ToString('N').Substring(0, 8)
            try { Israrla { Rename-Item -LiteralPath $KURULUM_KLASORU -NewName (Split-Path $eskiYedek -Leaf) -ErrorAction Stop } }
            catch { $eskiYedek = $null; throw "eski Node.js klasörü değiştirilemedi — Node.js şu an çalışıyor olabilir; engelleyen süreç belirlenmeli; kurulmadı" }
        }
        try { Israrla { Rename-Item -LiteralPath $hazirlik -NewName (Split-Path $KURULUM_KLASORU -Leaf) -ErrorAction Stop } }
        catch {
            $hata = Kisalt $_.Exception.Message 150
            if ($eskiYedek) {
                try { Israrla { Rename-Item -LiteralPath $eskiYedek -NewName (Split-Path $KURULUM_KLASORU -Leaf) -ErrorAction Stop }; $eskiYedek = $null }
                catch { $kalan = $eskiYedek; $eskiYedek = $null; throw "yeni sürüm yerine konamadı ($hata); eski kurulum geri konamadı, $kalan klasöründe duruyor" }
            }
            throw "yeni sürüm yerine konamadı ($hata); eski kurulum yerinde"
        }
        New-Item -ItemType Directory -Path $NPM_KLASORU -Force | Out-Null   # npm'in genel paket klasörü; yoksa npx hata verir
        $pathDegisti = KullaniciPathEkle -BasaKlasorler @($KURULUM_KLASORU) -Klasorler @($NPM_KLASORU)
        if ($eskiYedek) {
            try {
                $karantina = Join-Path $programs '_karantina'
                New-Item -ItemType Directory -Path $karantina -Force | Out-Null
                Israrla { Move-Item -LiteralPath $eskiYedek -Destination $karantina -ErrorAction Stop }
                $eskiYedek = $null
            } catch { Yaz "Eski Node.js silinmedi; korunduğu klasör: $eskiYedek" }
        }
        return [pscustomobject]@{ Kod = 0; Neden = ''; PathDegisti = $pathDegisti }
    } catch {
        return [pscustomobject]@{ Kod = -3; Neden = (Kisalt $_.Exception.Message); PathDegisti = $false }
    } finally {
        # Eski kurulum geri dönüş/karantina hatasında da saklanır.
        foreach ($k in @($hazirlik, $gecici)) {
            if ($k -and (Test-Path -LiteralPath $k)) { try { Israrla { Remove-Item -LiteralPath $k -Recurse -Force -ErrorAction Stop } } catch {} }
        }
    }
}

# Seçilen Node.js ile npm ve gerçek bir iş (SHA-256 hesabı) denenir.
function NodeTest([object]$Node) {
    $klasor = Split-Path $Node.Yol -Parent
    $npm = Join-Path $klasor 'npm.cmd'
    if (Test-Path -LiteralPath $npm) {
        $r = Calistir $env:ComSpec "/d /c `"`"$npm`" -v`"" 60000
        if ($r.Kod -eq 0 -and $r.Cikti -match '^\d+\.\d+\.\d+') { $testler.Add([ordered]@{ ad = 'npm'; durum = 'GEÇTİ'; ayrinti = "sürüm $($r.Cikti)" }) }
        else { $testler.Add([ordered]@{ ad = 'npm'; durum = 'UYARI'; ayrinti = "çalışmadı (kod $($r.Kod)): $(Kisalt "$($r.Cikti) $($r.Hata)" 200)" }) }
    } else {
        $testler.Add([ordered]@{ ad = 'npm'; durum = 'UYARI'; ayrinti = "npm.cmd bulunamadı ($klasor)" })
    }
    $beklenen = -join ([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes('program-guncelle')) | ForEach-Object { $_.ToString('x2') })
    $r = Calistir $Node.Yol "-e `"process.stdout.write(require('crypto').createHash('sha256').update('program-guncelle').digest('hex'))`"" 30000
    if ($r.Kod -eq 0 -and $r.Cikti -eq $beklenen) { $testler.Add([ordered]@{ ad = 'Node.js işlev testi'; durum = 'GEÇTİ'; ayrinti = 'betik çalıştı, SHA-256 hesabı doğru' }) }
    else { $testler.Add([ordered]@{ ad = 'Node.js işlev testi'; durum = 'ENGEL'; ayrinti = "betik çalışmadı ya da sonuç yanlış (kod $($r.Kod)): $(Kisalt $r.Hata 200)" }) }
    foreach ($t in $testler) { Yaz "[$($t.durum)] $($t.ad): $($t.ayrinti)" }
}

function Bitir([string]$Durum, $Bulunan, [string]$Yontem, [string]$Neden, [string]$ItIsi) {
    $sonuc = [ordered]@{
        durum          = $Durum
        node           = $(if ($Bulunan) { $Bulunan.Yol } else { $null })
        surum          = $(if ($Bulunan) { $Bulunan.Surum } else { $null })
        kapsam         = $(if ($Bulunan) { Kapsam $Bulunan.Yol } else { '' })
        hedef_surum    = $(if ($hedef) { $hedef.Surum } else { $null })
        hedef_lts      = $(if ($hedef) { $hedef.LtsAdi } else { $null })
        hedef_kaynagi  = $(if ($hedef) { $hedef.Kaynak } else { $null })
        mevcut_nodelar = @($ilkNodelar | ForEach-Object { "$($_.Surum) — $($_.Yol) ($(Kapsam $_.Yol))" })
        yontem         = $Yontem
        neden          = $Neden
        it_isi         = $ItIsi
        testler        = $testler
        denemeler      = $denemeler
        bilgisayar     = $env:COMPUTERNAME
        zaman          = (Get-Date).ToString('s')
    }
    $ozet = switch ($Durum) {
        'MEVCUT'     { 'GEÇTİ' }
        'KURULDU'    { 'GEÇTİ' }
        'ESKI_SURUM' { 'UYARI' }
        'YOK'        { 'BİLGİ' }
        default      { 'ENGEL' }
    }
    if ($ozet -eq 'GEÇTİ' -and @($testler | Where-Object { $_.durum -eq 'ENGEL' }).Count) { $ozet = 'ENGEL' }
    elseif ($ozet -eq 'GEÇTİ' -and @($testler | Where-Object { $_.durum -eq 'UYARI' }).Count) { $ozet = 'UYARI' }
    $sonuc['ozet'] = $ozet

    $satirlar = @('', 'AŞAMA 5 — NODE.JS', '-----------------',
        "[BİLGİ] Yüklü Node.js (kurulumdan önce): $(if ($sonuc.mevcut_nodelar.Count) { $sonuc.mevcut_nodelar -join '; ' } else { 'yoktu' })",
        "[BİLGİ] Son sürüm: Node.js $($sonuc.hedef_surum) LTS ($($sonuc.hedef_lts); $($sonuc.hedef_kaynagi))",
        "[$($ozet.PadRight(5))] Durum: $Durum$(if ($Bulunan) { " — kullanılan $($Bulunan.Surum), $($Bulunan.Yol)" })$(if ($Yontem) { "; $Yontem" })$(if ($Neden) { "; $Neden" })")
    foreach ($t in $testler) { $satirlar += "[$($t.durum.PadRight(5))] $($t.ad): $($t.ayrinti)" }
    foreach ($d in $denemeler) { $satirlar += "- kurulum denemesi $($d.yol): $($d.sonuc) $($d.ayrinti)".TrimEnd() }
    if ($ItIsi) { $satirlar += "IT'den gereken: $ItIsi" }

    if ($Rapor -and (Test-Path -LiteralPath $Rapor)) {
        [IO.File]::AppendAllText($Rapor, (($satirlar -join "`r`n") + "`r`n"), (New-Object Text.UTF8Encoding $false))
        $sonuc['rapor'] = $Rapor
    } elseif ($Durum -eq 'BASARISIZ' -or $ItIsi) {
        $masaustu = [Environment]::GetFolderPath('Desktop')
        if (-not $masaustu -or -not (Test-Path $masaustu)) { $masaustu = $durumKlasoru }
        $dosya = Join-Path $masaustu ("node-kurulumu-{0}-{1}.txt" -f $env:COMPUTERNAME, (Get-Date).ToString('yyyyMMdd-HHmm'))
        $bas = @("GÜNCELLEYİCİ · sürüm $skillSurum — NODE.JS KURULUMU", $AMAC, "Bilgisayar: $env:COMPUTERNAME  Kullanıcı: $env:USERDOMAIN\$env:USERNAME", "Tarih: $((Get-Date).ToString('dd.MM.yyyy HH:mm'))")
        ($bas + $satirlar) | Out-File -FilePath $dosya -Encoding utf8
        $sonuc['rapor'] = $dosya
    }
    $json = $sonuc | ConvertTo-Json -Compress -Depth 5
    [IO.File]::WriteAllText((Join-Path $durumKlasoru 'node-kur-sonuc.json'), $json, (New-Object Text.UTF8Encoding $false))
    Write-Output "@@SONUC $json"
    exit 0
}

# SKILL.md başlangıç mesajı, python-kur.ps1 ve kurulum-testi.py ile aynı cümle; birini değiştiren hepsini değiştirir.
$AMAC = 'Satınalma Departmanının kullandığı yapay zekâ projelerinde gerekli olan programların personel bilgisayarına yüklenmesini sağlar.'
$skillSurum = '?'
try { $skillSurum = (Get-Content -LiteralPath (Join-Path (Split-Path $PSScriptRoot -Parent) 'VERSION') -TotalCount 1 -ErrorAction Stop).Trim() } catch {}

Write-Host ''
Yaz "Güncelleyici · sürüm $skillSurum — Node.js"
Yaz $AMAC
Write-Host ''
Yaz 'Aşama 5 — Node.js'

$nodelar = @(TumNodelar)
$ilkNodelar = $nodelar   # kurulumdan ÖNCEKİ durum (rapora bu gider)
if ($nodelar.Count -eq 0) { Yaz 'Node.js yüklü değil; kurulacak.' }
else { foreach ($n in $nodelar) { Yaz "Node.js yüklü: $($n.Surum) — $($n.Yol) ($(Kapsam $n.Yol))" } }

$hedef = SonLtsOgren
$hedefV = SurumNesnesi $hedef.Surum
Yaz "Son sürüm: Node.js $($hedef.Surum) LTS ($($hedef.LtsAdi); $($hedef.Kaynak))"

# Yeni bir oturumda "node" yazınca açılacak olan: PATH'te ilk sıradaki.
$etkin = @($nodelar | Where-Object { $_.Sira -lt 9999 }) | Select-Object -First 1

if ($etkin -and (SurumNesnesi $etkin.Surum) -ge $hedefV) {
    Yaz "Node.js güncel, sonraki aşamaya geçiliyor: $($etkin.Surum) — $($etkin.Yol)"
    if (-not $YalnizBul) { NodeTest $etkin }
    Bitir 'MEVCUT' $etkin 'zaten kurulu' '' ''
}

if ($YalnizBul) {
    if ($etkin) { Bitir 'ESKI_SURUM' $etkin 'zaten kurulu' "son LTS $($hedef.Surum), kurulu $($etkin.Surum) (yalnız bakıldı)" '' }
    Bitir 'YOK' $null '' 'Node.js PATH üzerinde yok (yalnız bakıldı)' ''
}

if ($etkin -and (Kapsam $etkin.Yol) -eq 'makine geneli') {
    # Makine geneli kurulum yönetici yetkisi olmadan güncellenemez; kullanıcıya ikinci kopya kurmak da işe yaramaz
    # (makine PATH'i önce okunur, "node" yine eskisini açar).
    Yaz "Node.js $($etkin.Surum) makine geneline kurulu; son sürüme ($($hedef.Surum)) güncellemek yönetici yetkisi ister. Bu sürümle devam ediliyor, IT'ye bildirilecek."
    NodeTest $etkin
    Bitir 'ESKI_SURUM' $etkin 'zaten kurulu' "makine geneli kurulum; son LTS'e güncelleme IT'de" "Makine geneline kurulu Node.js $($etkin.Surum), son LTS sürümüne ($($hedef.Surum)) güncellenmeli (nodejs.org MSI veya merkezi dağıtım; yönetici yetkisi gerekir)."
}

if ($etkin) { Yaz "Node.js $($etkin.Surum) kullanıcı alanında kurulu ama son sürüm değil; $($hedef.Surum) sürümüne güncelleniyor." }
else { Yaz "Node.js son sürümü ($($hedef.Surum)) kullanıcı alanınıza kurulacak (yönetici yetkisi gerekmez)." }

$s = ZipKur
$yeni = if (Test-Path -LiteralPath (Join-Path $KURULUM_KLASORU 'node.exe')) { NodeDogrula (Join-Path $KURULUM_KLASORU 'node.exe') }
if ($s.Kod -eq 0 -and $yeni -and (SurumNesnesi $yeni.Surum) -ge $hedefV) {
    $denemeler.Add([ordered]@{ yol = 'nodejs.org zip'; sonuc = 'başarılı'; ayrinti = $(if ($s.PathDegisti) { "kullanıcı PATH'ine eklendi" } else { '' }) })
    Yaz "$(if ($etkin) { 'Güncellendi' } else { 'Kuruldu' }): Node.js $($yeni.Surum) — $($yeni.Yol)"
    if ($s.PathDegisti) { Yaz "Yeni açılan pencerelerde 'node' ve 'npm' komutları çalışır (açık pencereler yeniden açılmalı)." }
    NodeTest $yeni
    Bitir 'KURULDU' $yeni "nodejs.org resmi zip (kullanıcı kapsamı)$(if ($etkin) { ", $($etkin.Surum) sürümünden güncelleme" })" '' ''
}
$denemeler.Add([ordered]@{ yol = 'nodejs.org zip'; sonuc = 'başarısız'; ayrinti = $s.Neden })
if ($etkin) {
    Yaz "Güncellenemedi; kurulu $($etkin.Surum) ile devam ediliyor."
    NodeTest $etkin
    Bitir 'ESKI_SURUM' $etkin 'zaten kurulu' "son LTS $($hedef.Surum) kurulamadı: $($s.Neden)" ''
}
Yaz 'Node.js kurulamadı. IT desteği gerekiyor.'
Bitir 'BASARISIZ' $null '' "Node.js $($hedef.Surum) kullanıcı alanına kurulamadı: $($s.Neden)" "nodejs.org erişiminin (HTTPS, yalnız okuma) ve kullanıcı klasöründen node.exe çalıştırılmasının açılması, ya da Node.js $($hedef.Surum) LTS'in merkezi dağıtımla kurulması."
