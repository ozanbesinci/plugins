#requires -Version 5.1
<#
  program-guncelle — Aşama 1 ve 2: Python yüklü mü? · Python'un son sürümü

  Aşama 1: bilgisayardaki bütün gerçek Python kurulumlarını listeler.
  Aşama 2: Python'un son sürümü kurulu mu bakar; değilse kullanıcı kapsamında kurar/günceller.
    "Son sürüm" = skill'in desteklediği en yeni Python serisinin ($DESTEK_SERI) python.org'daki
    son yaması; her çalıştırmada python.org'dan öğrenilir. Kütüphane özetleri bu seriye göredir;
    daha yeni bir seri çıkarsa raporda bildirilir, seri skill güncellemesiyle ilerletilir.
    Kurulum sırası: winget (--scope user) → python.org resmi kurulum dosyası (boyut + SHA-256 +
    Python Software Foundation imzası doğrulanmadan kurulmaz) → olmazsa durur.
  Yönetici yetkisi istemez, güvenlik ayarlarını atlatmaya çalışmaz.

  Çıktı: son satır "@@SONUC {json}"; aynı JSON %LOCALAPPDATA%\program-guncelle\python-kur-sonuc.json
  durum: MEVCUT | KURULDU | ESKI_YAMA (kullanılabilir ama son yama değil) | BASARISIZ | YOK (-YalnizBul)
  Parametre: -YalnizBul → hiçbir şey kurmaz, yalnız bakar.
#>
param([switch]$YalnizBul)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
# Çıktıyı okuyan ajan (Codex) UTF-8 bekler; konsolun OEM kod sayfası Türkçeyi ve · — işaretlerini bozar.
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch {}
# Git Bash farklı PowerShell sürümünün modül yolunu taşıyabilir; çalışan kabuğun modüllerini kullan.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -ErrorAction Stop

# Skill'in desteklediği en yeni Python serisi. kurulum-testi.py'deki DESTEK_SERI ve paket özetleriyle
# birlikte değişir (bkz. proje CLAUDE.md).
$DESTEK_SERI = '3.14'
# python.org'a ulaşılamazsa kullanılacak bilinen son yama (2026-09-24, python.org API'sinden alındı).
$YEDEK = [pscustomobject]@{
    Surum  = '3.14.7'
    Url    = 'https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.exe'
    Boyut  = 33258168
    Sha256 = '9d9eb2709ef81bf5cd30db3c2096bdbc4ea10087c22e62f27d356b36f6ae9649'
    Kaynak = "skill içindeki bilinen sürüm (python.org'a ulaşılamadı)"
    EnYeniKararli = $null
}
$IMZA_YAYINCI = 'Python Software Foundation'

$durumKlasoru = Join-Path $env:LOCALAPPDATA 'program-guncelle'
New-Item -ItemType Directory -Path $durumKlasoru -Force | Out-Null
$denemeler = New-Object System.Collections.Generic.List[object]
$tumPythonlar = @()
$ilkPythonlar = @()
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

function SurumNesnesi([string]$Metin) { try { return [version]$Metin } catch { return [version]'0.0' } }

