$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
Write-Output 'Inicializando voz'
$narrator = New-Object System.Speech.Synthesis.SpeechSynthesizer
$narrator.SelectVoice('Microsoft Sabina Desktop')
$narrator.Rate = 0
$videoFolder = Join-Path $PSScriptRoot '..\output\videos\movilizacion_html'
$lines = Get-Content -LiteralPath (Join-Path $videoFolder 'narracion.json') -Raw -Encoding utf8 | ConvertFrom-Json
for ($idx = 0; $idx -lt $lines.Count; $idx++) {
  $audioPath = [IO.Path]::GetFullPath((Join-Path $videoFolder ('voice-{0:00}.wav' -f $idx)))
  $narrator.SetOutputToWaveFile($audioPath)
  $narrator.Speak($lines[$idx])
  $narrator.SetOutputToNull()
  Write-Output ('Voz lista: ' + $idx)
}
$narrator.Dispose()
