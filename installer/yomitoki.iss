; Yomitoki 安裝檔（Inno Setup 6）。由 installer/build.py 準備好 stage\ 之後編譯：
;   ISCC.exe /DAppVersion=0.1.0 installer\yomitoki.iss
;
; 安裝檔只放程式本身與 uv；Python、翻譯核心與模型在安裝後下載，讓安裝檔保持輕量。
; 預設裝在 %LOCALAPPDATA%\Yomitoki，不需要系統管理員權限。

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define Stage "build\stage"

[Setup]
AppId={{E15398AA-DDA8-4C02-94DB-B6F87F1974BB}
AppName=Yomitoki
AppVersion={#AppVersion}
AppVerName=Yomitoki {#AppVersion}
AppPublisher=Yomitoki contributors
AppPublisherURL=https://github.com/cacich/yomitoki
AppSupportURL=https://github.com/cacich/yomitoki/issues
DefaultDirName={localappdata}\Yomitoki
DefaultGroupName=Yomitoki
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=build\Output
OutputBaseFilename=Yomitoki-Setup-{#AppVersion}
SetupIconFile=..\assets\icons\app.ico
UninstallDisplayIcon={app}\program\assets\icons\app.ico
UninstallDisplayName=Yomitoki
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
; 自己用 PID 檔結束 Yomitoki，不讓 Restart Manager 去關其他 Python 程式
CloseApplications=no
; Inno Setup 6.5 起預設開啟 Windows 的 RedirectionGuard，子程序也會繼承：它不讓程序穿過一般使用者建立的
; junction。uv 管理 Python 需要 junction（os error 448）。這個防護是為了避免「以系統管理員安裝」時被
; 導向攻擊提權；Yomitoki 只裝在使用者自己的資料夾、不要求系統管理員權限，關掉不影響安全性。
RedirectionGuard=no
AllowNoIcons=yes

[Languages]
Name: "zh"; MessagesFile: "ChineseTraditional.isl"; InfoBeforeFile: "{#Stage}\notice-zh.txt"
Name: "en"; MessagesFile: "compiler:Default.isl"; InfoBeforeFile: "{#Stage}\notice-en.txt"

[CustomMessages]
zh.PreparingPython=正在準備 Python 環境（約 1～2 分鐘，需要網路）…
en.PreparingPython=Preparing the Python environment (1-2 minutes, internet required)...
zh.BootstrapFailed=Python 環境沒有準備好（錯誤碼 %1）。%n%n請確認網路連線後重新執行安裝檔。記錄檔在：%n%2
en.BootstrapFailed=The Python environment could not be prepared (error %1).%n%nCheck your internet connection and run the installer again. Log file:%n%2
zh.DeleteUserData=要一併刪除你的作品資料嗎？%n%n%1%n（截圖、譯圖、詞彙表、劇情摘要）%n%n選「否」會保留，之後重新安裝還能繼續使用。
en.DeleteUserData=Also delete your series data?%n%n%1%n(screenshots, translated pages, glossaries, story notes)%n%nChoose No to keep it for a future reinstall.
zh.StoppingApp=正在關閉 Yomitoki…
en.StoppingApp=Closing Yomitoki...

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#Stage}\program\*"; DestDir: "{app}\program"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Stage}\bin\uv.exe"; DestDir: "{app}\bin"; Flags: ignoreversion

[InstallDelete]
; 更新時先清掉舊的程式檔，避免留下已經刪除的舊檔案
Type: filesandordirs; Name: "{app}\program"

[Icons]
Name: "{autoprograms}\Yomitoki"; Filename: "{app}\env\launcher\Scripts\pythonw.exe"; Parameters: "-m app.launcher"; WorkingDir: "{app}\program"; IconFilename: "{app}\program\assets\icons\app.ico"; AppUserModelID: "Yomitoki.Reader"
Name: "{autodesktop}\Yomitoki"; Filename: "{app}\env\launcher\Scripts\pythonw.exe"; Parameters: "-m app.launcher"; WorkingDir: "{app}\program"; IconFilename: "{app}\program\assets\icons\app.ico"; AppUserModelID: "Yomitoki.Reader"; Tasks: desktopicon

[Run]
Filename: "{app}\env\launcher\Scripts\pythonw.exe"; Parameters: "-m app.launcher"; WorkingDir: "{app}\program"; Description: "{cm:LaunchProgram,Yomitoki}"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\program"
Type: filesandordirs; Name: "{app}\bin"
Type: filesandordirs; Name: "{app}\env"
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\cache"
Type: filesandordirs; Name: "{app}\models"
Type: filesandordirs; Name: "{app}\fonts"
Type: filesandordirs; Name: "{app}\vendor"
Type: filesandordirs; Name: "{app}\work"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\run"
Type: filesandordirs; Name: "{app}\webview"
Type: files; Name: "{app}\launcher.json"
Type: dirifempty; Name: "{app}"

[Code]
{ 依 run\*.pid 結束還在執行的啟動器與翻譯伺服器（/T 連同子程序） }
procedure StopByPidFile(const Name: String);
var
  PidFile: String;
  Pid: AnsiString;
  ResultCode: Integer;
begin
  PidFile := ExpandConstant('{app}\run\' + Name + '.pid');
  if FileExists(PidFile) and LoadStringFromFile(PidFile, Pid) then
  begin
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/PID ' + Trim(String(Pid)) + ' /T /F', '', SW_HIDE,
         ewWaitUntilTerminated, ResultCode);
    DeleteFile(PidFile);
  end;
end;

procedure StopYomitoki();
begin
  StopByPidFile('launcher');
  StopByPidFile('server');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  WizardForm.StatusLabel.Caption := CustomMessage('StoppingApp');
  StopYomitoki();
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Script: String;
begin
  if CurStep = ssPostInstall then
  begin
    WizardForm.StatusLabel.Caption := CustomMessage('PreparingPython');
    WizardForm.ProgressGauge.Style := npbstMarquee;
    Script := ExpandConstant('{app}\program\installer\bootstrap-launcher.cmd');
    if not Exec(ExpandConstant('{cmd}'), '/C ""' + Script + '" "' + ExpandConstant('{app}') + '""', '', SW_HIDE,
                ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
    begin
      { 注意：[ 不能放在行首，Inno Setup 會把它當成區段標題 }
      SuppressibleMsgBox(FmtMessage(CustomMessage('BootstrapFailed'), [IntToStr(ResultCode),
        ExpandConstant('{app}\logs\install.log')]), mbError, MB_OK, IDOK);
    end;
    WizardForm.ProgressGauge.Style := npbstNormal;
  end;
end;

function InitializeUninstall(): Boolean;
begin
  StopYomitoki();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userdocs}\Yomitoki');
    if DirExists(DataDir) then
      if SuppressibleMsgBox(FmtMessage(CustomMessage('DeleteUserData'), [DataDir]),
                            mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
