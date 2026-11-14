param(
    [Parameter(Mandatory=$true)][string]$DocxPath,
    [Parameter(Mandatory=$true)][string]$QaDirectory,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{32}$')][string]$Token
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

# This adapter never obtains an existing application using GetActiveObject.
# Documents.Open parameter contract: learn.microsoft.com/office/vba/api/word.documents.open
# AutomationSecurity: learn.microsoft.com/office/vba/api/word.application.automationsecurity
function Write-NewJson([string]$Path, $Value) {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($Value | ConvertTo-Json -Depth 5 -Compress))
    # Move a complete create-new receipt; the parent must never read a partial JSON.
    $temporary = $Path + '.writing'
    $stream = [IO.File]::Open($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
    [IO.File]::Move($temporary, $Path)
}

function New-Failure([string]$Stage, [Exception]$Exception) {
    $baseException = $Exception.GetBaseException()
    # Only type and HRESULT; never exception messages, paths or document text.
    return [ordered]@{protocol=1;token=$Token;status='FAILED';stage=$Stage;
        exception_type=$baseException.GetType().FullName;hresult=[int]$baseException.HResult}
}

function Get-Sha256([string]$Path) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $algorithm.Dispose(); $stream.Dispose() }
}

$word = $null
$document = $null
$blank = $null
$owned = $false
$success = $false
$wordProcess = $null
$result = $null
$securityChanged = $false
$optionsChanged = $false
$previousSecurity = $null
$previousLinks = $null
$previousNormalPrompt = $null
$failure = $null
$stage = 'INPUT'
$errorPath = [IO.Path]::Combine($QaDirectory, 'word-error.json')
try {
    $source = [IO.Path]::GetFullPath($DocxPath)
    $qaRoot = [IO.Path]::GetFullPath($QaDirectory)
    if ($source -ne $DocxPath -or $qaRoot -ne $QaDirectory -or [IO.Path]::GetExtension($source) -ine '.docx') {
        throw 'Absolute canonical DOCX and QA paths are required.'
    }
    if (-not [IO.File]::Exists($source) -or -not [IO.Directory]::Exists($qaRoot)) { throw 'Input or QA directory is unavailable.' }
    $pdfPath = [IO.Path]::Combine($qaRoot, 'document.pdf')
    $ownerPath = [IO.Path]::Combine($qaRoot, 'word-owner.json')
    $continuePath = [IO.Path]::Combine($qaRoot, 'word-continue.json')
    $receiptPath = [IO.Path]::Combine($qaRoot, 'word-render.json')
    $optionsPath = [IO.Path]::Combine($qaRoot, 'word-options.json')
    foreach ($path in @($pdfPath, $ownerPath, $continuePath, $receiptPath, $errorPath, $optionsPath)) {
        if ([IO.File]::Exists($path)) { throw 'Renderer targets must be new.' }
    }
    $stage = 'NATIVE_API'
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class DraftWordWindow {
    [DllImport("user32.dll", SetLastError=true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindowVisible(IntPtr hwnd);
}
'@
    $existingIds = @([Diagnostics.Process]::GetProcessesByName('WINWORD') | ForEach-Object { $_.Id })
    $started = [DateTime]::UtcNow
    $stage = 'ACTIVATE'
    $word = New-Object -ComObject Word.Application
    $stage = 'BLANK'
    # Word.Application has no HWND. Its Window object does. Create one unsaved,
    # invisible blank document before opening the source, with macros disabled.
    # If activation reused a user's process, only this new blank is closed below.
    $previousSecurity = $word.AutomationSecurity
    $word.AutomationSecurity = 3
    $securityChanged = $true
    $missing = [Type]::Missing
    if ($word.Visible) { throw 'A visible application cannot be used for ownership setup.' }
    # A document window is needed for HWND. The application itself remains hidden;
    # Visible=false here would create a windowless document in native Word.
    $blank = $word.Documents.Add($missing, $false, 0, $true)
    $stage = 'WINDOW'
    $window = [IntPtr]([int64]$blank.Windows.Item(1).Hwnd)
    [uint32]$wordProcessId = 0
    [void][DraftWordWindow]::GetWindowThreadProcessId($window, [ref]$wordProcessId)
    $stage = 'OWNERSHIP'
    if ($wordProcessId -eq 0 -or $existingIds -contains [int]$wordProcessId) {
        # In particular, do not Quit this COM object: it may be the user's Word.
        throw 'COM activation did not create a separately owned Word process.'
    }
    $wordProcess = [Diagnostics.Process]::GetProcessById([int]$wordProcessId)
    if ($wordProcess.ProcessName -ine 'WINWORD' -or $wordProcess.StartTime.ToUniversalTime() -lt $started) {
        throw 'Word creation identity could not be established.'
    }
    $created = $wordProcess.StartTime.ToFileTimeUtc()
    $exe = $wordProcess.MainModule.FileName
    $version = [string]$word.Version
    $owned = $true
    if ([DraftWordWindow]::IsWindowVisible($window)) { throw 'The owned Word window must remain hidden.' }
    $stage = 'OWNER_RECEIPT'
    Write-NewJson $ownerPath ([ordered]@{protocol=1;token=$Token;pid=[int]$wordProcessId;creation_filetime=$created;
        hwnd=$window.ToInt64();owned=$true;exe=$exe;version=$version})
    $stage = 'CONFIGURE'
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $previousLinks = $word.Options.UpdateLinksAtOpen
    $previousNormalPrompt = $word.Options.SaveNormalPrompt
    $optionsChanged = $true
    $word.Options.UpdateLinksAtOpen = $false
    $word.Options.SaveNormalPrompt = $false
    $stage = 'HANDSHAKE'
    # Parent binds a retained process HANDLE and establishes monitoring before opening.
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    while (-not [IO.File]::Exists($continuePath)) {
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Parent ownership handshake timed out.' }
        Start-Sleep -Milliseconds 50
    }
    $go = Get-Content -LiteralPath $continuePath -Raw | ConvertFrom-Json
    if ($go.token -cne $Token) { throw 'Parent handshake token mismatch.' }
    $blank.Close(0)
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($blank)
    $blank = $null
    # Supply only the stable COM prefix. Word remains hidden at application level;
    # no optional Missing sentinel is passed through PowerShell's COM binder.
    # ReadOnly true and AddToRecentFiles false are explicit; no source is saved.
    $stage = 'OPEN'
    $document = $word.Documents.Open($source, $false, $true, $false)
    if (-not $document.ReadOnly) { throw 'Word did not open the draft read-only.' }
    $stage = 'PAGINATE'
    $document.Repaginate()
    $pageCount = [int]$document.ComputeStatistics(2)
    if ($pageCount -lt 1 -or $pageCount -gt 25) { throw 'Draft page budget exceeded.' }
    if ([IO.File]::Exists($pdfPath)) { throw 'PDF target already exists.' }
    # wdExportFormatPDF=17, screen-independent print quality=0, document content=0;
    # exclude document properties, no bookmarks, no automatic file opening.
    $stage = 'EXPORT'
    $document.ExportAsFixedFormat($pdfPath, 17, $false, 0, 0, 1, $pageCount, 0, $false, $false, 0, $true, $true, $false)
    $pdf = [IO.FileInfo]::new($pdfPath)
    if (-not $pdf.Exists -or $pdf.Length -le 0 -or $pdf.Length -gt 33554432) { throw 'PDF byte budget exceeded.' }
    $stage = 'HASH'
    $result = [ordered]@{protocol=1;token=$Token;status='EXPORTED';pid=[int]$wordProcessId;creation_filetime=$created;
        version=$version;page_count=$pageCount;pdf_sha256=(Get-Sha256 $pdfPath);
        exe_sha256=(Get-Sha256 $exe);options_restored=$false}
    $success = $true
}
catch {
    $failure = New-Failure $stage $_.Exception
    $success = $false
}
finally {
    # This reference identifies only the blank we created, even if ownership was
    # rejected. Do not close any user document or Quit an unowned application.
    if ($null -ne $blank) {
        try { $blank.Close(0) } catch {
            if ($null -eq $failure) { $failure = New-Failure 'CLOSE' $_.Exception }
            $success = $false
        }
    }
    if ($owned) {
        if ($null -ne $document) {
            try { $document.Close(0) } catch {
                if ($null -eq $failure) { $failure = New-Failure 'CLOSE' $_.Exception }
                $success = $false
            }
        }
    }
    if ($null -ne $word) {
        try {
            if ($optionsChanged) {
                $word.Options.UpdateLinksAtOpen = $previousLinks
                $word.Options.SaveNormalPrompt = $previousNormalPrompt
                $restoredLinks = $word.Options.UpdateLinksAtOpen
                $restoredNormalPrompt = $word.Options.SaveNormalPrompt
                if ($restoredLinks -ne $previousLinks -or $restoredNormalPrompt -ne $previousNormalPrompt) {
                    throw 'Word preferences were not restored.'
                }
                Write-NewJson $optionsPath ([ordered]@{protocol=1;token=$Token;
                    before=[ordered]@{update_links_at_open=[bool]$previousLinks;save_normal_prompt=[bool]$previousNormalPrompt};
                    after=[ordered]@{update_links_at_open=[bool]$restoredLinks;save_normal_prompt=[bool]$restoredNormalPrompt}})
                if ($null -ne $result) { $result.options_restored = $true }
            }
            if ($securityChanged) { $word.AutomationSecurity = $previousSecurity }
        } catch {
            if ($null -eq $failure) { $failure = New-Failure 'RESTORE' $_.Exception }
            $success = $false
        }
        if ($owned) {
            # Owned documents were explicitly closed without saving above. Avoid
            # the optional ref-object binder used by Word.Application.Quit.
            try { $word.Quit() } catch {
                if ($null -eq $failure) { $failure = New-Failure 'QUIT' $_.Exception }
                $success = $false
            }
        }
    }
    try {
        if ($null -ne $blank) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($blank) }
        if ($null -ne $document) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) }
        if ($null -ne $word) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) }
    } catch {
        if ($null -eq $failure) { $failure = New-Failure 'RELEASE' $_.Exception }
        $success = $false
    }
    if ($null -ne $wordProcess) { $wordProcess.Dispose() }
}
if ($success) {
    Write-NewJson $receiptPath $result
    exit 0
}
if ($null -ne $failure) { Write-NewJson $errorPath $failure }
exit 1
