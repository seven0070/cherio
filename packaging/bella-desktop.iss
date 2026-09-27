#define BellaVersion "0.1.0"
[Setup]
AppId={{F7661247-10C9-4ED1-8506-74E50780B4D2}
AppName=Bella Desktop
AppVersion={#BellaVersion}
AppPublisher=Cheerio
DefaultDirName={localappdata}\Programs\Bella Desktop
DefaultGroupName=Bella Desktop
UninstallDisplayIcon={app}\BellaDesktop.exe
OutputDir=..\dist-installer
OutputBaseFilename=BellaDesktop-v{#BellaVersion}-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
DisableProgramGroupPage=yes
WizardStyle=modern

[Files]
Source: "..\dist\BellaDesktop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Bella Desktop"; Filename: "{app}\BellaDesktop.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\Bella Desktop"; Filename: "{app}\BellaDesktop.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
