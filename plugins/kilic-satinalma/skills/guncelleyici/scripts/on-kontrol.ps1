#requires -Version 5.1
<#
  Program Guncelle - On kontrol (salt okunur)
  Ozan Besinci / Satinalma Departmani

  Ne yapar : Personel bilgisayarinda uc kalemi olcer:
             1) Python'un (son surum) kullanici alanina kurulabilmesi
             2) Pakete gomulu Python kutuphanelerinin kurulabilmesi
             3) Excel'in otomasyonla arka planda acilip kapatilabilmesi
  Ne yapmaz: Hicbir sey KURMAZ, hicbir ayari DEGISTIRMEZ, guvenlik kontrollerini atlatmaya
             calismaz. Yalniz ayar/politika okur, Excel'i bir kez gorunmez acip kapatir ve
             birkac adrese erisilebiliyor mu diye bakar. Gecici test dosyasi %TEMP% altina
             yazilir ve sonunda silinir.
  Cikti    : Masaustunde on-kontrol-<BILGISAYAR>-<tarih>.txt
#>
param([switch]$Sessiz)   # -Sessiz: raporu Not Defteri'nde açma (skill çalıştırırken); KSK_ONKONTROL_SESSIZ=1 ile aynı

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch {}
# Git Bash farklı PowerShell sürümünün modül yolunu taşıyabilir; çalışan kabuğun modüllerini kullan.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -ErrorAction Stop
$Surum = '1.0.0'
$Baslangic = Get-Date
$Sonuclar = New-Object System.Collections.Generic.List[object]
$Aksiyonlar = New-Object System.Collections.Generic.List[object]

$B_ORTAM = 'Ortam'
$B_K1 = 'Kalem 1 - Python kurulumu'
$B_K2 = 'Kalem 2 - Kütüphane kurulumu'
$B_K3 = 'Kalem 3 - Excel otomasyonu'
$B_AG = 'Ağ erişimi'

function Ekle([string]$Bolum, [string]$Kontrol, [string]$Durum, [string]$Ayrinti) {
    $Sonuclar.Add([pscustomobject]@{ Bolum = $Bolum; Kontrol = $Kontrol; Durum = $Durum; Ayrinti = $Ayrinti })
    $renk = @{ 'GEÇTİ' = 'Green'; 'ENGEL' = 'Red'; 'UYARI' = 'Yellow'; 'BİLGİ' = 'Gray' }[$Durum]
    Write-Host ("  [{0,-5}] {1}: {2}" -f $Durum, $Kontrol, $Ayrinti) -ForegroundColor $renk
}

function Aksiyon([string]$Kalem, [string]$Metin) {
    foreach ($a in $Aksiyonlar) { if ($a.Kalem -eq $Kalem -and $a.Metin -eq $Metin) { return } }
    $Aksiyonlar.Add([pscustomobject]@{ Kalem = $Kalem; Metin = $Metin })
}

function Baslik([string]$Metin) { Write-Host "`n== $Metin ==" -ForegroundColor Cyan }

function RegDeger([string]$Yol, [string]$Ad) {
    try { return (Get-ItemProperty -LiteralPath $Yol -Name $Ad -ErrorAction Stop).$Ad } catch { return $null }
}

function Calistir([string]$Dosya, [string]$Argumanlar, [int]$SureMs = 15000) {
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $Dosya; $psi.Arguments = $Argumanlar; $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true; $psi.CreateNoWindow = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        $o = $p.StandardOutput.ReadToEndAsync(); $e = $p.StandardError.ReadToEndAsync()
        if (-not $p.WaitForExit($SureMs)) {
            try { $p.Kill() } catch {}
            return [pscustomobject]@{ Kod = -1; Cikti = ''; Hata = "zaman aşımı ($SureMs ms)" }
        }
        return [pscustomobject]@{ Kod = $p.ExitCode; Cikti = $o.Result.Trim(); Hata = $e.Result.Trim() }
    } catch {
        return [pscustomobject]@{ Kod = -2; Cikti = ''; Hata = $_.Exception.Message }
    }
}

Write-Host ""
Write-Host "  Güncelleyici — ön kontrol $Surum" -ForegroundColor Cyan
Write-Host "  Hiçbir şey kurulmaz, hiçbir ayar değişmez. Yaklaşık 1 dakika sürer." -ForegroundColor Cyan

# ---------------------------------------------------------------- Ortam
Baslik $B_ORTAM
$os = Get-CimInstance Win32_OperatingSystem
Ekle $B_ORTAM 'Bilgisayar / kullanıcı' 'BİLGİ' "$env:COMPUTERNAME / $env:USERDOMAIN\$env:USERNAME"
Ekle $B_ORTAM 'Windows' 'BİLGİ' "$($os.Caption) $($os.Version) ($($os.OSArchitecture))"

$kimlik = [Security.Principal.WindowsIdentity]::GetCurrent()
$yukseltilmis = (New-Object Security.Principal.WindowsPrincipal $kimlik).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$adminGrubu = [bool](whoami /groups /fo csv 2>$null | Where-Object { $_ -match 'S-1-5-32-544' })
Ekle $B_ORTAM 'Yönetici yetkisi' 'BİLGİ' ("yerel yönetici grubunda: {0}; bu oturum yükseltilmiş: {1}" -f $(if ($adminGrubu) { 'evet' } else { 'hayır' }), $(if ($yukseltilmis) { 'evet' } else { 'hayır' }))
if ($adminGrubu) {
    Ekle $B_ORTAM 'Temsil gücü' 'UYARI' 'Bu kullanıcı yönetici grubunda; tipik personel hesabını temsil etmeyebilir. Mümkünse yöneticisi olmayan bir personelde de çalıştırın.'
}

