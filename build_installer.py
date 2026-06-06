import os
import shutil
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ISS_PATH = os.path.join(PROJECT_ROOT, "installer.iss")
ICON_PATH = os.path.join(PROJECT_ROOT, "app_icon.ico")
DIST_DIR = os.path.join(PROJECT_ROOT, "dist", "MangaRecapEditor")

# Detect ISCC.exe compiler
COMPILER_PATHS = [
    os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "Programs", "Inno Setup 6", "ISCC.exe"),
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]

def find_compiler():
    # Check PATH first
    path_iscc = shutil.which("ISCC")
    if path_iscc:
        return path_iscc
    
    # Check standard paths
    for path in COMPILER_PATHS:
        if os.path.exists(path):
            return path
            
    return None

def generate_iss():
    print("[*] Generating Inno Setup script (installer.iss)...")
    iss_content = f"""; Inno Setup script for Manga Recap Storyboard Editor
[Setup]
AppName=Manga Recap Storyboard Editor
AppVersion=1.0
AppPublisher=Antigravity
DefaultDirName={{autopf}}\\MangaRecapEditor
DefaultGroupName=Manga Recap Storyboard Editor
OutputDir={os.path.join(PROJECT_ROOT, "dist-setup")}
OutputBaseFilename=MangaRecapEditorSetup
SetupIconFile={ICON_PATH}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
DisableWelcomePage=no
DisableProgramGroupPage=yes

[Files]
Source: "{DIST_DIR}\\*"; DestDir: "{{app}}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\Manga Recap Editor"; Filename: "{{app}}\\MangaRecapEditor.exe"
Name: "{{autodesktop}}\\Manga Recap Editor"; Filename: "{{app}}\\MangaRecapEditor.exe"

[Run]
Filename: "{{app}}\\MangaRecapEditor.exe"; Description: "Launch Manga Recap Editor"; Flags: nowait postinstall skipifsilent
"""
    with open(ISS_PATH, "w", encoding="utf-8") as f:
        f.write(iss_content)
    print("[+] installer.iss generated successfully.")

def main():
    compiler = find_compiler()
    if not compiler:
        print("[-] Error: Inno Setup compiler (ISCC.exe) not found.")
        print("[-] Please ensure Inno Setup 6 is installed correctly.")
        sys.exit(1)
        
    print(f"[+] Found Inno Setup compiler: {compiler}")
    
    # Verify build dist exists
    if not os.path.exists(DIST_DIR):
        print(f"[-] Error: Build directory not found: {DIST_DIR}")
        print("[-] Please run 'build_exe.py' first to build the executable files.")
        sys.exit(1)

    generate_iss()
    
    print("[*] Compiling Windows setup installer...")
    cmd = [compiler, ISS_PATH]
    try:
        subprocess.run(cmd, check=True)
        print("\n[+] WINDOWS SETUP INSTALLER COMPILED SUCCESSFULLY!")
        print(f"[+] Output: {os.path.join(PROJECT_ROOT, 'dist-setup', 'MangaRecapEditorSetup.exe')}")
    except subprocess.CalledProcessError as e:
        print(f"[-] Installer compilation failed with exit code: {e.returncode}")
        sys.exit(1)

if __name__ == "__main__":
    main()
