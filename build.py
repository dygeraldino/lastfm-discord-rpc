import sys
import os
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw


def generate_icon() -> Path:
    assets_dir = Path(__file__).parent / "src" / "presentation" / "gui" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    icon_path = assets_dir / "icon.ico"

    if icon_path.exists():
        print(f"Icon already exists at {icon_path}")
        return icon_path

    print("Generating placeholder icon...")
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.ellipse([16, 16, 240, 240], fill=(29, 185, 84, 255))

    try:
        from PIL import ImageFont
        font = ImageFont.truetype("arial.ttf", 140)
    except Exception:
        font = None

    if font:
        bbox = draw.textbbox((0, 0), "♪", font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.text(((256 - text_w) / 2, (256 - text_h) / 2 - 10), "♪", fill=(255, 255, 255, 255), font=font)
    else:
        draw.text((100, 80), "♪", fill=(255, 255, 255, 255))

    img.save(icon_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Icon generated at {icon_path}")
    return icon_path


def build_executable() -> None:
    project_root = Path(__file__).parent
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"

    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    icon_path = generate_icon()

    main_py = project_root / "main.py"
    assets_dir = project_root / "src" / "presentation" / "gui" / "assets"
    config_example = project_root / ".env.example"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconsole",
        "--onefile",
        "--clean",
        f"--name=LastfmPresence",
        f"--icon={icon_path}",
        f"--add-data={assets_dir}{os.pathsep}assets",
        f"--add-data={assets_dir}{os.pathsep}src/presentation/gui/assets",
        f"--add-data={config_example}{os.pathsep}.",
        "--collect-all=customtkinter",
        "--hidden-import=pystray",
        "--hidden-import=pystray._win32",
        "--hidden-import=pystray._util",
        "--hidden-import=pystray._base",
        "--hidden-import=PIL._tkinter_finder",
        "--hidden-import=loguru",
        "--hidden-import=pydantic",
        "--hidden-import=pydantic_settings",
        "--hidden-import=httpx",
        "--hidden-import=pypresence",
        "--hidden-import=src.infrastructure.persistence.json_config_repository",
        "--hidden-import=src.presentation.gui.main_window",
        "--hidden-import=src.presentation.gui.tray_app",
        "--hidden-import=src.daemon.runner",
        "--hidden-import=src.daemon.signal_handler",
        "--hidden-import=src.application.use_cases.sync_presence",
        "--hidden-import=src.infrastructure.providers.lastfm_client",
        "--hidden-import=src.infrastructure.publishers.discord_rpc",
        "--hidden-import=config.settings",
        "--hidden-import=config.logging_config",
        str(main_py),
    ]

    print("Running PyInstaller...")
    print(" ".join(cmd))

    result = subprocess.run(cmd, cwd=project_root)

    if result.returncode != 0:
        print("Build failed!")
        sys.exit(1)

    exe_path = dist_dir / "LastfmPresence.exe"
    if exe_path.exists():
        print(f"\nPyInstaller build successful!")
        print(f"Executable: {exe_path}")
        print(f"Size: {exe_path.stat().st_size / (1024*1024):.1f} MB")
    else:
        print("Error: Executable not found in dist/")
        sys.exit(1)

    # Compile Inno Setup installer if available
    iscc_path = shutil.which("iscc")
    if not iscc_path:
        for possible in [
            r"C:\Program Files\Inno Setup 7\ISCC.exe",
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe",
        ]:
            if os.path.exists(possible):
                iscc_path = possible
                break

    iss_script = project_root / "installer.iss"
    if iscc_path and iss_script.exists():
        print("\nCompiling Inno Setup installer...")
        iscc_cmd = [iscc_path, str(iss_script)]
        iscc_result = subprocess.run(iscc_cmd, cwd=project_root)
        if iscc_result.returncode == 0:
            print("Inno Setup installer created successfully in dist/")
        else:
            print("Warning: Inno Setup compilation failed.")
    elif not iscc_path:
        print("\nInno Setup (iscc) not found in PATH or standard installation directories. Skipping setup compilation.")


if __name__ == "__main__":
    build_executable()