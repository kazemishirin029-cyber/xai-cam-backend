from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from imageio_ffmpeg import get_ffmpeg_exe


BASE_DIR = Path(__file__).resolve().parent
CAM_DIR = (BASE_DIR.parent / "CAM").resolve()
CONVERTED_DIR = (BASE_DIR / "converted").resolve()


def convert_avi_to_mp4(source_path: Path, target_path: Path) -> tuple[bool, str]:
    try:
        with source_path.open("rb") as handle:
            handle.read(1)
    except OSError as exc:
        return False, f"source file is not locally readable ({exc})"

    ffmpeg_exe = get_ffmpeg_exe()
    command = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(source_path),
        "-movflags",
        "+faststart",
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(target_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        target_path.unlink(missing_ok=True)
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "ffmpeg failed"
        return False, detail

    if not target_path.exists() or target_path.stat().st_size == 0:
        target_path.unlink(missing_ok=True)
        return False, "target mp4 was not created"

    return True, f"{target_path.stat().st_size} bytes"


def main() -> int:
    if not CAM_DIR.exists():
        print(f"CAM directory not found: {CAM_DIR}")
        return 1
    CONVERTED_DIR.mkdir(exist_ok=True)

    folders = sorted(
        [folder for folder in CAM_DIR.iterdir() if folder.is_dir() and folder.name.isdigit()],
        key=lambda item: int(item.name),
    )

    converted = 0
    skipped = 0
    failed = 0

    for folder in folders:
        avi_files = sorted(folder.glob("*.avi"))
        if not avi_files:
            skipped += 1
            continue

        source_path = avi_files[0]
        target_dir = CONVERTED_DIR / folder.name
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / source_path.with_suffix(".mp4").name

        if target_path.exists() and target_path.stat().st_size > 0:
            print(f"[skip] {folder.name}: {target_path.name} already exists")
            skipped += 1
            continue

        ok, detail = convert_avi_to_mp4(source_path, target_path)
        if ok:
            print(f"[ok]   {folder.name}: {source_path.name} -> {target_path.name} ({detail})")
            converted += 1
        else:
            print(f"[fail] {folder.name}: {source_path.name} ({detail})")
            failed += 1

    print(f"\nDone. converted={converted} skipped={skipped} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
