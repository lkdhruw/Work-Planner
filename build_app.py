"""
build_app.py — Cross-platform PyInstaller packaging script for Work Planner.

Handles the Google Drive 'path with spaces' issue by building in a temp
directory and then moving the result back to the project folder.
"""
import os
import sys
import shutil
import subprocess
import tempfile

APP_NAME = "WorkPlanner"
ENTRY   = "main.py"


def build():
    # ── Install PyInstaller if missing ────────────────────────────────────────
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    project_dir = os.path.dirname(os.path.abspath(__file__))
    sep         = ';' if sys.platform == 'win32' else ':'

    # ── Use a temp dir with no spaces as the work/dist target ─────────────────
    tmp_root  = tempfile.mkdtemp(prefix="wp_build_")
    dist_tmp  = os.path.join(tmp_root, "dist")
    build_tmp = os.path.join(tmp_root, "build")
    os.makedirs(dist_tmp,  exist_ok=True)
    os.makedirs(build_tmp, exist_ok=True)

    # QSS stylesheet bundled alongside app package
    data_arg = (
        f"{os.path.join(project_dir, 'app', 'ui', 'styles', 'theme.qss')}"
        f"{sep}app/ui/styles"
    )

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name",       APP_NAME,
        "--distpath",   dist_tmp,
        "--workpath",   build_tmp,
        f"--add-data={data_arg}",
        os.path.join(project_dir, ENTRY),
    ]

    print(f"Building in temp dir: {tmp_root}\n")

    try:
        subprocess.check_call(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed (exit {e.returncode}). Check the output above.")
        shutil.rmtree(tmp_root, ignore_errors=True)
        sys.exit(e.returncode)

    # ── Move result back to project/dist ──────────────────────────────────────
    final_dist = os.path.join(project_dir, "dist")
    final_app  = os.path.join(final_dist, APP_NAME)

    if os.path.exists(final_app):
        shutil.rmtree(final_app)
    os.makedirs(final_dist, exist_ok=True)
    shutil.move(os.path.join(dist_tmp, APP_NAME), final_app)

    # Cleanup temp dir
    shutil.rmtree(tmp_root, ignore_errors=True)

    print("\nBuild complete!")
    if sys.platform == 'win32':
        exe = os.path.join(final_app, f"{APP_NAME}.exe")
        print(f"Executable: {exe}")
    else:
        print(f"Bundle: {final_app}")


if __name__ == "__main__":
    build()
