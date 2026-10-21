# Offline TTS with Windows System.Speech: one WAV per scene text file in audio\ (sXX.txt -> sXX.wav)
param([string]$Voice = "Microsoft Zira Desktop", [int]$Rate = -1)
Add-Type -AssemblyName System.Speech
$dir = Join-Path $PSScriptRoot "audio"
foreach ($f in Get-ChildItem $dir -Filter "s*.txt") {
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $s.SelectVoice($Voice); $s.Rate = $Rate
  $wav = [IO.Path]::ChangeExtension($f.FullName, ".wav")
  $s.SetOutputToWaveFile($wav)
  $s.Speak((Get-Content $f.FullName -Raw -Encoding UTF8))
  $s.Dispose()
  "{0} -> {1}" -f $f.Name, (Split-Path $wav -Leaf)
}
