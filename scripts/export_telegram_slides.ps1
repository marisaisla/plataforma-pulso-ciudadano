$ErrorActionPreference = 'Stop'
$ppt = New-Object -ComObject PowerPoint.Application
try {
 $deck = $ppt.Presentations.Open('C:\Users\jorge\OneDrive\Documentos\ChatGPT\New project\output\pptx\Arquitectura_Integracion_Telegram_Go2Win_Tres_Flujos_Operativos.pptx', -1, 0, 0)
 try {
  foreach ($s in $deck.Slides) {
   $dest = Join-Path (Get-Location) ('output\videos\telegram_slides\telegram-{0:00}.png' -f $s.SlideIndex)
   $s.Export($dest, 'PNG', 1920, 1080)
   Write-Output $dest
  }
 } finally { $deck.Close() }
} finally { $ppt.Quit() }