$dilModu = $ExecutionContext.SessionState.LanguageMode
if ($dilModu -eq 'FullLanguage') {
    Ekle $B_ORTAM 'PowerShell dil modu' 'BİLGİ' 'FullLanguage (kısıtsız)'
} else {
    Ekle $B_ORTAM 'PowerShell dil modu' 'UYARI' "$dilModu — makinede uygulama denetimi (WDAC/AppLocker) etkin görünüyor"
}

$epListe = (Get-ExecutionPolicy -List | ForEach-Object { "$($_.Scope)=$($_.ExecutionPolicy)" }) -join ', '
Ekle $B_ORTAM 'PowerShell çalıştırma politikası' 'BİLGİ' "$epListe (skill kurulum ve kontrol için PowerShell betikleri kullanır)"

try {
    $surucu = Get-PSDrive -Name ($env:SystemDrive.TrimEnd(':')) -ErrorAction Stop
    $bosGB = [math]::Round($surucu.Free / 1GB, 1)
    if ($bosGB -lt 2) { Ekle $B_ORTAM 'Boş disk' 'UYARI' "$env:SystemDrive $bosGB GB (Python + kütüphaneler için ~0,5 GB gerekir)" }
    else { Ekle $B_ORTAM 'Boş disk' 'BİLGİ' "$env:SystemDrive $bosGB GB" }
} catch {}

$codexKlasor = Test-Path (Join-Path $env:USERPROFILE '.codex')
$openaiPaket = @(Get-AppxPackage -Name '*OpenAI*' -ErrorAction SilentlyContinue | ForEach-Object { "$($_.Name) $($_.Version)" })
$codexMetin = "~\.codex klasörü: $(if ($codexKlasor) { 'var' } else { 'yok' })"
if ($openaiPaket.Count -gt 0) { $codexMetin += "; paket: $($openaiPaket -join ', ')" }
Ekle $B_ORTAM 'Codex / ChatGPT masaüstü' 'BİLGİ' $codexMetin

# ---------------------------------------------------------------- Kalem 1
Baslik $B_K1

# Mevcut Python
$adaylar = New-Object System.Collections.Generic.List[string]
foreach ($ad in 'python', 'python3', 'py') {
    Get-Command $ad -All -CommandType Application -ErrorAction SilentlyContinue | ForEach-Object { $adaylar.Add($_.Source) }
}
foreach ($kok in 'HKCU:\SOFTWARE\Python\PythonCore', 'HKLM:\SOFTWARE\Python\PythonCore', 'HKLM:\SOFTWARE\WOW6432Node\Python\PythonCore') {
    if (Test-Path $kok) {
        Get-ChildItem $kok -ErrorAction SilentlyContinue | ForEach-Object {
            $ipYol = Join-Path $_.PSPath 'InstallPath'
            $exe = RegDeger $ipYol 'ExecutablePath'
            if (-not $exe) { $d = RegDeger $ipYol '(default)'; if ($d) { $exe = Join-Path $d 'python.exe' } }
            if ($exe -and (Test-Path $exe)) { $adaylar.Add($exe) }
        }
    }
}
$gercekPython = $null
$storeKisayolu = $false
foreach ($yol in ($adaylar | Select-Object -Unique)) {
    if ($yol -like '*\WindowsApps\*') { $storeKisayolu = $true; continue }   # Store kısayolu: çalıştırılmaz
    $r = Calistir $yol '--version' 8000
    $metin = ("$($r.Cikti) $($r.Hata)").Trim()
    if ($r.Kod -eq 0 -and $metin -match 'Python (\d+\.\d+\.\d+)') {
        Ekle $B_K1 'Mevcut Python' 'BİLGİ' "$($Matches[1]) — $yol"
        if ((Split-Path $yol -Leaf) -ieq 'python.exe' -and ($null -eq $gercekPython -or $Matches[1] -like '3.14.*')) { $gercekPython = $yol }
    } else {
        Ekle $B_K1 'Mevcut Python' 'UYARI' "çalışmadı — $yol ($metin)"
        if ($r.Hata -match 'engellen|blocked|policy|ilke') {
            Aksiyon $B_K1 "Mevcut Python çalıştırılırken engellendi ($yol): uygulama denetimi kuralı gözden geçirilmeli."
        }
    }
}
if (-not $gercekPython) {
    $ek = ''
    if ($storeKisayolu) { $ek = ' (yalnız Microsoft Store kısayolu var; gerçek Python değil)' }
    Ekle $B_K1 'Mevcut Python' 'BİLGİ' "kurulu Python yok$ek — skill ilk kullanımda kurmaya çalışacak"
}

