; Inno Setup script for Manga Recap Storyboard Editor
[Setup]
AppName=Manga Recap Storyboard Editor
AppVersion=1.0
AppPublisher=Antigravity
DefaultDirName={autopf}\MangaRecapEditor
DefaultGroupName=Manga Recap Storyboard Editor
OutputDir=C:\Users\User\PycharmProjects\pythonProject2\dist-setup
OutputBaseFilename=MangaRecapEditorSetup
SetupIconFile=C:\Users\User\PycharmProjects\pythonProject2\app_icon.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
DisableWelcomePage=no
DisableProgramGroupPage=yes

[Files]
Source: "C:\Users\User\PycharmProjects\pythonProject2\dist\MangaRecapEditor\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Manga Recap Editor"; Filename: "{app}\MangaRecapEditor.exe"
Name: "{autodesktop}\Manga Recap Editor"; Filename: "{app}\MangaRecapEditor.exe"

[Run]
Filename: "{app}\MangaRecapEditor.exe"; Description: "Launch Manga Recap Editor"; Flags: nowait postinstall skipifsilent
