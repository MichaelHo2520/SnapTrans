; Inno Setup Script for SnapTrans
; Requirements: Inno Setup 6 (https://jrsoftware.org/isinfo.php)

[Setup]
; App Information
AppName=SnapTrans
AppVersion=1.2.1
AppPublisher=MichaelHo2520
AppVerName=SnapTrans 1.2.1

; Installation Directory
DefaultDirName={autopf}\SnapTrans
DefaultGroupName=SnapTrans
DisableProgramGroupPage=yes

; Output Settings (Generated Installer Location)
OutputDir=deploy
OutputBaseFilename=SnapTrans_Setup_v1.2.1
SetupIconFile=icon\icon.ico

; Compression Settings (Reduces file size significantly)
Compression=lzma2/ultra64
SolidCompression=yes

; Architecture specifies x64 as target platform
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main Executable First
Source: "dist\SnapTrans\SnapTrans.exe"; DestDir: "{app}"; Flags: ignoreversion
; All other files inside the Dist folder
Source: "dist\SnapTrans\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SnapTrans"; Filename: "{app}\SnapTrans.exe"
Name: "{group}\{cm:UninstallProgram,SnapTrans}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\SnapTrans"; Filename: "{app}\SnapTrans.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SnapTrans.exe"; Description: "{cm:LaunchProgram,SnapTrans}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up temp files when uninstalling
Type: filesandordirs; Name: "{app}\temp"