# Kurulum yolları: winget ve kullanıcı kapsamlı MSI
$wingetYolu = $false
$wg = Get-Command winget -ErrorAction SilentlyContinue
if ($wg) {
    $r = Calistir $wg.Source '--version' 15000
    if ($r.Kod -eq 0) { Ekle $B_K1 'winget' 'GEÇTİ' "var, sürüm $($r.Cikti)"; $wingetYolu = $true }
    else { Ekle $B_K1 'winget' 'UYARI' "var ama çalışmadı ($($r.Hata))" }
} else {
    Ekle $B_K1 'winget' 'UYARI' 'bulunamadı — skill python.org resmi kurulumuna düşer'
}
$aiPol = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\AppInstaller'
foreach ($ad in 'EnableAppInstaller', 'EnableDefaultSource', 'EnableWindowsPackageManagerCommandLineInterfaces') {
    $v = RegDeger $aiPol $ad
    if ($null -ne $v -and $v -eq 0) {
        Ekle $B_K1 "winget politikası $ad" 'ENGEL' 'politika ile kapalı'
        $wingetYolu = $false
    }
}
$storePol = RegDeger 'HKLM:\SOFTWARE\Policies\Microsoft\WindowsStore' 'RemoveWindowsStore'
if ($storePol -eq 1) { Ekle $B_K1 'Microsoft Store' 'BİLGİ' 'politika ile kapalı (skill Store kullanmıyor)' }

$msiYolu = $true
$insPol = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Installer'
$dui = RegDeger $insPol 'DisableUserInstalls'
$dmsi = RegDeger $insPol 'DisableMSI'
if ($dui -eq 1) {
    Ekle $B_K1 'Kullanıcı kapsamlı kurulum (DisableUserInstalls)' 'ENGEL' 'politika kullanıcı kapsamlı MSI kurulumunu engelliyor — Python kullanıcı alanına kurulamaz'
    $msiYolu = $false
} elseif ($null -ne $dmsi -and $dmsi -ge 1) {
    Ekle $B_K1 'Windows Installer (DisableMSI)' 'ENGEL' "DisableMSI=$dmsi — yönetilmeyen MSI kurulumu kapalı"
    $msiYolu = $false
} else {
    Ekle $B_K1 'Kullanıcı kapsamlı kurulum politikası' 'GEÇTİ' 'engelleyen Windows Installer politikası yok'
}
if (-not $msiYolu) {
    Aksiyon $B_K1 'Kullanıcı kapsamlı kurulum politikayla kapalı: Python IT tarafından merkezi dağıtılmalı (Intune/SCCM) ya da satınalma grubu için istisna tanımlanmalı.'
}

# Kullanıcı klasörüne yazabilme (kurulumun gideceği yer)
$yazmaTest = Join-Path $env:LOCALAPPDATA ('_ksk_onkontrol_' + [guid]::NewGuid().ToString('N').Substring(0, 8))
try {
    New-Item -ItemType Directory -Path $yazmaTest -ErrorAction Stop | Out-Null
    Remove-Item -LiteralPath $yazmaTest -Force -ErrorAction SilentlyContinue
    Ekle $B_K1 'Kullanıcı klasörüne yazma' 'GEÇTİ' "$env:LOCALAPPDATA yazılabilir"
} catch {
    Ekle $B_K1 'Kullanıcı klasörüne yazma' 'ENGEL' "$env:LOCALAPPDATA yazılamıyor: $($_.Exception.Message)"
}

