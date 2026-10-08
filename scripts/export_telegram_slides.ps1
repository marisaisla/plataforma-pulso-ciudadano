$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'shared_files.ps1')
$filesRoot = Get-Go2WinFilesRoot
$source = Join-Path $filesRoot 'assets\go2win_video\fuentes\Arquitectura_Integracion_Telegram_Go2Win_Tres_Flujos_Operativos.pptx'
$outputFolder = Join-Path $filesRoot 'output\videos\telegram_slides'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Falta la presentacion: $source" }
New-Item -ItemType Directory -Path $outputFolder -Force | Out-Null
$ppt = New-Object -ComObject PowerPoint.Application
try {
 $deck = $ppt.Presentations.Open($source, -1, 0, 0)
 try {
  foreach ($s in $deck.Slides) {
   $dest = Join-Path $outputFolder ('telegram-{0:00}.png' -f $s.SlideIndex)
   $s.Export($dest, 'PNG', 1920, 1080)
   Write-Output $dest
  }
 } finally { $deck.Close() }
} finally { $ppt.Quit() }
