!macro customUnInstall
  nsExec::ExecToLog 'schtasks.exe /Delete /TN "VivooCaptureService" /F'
!macroend
