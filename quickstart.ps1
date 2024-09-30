#Requires –Version 5
$skipConda = $false
if ( -not ( get-command conda -ea silentlycontinue ) ) {
  $confirmation = Read-Host "Could not detect conda installation. Install Conda?"
    if ($confirmation -eq 'y') {
      if ( Invoke-WebRequest 'https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe' -OutFile 'Miniforge3-Windows-x86_64.exe' ) {
        & 'Miniforge3-Windows-x86_64.exe'
    } else {
      write-host "Download failed, exiting."
        exit 1
    }
    } else {
      $confirmation = Read-Host "Attempt to install in current Python environment instead?"
        if ($confirm -ne 'y') {
          exit 1
        } else {
          $skipConda = $true
        }
    }
} 
if ( -not ( $skipConda )) {
  invoke-conda create -n ttspod python=3.11
  invoke-conda activate ttspod
}
if ( -not ( get-command pip -ea silentlycontinue ) ) {
  write-host "pip command not found, cannot continue."
    exit 1
}

write-host 'optional requirements - you should install at least one TTS engine (Whisper, Coqui "TTS", OpenAI, or Eleven)'
write-host 'also install truststore if you need to trust locally-installed certificates (e.g. due to a firewall/VPN)'
$add_on='['
$whisper = Read-Host "Install Whisper speech engine?"
$coqui = Read-Host "Install coqui speech engine?"
$openai = Read-Host "Install OpenAI speech engine?"
$eleven = Read-Host "Install Eleven speech engine?"
$truststore = Read-Host "Install Truststore?"
if ( $whisper -eq 'y' ) { $add_on += 'whisper,' }
if ( $coqui -eq 'y' ) { $add_on += 'coqui,' }
if ( $openai -eq 'y' ) { $add_on += 'openai,' }
if ( $truststore -eq 'y' ) { $add_on += 'truststore,' }
$add_on = $add_on.Substring(0,($add_on.length)-1)
  if ( ($add_on.length) -gt 0 ) { 
    $add_on += ']'
  }

$installString = ('ttspod' + $add_on)
& "pip3.exe" install $installString

$cuda = ( python -c "import torch; print(torch.cuda.is_available())" )
if ( $cuda -ne 'True' ) {
  write-host 'cuda GPU not detected. You can try installing torch from https://pytorch.org/get-started/locally/ for your processor to obtain cuda support.'
}
