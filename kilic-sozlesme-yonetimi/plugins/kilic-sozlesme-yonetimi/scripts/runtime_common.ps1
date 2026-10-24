# Plugin-owned runtime helpers; no installer or vendor dependency.
function Read-Field($Value,[string]$Name,$Default=$null) {
    if($null -eq $Value){return $Default}
    if($Value -is [Collections.IDictionary]){if($Value.Contains($Name)){return $Value[$Name]};return $Default}
    $p=$Value.PSObject.Properties[$Name];if($p){return $p.Value};return $Default
}
function Assert-PlainPath([string]$Path) {
    $full=[IO.Path]::GetFullPath($Path)
    $node=$full
    while($node){
        if(Test-Path -LiteralPath $node){if((Get-Item -LiteralPath $node -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse path rejected'}}
        $node=Split-Path $node -Parent
    }
}
function File-Sha256([string]$Path) {
    $h=[Security.Cryptography.SHA256]::Create();$f=[IO.File]::OpenRead($Path)
    try{return ([BitConverter]::ToString($h.ComputeHash($f))).Replace('-','').ToLowerInvariant()}finally{$f.Dispose();$h.Dispose()}
}
function Get-ContractBootstrapSha([string]$Path) {
    Assert-PlainPath $Path
    return File-Sha256 $Path
}
