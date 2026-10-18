#requires -Version 5.1
param([string]$BasePython, [string]$Wheelhouse)
# Optional compatibility entry. End users open Kur.cmd; no PS1 policy change is needed.
$savedBase = $env:KILIC_BASE_PYTHON
$savedWheels = $env:KILIC_WHEELHOUSE
try {
    if ($BasePython) { $env:KILIC_BASE_PYTHON = $BasePython }
    if ($Wheelhouse) { $env:KILIC_WHEELHOUSE = $Wheelhouse }
    & (Join-Path $PSScriptRoot 'Kur.cmd')
    $result = $LASTEXITCODE
} finally {
    $env:KILIC_BASE_PYTHON = $savedBase
    $env:KILIC_WHEELHOUSE = $savedWheels
}
exit $result
