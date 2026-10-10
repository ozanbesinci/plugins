# Stdlib-only bootstrap fallback; no Python, network, messages or source data.
$script:KilicLogPluginRoot=Split-Path $PSScriptRoot -Parent
if(-not (Get-Variable -Name KilicLogSession -Scope Script -ErrorAction SilentlyContinue)){
    $script:KilicLogSession=[guid]::NewGuid().ToString('N')
    $script:KilicLogCount=0
}
function Write-KilicErrorLog {
    param([string]$Stage, [string]$Code, $ErrorRecord=$null,
          [string]$SkillId='', [string]$Category='TECHNICAL_ERROR')
    try {
        $ErrorActionPreference='Stop'
        if(-not $env:LOCALAPPDATA){return}
        if($script:KilicLogCount -ge 100){return}
        $root=Join-Path $env:LOCALAPPDATA 'KilicSozlesme\logs'
        [void][IO.Directory]::CreateDirectory($root)
        $now=[DateTime]::UtcNow
        $path=Join-Path $root ('errors_'+$now.ToString('yyyyMMdd')+'_'+$PID+'_'+$script:KilicLogSession+'.jsonl')
        $version='UNKNOWN'
        try{
            $candidate=(Get-Content -LiteralPath (Join-Path $script:KilicLogPluginRoot 'plugin.json') -Raw -Encoding UTF8 | ConvertFrom-Json).version
            if($candidate -cmatch '^[A-Za-z0-9_.-]{1,80}$'){$version=$candidate}
        }catch{}
        $exceptionType=$null;$line=$null
        if($ErrorRecord){$exceptionType=$ErrorRecord.Exception.GetType().Name;$line=$ErrorRecord.InvocationInfo.ScriptLineNumber}
        $safeSkill=$null
        if($SkillId -cmatch '^(K[0-9]{2}|guncelleyici)$'){$safeSkill=$SkillId}
        $event=[ordered]@{schema_version='1.0';event_id=[guid]::NewGuid().ToString('N');
            timestamp_utc=$now.ToString('o');session_id=$script:KilicLogSession;
            package_version=$version;skill_id=$safeSkill;stage=$Stage;category=$Category;
            error_code=$Code;exception_type=$exceptionType;line=$line;
            powershell_version=$PSVersionTable.PSVersion.ToString()}
        $bytes=(New-Object Text.UTF8Encoding $false).GetBytes(($event|ConvertTo-Json -Compress)+"`n")
        if((Test-Path -LiteralPath $path) -and (((Get-Item -LiteralPath $path).Length+$bytes.Length) -gt 1048576)){return}
        $stream=New-Object IO.FileStream($path,[IO.FileMode]::Append,[IO.FileAccess]::Write,[IO.FileShare]::Read)
        try{$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
        $script:KilicLogCount++
    }catch{ # Never block or retry the original operation because logging failed.
    }
}