# Aday bir yorumlayıcıyı çalıştırarak doğrular; Store'un sahte kısayolu burada elenir.
function Dogrula([string]$Dosya, [string]$OnEk) {
    $kod = 'import sys;print(sys.version.split()[0]);print(sys.executable)'
    $r = Calistir $Dosya "$OnEk -c `"$kod`"" 15000
    if ($r.Kod -ne 0) { return $null }
    $satir = @($r.Cikti -split "`r?`n")
    if ($satir.Count -lt 2 -or $satir[0] -notmatch '^\d+\.\d+\.\d+$') { return $null }
    return [pscustomobject]@{ Surum = $satir[0].Trim(); Yol = $satir[1].Trim() }
}

# Aşama 1: bilgisayardaki bütün gerçek Python kurulumları (sürümü ne olursa olsun).
function TumPythonlar {
    $adaylar = New-Object System.Collections.Generic.List[string]
    $py = Get-Command py -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($py) {
        $r = Calistir $py.Source '-0p' 10000
        foreach ($s in @($r.Cikti -split "`r?`n")) { if ($s -match '([A-Za-z]:\\.+?\.exe)\s*$') { $adaylar.Add($Matches[1]) } }
    }
    foreach ($kok in 'HKCU:\SOFTWARE\Python\PythonCore', 'HKLM:\SOFTWARE\Python\PythonCore', 'HKLM:\SOFTWARE\WOW6432Node\Python\PythonCore') {
        if (-not (Test-Path $kok)) { continue }
        Get-ChildItem $kok -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                $ip = Get-ItemProperty -LiteralPath (Join-Path $_.PSPath 'InstallPath') -ErrorAction Stop
                if ($ip.ExecutablePath) { $adaylar.Add($ip.ExecutablePath) }
                elseif ($ip.'(default)') { $adaylar.Add((Join-Path $ip.'(default)' 'python.exe')) }
            } catch {}
        }
    }
    $seriKlasoru = 'Python' + ($DESTEK_SERI -replace '\.', '')
    $adaylar.Add((Join-Path $env:LOCALAPPDATA "Programs\Python\$seriKlasoru\python.exe"))
    $adaylar.Add((Join-Path $env:ProgramFiles "$seriKlasoru\python.exe"))
    foreach ($ad in 'python', 'python3') {
        Get-Command $ad -All -CommandType Application -ErrorAction SilentlyContinue | ForEach-Object { $adaylar.Add($_.Source) }
    }
    $bulunanlar = @(); $gorulen = @{}
    foreach ($a in ($adaylar | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $a)) { continue }
        $v = Dogrula $a ''
        if ($v -and -not $gorulen.ContainsKey($v.Yol.ToLower())) { $gorulen[$v.Yol.ToLower()] = $true; $bulunanlar += $v }
    }
    return @($bulunanlar | Sort-Object { SurumNesnesi $_.Surum } -Descending)
}

function SeriKurulumlari { return @($tumPythonlar | Where-Object { $_.Surum -like "$DESTEK_SERI.*" }) }

function Kapsam([string]$Yol) {
    if ($Yol -like "$env:LOCALAPPDATA*") { return 'kullanıcı' }
    if ($Yol -like '*\WindowsApps\*') { return 'Microsoft Store' }
    return 'makine geneli'
}

# python.org'dan desteklenen serinin son yamasını ve kurulum dosyasının özetini öğrenir.
function SonSurumuOgren {
    try {
        try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
        try { [Net.WebRequest]::DefaultWebProxy.Credentials = [Net.CredentialCache]::DefaultNetworkCredentials } catch {}
        $surumler = Invoke-RestMethod -Uri 'https://www.python.org/api/v2/downloads/release/?is_published=true&pre_release=false' -TimeoutSec 20 -UseBasicParsing
        $kararli = @($surumler | Where-Object { $_.name -match '^Python 3\.\d+\.\d+$' })
        $enYeni = ($kararli | Sort-Object { SurumNesnesi ($_.name -replace '^Python ', '') } -Descending | Select-Object -First 1).name -replace '^Python ', ''
        $seri = @($kararli | Where-Object { $_.name -like "Python $DESTEK_SERI.*" } | Sort-Object { SurumNesnesi ($_.name -replace '^Python ', '') } -Descending)
        if ($seri.Count -eq 0) { throw "python.org'da $DESTEK_SERI serisi bulunamadı" }
        $surum = $seri[0].name -replace '^Python ', ''
        $rid = ($seri[0].resource_uri.TrimEnd('/') -split '/')[-1]
        $dosyalar = Invoke-RestMethod -Uri "https://www.python.org/api/v2/downloads/release_file/?release=$rid" -TimeoutSec 20 -UseBasicParsing
        $exe = @($dosyalar | Where-Object { $_.url -like "*/python-$surum-amd64.exe" }) | Select-Object -First 1
        if (-not $exe -or $exe.sha256_sum -notmatch '^[0-9a-fA-F]{64}$' -or -not $exe.filesize) { throw "python.org'da $surum için doğrulanabilir kurulum dosyası bilgisi yok" }
        return [pscustomobject]@{ Surum = $surum; Url = $exe.url; Boyut = [int64]$exe.filesize; Sha256 = $exe.sha256_sum.ToLower(); Kaynak = 'python.org'; EnYeniKararli = $enYeni }
    } catch {
        Yaz "python.org'dan son sürüm öğrenilemedi ($(Kisalt $_.Exception.Message 150)); bilinen sürüm kullanılacak."
        return $YEDEK
    }
}

# python.org resmi kurulum dosyasını indirir, doğrular ve kullanıcı kapsamında çalıştırır.
# Aynı serinin daha eski kullanıcı kurulumu varsa onu son yamaya yükseltir.
function PyorgKur {
    $klasor = Join-Path $env:TEMP ('program-guncelle-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    New-Item -ItemType Directory -Path $klasor -Force | Out-Null
    $dosya = Join-Path $klasor "python-$($hedef.Surum)-amd64.exe"
    try {
        Yaz ("python.org'dan Python {0} kurulum dosyası indiriliyor ({1:N0} MB)..." -f $hedef.Surum, ($hedef.Boyut / 1MB))
        Invoke-WebRequest -Uri $hedef.Url -OutFile $dosya -UseBasicParsing -TimeoutSec 600 -ErrorAction Stop
        $boyut = (Get-Item -LiteralPath $dosya).Length
        $ozet = (Get-FileHash -LiteralPath $dosya -Algorithm SHA256).Hash.ToLower()
        if ($boyut -ne $hedef.Boyut -or $ozet -ne $hedef.Sha256) {
            throw "indirilen dosya doğrulanamadı (boyut $boyut / beklenen $($hedef.Boyut), SHA-256 $ozet) — dosya değişmiş ya da ağda araya giren var; kurulmadı"
        }
        $imza = Get-AuthenticodeSignature -LiteralPath $dosya
        if ($imza.Status -ne 'Valid' -or $imza.SignerCertificate.Subject -notlike "*$IMZA_YAYINCI*") {
            throw "dijital imza doğrulanamadı (durum $($imza.Status), imzalayan $($imza.SignerCertificate.Subject)); kurulmadı"
        }
        Yaz 'Dosya doğrulandı (boyut, SHA-256, Python Software Foundation imzası). Kuruluyor...'
        $log = Join-Path $durumKlasoru 'python-kurulum.log'
        $arg = "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 InstallLauncherAllUsers=0 Include_test=0 Include_doc=0 /log `"$log`""
        $r = Calistir $dosya $arg 900000
        $neden = "kurulum dosyası çıkış kodu $($r.Kod)"
        if ($r.Kod -eq 1625) { $neden += ' — kurulum grup ilkesiyle engellendi' }
        elseif ($r.Kod -eq 1260) { $neden += ' — program grup ilkesiyle engellendi' }
        return [pscustomobject]@{ Kod = $r.Kod; Neden = "$neden; ayrıntı: $log" }
    } catch {
        return [pscustomobject]@{ Kod = -3; Neden = (Kisalt $_.Exception.Message) }
    } finally {
        Remove-Item -LiteralPath $klasor -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Bitir([string]$Durum, $Bulunan, [string]$Yontem, [string]$Neden) {
    $yeniSeri = $null
    if ($hedef -and $hedef.EnYeniKararli -and ((SurumNesnesi (($hedef.EnYeniKararli -split '\.')[0..1] -join '.')) -gt (SurumNesnesi $DESTEK_SERI))) {
        $yeniSeri = $hedef.EnYeniKararli
    }
    $sonuc = [ordered]@{
        durum            = $Durum
        python           = $(if ($Bulunan) { $Bulunan.Yol } else { $null })
        surum            = $(if ($Bulunan) { $Bulunan.Surum } else { $null })
        kapsam           = $(if ($Bulunan) { Kapsam $Bulunan.Yol } else { '' })
        hedef_surum      = $(if ($hedef) { $hedef.Surum } else { $null })
        hedef_kaynagi    = $(if ($hedef) { $hedef.Kaynak } else { $null })
        destek_serisi    = $DESTEK_SERI
        yeni_seri_var    = $yeniSeri
        mevcut_pythonlar = @($ilkPythonlar | ForEach-Object { "$($_.Surum) — $($_.Yol)" })
        yontem           = $Yontem
        neden            = $Neden
        denemeler        = $denemeler
        bilgisayar       = $env:COMPUTERNAME
        zaman            = (Get-Date).ToString('s')
    }
    $json = $sonuc | ConvertTo-Json -Compress -Depth 5
    [IO.File]::WriteAllText((Join-Path $durumKlasoru 'python-kur-sonuc.json'), $json, (New-Object Text.UTF8Encoding $false))
    if ($Durum -eq 'BASARISIZ') {
        $masaustu = [Environment]::GetFolderPath('Desktop')
        if (-not $masaustu -or -not (Test-Path $masaustu)) { $masaustu = $durumKlasoru }
        $rapor = Join-Path $masaustu ("python-kurulumu-BASARISIZ-{0}-{1}.txt" -f $env:COMPUTERNAME, (Get-Date).ToString('yyyyMMdd-HHmm'))
        $satirlar = @('PYTHON KURULUMU BAŞARISIZ', "Bilgisayar: $env:COMPUTERNAME  Kullanıcı: $env:USERDOMAIN\$env:USERNAME", "Tarih: $((Get-Date).ToString('dd.MM.yyyy HH:mm'))", "Hedef: Python $($sonuc.hedef_surum)", '', "Neden: $Neden", '', 'Denemeler:')
        foreach ($d in $denemeler) { $satirlar += "- $($d.yol): $($d.sonuc) $($d.ayrinti)" }
        $satirlar | Out-File -FilePath $rapor -Encoding utf8
        $sonuc['rapor'] = $rapor
        $json = $sonuc | ConvertTo-Json -Compress -Depth 5
    }
    Write-Output "@@SONUC $json"
    exit 0
}

function Yeniden { $script:tumPythonlar = @(TumPythonlar); return @(SeriKurulumlari) }

# SKILL.md başlangıç mesajı ve kurulum-testi.py ile aynı cümle; birini değiştiren üçünü de değiştirir.
$AMAC = 'Satınalma Departmanının kullandığı yapay zekâ projelerinde gerekli olan programların personel bilgisayarına yüklenmesini sağlar.'
$skillSurum = '?'
try { $skillSurum = (Get-Content -LiteralPath (Join-Path (Split-Path $PSScriptRoot -Parent) 'VERSION') -TotalCount 1 -ErrorAction Stop).Trim() } catch {}

Write-Host ''
Yaz "Güncelleyici · sürüm $skillSurum — Python kurulumu"
Yaz $AMAC

# ---------------------------------------------------------------- Aşama 1
Write-Host ''
Yaz 'Aşama 1 — Python yüklü mü?'
$tumPythonlar = @(TumPythonlar)
$ilkPythonlar = $tumPythonlar   # Aşama 1'in sonucu: kurulumdan ÖNCEKİ durum (rapora bu gider)
if ($tumPythonlar.Count -eq 0) {
    Yaz 'Python yüklü değil; kurulacak.'
} else {
    foreach ($p in $tumPythonlar) { Yaz "Python yüklü: $($p.Surum) — $($p.Yol)" }
    Yaz 'Sonraki aşamaya geçiliyor.'
}

# ---------------------------------------------------------------- Aşama 2
Write-Host ''
Yaz "Aşama 2 — Python'un son sürümü"
$hedef = SonSurumuOgren
Yaz "Son sürüm: Python $($hedef.Surum) ($($hedef.Kaynak))"
if ($hedef.EnYeniKararli -and ((SurumNesnesi (($hedef.EnYeniKararli -split '\.')[0..1] -join '.')) -gt (SurumNesnesi $DESTEK_SERI))) {
    Yaz "Not: Python $($hedef.EnYeniKararli) yayımlandı; bu skill şimdilik $DESTEK_SERI serisini kuruyor (kütüphaneler o seriye göre doğrulandı)."
}
$hedefV = SurumNesnesi $hedef.Surum
$seri = @(SeriKurulumlari)
$tam = @($seri | Where-Object { (SurumNesnesi $_.Surum) -ge $hedefV }) | Select-Object -First 1
if ($tam) {
    Yaz "Son sürüm kurulu, o kullanılacak: $($tam.Surum) — $($tam.Yol)"
    Bitir 'MEVCUT' $tam 'zaten kurulu' ''
}
$eski = $seri | Select-Object -First 1
if ($YalnizBul) {
    if ($eski) { Bitir 'ESKI_YAMA' $eski 'zaten kurulu' "son sürüm $($hedef.Surum), kurulu $($eski.Surum) (yalnız bakıldı)" }
    Bitir 'YOK' $null '' "Python $DESTEK_SERI serisi kurulu değil (yalnız bakıldı)"
}

if ($eski) {
    if ((Kapsam $eski.Yol) -eq 'kullanıcı') {
        # Kullanıcı kurulumu: yönetici yetkisi olmadan son yamaya yükseltilebilir.
        Yaz "Python $($eski.Surum) kurulu ama son sürüm değil; $($hedef.Surum) sürümüne güncelleniyor."
        $s = PyorgKur
        $seri = Yeniden
        $tam = @($seri | Where-Object { (SurumNesnesi $_.Surum) -ge $hedefV }) | Select-Object -First 1
        if ($tam) {
            $denemeler.Add([ordered]@{ yol = 'python.org (güncelleme)'; sonuc = 'başarılı'; ayrinti = '' })
            Yaz "Güncellendi: Python $($tam.Surum) — $($tam.Yol)"
            Bitir 'KURULDU' $tam 'python.org resmi kurulum ile güncelleme (kullanıcı kapsamı)' ''
        }
        $denemeler.Add([ordered]@{ yol = 'python.org (güncelleme)'; sonuc = 'başarısız'; ayrinti = $s.Neden })
        Yaz "Güncellenemedi; kurulu $($eski.Surum) ile devam ediliyor."
        Bitir 'ESKI_YAMA' $eski 'zaten kurulu' "son sürüm $($hedef.Surum) kurulamadı: $($s.Neden)"
    }
    # Makine geneli / Store kurulumu yönetici yetkisi olmadan güncellenemez.
    Yaz "Python $($eski.Surum) $(Kapsam $eski.Yol) kurulu; son sürüme ($($hedef.Surum)) güncellemek yönetici yetkisi ister. Bu sürümle devam ediliyor, IT'ye bildirilecek."
    Bitir 'ESKI_YAMA' $eski 'zaten kurulu' "$(Kapsam $eski.Yol) kurulum; son sürüme güncelleme IT'de (hedef $($hedef.Surum))"
}

Yaz "Python $DESTEK_SERI kurulu değil; son sürüm ($($hedef.Surum)) kullanıcı alanınıza kurulacak (yönetici yetkisi gerekmez)."

# 1) winget, kullanıcı kapsamı
$wg = Get-Command winget -ErrorAction SilentlyContinue
if ($wg) {
    Yaz "Python winget ile kullanıcı alanına kuruluyor (birkaç dakika sürebilir)..."
    $r = Calistir $wg.Source "install --id Python.Python.$DESTEK_SERI --exact --scope user --silent --disable-interactivity --accept-package-agreements --accept-source-agreements" 900000
    $seri = Yeniden
    $tam = @($seri | Where-Object { (SurumNesnesi $_.Surum) -ge $hedefV }) | Select-Object -First 1
    if ($tam) {
        $denemeler.Add([ordered]@{ yol = 'winget'; sonuc = 'başarılı'; ayrinti = '' })
        Yaz "Kuruldu: Python $($tam.Surum) — $($tam.Yol)"
        Bitir 'KURULDU' $tam 'winget (kullanıcı kapsamı)' ''
    }
    $wgKurulan = $seri | Select-Object -First 1
    if ($wgKurulan) {
        # winget'in kataloğu python.org'un gerisinde kalabilir: kurduğunu son yamaya yükselt.
        $denemeler.Add([ordered]@{ yol = 'winget'; sonuc = "kurdu ama son yama değil ($($wgKurulan.Surum))"; ayrinti = '' })
        Yaz "winget $($wgKurulan.Surum) kurdu; son yamaya ($($hedef.Surum)) python.org ile yükseltiliyor."
        $s = PyorgKur
        $seri = Yeniden
        $tam = @($seri | Where-Object { (SurumNesnesi $_.Surum) -ge $hedefV }) | Select-Object -First 1
        if ($tam) {
            $denemeler.Add([ordered]@{ yol = 'python.org (güncelleme)'; sonuc = 'başarılı'; ayrinti = '' })
            Bitir 'KURULDU' $tam 'winget + python.org güncelleme (kullanıcı kapsamı)' ''
        }
        $denemeler.Add([ordered]@{ yol = 'python.org (güncelleme)'; sonuc = 'başarısız'; ayrinti = $s.Neden })
        Bitir 'ESKI_YAMA' ($seri | Select-Object -First 1) 'winget (kullanıcı kapsamı)' "son yamaya yükseltilemedi: $($s.Neden)"
    }
    $denemeler.Add([ordered]@{ yol = 'winget'; sonuc = "başarısız (çıkış kodu $($r.Kod))"; ayrinti = (Kisalt "$($r.Cikti) $($r.Hata)") })
    Yaz "winget ile kurulamadı (çıkış kodu $($r.Kod)); python.org yoluna geçiliyor."
} else {
    $denemeler.Add([ordered]@{ yol = 'winget'; sonuc = 'yok'; ayrinti = 'winget bu bilgisayarda bulunamadı' })
    Yaz 'winget bulunamadı; python.org yoluna geçiliyor.'
}

# 2) python.org resmi kurulum dosyası
$s = PyorgKur
$seri = Yeniden
$tam = @($seri | Where-Object { (SurumNesnesi $_.Surum) -ge $hedefV }) | Select-Object -First 1
if ($tam) {
    $denemeler.Add([ordered]@{ yol = 'python.org'; sonuc = 'başarılı'; ayrinti = '' })
    Yaz "Kuruldu: Python $($tam.Surum) — $($tam.Yol)"
    Bitir 'KURULDU' $tam 'python.org resmi kurulum (kullanıcı kapsamı)' ''
}
$denemeler.Add([ordered]@{ yol = 'python.org'; sonuc = 'başarısız'; ayrinti = $s.Neden })

Yaz 'Python kurulamadı. IT desteği gerekiyor.'
Bitir 'BASARISIZ' $null '' "Python $($hedef.Surum) ne winget ne python.org yoluyla kullanıcı alanına kurulabildi"
