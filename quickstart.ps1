#Requires -version 5.0
function Update-Profile {
  @(
    $Profile.AllUsersAllHosts,
    $Profile.AllUsersCurrentHost,
    $Profile.CurrentUserAllHosts,
    $Profile.CurrentUserCurrentHost
  ) | ForEach-Object {
    if (Test-Path $_) {
      . $_
    }
  }
}
$skipConda = $false
if ( -not ( get-command conda -ea silentlycontinue ) ) {
  $confirmation = Read-Host "Could not detect conda installation. Install Conda?"
  if ($confirmation -eq 'y') {
    Invoke-WebRequest 'https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe' -OutFile 'Miniforge3-Windows-x86_64.exe'
    if ( test-path 'Miniforge3-Windows-x86_64.exe' ) {
      Start-Process -Wait 'Miniforge3-Windows-x86_64.exe'
      Upload-Profile
    }
    else {
      write-host "Download failed, exiting."
      exit 1
    }
  }
  else {
    $confirmation = Read-Host "Attempt to install in current Python environment instead?"
    if ($confirmation -ne 'y') {
      exit 1
    }
    else {
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

write-host 'Optional components'
$add_on = '[remote,'
$local = Read-Host "Generate speech locally (y/n)"
$truststore = Read-Host "Trust locally installed certificates (y/n)"
if ( $local -eq 'y' ) { $add_on += 'local,' }
if ( $truststore -eq 'y' ) { $add_on += 'truststore,' }
$add_on = $add_on.Substring(0, ($add_on.length) - 1)
if ( ($add_on.length) -gt 0 ) { 
  $add_on += ']'
}

$installString = ('ttspod' + $add_on)
Start-Process -NoNewWindow -Wait "pip3.exe" -ArgumentList "install", $installString

$cuda = ( python -c "import torch; print(torch.cuda.is_available())" )
if ( $cuda -ne 'True' ) {
  write-host 'cuda GPU not detected. You can try installing torch from https://pytorch.org/get-started/locally/ for your processor to obtain cuda support.'
}

write-host 'You should be good to go. You can use the following command to generate a config file and get started:'
write-host 'ttspod -g'