# Uygulama denetimi: AppLocker
$alXml = $null; $alHata = $null
try { [xml]$alXml = Get-AppLockerPolicy -Effective -Xml -ErrorAction Stop } catch { $alHata = $_.Exception.Message }
$appIdSvc = Get-Service -Name AppIDSvc -ErrorAction SilentlyContinue
$appIdCalisiyor = ($appIdSvc -and $appIdSvc.Status -eq 'Running')
$alKoleksiyon = @{}
if ($alXml -and $alXml.AppLockerPolicy) {
    foreach ($rc in @($alXml.AppLockerPolicy.RuleCollection | Where-Object { $_ })) {
        $kurallar = @($rc.ChildNodes | Where-Object { $_.NodeType -eq 'Element' })
        $izinler = @($kurallar | Where-Object { $_.Action -eq 'Allow' })
        $pyYayinci = [bool]($izinler | Where-Object { $_.OuterXml -match 'PYTHON SOFTWARE FOUNDATION' })
        $kullaniciYolu = [bool]($izinler | Where-Object { $_.OuterXml -match 'Path="(%OSDRIVE%\\USERS|%LOCALAPPDATA%|%USERPROFILE%|\*)' })
        $alKoleksiyon[$rc.Type] = [pscustomobject]@{ Mod = $rc.EnforcementMode; Kural = $kurallar.Count; PyYayinci = $pyYayinci; KullaniciYolu = $kullaniciYolu }
    }
}
function AppLockerDegerlendir([string]$Bolum, [string]$Tur, [string]$Etiket, [string]$AksiyonMetni) {
    $k = $alKoleksiyon[$Tur]
    if (-not $k -or $k.Mod -eq 'NotConfigured' -or $k.Kural -eq 0) {
        Ekle $Bolum "AppLocker $Etiket" 'GEÇTİ' 'kural yok'
        return
    }
    $ozet = "mod=$($k.Mod), kural=$($k.Kural), Python yayıncı izni=$(if ($k.PyYayinci) {'var'} else {'yok'}), kullanıcı klasörü izni=$(if ($k.KullaniciYolu) {'var'} else {'yok'}), AppIDSvc=$(if ($appIdCalisiyor) {'çalışıyor'} else {'durmuş'})"
    if ($k.Mod -eq 'Enabled' -and $appIdCalisiyor -and -not ($k.PyYayinci -or $k.KullaniciYolu)) {
        Ekle $Bolum "AppLocker $Etiket" 'ENGEL' "uygulanıyor; Python için izin görünmüyor ($ozet)"
        Aksiyon $Bolum $AksiyonMetni
    } elseif ($k.Mod -eq 'Enabled' -and $appIdCalisiyor) {
        Ekle $Bolum "AppLocker $Etiket" 'UYARI' "uygulanıyor, izin kuralı var görünüyor — pilotta teyit ($ozet)"
    } elseif ($k.Mod -eq 'AuditOnly') {
        Ekle $Bolum "AppLocker $Etiket" 'UYARI' "yalnız denetim modunda; engellemez ama kayıt düşer ($ozet)"
    } else {
        Ekle $Bolum "AppLocker $Etiket" 'BİLGİ' $ozet
    }
}
if ($alHata) {
    Ekle $B_K1 'AppLocker' 'BİLGİ' "politika okunamadı ($alHata); AppIDSvc=$(if ($appIdCalisiyor) {'çalışıyor'} else {'durmuş/yok'})"
    if ($appIdCalisiyor) { Aksiyon $B_K1 'AppLocker hizmeti çalışıyor ama politika kullanıcıdan okunamadı: IT, Python için yayıncı kuralı olup olmadığını teyit etmeli.' }
} else {
    AppLockerDegerlendir $B_K1 'Exe' 'EXE' 'AppLocker EXE: "Python Software Foundation" yayıncı imzalı python.exe / pythonw.exe için izin kuralı.'
    AppLockerDegerlendir $B_K1 'Msi' 'MSI' 'AppLocker MSI: python.org resmi Python kurulum paketleri (PSF imzalı) için kullanıcı kapsamlı izin.'
    AppLockerDegerlendir $B_K2 'Dll' 'DLL' 'AppLocker DLL: kullanıcının Python klasöründeki kütüphane DLL/PYD dosyaları için izin (bir kısmı imzasız olabilir; yol veya hash kuralı gerekebilir).'
}

# Uygulama denetimi: WDAC / Smart App Control / SRP
try {
    $dg = Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard -ClassName Win32_DeviceGuard -ErrorAction Stop
    $um = $dg.UsermodeCodeIntegrityPolicyEnforcementStatus
    switch ($um) {
        2 { Ekle $B_K1 'WDAC (kullanıcı modu kod bütünlüğü)' 'ENGEL' 'uygulanıyor — Python ve kütüphaneler politikada izinli değilse çalışmaz'
            Aksiyon $B_K1 'WDAC politikası: Python (PSF imzası) ve kütüphane DLL''leri için izin.' }
        1 { Ekle $B_K1 'WDAC (kullanıcı modu kod bütünlüğü)' 'UYARI' 'denetim modunda; engellemez ama kayıt düşer' }
        default { Ekle $B_K1 'WDAC (kullanıcı modu kod bütünlüğü)' 'GEÇTİ' 'kapalı' }
    }
} catch {
    Ekle $B_K1 'WDAC' 'BİLGİ' "durum okunamadı ($($_.Exception.Message))"
}
$sac = RegDeger 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy' 'VerifiedAndReputablePolicyState'
if ($sac -eq 1) { Ekle $B_K1 'Akıllı Uygulama Denetimi' 'UYARI' 'açık — imzasız kütüphane DLL''leri engellenebilir' }
$srp = RegDeger 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Safer\CodeIdentifiers' 'DefaultLevel'
if ($null -ne $srp -and $srp -eq 0) {
    Ekle $B_K1 'Yazılım Kısıtlama İlkesi (SRP)' 'ENGEL' 'varsayılan: izin verilmeyen — kullanıcı klasöründen program çalışmaz'
    Aksiyon $B_K1 'Yazılım Kısıtlama İlkesi: kullanıcının Python klasörü için yol kuralı.'
}

