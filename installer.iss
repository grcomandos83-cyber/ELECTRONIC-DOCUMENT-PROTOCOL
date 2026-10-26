; ─────────────────────────────────────────────────────────────
;  Inno Setup Script — Ηλεκτρονικό Πρωτόκολλο Εγγράφων
;  Οδηγία Ασφαλούς Υλοποίησης (Safe Upgrade & DLL Protection)
; ─────────────────────────────────────────────────────────────

#ifndef MyAppVersion
  #define MyAppVersion "1.0.6"
#endif

#define MyAppName "Ηλεκτρονικό Πρωτόκολλο Εγγράφων"
#define MyAppNameEn "Protokollo"
#define MyAppPublisher "Gregory"
#define MyAppExeName "Protokollo.exe"
#define MyAppLauncher "launcher.bat"

[Setup]
; Unique GUID for this application
AppId={{E68A8F43-4C3D-4A42-995F-82D1B8756F31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

; Προτίμηση αγγλικού ονόματος για τη φυσική διαδρομή του φακέλου στο δίσκο
; Αποτρέπει προβλήματα κωδικοποίησης (encoding glitches) σε batch scripts
DefaultDirName={autopf}\{#MyAppNameEn}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist_installer
OutputBaseFilename=Protocol_Setup_v{#MyAppVersion}
SetupIconFile=assets\app_icon.ico
UninstallDisplayIcon={app}\assets\app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; 1. Δικαιώματα χρήστη: Επίπεδο τρέχοντος χρήστη (Χωρίς απαίτηση UAC)
; Επιτρέπει την απρόσκοπτη εγγραφή τοπικών αρχείων και βάσης δεδομένων
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline

; 2. Αποτροπή DLL Crashes: Απενεργοποίηση αυτόματης επανεκκίνησης του λειτουργικού
; Αποτρέπει την αναπαραγωγή «μολυσμένου» περιβάλλοντος διεργασίας
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "greek"; MessagesFile: "languages\Greek.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Ενημερώνει αποκλειστικά binaries και assets. Η βάση δεδομένων και τα δεδομένα χρήστη μένουν ανέπαφα.
Source: "dist\Protokollo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\app_icon.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
; Ρητή προσθήκη του launcher.bat ώστε να υπάρχει εγγυημένα στον φάκελο εγκατάστασης
Source: "launcher.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\app_icon.ico"; IconIndex: 0
Name: "{group}\Απεγκατάσταση"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\app_icon.ico"; IconIndex: 0; Tasks: desktopicon

[Run]
; 1. Για κανονική (διαδραστική) εγκατάσταση από τον χρήστη (εμφανίζει το checkbox στο τέλος)
Filename: "{app}\{#MyAppLauncher}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent runhidden

; 2. Για ΑΘΟΡΥΒΟ Auto-Update (/SILENT): Εκτελείται αυτόματα χωρίς το skipifsilent!
Filename: "{app}\{#MyAppLauncher}"; Flags: nowait runhidden; Check: WizardSilent
