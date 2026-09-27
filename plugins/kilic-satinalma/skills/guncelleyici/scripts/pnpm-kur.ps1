#requires -Version 5.1
<#
  program-guncelle — Aşama 6: pnpm
  Node.js aşamasından sonra çalışır. npm kayıt deposundaki latest etiketinin gösterdiği
  kararlı pnpm sürümünü kullanıcı alanına kurar; kurulu sürüm yeni veya eşitse dokunmaz.
  -YalnizBul hiçbir kurulum, PATH veya rapor yazımı yapmaz.
  Son satır: @@SONUC {json}
#>
param([switch]$YalnizBul, [string]$Rapor, [string]$NodeYolu)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch {}

$KURULUM_KLASORU = Join-Path $env:LOCALAPPDATA 'Programs\pnpm'
$KARANTINA = Join-Path $env:LOCALAPPDATA 'Programs\_karantina'
$NPM_REGISTRY = 'https://registry.npmjs.org/pnpm/latest'
$testler = New-Object System.Collections.Generic.List[object]
$ilkPnpm = @()
$hedefSurum = $null
$hedefKaynak = 'npm latest (kararlı)'
$node = $null
$skillSurum = '?'
try { $skillSurum = (Get-Content -LiteralPath (Join-Path (Split-Path $PSScriptRoot -Parent) 'VERSION') -TotalCount 1).Trim() } catch {}
$AMAC = 'Satınalma Departmanının kullandığı yapay zekâ projelerinde gerekli olan programların personel bilgisayarına yüklenmesini sağlar.'