# ---------------------------------------------------------------- Kalem 2
Baslik $B_K2
if ($gercekPython) {
    $r = Calistir $gercekPython '-m pip --version' 20000
    if ($r.Kod -eq 0) { Ekle $B_K2 'pip' 'GEÇTİ' $r.Cikti } else { Ekle $B_K2 'pip' 'UYARI' "çalışmadı ($($r.Hata))" }
    $kod = "import importlib.util as u;print(';'.join(n+'='+('var' if u.find_spec(n) else 'yok') for n in ['openpyxl','pypdf','pdfplumber','pypdfium2','win32com']))"
    $r = Calistir $gercekPython ("-c `"$kod`"") 20000
    if ($r.Kod -eq 0) { Ekle $B_K2 'Kütüphaneler (mevcut Python)' 'BİLGİ' $r.Cikti }
} else {
    Ekle $B_K2 'Kurulum denemesi' 'BİLGİ' 'Python olmadığı için kurulum denenemez; aşağıdakiler engel göstergeleridir. Kesin sonuç pilot kurulumda.'
}
Ekle $B_K2 'İnternet ihtiyacı' 'BİLGİ' 'kütüphaneler PyPI üzerinden indirilir; pypi.org ve files.pythonhosted.org için HTTPS erişimi gerekir'

try {
    $av = @(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction Stop | ForEach-Object { $_.displayName })
    if ($av.Count -gt 0) { Ekle $B_K2 'Antivirüs / EDR' 'BİLGİ' ($av -join ', ') }
} catch {}
$mpDurum = $null; $mpTercih = $null
try { $mpDurum = Get-MpComputerStatus -ErrorAction Stop } catch {}
try { $mpTercih = Get-MpPreference -ErrorAction Stop } catch {}
if ($mpDurum) { Ekle $B_K2 'Microsoft Defender' 'BİLGİ' "çalışma modu: $($mpDurum.AMRunningMode); gerçek zamanlı koruma: $($mpDurum.RealTimeProtectionEnabled)" }
if ($mpTercih) {
    $asrAd = @{
        '01443614-cd74-433a-b99e-2ecdc07bfc25' = 'Yaygınlık/yaş ölçütünü karşılamayan yürütülebilirleri engelle'
        'c1db55ab-c21a-4637-bb3f-a12568109d35' = 'Fidye yazılımına karşı gelişmiş koruma'
        'd4f940ab-401b-4efc-aadc-ad5f3c50688a' = 'Office uygulamalarının alt süreç oluşturmasını engelle'
        'd1e49aac-8f56-4280-b9ba-993a6d77406c' = 'PSExec/WMI kaynaklı süreç oluşturmayı engelle'
        '5beb7efe-fd9a-4556-801d-275e5ffc04cc' = 'Gizlenmiş betikleri engelle'
    }
    $asrMod = @{ 0 = 'kapalı'; 1 = 'engelle'; 2 = 'denetim'; 6 = 'uyar' }
    $ids = @($mpTercih.AttackSurfaceReductionRules_Ids)
    $acts = @($mpTercih.AttackSurfaceReductionRules_Actions)
    if ($ids.Count -gt 0 -and $ids[0] -and $ids[0] -notmatch 'N/A') {
        for ($i = 0; $i -lt $ids.Count; $i++) {
            $id = ([string]$ids[$i]).ToLower(); $m = [int]$acts[$i]
            $ad = $asrAd[$id]; if (-not $ad) { continue }
            $modMetin = $asrMod[$m]; if (-not $modMetin) { $modMetin = "$m" }
            if (($id -in @('01443614-cd74-433a-b99e-2ecdc07bfc25', 'c1db55ab-c21a-4637-bb3f-a12568109d35')) -and $m -eq 1) {
                Ekle $B_K2 "ASR kuralı: $ad" 'UYARI' "$modMetin — yeni kurulan Python/kütüphane dosyaları düşük yaygınlıkta sayılıp engellenebilir"
                Aksiyon $B_K2 "Defender ASR ($ad): kullanıcının Python klasörü için dışlama."
            } else {
                Ekle $B_K2 "ASR kuralı: $ad" 'BİLGİ' $modMetin
            }
        }
    } else {
        Ekle $B_K2 'Defender ASR kuralları' 'BİLGİ' 'kullanıcı yetkisiyle okunamadı veya tanımlı değil'
    }
    if ($mpTercih.EnableControlledFolderAccess -eq 1) {
        Ekle $B_K2 'Denetimli klasör erişimi' 'UYARI' 'açık — python.exe Belgeler/Masaüstü klasörlerine rapor yazamayabilir'
        Aksiyon $B_K2 'Denetimli klasör erişimi: python.exe izinli uygulamalara eklenmeli.'
    }
}
if ($dilModu -ne 'FullLanguage') {
    Aksiyon $B_K2 'PowerShell kısıtlı dil modunda: uygulama denetimi etkin; Python ve kütüphane DLL''leri politikada izinli olmalı.'
}

# ---------------------------------------------------------------- Kalem 3
Baslik $B_K3
$excelKayit = Test-Path 'Registry::HKEY_CLASSES_ROOT\Excel.Application'
if (-not $excelKayit) {
    Ekle $B_K3 'Masaüstü Excel' 'ENGEL' 'Excel otomasyon kaydı bulunamadı (masaüstü Excel kurulu değil veya yalnız web sürümü)'
    Aksiyon $B_K3 'Masaüstü Excel kurulu değil: Microsoft 365 masaüstü Excel kurulmalı.'
} else {
    $curVer = RegDeger 'Registry::HKEY_CLASSES_ROOT\Excel.Application\CurVer' '(default)'
    $c2r = 'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\Configuration'
    $plat = RegDeger $c2r 'Platform'; $vtr = RegDeger $c2r 'VersionToReport'
    Ekle $B_K3 'Masaüstü Excel' 'BİLGİ' "kayıtlı ($curVer); Office $vtr $plat"

    $pvPol = 'HKCU:\Software\Policies\Microsoft\Office\16.0\Excel\Security\ProtectedView'
    $pvMetin = @()
    foreach ($ad in 'DisableInternetFilesInPV', 'DisableAttachmentsInPV', 'DisableUnsafeLocationsInPV') {
        $v = RegDeger $pvPol $ad; if ($null -ne $v) { $pvMetin += "$ad=$v" }
    }
    if ($pvMetin.Count -gt 0) { Ekle $B_K3 'Korumalı görünüm politikası' 'BİLGİ' ($pvMetin -join ', ') }
    if (Test-Path 'HKCU:\Software\Policies\Microsoft\Office\16.0\Excel\Security\FileBlock') {
        Ekle $B_K3 'Dosya engelleme politikası' 'BİLGİ' 'tanımlı (xlsx dışındaki eski biçimler etkilenebilir)'
    }
    $tlKapali = RegDeger 'HKCU:\Software\Policies\Microsoft\Office\16.0\Excel\Security\Trusted Locations' 'AllLocationsDisabled'
    if ($tlKapali -eq 1) { Ekle $B_K3 'Güvenilen konumlar' 'UYARI' 'politika ile tümü kapalı' }

    if ($dilModu -ne 'FullLanguage') {
        Ekle $B_K3 'Excel otomasyon testi' 'UYARI' "PowerShell $dilModu modunda COM testi yapamıyor; bu Python'un yapamayacağı anlamına gelmez — pilotta Python ile denenmeli"
    } else {
        $tmp = Join-Path $env:TEMP ('ksk-onkontrol-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
        New-Item -ItemType Directory -Path $tmp -Force | Out-Null
        $once = @(Get-Process EXCEL -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
        $bizimPid = @()
        $xl = $null; $wb = $null; $ws = $null; $wb2 = $null
        $sw = [Diagnostics.Stopwatch]::StartNew()
        try {
            if (-not ('ProgramGuncelleExcelPencere' -as [type])) {
                Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class ProgramGuncelleExcelPencere { [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId); }' -ErrorAction Stop
            }
            $xl = New-Object -ComObject Excel.Application
            try {
                [uint32]$excelIslemId = 0
                [void][ProgramGuncelleExcelPencere]::GetWindowThreadProcessId([IntPtr]$xl.Hwnd, [ref]$excelIslemId)
                if (-not $excelIslemId -or $once -contains $excelIslemId) { throw 'Test için ayrı Excel süreci doğrulanamadı; mevcut Excel oturumu değiştirilmedi.' }
                $bizimPid = @($excelIslemId)
            } catch {
                [void][Runtime.InteropServices.Marshal]::ReleaseComObject($xl)
                $xl = $null
                throw
            }
            $xl.Visible = $false; $xl.DisplayAlerts = $false; $xl.ScreenUpdating = $false
            $xlSurum = $xl.Version
            $wb = $xl.Workbooks.Add()
            $ws = $wb.Worksheets.Item(1)
            $ws.Range('A1').Value2 = 21
            $ws.Range('A2').Formula = '=A1*2'
            $xl.CalculateFull()
            $deger = $ws.Range('A2').Value2
            $f = Join-Path $tmp 'deneme.xlsx'
            $wb.SaveAs($f, 51)
            $wb.Close($false)
            [void][Runtime.InteropServices.Marshal]::ReleaseComObject($ws); $ws = $null
            [void][Runtime.InteropServices.Marshal]::ReleaseComObject($wb); $wb = $null
            if ($deger -eq 42) {
                Ekle $B_K3 'Görünmez açma + hesaplama + kaydetme' 'GEÇTİ' "Excel $xlSurum görünmez açıldı, formül hesaplandı (=A1*2 → $deger), dosya kaydedildi"
            } else {
                Ekle $B_K3 'Görünmez açma + hesaplama' 'UYARI' "Excel açıldı ama hesap beklenen sonucu vermedi (A2=$deger)"
            }

            # Mailden/internetten gelmiş dosya: Windows'un "internetten indirildi" işaretiyle
            Set-Content -LiteralPath $f -Stream Zone.Identifier -Value "[ZoneTransfer]`r`nZoneId=3" -Encoding Ascii
            try {
                $wb2 = $xl.Workbooks.Open($f)
                $v2 = $wb2.Worksheets.Item(1).Range('A2').Value2
                $pv = $xl.ProtectedViewWindows.Count
                $wb2.Close($false)
                [void][Runtime.InteropServices.Marshal]::ReleaseComObject($wb2); $wb2 = $null
                Ekle $B_K3 'İnternetten gelmiş dosyayı açma' 'GEÇTİ' "otomasyonla açıldı (A2=$v2, korumalı görünüm penceresi: $pv)"
            } catch {
                Ekle $B_K3 'İnternetten gelmiş dosyayı açma' 'UYARI' "açılamadı: $($_.Exception.Message)"
                Aksiyon $B_K3 'Mailden gelen dosyalar otomasyonla açılamıyor: skill çalışma klasörü Excel''de Güvenilen Konum olarak tanımlanmalı.'
            }
        } catch {
            Ekle $B_K3 'Excel otomasyon testi' 'ENGEL' "Excel otomasyonla açılamadı: $($_.Exception.Message)"
            Aksiyon $B_K3 "Excel COM otomasyonu engelli ($($_.Exception.Message)): EDR/DCOM kuralı gözden geçirilmeli; python.exe'nin kullanıcı oturumunda Excel'i görünmez başlatmasına izin verilmeli."
        } finally {
            if ($wb2) { try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($wb2) } catch {} }
            if ($ws) { try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($ws) } catch {} }
            if ($wb) { try { $wb.Close($false) } catch {}; try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($wb) } catch {} }
            if ($xl) { try { $xl.Quit() } catch {}; try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($xl) } catch {} }
            $wb2 = $null; $ws = $null; $wb = $null; $xl = $null
            [GC]::Collect(); [GC]::WaitForPendingFinalizers(); [GC]::Collect(); [GC]::WaitForPendingFinalizers()
        }
        # Yalnız bu testin açtığı Excel'i bekle; kullanıcının açık Excel'ine dokunma
        $kalan = @()
        for ($i = 0; $i -lt 20; $i++) {
            $kalan = @($bizimPid | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
            if ($kalan.Count -eq 0) { break }
            Start-Sleep -Seconds 1
        }
        $sw.Stop()
        if ($bizimPid.Count -gt 0) {
            if ($kalan.Count -eq 0) {
                Ekle $B_K3 'Temiz kapanış' 'GEÇTİ' ("Excel kapandı, arkada süreç kalmadı; toplam {0:N1} sn" -f $sw.Elapsed.TotalSeconds)
            } else {
                $kalan | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
                Ekle $B_K3 'Temiz kapanış' 'UYARI' '20 sn içinde kapanmadı; testin açtığı Excel süreci sonlandırıldı (skill betiği bunu kendisi yönetecek, IT işi değil)'
            }
        }
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------- Ağ
Baslik $B_AG
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
try { [Net.WebRequest]::DefaultWebProxy.Credentials = [Net.CredentialCache]::DefaultNetworkCredentials } catch {}
$ieYol = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
$pxAcik = RegDeger $ieYol 'ProxyEnable'; $pxSunucu = RegDeger $ieYol 'ProxyServer'; $pac = RegDeger $ieYol 'AutoConfigURL'
$pxMetin = 'yok'
if ($pxAcik -eq 1 -and $pxSunucu) { $pxMetin = $pxSunucu }
if ($pac) { $pxMetin += "; PAC: $pac" }
Ekle $B_AG 'Proxy' 'BİLGİ' $pxMetin

$adresler = @(
    @{ U = 'https://api.github.com/';                      N = 'skill sürüm kontrolü';            Gerekli = $true;  K = $null }
    @{ U = 'https://github.com/';                          N = 'skill indirme / güncelleme';      Gerekli = $true;  K = $null }
    @{ U = 'https://objects.githubusercontent.com/';       N = 'GitHub sürüm dosyaları';          Gerekli = $true;  K = $null }
    @{ U = 'https://release-assets.githubusercontent.com/'; N = 'GitHub sürüm dosyaları';         Gerekli = $true;  K = $null }
    @{ U = 'https://www.python.org/';                      N = 'Python resmi kurulum dosyası';    Gerekli = $true;  K = $B_K1 }
    @{ U = 'https://cdn.winget.microsoft.com/cache/';      N = 'winget kaynağı';                  Gerekli = $false; K = $B_K1 }
    @{ U = 'https://pypi.org/';                            N = 'Python kütüphane kaynağı';       Gerekli = $true;  K = $B_K2 }
    @{ U = 'https://files.pythonhosted.org/';              N = 'Python kütüphane dosyaları';    Gerekli = $true;  K = $B_K2 }
    @{ U = 'https://nodejs.org/';                          N = 'Node.js kurulum kaynağı';       Gerekli = $true;  K = $null }
    @{ U = 'https://registry.npmjs.org/pnpm/latest';        N = 'pnpm kayıt deposu';             Gerekli = $true;  K = $null }
)
$pyOrgErisim = $true
foreach ($a in $adresler) {
    $durumMetin = $null; $erisim = $false
    try {
        $yanit = Invoke-WebRequest -Uri $a.U -Method Head -UseBasicParsing -TimeoutSec 8 -ErrorAction Stop
        $erisim = $true; $durumMetin = "HTTP $([int]$yanit.StatusCode)"
    } catch {
        $resp = $_.Exception.Response
        if ($resp) {
            $kod = [int]$resp.StatusCode
            if ($kod -eq 407) { $durumMetin = 'HTTP 407 — proxy kimlik doğrulaması istiyor' }
            else { $erisim = $true; $durumMetin = "HTTP $kod (sunucuya ulaşıldı)" }
        } else {
            $durumMetin = $_.Exception.Message
        }
    }
    $host_ = ([uri]$a.U).Host
    if ($erisim) { Ekle $B_AG "$host_" 'GEÇTİ' "$($a.N) — $durumMetin" }
    elseif ($a.Gerekli) { Ekle $B_AG "$host_" 'UYARI' "$($a.N) — erişilemedi: $durumMetin" }
    else { Ekle $B_AG "$host_" 'BİLGİ' "$($a.N) — erişilemedi: $durumMetin" }
    if (-not $erisim -and $a.U -like '*python.org*') { $pyOrgErisim = $false }
    if (-not $erisim -and $a.U -like '*winget*') { $wingetYolu = $false }
}
if (-not $gercekPython -and -not $wingetYolu -and -not $pyOrgErisim) {
    Aksiyon $B_K1 'Python kurulum dosyasına ne winget ne python.org üzerinden erişilebiliyor: Python IT tarafından merkezi dağıtılmalı ya da www.python.org erişimi açılmalı.'
}
if (-not $gercekPython -and $msiYolu -and -not $wingetYolu -and $pyOrgErisim) {
    Ekle $B_K1 'Kurulum yolu' 'BİLGİ' 'winget kullanılamıyor; skill python.org resmi kurulumuna düşecek'
}

# ---------------------------------------------------------------- Özet ve rapor
function EnKotu([string]$Bolum) {
    $d = @($Sonuclar | Where-Object { $_.Bolum -eq $Bolum } | ForEach-Object { $_.Durum })
    if ($d -contains 'ENGEL') { return 'ENGEL' }
    if ($d -contains 'UYARI') { return 'UYARI' }
    return 'GEÇTİ'
}
$yorum = @{
    'ENGEL' = 'engel var — IT işlemi gerekli'
    'UYARI' = 'engel görünmüyor ama teyit gerekli'
    'GEÇTİ' = 'politika engeli görünmüyor'
}

$sure = [math]::Round(((Get-Date) - $Baslangic).TotalSeconds)
$satirlar = New-Object System.Collections.Generic.List[string]
$satirlar.Add('GÜNCELLEYİCİ — ÖN KONTROL RAPORU')
$satirlar.Add("Ön kontrol sürümü : $Surum")
$satirlar.Add("Tarih             : $($Baslangic.ToString('dd.MM.yyyy HH:mm'))")
$satirlar.Add("Bilgisayar        : $env:COMPUTERNAME")
$satirlar.Add("Kullanıcı         : $env:USERDOMAIN\$env:USERNAME")
$satirlar.Add("Süre              : $sure sn")
$satirlar.Add('')
$satirlar.Add('ÖZET')
$satirlar.Add('----')
foreach ($b in $B_K1, $B_K2, $B_K3, $B_AG) {
    $e = EnKotu $b
    $satirlar.Add(("{0,-30} {1,-6} {2}" -f $b, $e, $yorum[$e]))
}
if ($adminGrubu) { $satirlar.Add('Dikkat: bu kullanıcı yerel yönetici grubunda; sonuç tipik personel hesabını temsil etmeyebilir.') }
$av2 = @($Sonuclar | Where-Object { $_.Kontrol -eq 'Antivirüs / EDR' } | ForEach-Object { $_.Ayrinti })
if ($av2.Count -gt 0) { $satirlar.Add("Güvenlik yazılımı: $($av2 -join ', ') — davranış tabanlı engeller politika okumasında görünmez.") }
$satirlar.Add('')
$satirlar.Add('IT''DEN GEREKEN İŞLEMLER (bu makinede ölçülenlere göre)')
$satirlar.Add('-------------------------------------------------------')
if ($Aksiyonlar.Count -eq 0) {
    $satirlar.Add('Politika düzeyinde engel görülmedi. IT''den onay ve EDR tarafında istisna gerekip gerekmediğinin teyidi yeterli; kesin sonuç pilot kurulumda.')
} else {
    foreach ($a in $Aksiyonlar) { $satirlar.Add("- [$($a.Kalem)] $($a.Metin)") }
}
foreach ($b in $B_ORTAM, $B_K1, $B_K2, $B_K3, $B_AG) {
    $satirlar.Add('')
    $satirlar.Add($b.ToUpper())
    $satirlar.Add(('-' * $b.Length))
    foreach ($s in ($Sonuclar | Where-Object { $_.Bolum -eq $b })) {
        $satirlar.Add(("[{0,-5}] {1}: {2}" -f $s.Durum, $s.Kontrol, $s.Ayrinti))
    }
}
$satirlar.Add('')
$satirlar.Add('Not: Bu rapor hiçbir şey kurmadan ve hiçbir ayarı değiştirmeden üretildi. Yazılan tek şey')
$satirlar.Add('%TEMP% altında bir test Excel dosyasıydı; test sonunda silindi. Politika okumaları kullanıcı')
$satirlar.Add('yetkisiyle yapıldığı için bazı kurallar görünmeyebilir; kesin sonuç pilot kurulumda alınır.')

$masaustu = [Environment]::GetFolderPath('Desktop')
if ($env:KSK_ONKONTROL_CIKTI) { $masaustu = $env:KSK_ONKONTROL_CIKTI }
if (-not $masaustu -or -not (Test-Path $masaustu)) { $masaustu = $PSScriptRoot }
$rapor = Join-Path $masaustu ("on-kontrol-{0}-{1}.txt" -f $env:COMPUTERNAME, $Baslangic.ToString('yyyyMMdd-HHmm'))
$satirlar | Out-File -FilePath $rapor -Encoding utf8

Write-Host "`n== Özet ==" -ForegroundColor Cyan
foreach ($b in $B_K1, $B_K2, $B_K3, $B_AG) {
    $e = EnKotu $b
    $renk = @{ 'GEÇTİ' = 'Green'; 'ENGEL' = 'Red'; 'UYARI' = 'Yellow' }[$e]
    Write-Host ("  {0,-30} {1,-6} {2}" -f $b, $e, $yorum[$e]) -ForegroundColor $renk
}
Write-Host "`n  Rapor kaydedildi: $rapor" -ForegroundColor Cyan
Write-Host '  Lütfen bu dosyayı Ozan Beşinci''ye gönderin.' -ForegroundColor Cyan
if (-not $Sessiz -and -not $env:KSK_ONKONTROL_SESSIZ) { try { Start-Process notepad.exe -ArgumentList "`"$rapor`"" } catch {} }
exit 0
