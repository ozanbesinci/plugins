# Shared Windows PowerShell 5.1 primitives. Importing this file has no persistent side effects.
Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = New-Object Text.UTF8Encoding $false } catch {}

function Read-Field($Object, [string]$Name, $Default = $null) {
    if ($null -eq $Object) { return $Default }
    if ($Object -is [Collections.IDictionary]) { if ($Object.Contains($Name)) { return ,$Object[$Name] }; return $Default }
    $p = $Object.PSObject.Properties[$Name]
    if ($p) { return ,$p.Value }
    return $Default
}
function Assert-SupportedPlatform {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'Yalnız Windows desteklenir.' }
    if (-not [Environment]::Is64BitOperatingSystem -or -not [Environment]::Is64BitProcess) { throw '64-bit Windows ve 64-bit Windows PowerShell gerekli.' }
    $arch = [string]$env:PROCESSOR_ARCHITECTURE
    if ($arch -ne 'AMD64') { throw "Bu sürüm yalnız Windows amd64 için doğrulandı; mimari: $arch" }
}
function Hide-Secrets([string]$Text) {
    $v = [regex]::Replace($Text, '(?i)\b(https?://)[^\s/]+@', '$1***@')
    return [regex]::Replace($v, '(?i)([?&](?:token|access_token|api_key)=)[^&\s]+', '$1***')
}
function Quote-NativeArgument([string]$Argument) {
    $escaped = [regex]::Replace($Argument, '(\\*)"', '$1$1\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '$1$1')
    return '"' + $escaped + '"'
}
function Invoke-Native([string]$Exe, [string[]]$Arguments, [int]$TimeoutSeconds = 120, [hashtable]$Environment = @{}) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $Exe
    $info.Arguments = (@($Arguments | ForEach-Object { Quote-NativeArgument $_ }) -join ' ')
    $info.UseShellExecute = $false; $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true; $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = New-Object Text.UTF8Encoding $false
    $info.StandardErrorEncoding = New-Object Text.UTF8Encoding $false
    $info.WorkingDirectory=$env:TEMP
    $info.EnvironmentVariables['COREPACK_ENABLE_NETWORK']='0'
    $info.EnvironmentVariables['npm_config_manage_package_manager_versions']='false'
    $info.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
    $info.EnvironmentVariables['PYTHONDONTWRITEBYTECODE'] = '1'
    foreach ($key in $Environment.Keys) { $info.EnvironmentVariables[$key] = [string]$Environment[$key] }
    $process = [Diagnostics.Process]::Start($info)
    try {
        $stdout = $process.StandardOutput.ReadToEndAsync(); $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            # Only terminate the process tree started by this invocation, never arbitrary applications.
            if (-not $process.HasExited) {
                & "$env:SystemRoot\System32\taskkill.exe" /PID $process.Id /T /F 2>$null | Out-Null
                if (-not $process.WaitForExit(5000)) { $process.Kill() }
            }
            throw "Alt süreç zaman aşımı: $([IO.Path]::GetFileName($Exe)); kurulum durumu yeniden kontrol edilmeli."
        }
        if(-not $stdout.Wait(5000) -or -not $stderr.Wait(5000)){throw 'Alt süreç çıktı akışı kapanmadı; işlem durumu incelenmeli.'}
        return [pscustomobject]@{ ExitCode=$process.ExitCode; Output=$stdout.Result; Error=$stderr.Result }
    } finally { $process.Dispose() }
}
function Invoke-Json([string]$Exe, [string[]]$Arguments, [int]$TimeoutSeconds = 120) {
    $r = Invoke-Native $Exe $Arguments $TimeoutSeconds
    $lines = @($r.Output -split '\r?\n' | Where-Object { $_.StartsWith('@@SONUC ') })
    if (-not $lines.Count) { $lines = @($r.Output -split '\r?\n' | Where-Object { $_.Trim().StartsWith('{') }) }
    if (-not $lines.Count) { $detail=Hide-Secrets ($r.Error + $r.Output); throw ('Sonuç kaydı yok. ' + $detail.Substring(0, [Math]::Min(600, $detail.Length))) }
    $line = [string]$lines[-1]; if ($line.StartsWith('@@SONUC ')) { $line = $line.Substring(8) }
    $value = $line | ConvertFrom-Json
    if ($null -eq $value -or $value -isnot [pscustomobject]) { throw 'Geçerli sonuç nesnesi yok.' }
    if ($r.ExitCode -ne 0) {
        $value | Add-Member -NotePropertyName process_exit_code -NotePropertyValue $r.ExitCode -Force
        $value | Add-Member -NotePropertyName ozet -NotePropertyValue 'ENGEL' -Force
    }
    return $value
}
function File-Sha256([string]$Path) {
    $stream = [IO.File]::OpenRead($Path); $h = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($h.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $h.Dispose(); $stream.Dispose() }
}
function Text-Sha256([string]$Text) {
    $h = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($h.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text))).Replace('-','').ToLowerInvariant() }
    finally { $h.Dispose() }
}
function Assert-PlainPath([string]$Path) {
    $p = [IO.Path]::GetFullPath($Path)
    while ($p) {
        if (Test-Path -LiteralPath $p) {
            $item = Get-Item -LiteralPath $p -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Bağlantı/reparse point yolu reddedildi: $p" }
        }
        $parent = [IO.Path]::GetDirectoryName($p)
        if ($parent -eq $p) { break }; $p = $parent
    }
}
function Write-AtomicJson([string]$Path, $Value) {
    Assert-PlainPath $Path
    $parent = Split-Path $Path -Parent
    [void][IO.Directory]::CreateDirectory($parent)
    $temp = Join-Path $parent ('.write-' + [guid]::NewGuid().ToString('N'))
    try {
        $data = [Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 30))
        $s = New-Object IO.FileStream($temp, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $s.Write($data,0,$data.Length); $s.Flush($true) } finally { $s.Dispose() }
        if ([IO.File]::Exists($Path)) { [IO.File]::Replace($temp,$Path,[System.Management.Automation.Language.NullString]::Value) } else { [IO.File]::Move($temp,$Path) }
    } finally { if ([IO.File]::Exists($temp)) { [IO.File]::Delete($temp) } }
}
function Assert-TrustedUri([string]$Uri) {
    $u = [uri]$Uri
    $hosts = @('www.python.org','nodejs.org','registry.npmjs.org','pypi.org','files.pythonhosted.org',
        'api.github.com','github.com','release-assets.githubusercontent.com','objects.githubusercontent.com',
        'marketplace.visualstudio.com','community-extensions.duckdb.org')
    if ($u.Scheme -ne 'https' -or $u.UserInfo -or -not ($u.IsDefaultPort -or $u.Port -eq 443) -or
        ($u.Host -notin $hosts -and -not $u.Host.EndsWith('.gallerycdn.vsassets.io',[StringComparison]::OrdinalIgnoreCase))) {
        throw 'Güvenilmeyen indirme adresi.'
    }
}
function Get-RemoteJson([string]$Uri, [string]$Method = 'GET', [string]$Body = '') {
    Assert-TrustedUri $Uri
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    if([Net.WebRequest]::DefaultWebProxy){[Net.WebRequest]::DefaultWebProxy.Credentials=[Net.CredentialCache]::DefaultNetworkCredentials}
    $opts = @{Uri=$Uri;Method=$Method;MaximumRedirection=0;TimeoutSec=30;Headers=@{'User-Agent'='guncelleyici'};UseBasicParsing=$true;ErrorAction='Stop'}
    if ($Body) { $opts.Body=$Body; $opts.ContentType='application/json'; $opts.Headers.Accept='application/json;api-version=7.2-preview.1' }
    return Invoke-RestMethod @opts
}
function Download-VerifiedSource([string]$Uri, [string]$Path, [long]$Limit = 268435456) {
    Assert-PlainPath $Path
    for ($redirect = 0; $redirect -lt 6; $redirect++) {
        Assert-TrustedUri $Uri
        $req = [Net.HttpWebRequest]::Create($Uri); $req.AllowAutoRedirect=$false
        $req.Timeout=60000; $req.ReadWriteTimeout=60000; $req.UserAgent='guncelleyici'
        if($req.Proxy){$req.Proxy.Credentials=[Net.CredentialCache]::DefaultNetworkCredentials}
        $response = $req.GetResponse()
        try {
            $code = [int]$response.StatusCode
            if ($code -in 301,302,303,307,308) { $Uri = (New-Object Uri([uri]$Uri,$response.Headers['Location'])).AbsoluteUri; continue }
            if ($code -ne 200 -or $response.ContentLength -gt $Limit) { throw 'İndirme HTTP/boyut kontrolü başarısız.' }
            $input = $response.GetResponseStream(); $output = [IO.File]::Open($Path,[IO.FileMode]::CreateNew)
            $clock=[Diagnostics.Stopwatch]::StartNew()
            try {
                $buffer = New-Object byte[] 65536; [long]$total=0
                while (($count=$input.Read($buffer,0,$buffer.Length)) -gt 0) {
                    $total += $count; if($clock.Elapsed.TotalSeconds -gt 600){throw 'İndirme toplam süre sınırı aşıldı.'}; if ($total -gt $Limit) { throw 'İndirme boyut sınırı aşıldı.' }
                    $output.Write($buffer,0,$count)
                }
                $output.Flush($true)
            } finally { $input.Dispose(); $output.Dispose() }
            return
        } finally { $response.Dispose() }
    }
    throw 'İndirme yönlendirme sınırı aşıldı.'
}
function Read-Target([string]$Key, [string]$Path, [string]$ExpectedSha) {
    if (-not $Path -or $ExpectedSha -notmatch '^[a-f0-9]{64}$') { throw 'Onaylanan hedef dosyası ve SHA-256 gerekli; önce sohbet taramasını kullanın.' }
    Assert-PlainPath $Path
    if ((File-Sha256 $Path) -cne $ExpectedSha) { throw 'Hedef planı değişti; uygulanmadı.' }
    $record = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($record.key -ne $Key -or -not $record.target) { throw 'Plan bileşeni geçersiz.' }
    if (-not $env:GUNCELLEYICI_RUN_TOKEN -or (Read-Field $record 'run_token') -cne $env:GUNCELLEYICI_RUN_TOKEN) { throw 'Onayli sohbet uygulama islemi disinda kurulum baslatilamaz.' }
    return $record.target
}
function Stable-Version([string]$Text) {
    if ($Text -notmatch '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$') { throw "Kararlı sürüm biçimi geçersiz: $Text" }
    return [version]$Text
}
function Get-PathFolders {
    $out = @()
    foreach ($scope in 'Machine','User') {
        foreach ($part in @([Environment]::GetEnvironmentVariable('Path',$scope) -split ';')) {
            $p = [Environment]::ExpandEnvironmentVariables($part.Trim()).TrimEnd('\')
            if ($p -and $out -notcontains $p) { $out += $p }
        }
    }
    return $out
}
function Add-UserPath([string]$Folder) {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment',$true)
    try {
        $raw = [string]$key.GetValue('Path','',[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        $parts = @($raw -split ';' | Where-Object { $_.Trim() })
        $rest = @($parts | Where-Object { [Environment]::ExpandEnvironmentVariables($_).TrimEnd('\') -ine $Folder.TrimEnd('\') })
        $value=(@($Folder)+$rest)-join ';'
        if($value -cne $raw){$key.SetValue('Path',$value,[Microsoft.Win32.RegistryValueKind]::ExpandString)}
    } finally { $key.Close() }
}
function Test-UserScope([string]$Path) {
    return $Path.StartsWith($env:LOCALAPPDATA.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase) -or
        $Path.StartsWith($env:APPDATA.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)
}
function Assert-MaintenanceWindow {
    if ($env:GUNCELLEYICI_MAINTENANCE -ne 'confirmed') { throw 'Paylaşılan çalışma ortamı için bakım penceresi onayı gerekli.' }
    $busy = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { $_.Name -match '^(pythonw?|node|pnpm)\.exe$' })
    if ($busy.Count) { throw 'Python/Node iş yükü çalışıyor; otomatik kapatılmadı. İşler tamamlandıktan sonra yeniden deneyin.' }
}
function Emit-Result($Result, [int]$Code = 0) {
    $Result | Add-Member -NotePropertyName result_schema -NotePropertyValue 'guncelleyici-component/v1' -Force
    '@@SONUC ' + (Hide-Secrets ($Result | ConvertTo-Json -Compress -Depth 30))
    exit $Code
}

function Expand-SafeZip([string]$Archive, [string]$Destination, [string]$StripPrefix = '') {
    Assert-PlainPath $Destination
    [void][IO.Directory]::CreateDirectory($Destination)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip=[IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        if ($zip.Entries.Count -gt 10000) { throw 'Arşiv dosya sayısı sınırı aşıldı.' }
        $seen=New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        [long]$total=0
        $base=[IO.Path]::GetFullPath($Destination).TrimEnd('\')+'\'
        foreach ($entry in $zip.Entries) {
            $name=[string]$entry.FullName
            if ($StripPrefix) {
                if (-not $name.StartsWith($StripPrefix,[StringComparison]::Ordinal)) { throw 'Arşiv beklenen kök dışında.' }
                $name=$name.Substring($StripPrefix.Length)
                if (-not $name) { continue }
            }
            $isDir=$name.EndsWith('/')
            $clean=$name.TrimEnd('/')
            if (-not $clean -or $clean -match '[\\:\x00<>"|?*]' -or $clean.StartsWith('/')) { throw 'Güvensiz arşiv yolu.' }
            foreach($part in $clean.Split('/')) {
                if (-not $part -or $part -in '.', '..' -or $part.EndsWith('.') -or $part.EndsWith(' ') -or
                    $part -match '[\x00-\x1f]' -or $part.Split('.')[0] -match '^(?i:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])$') { throw 'Güvensiz/ayrılmış arşiv adı.' }
            }
            $normalized=$clean.Normalize([Text.NormalizationForm]::FormC)
            if (-not $seen.Add($normalized)) { throw 'Arşivde yinelenmiş/çakışan yol.' }
            $mode=(([int]$entry.ExternalAttributes -shr 16) -band 61440)
            if ($mode -notin @(0,32768,16384) -or ($mode -eq 16384 -and -not $isDir)) { throw 'Arşiv bağlantı/özel dosya içeriyor.' }
            $total+=$entry.Length
            if ($total -gt 536870912) { throw 'Arşiv açılmış boyut sınırı aşıldı.' }
            $path=[IO.Path]::GetFullPath((Join-Path $Destination ($clean -replace '/', '\')))
            if (-not $path.StartsWith($base,[StringComparison]::OrdinalIgnoreCase)) { throw 'Arşiv hedef kökü dışına çıkıyor.' }
            Assert-PlainPath $path
            if ($isDir) { [void][IO.Directory]::CreateDirectory($path);continue }
            [void][IO.Directory]::CreateDirectory((Split-Path $path -Parent))
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$path,$false)
        }
    } finally { $zip.Dispose() }
}
function Read-SafeXml([string]$Text) {
    $settings=New-Object Xml.XmlReaderSettings
    $settings.DtdProcessing=[Xml.DtdProcessing]::Prohibit;$settings.XmlResolver=$null
    $sr=New-Object IO.StringReader($Text)
    $reader=[Xml.XmlReader]::Create($sr,$settings)
    try { $doc=New-Object Xml.XmlDocument;$doc.XmlResolver=$null;$doc.Load($reader);return $doc }
    finally { $reader.Dispose();$sr.Dispose() }
}