function Yaz([string]$Metin) { Write-Host "  $Metin" }
function Surum([string]$Metin) {
    if ($Metin -match '^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$') { return [version]("$($Matches[1]).$($Matches[2]).$($Matches[3])") }
    return $null
}
function Kapsam([string]$Yol) {
    if ($Yol.StartsWith($env:LOCALAPPDATA.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase) -or
        $Yol.StartsWith($env:APPDATA.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { return 'kullanıcı' }
    return 'makine geneli'
}
function PathKlasorleri {
    $liste = @()
    foreach ($ad in 'Machine', 'User') {
        $ham = [Environment]::GetEnvironmentVariable('Path', $ad)
        foreach ($parca in @("$ham" -split ';')) {
            $d = [Environment]::ExpandEnvironmentVariables($parca.Trim()).TrimEnd('\')
            if ($d -and $liste -notcontains $d) { $liste += $d }
        }
    }
    return $liste
}
function Calistir([string]$Dosya, [string]$Argumanlar, [int]$SureMs, [string]$EkPath = '') {
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $Dosya
        $psi.Arguments = $Argumanlar
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $psi.WorkingDirectory = $env:TEMP
        $psi.EnvironmentVariables['COREPACK_ENABLE_NETWORK'] = '0'
        $psi.EnvironmentVariables['npm_config_manage_package_manager_versions'] = 'false'
        $path = @($EkPath, (Split-Path $node.Yol -Parent), ([Environment]::GetEnvironmentVariable('Path', 'Machine')), ([Environment]::GetEnvironmentVariable('Path', 'User'))) |
            Where-Object { $_ }
        $psi.EnvironmentVariables['Path'] = $path -join ';'
        $p = [System.Diagnostics.Process]::Start($psi)
        $o = $p.StandardOutput.ReadToEndAsync(); $e = $p.StandardError.ReadToEndAsync()
        if (-not $p.WaitForExit($SureMs)) {
            try { $p.Kill() } catch {}
            return [pscustomobject]@{ Kod = -1; Cikti = ''; Hata = 'zaman aşımı' }
        }
        return [pscustomobject]@{ Kod = $p.ExitCode; Cikti = $o.Result.Trim(); Hata = $e.Result.Trim() }
    } catch {
        return [pscustomobject]@{ Kod = -2; Cikti = ''; Hata = $_.Exception.Message }
    }
}
function PnpmDogrula([string]$Dosya) {
    if (-not (Test-Path -LiteralPath $Dosya)) { return $null }
    if ([IO.Path]::GetExtension($Dosya) -eq '.exe') { $r = Calistir $Dosya '--version' 30000 (Split-Path $Dosya -Parent) }
    else { $r = Calistir $env:ComSpec ("/d /c `"`"$Dosya`" --version`"") 30000 (Split-Path $Dosya -Parent) }
    if ($r.Kod -ne 0 -or $r.Cikti -notmatch '^(\d+\.\d+\.\d+)(?:[-+][\w.-]+)?$') { return $null }
    return [pscustomobject]@{ Surum = $r.Cikti; Yol = $Dosya }
}
function KullaniciPathEkle {
    $kullaniciPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $parcalar = @($kullaniciPath -split ';' | Where-Object { $_.Trim() })
    $kalanPath = @($parcalar | Where-Object { [Environment]::ExpandEnvironmentVariables($_).TrimEnd('\') -ne $KURULUM_KLASORU })
    $yeniPath = (@($KURULUM_KLASORU) + $kalanPath) -join ';'
    if ($yeniPath -ne $kullaniciPath) { [Environment]::SetEnvironmentVariable('Path', $yeniPath, 'User') }
}
function Israrla([scriptblock]$Is) {
    # Çalıştırılan yeni ikili kısa süreli tarama kilidi bırakabilir; aynı işlem en çok 15 sn bekler.
    for ($i = 1; ; $i++) {
        try { & $Is; return } catch { if ($i -ge 20) { throw }; Start-Sleep -Milliseconds 750 }
    }
}
function YeniPnpmDogrula([string]$Dosya) {
    Israrla {
        $bulunan = PnpmDogrula $Dosya
        if (-not $bulunan) { throw 'yeni pnpm çalıştırılamadı' }
        return $bulunan
    }
}
function Bitir([string]$Durum, $Etkin, [string]$Yontem, [string]$Neden, [string]$ItIsi) {
    $mevcutListe = New-Object System.Collections.Generic.List[string]
    foreach ($p in $ilkPnpm) { $mevcutListe.Add("$($p.Surum) — $($p.Yol)") }
    $ozet = switch ($Durum) {
        { $_ -in 'MEVCUT', 'KURULDU', 'GUNCELLENDI' } { 'GEÇTİ'; break }
        { $_ -in 'ESKI_SURUM', 'YOK', 'KONTROL_EDILEMEDI' } { 'UYARI'; break }
        default { 'ENGEL' }
    }
    if ($Durum -eq 'KONTROL_EDILEMEDI' -and -not $Etkin) { $ozet = 'ENGEL' }
    if ($ItIsi -and $ozet -eq 'GEÇTİ') { $ozet = 'UYARI' }
    $sonuc = [ordered]@{
        durum = $Durum; ozet = $ozet
        surum = $(if ($Etkin) { $Etkin.Surum } else { $null })
        pnpm = $(if ($Etkin) { $Etkin.Yol } else { $null })
        kapsam = $(if ($Etkin) { Kapsam $Etkin.Yol } else { '' })
        hedef_surum = $hedefSurum; hedef_kaynagi = $hedefKaynak
        mevcut_pnpmler = $mevcutListe.ToArray()
        yontem = $Yontem; neden = $Neden; it_isi = $ItIsi; testler = $testler.ToArray()
        bilgisayar = $env:COMPUTERNAME; zaman = (Get-Date).ToString('s')
    }
    $satirlar = @('', 'AŞAMA 6 — PNPM', '--------------',
        "[BİLGİ] Önceki pnpm: $(if ($ilkPnpm.Count) { $sonuc.mevcut_pnpmler -join '; ' } else { 'yoktu' })",
        "[BİLGİ] Hedef: $(if ($hedefSurum) { $hedefSurum } else { 'öğrenilemedi' }) ($hedefKaynak)",
        "[$ozet] Durum: $Durum$(if ($Etkin) { " — $($Etkin.Surum), $($Etkin.Yol)" })$(if ($Yontem) { "; $Yontem" })$(if ($Neden) { "; $Neden" })")
    foreach ($t in $testler) { $satirlar += "[$($t.durum)] $($t.ad): $($t.ayrinti)" }
    if ($ItIsi) { $satirlar += "IT'den gereken: $ItIsi" }
    if (-not $YalnizBul) {
        if ($Rapor -and (Test-Path -LiteralPath $Rapor)) {
            [IO.File]::AppendAllText($Rapor, (($satirlar -join "`r`n") + "`r`n"), (New-Object Text.UTF8Encoding $false))
            $sonuc['rapor'] = $Rapor
        } elseif ($Durum -eq 'BASARISIZ' -or $ItIsi) {
            $masaustu = [Environment]::GetFolderPath('Desktop')
            if (-not $masaustu -or -not (Test-Path -LiteralPath $masaustu)) { $masaustu = Join-Path $env:LOCALAPPDATA 'program-guncelle' }
            New-Item -ItemType Directory -Path $masaustu -Force | Out-Null
            $dosya = Join-Path $masaustu ("pnpm-kurulumu-{0}-{1}.txt" -f $env:COMPUTERNAME, (Get-Date).ToString('yyyyMMdd-HHmm'))
            @("GÜNCELLEYİCİ · sürüm $skillSurum — PNPM KURULUMU", $AMAC) + $satirlar | Out-File -LiteralPath $dosya -Encoding utf8
            $sonuc['rapor'] = $dosya
        }
    }
    $json = $sonuc | ConvertTo-Json -Compress -Depth 5
    Write-Output "@@SONUC $json"
    exit 0
}

Write-Host ''
Yaz "Güncelleyici · sürüm $skillSurum — pnpm"
Yaz $AMAC
Yaz 'Aşama 6 — pnpm'

# Aşama 5'in seçtiği Node.js'i kullan. Açık terminalin eski PATH'ine güvenme.
if ($NodeYolu) {
    if (-not (Test-Path -LiteralPath $NodeYolu -PathType Leaf)) { Bitir 'BASARISIZ' $null '' 'Aşama 5 tarafından seçilen Node.js yolu bulunamadı' 'Node.js kurulum yolu incelenmeli.' }
    $adayNode = $NodeYolu
}
else {
    $adayNode = @(PathKlasorleri | ForEach-Object { Join-Path $_ 'node.exe' } | Where-Object { Test-Path -LiteralPath $_ }) | Select-Object -First 1
}
if (-not $adayNode) { Bitir 'BASARISIZ' $null '' 'Node.js bulunamadı; pnpm kurulamaz' 'Node.js kullanıcı alanında çalışır durumda olmalı.' }
$node = [pscustomobject]@{ Yol = $adayNode }
$nodeV = Calistir $node.Yol '-p "process.versions.node"' 15000
if ($nodeV.Kod -ne 0 -or -not (Surum $nodeV.Cikti)) { Bitir 'BASARISIZ' $null '' 'Node.js çalışmadı; pnpm kurulamaz' 'Node.js çalıştırma engeli incelenmeli.' }
$npmCli = Join-Path (Split-Path $node.Yol -Parent) 'node_modules\npm\bin\npm-cli.js'

$adaylar = @()
foreach ($klasor in @(@(PathKlasorleri) + @($KURULUM_KLASORU) | Select-Object -Unique)) {
    foreach ($ad in 'pnpm.exe', 'pnpm.cmd') {
        $p = PnpmDogrula (Join-Path $klasor $ad)
        if ($p) { $adaylar += $p; break }
    }
}
$ilkPnpm = @($adaylar)
$etkin = $adaylar | Select-Object -First 1
if ($etkin) { Yaz "pnpm yüklü: $($etkin.Surum) — $($etkin.Yol)" } else { Yaz 'pnpm yüklü değil.' }

try {
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
    try { [Net.WebRequest]::DefaultWebProxy.Credentials = [Net.CredentialCache]::DefaultNetworkCredentials } catch {}
    $meta = Invoke-RestMethod -Uri $NPM_REGISTRY -TimeoutSec 30 -UseBasicParsing
    if ($meta.name -ne 'pnpm' -or $meta.version -notmatch '^\d+\.\d+\.\d+$' -or
        $meta.dist.integrity -notmatch '^sha512-[A-Za-z0-9+/=]+$') { throw 'npm kayıt verisi doğrulanamadı' }
    $hedefSurum = [string]$meta.version
    $engine = [string]$meta.engines.node
    $semver = Join-Path (Split-Path $node.Yol -Parent) 'node_modules\npm\node_modules\semver'
    if (-not $engine -or $engine -notmatch '^[0-9.xX*<>=|~^+ -]+$' -or -not (Test-Path -LiteralPath $semver)) { throw 'Node.js uyumluluk şartı doğrulanamadı' }
    $uyum = Calistir $node.Yol ("-e `"process.stdout.write(String(require(process.argv[1]).satisfies(process.argv[2],process.argv[3])))`" `"$semver`" `"$($nodeV.Cikti)`" `"$engine`"") 15000
    if ($uyum.Kod -ne 0 -or $uyum.Cikti -notin 'true', 'false') { throw 'Node.js uyumluluğu ölçülemedi' }
    if ($uyum.Cikti -eq 'false') { Bitir 'BASARISIZ' $etkin '' "pnpm $hedefSurum için Node.js şartı: $engine" "Node.js $($nodeV.Cikti), pnpm $hedefSurum şartını karşılamıyor ($engine)." }
} catch {
    Bitir 'KONTROL_EDILEMEDI' $etkin '' 'npm kayıt deposundaki kararlı sürüm doğrulanamadı; kurulum yapılmadı' 'registry.npmjs.org HTTPS erişimi veya kayıt yanıtı incelenmeli.'
}
Yaz "Son kararlı sürüm: pnpm $hedefSurum (npm latest)."

if ($etkin -and ((Surum $etkin.Surum) -gt (Surum $hedefSurum) -or $etkin.Surum -eq $hedefSurum)) {
    if (-not $YalnizBul -and (Split-Path $etkin.Yol -Parent) -eq $KURULUM_KLASORU) {
        try { KullaniciPathEkle } catch { Bitir 'MEVCUT' $etkin 'kurulu ve çalışıyor' 'kullanıcı PATH kaydı güncellenemedi' 'pnpm kullanıcı PATH kaydı incelenmeli.' }
    }
    $testler.Add([ordered]@{ ad = 'pnpm sürüm testi'; durum = 'GEÇTİ'; ayrinti = $etkin.Surum })
    Bitir 'MEVCUT' $etkin 'zaten kurulu' '' ''
}
if ($YalnizBul) {
    if ($etkin) { Bitir 'ESKI_SURUM' $etkin 'yalnız bakıldı' 'kararlı sürüm daha yeni' '' }
    Bitir 'YOK' $null 'yalnız bakıldı' 'pnpm kurulu değil' ''
}
if ($etkin -and (Kapsam $etkin.Yol) -eq 'makine geneli') {
    Bitir 'ESKI_SURUM' $etkin 'zaten kurulu' 'makine PATH önceliğindeki pnpm kullanıcı kurulumu ile güncellenemez' "Makine geneline kurulu pnpm $($etkin.Surum), $hedefSurum sürümüne güncellenmeli."
}
if (-not (Test-Path -LiteralPath $npmCli)) { Bitir 'BASARISIZ' $etkin '' 'Seçilen Node.js yanında npm bulunamadı' 'Node.js kurulumundaki npm eksik veya engelli.' }

$programs = Split-Path $KURULUM_KLASORU -Parent
$hazirlik = Join-Path $programs ('pnpm.yeni-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
$eski = $null
$yerlestirildi = $false
try {
    New-Item -ItemType Directory -Path $programs -Force | Out-Null
    Yaz "pnpm $hedefSurum npm üzerinden kullanıcı klasörüne kuruluyor (birkaç dakika sürebilir)..."
    $npmArgumanlar = "`"$npmCli`" install --global --prefix `"$hazirlik`" pnpm@$hedefSurum --registry=https://registry.npmjs.org --engine-strict --no-audit --no-fund"
    $kur = Calistir $node.Yol $npmArgumanlar 600000
    if ($kur.Kod -ne 0) { throw "npm kurulumu başarısız (çıkış kodu $($kur.Kod))" }
    $yeni = YeniPnpmDogrula (Join-Path $hazirlik 'pnpm.cmd')
    if (-not $yeni -or $yeni.Surum -ne $hedefSurum) { throw 'kurulan pnpm çalışmadı veya sürümü uyuşmadı' }
    if (Test-Path -LiteralPath $KURULUM_KLASORU) {
        New-Item -ItemType Directory -Path $KARANTINA -Force | Out-Null
        $eski = Join-Path $KARANTINA ('pnpm-eski-' + (Get-Date).ToString('yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 4))
        Israrla { Move-Item -LiteralPath $KURULUM_KLASORU -Destination $eski -ErrorAction Stop }
    }
    try { Israrla { Rename-Item -LiteralPath $hazirlik -NewName (Split-Path $KURULUM_KLASORU -Leaf) -ErrorAction Stop } }
    catch {
        $tasimaHatasi = $_.Exception.Message
        if ($eski) { Israrla { Move-Item -LiteralPath $eski -Destination $KURULUM_KLASORU -ErrorAction Stop }; $eski = $null }
        throw "yeni pnpm yerine konamadı: $tasimaHatasi"
    }
    $yerlestirildi = $true
    $son = YeniPnpmDogrula (Join-Path $KURULUM_KLASORU 'pnpm.cmd')
    if (-not $son -or $son.Surum -ne $hedefSurum) { throw 'pnpm son konumunda çalışmadı' }
    KullaniciPathEkle
    $testler.Add([ordered]@{ ad = 'pnpm sürüm testi'; durum = 'GEÇTİ'; ayrinti = $son.Surum })
    Yaz "pnpm $($son.Surum) hazır; yeni açılan pencerelerde kullanılabilir."
    Bitir $(if ($etkin) { 'GUNCELLENDI' } else { 'KURULDU' }) $son 'npm kayıt deposu; bütünlük npm tarafından doğrulandı; kullanıcı kapsamı' '' ''
} catch {
    $neden = $_.Exception.Message
    $kurulmus = PnpmDogrula (Join-Path $KURULUM_KLASORU 'pnpm.cmd')
    if ($kurulmus -and $kurulmus.Surum -eq $hedefSurum) {
        Bitir $(if ($etkin) { 'GUNCELLENDI' } else { 'KURULDU' }) $kurulmus 'kuruldu ve çalıştı' "kullanıcı PATH'i güncellenememiş olabilir: $neden" 'pnpm komutunun yeni pencerelerde bulunması için kullanıcı PATH kaydı incelenmeli.'
    }
    if ($yerlestirildi) {
        try {
            New-Item -ItemType Directory -Path $KARANTINA -Force | Out-Null
            $bozuk = Join-Path $KARANTINA ('pnpm-basarisiz-' + [guid]::NewGuid().ToString('N'))
            Israrla { Move-Item -LiteralPath $KURULUM_KLASORU -Destination $bozuk -ErrorAction Stop }
            if ($eski) { Israrla { Move-Item -LiteralPath $eski -Destination $KURULUM_KLASORU -ErrorAction Stop }; $eski = $null }
        } catch { $neden += "; geri dönüş tamamlanamadı, önceki klasör: $eski" }
    }
    $geri = if ($etkin) { PnpmDogrula $etkin.Yol }
    if ($geri) { Bitir 'ESKI_SURUM' $geri 'önceki kurulum doğrulandı' $neden '' }
    if ($eski) { $neden += "; önceki kurulum korunduğu klasör: $eski" }
    Bitir 'BASARISIZ' $null '' $neden 'registry.npmjs.org erişimi ve npm/pnpm çalıştırma izni incelenmeli.'
}
