param(
    [Parameter(Mandatory=$true)][ValidateSet('begin','recall','capture','status','export')][string]$Action,
    [string]$InputFile,
    [string]$Query,
    [string[]]$Topics=@(),
    [string]$TaskId
)
$ErrorActionPreference='Stop'
if ($PSBoundParameters.ContainsKey('TaskId') -and [string]::IsNullOrWhiteSpace($TaskId)) {
    [Console]::Error.WriteLine('{"error":"invalid task_id"}')
    exit 2
}
$scriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$helper=Join-Path $scriptDir 'devbrain_memory.py'
$argsList=[System.Collections.Generic.List[string]]::new()
$argsList.Add($helper); $argsList.Add($Action.ToLowerInvariant())
if ($InputFile) {
    $resolved=(Resolve-Path -LiteralPath $InputFile).Path
    $inputInfo=Get-Item -LiteralPath $resolved
    if ($inputInfo.Length -gt 32768) { [Console]::Error.WriteLine('{"error":"input exceeds 32 KB"}'); exit 2 }
    $argsList.Add('--input-file'); $argsList.Add($resolved)
}
if ($Query) { $argsList.Add('--query'); $argsList.Add($Query) }
if ($Topics.Count) { $argsList.Add('--topics'); $argsList.Add(($Topics -join ' ')) }
if ($PSBoundParameters.ContainsKey('TaskId')) { $argsList.Add('--task-id'); $argsList.Add($TaskId) }
& (Join-Path $scriptDir 'run_python.ps1') -PythonArgs $argsList.ToArray() 6>$null
exit $LASTEXITCODE
