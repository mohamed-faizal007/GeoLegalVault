# Offline TTS with Windows System.Speech: one WAV per sentence file in audio\ (sXX_key.txt -> sXX_key.wav).
# Only sentences without a WAV are synthesised (narration.py deletes the WAV of any sentence whose text changed).
param([string]$Voice = "Microsoft Zira Desktop", [int]$Rate = 1)
Add-Type -AssemblyName System.Speech
$dir = Join-Path $PSScriptRoot "audio"
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice($Voice); $s.Rate = $Rate
$n = 0
foreach ($f in Get-ChildItem $dir -Filter "s*.txt") {
  $wav = [IO.Path]::ChangeExtension($f.FullName, ".wav")
  if (Test-Path $wav) { continue }
  $s.SetOutputToWaveFile($wav)
  $s.Speak((Get-Content $f.FullName -Raw -Encoding UTF8))
  $s.SetOutputToNull()
  $n++
}
$s.Dispose()
"synthesised $n sentence(s)"
