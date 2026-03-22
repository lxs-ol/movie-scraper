[Setup]
AppId={{8F3F9E5A-1234-5678-9ABC-DEF012345678}
AppName=Movie Scraper
AppVersion=1.1.6
AppVerName=Movie Scraper 1.1.6
AppPublisher=lxs-ol
AppPublisherURL=https://github.com/lxs-ol/movie-scraper
AppSupportURL=https://github.com/lxs-ol/movie-scraper
AppUpdatesURL=https://github.com/lxs-ol/movie-scraper
DefaultDirName={autopf}\Movie Scraper
DefaultGroupName=Movie Scraper
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=MovieScraper-1.1.6-Setup
SetupIconFile=logo.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
UninstallDisplayIcon={app}\Movie Scraper.exe
UninstallDisplayName=Movie Scraper

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "build_single_exe\Movie Scraper.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "build_single_exe\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Movie Scraper"; Filename: "{app}\Movie Scraper.exe"
Name: "{group}\{cm:UninstallProgram,Movie Scraper}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Movie Scraper"; Filename: "{app}\Movie Scraper.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Movie Scraper.exe"; Description: "{cm:LaunchProgram,Movie Scraper}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
