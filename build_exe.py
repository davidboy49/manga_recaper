import os
import shutil
import subprocess
import sys
from PIL import Image

# Configs
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
GENERATED_PNG = r"C:\Users\User\.gemini\antigravity\brain\a0a71d41-8f1f-4258-81b4-a2fbe4fe07de\app_icon_1780724166970.png"
TARGET_PNG = os.path.join(PROJECT_ROOT, "app_icon.png")
TARGET_ICO = os.path.join(PROJECT_ROOT, "app_icon.ico")

def main():
    print("[*] Starting Build Automation Script...")

    # Step 1: Copy PNG icon
    print(f"[*] Copying generated icon from:\n  {GENERATED_PNG}\n  to:\n  {TARGET_PNG}")
    try:
        shutil.copy(GENERATED_PNG, TARGET_PNG)
        print("[+] Icon copied successfully.")
    except Exception as e:
        print(f"[-] Failed to copy PNG icon: {e}")
        sys.exit(1)

    # Step 2: Convert PNG to ICO
    print(f"[*] Converting {TARGET_PNG} to Windows ICO format...")
    try:
        img = Image.open(TARGET_PNG)
        # standard sizes for windows icon
        icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(TARGET_ICO, format="ICO", sizes=icon_sizes)
        print(f"[+] ICO icon saved successfully to: {TARGET_ICO}")
    except Exception as e:
        print(f"[-] Failed to convert icon: {e}")
        sys.exit(1)

    # Step 3: Install PyInstaller if missing
    print("[*] Checking if PyInstaller is installed...")
    try:
        import PyInstaller
        print("[+] PyInstaller is already installed.")
    except ImportError:
        print("[*] PyInstaller not found. Installing via pip...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
            print("[+] PyInstaller installed successfully.")
        except Exception as e:
            print(f"[-] Failed to install PyInstaller: {e}")
            sys.exit(1)

    # Step 4: Run PyInstaller build
    print("[*] Executing PyInstaller build process...")
    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        f"--icon={TARGET_ICO}",
        "--name=MangaRecapEditor",
        "--collect-all=customtkinter",
        os.path.join(PROJECT_ROOT, "gui.py")
    ]
    
    print(f"[*] Running command: {' '.join(pyinstaller_cmd)}")
    try:
        subprocess.run(pyinstaller_cmd, check=True)
        print("\n[+] APPLICATION PACKAGING COMPLETED SUCCESSFULLY!")
        print(f"[+] Output folder: {os.path.join(PROJECT_ROOT, 'dist', 'MangaRecapEditor')}")
        print(f"[+] Executable: {os.path.join(PROJECT_ROOT, 'dist', 'MangaRecapEditor', 'MangaRecapEditor.exe')}")
    except subprocess.CalledProcessError as e:
        print(f"[-] PyInstaller build failed with exit code: {e.returncode}")
        sys.exit(1)

if __name__ == "__main__":
    main()
