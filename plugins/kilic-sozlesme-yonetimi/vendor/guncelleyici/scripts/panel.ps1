# Compatibility import only. The old GUI cannot perform cleanup or installation.
param([switch]$TestMode,[switch]$LayoutTest)
if($TestMode){. (Join-Path $PSScriptRoot 'core.ps1');'PANEL_TEST_MODE_OK';return}
throw 'Eski panel girişi kapalıdır. Sohbet tablosu için sohbet.ps1 -Action scan kullanın.'