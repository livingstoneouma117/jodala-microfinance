"""Build React frontend assets without npm by downloading the esbuild binary package."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path
from tempfile import mkdtemp


VERSION = "0.12.28"
ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
ASSETS = DIST / "assets"
CACHE_DIR = ROOT / ".esbuild"


def resolve_package() -> tuple[str, str]:
    system = platform.system().lower().replace("win32", "windows")
    arch = platform.machine().lower()

    if arch in {"x86_64", "amd64"}:
        if system == "windows":
            return "esbuild-windows-64", "package/esbuild.exe"
        if system == "linux":
            return "esbuild-linux-64", "package/bin/esbuild"
        if system == "darwin":
            return "esbuild-darwin-64", "package/bin/esbuild"

    if arch in {"aarch64", "arm64"}:
        if system == "linux":
            return "esbuild-linux-arm64", "package/bin/esbuild"
        if system == "darwin":
            return "esbuild-darwin-arm64", "package/bin/esbuild"

    raise RuntimeError(f"Unsupported platform for bundled build: {system} {arch}")


def ensure_esbuild_binary() -> Path:
    package_name, binary_rel = resolve_package()
    target_dir = CACHE_DIR / f"{package_name}-{VERSION}"
    binary_path = target_dir / ("esbuild.exe" if os.name == "nt" else "esbuild")

    if binary_path.exists():
        return binary_path

    target_dir.mkdir(parents=True, exist_ok=True)

    url = f"https://registry.npmjs.org/{package_name}/-/{package_name}-{VERSION}.tgz"
    temp_dir = Path(mkdtemp(prefix="jodala-esbuild-"))
    archive_path = temp_dir / f"{package_name}-{VERSION}.tgz"

    try:
        urllib.request.urlretrieve(url, archive_path)
        with tarfile.open(archive_path) as tar:
            tar.extractall(temp_dir)

        src_binary = temp_dir / binary_rel
        if not src_binary.exists():
            raise RuntimeError(f"esbuild binary not found in archive: {binary_rel}")

        shutil.copy2(src_binary, binary_path)
        if os.name != "nt":
            binary_path.chmod(0o755)
        return binary_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def build_assets() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)

    binary = ensure_esbuild_binary()

    subprocess.run(
        [
            str(binary),
            "src/main.jsx",
            "--bundle",
            "--format=esm",
            "--minify",
            "--sourcemap",
            "--outdir=dist/assets",
            "--entry-names=app",
            "--loader:.js=jsx",
            "--loader:.jsx=jsx",
            "--external:react",
            "--external:react-dom/client",
            "--external:react-router-dom",
        ],
        cwd=str(ROOT),
        check=True,
    )

    html = """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>Jodala Microfinance v3</title>
    <meta name=\"theme-color\" content=\"#0f766e\" />
    <meta name=\"mobile-web-app-capable\" content=\"yes\" />
    <meta name=\"apple-mobile-web-app-capable\" content=\"yes\" />
    <meta name=\"apple-mobile-web-app-title\" content=\"Jodala\" />
    <meta name=\"apple-mobile-web-app-status-bar-style\" content=\"default\" />
    <meta name=\"msapplication-TileColor\" content=\"#0f766e\" />
    <link rel=\"manifest\" href=\"/manifest.webmanifest\" />
    <link rel=\"icon\" type=\"image/x-icon\" href=\"/favicon.ico\" />
    <link rel=\"icon\" type=\"image/png\" sizes=\"16x16\" href=\"/icons/favicon-16.png\" />
    <link rel=\"icon\" type=\"image/png\" sizes=\"32x32\" href=\"/icons/favicon-32.png\" />
    <link rel=\"icon\" type=\"image/png\" sizes=\"48x48\" href=\"/icons/favicon-48.png\" />
    <link rel=\"apple-touch-icon\" sizes=\"180x180\" href=\"/icons/apple-touch-icon.png\" />
    <link rel=\"stylesheet\" href=\"./assets/app.css\" />
    <script type=\"importmap\">
      {
        \"imports\": {
          \"react\": \"https://esm.sh/react@18.3.1\",
          \"react-dom/client\": \"https://esm.sh/react-dom@18.3.1/client\",
          \"react-router-dom\": \"https://esm.sh/react-router-dom@6.27.0?external=react,react-dom/client\"
        }
      }
    </script>
  </head>
  <body>
    <div id=\"root\"></div>
    <script type=\"module\" src=\"./assets/app.js\"></script>
    <script>
      if (\"serviceWorker\" in navigator) {
        window.addEventListener(\"load\", () => {
          navigator.serviceWorker.register(\"/service-worker.js\").catch(() => {});
        });
      }
    </script>
  </body>
</html>
"""
    (DIST / "index.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    print(f"Building frontend with bundled esbuild {VERSION}...")
    build_assets()
    print("Frontend build complete: frontend/dist")
