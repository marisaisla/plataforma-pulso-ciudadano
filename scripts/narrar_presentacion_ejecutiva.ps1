$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'shared_files.ps1')
$filesRoot = Get-Go2WinFilesRoot
Add-Type -AssemblyName System.Speech
$narrator = New-Object System.Speech.Synthesis.SpeechSynthesizer
$narrator.SelectVoice('Microsoft Sabina Desktop')
$narrator.Rate = 0
$narrator.Volume = 100
$videoFolder = Join-Path $filesRoot 'output\videos\presentacion_ejecutiva'
$lines = Get-Content -LiteralPath (Join-Path $videoFolder 'narracion.json') -Raw -Encoding utf8 | ConvertFrom-Json
try {
  for ($idx = 0; $idx -lt $lines.Count; $idx++) {
    $audioPath = [IO.Path]::GetFullPath((Join-Path $videoFolder ('voice-{0:00}.wav' -f $idx)))
    $narrator.SetOutputToWaveFile($audioPath)
    $narrator.Speak($lines[$idx])
    $narrator.SetOutputToNull()
    Write-Output ('Voz lista: ' + ($idx + 1))
  }
} finally { $narrator.Dispose() }
