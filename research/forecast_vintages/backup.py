"""Mirror the vintage archive to a second location.

The archive is git-ignored and strictly non-reproducible: nothing can rebuild a
vintage that was never captured, so a lost disk is a lost archive. This copies
what is missing at the destination and verifies it by size. It is additive only -
it never deletes at the destination, because a bug here would otherwise destroy
the one thing that cannot be recreated.

    python -m research.forecast_vintages.backup --dest "<path>"

Requires the ``archive`` extra only for the archive itself; this module uses the
standard library.
"""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from research.forecast_vintages.capture import DEFAULT_ROOT, MANIFEST_NAME, VINTAGES_DIR


@dataclass
class BackupResult:
    copied: list[str] = field(default_factory=list)
    already_present: int = 0
    verified: int = 0
    mismatched: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.mismatched


def _relative_files(root: Path) -> list[Path]:
    """Every file worth copying: the Parquet vintages and the manifest."""
    files = sorted(p for p in (root / VINTAGES_DIR).rglob("*.parquet") if p.is_file())
    manifest = root / MANIFEST_NAME
    if manifest.exists():
        files.append(manifest)
    return [p.relative_to(root) for p in files]


def back_up(source: Path = DEFAULT_ROOT, *, dest: Path) -> BackupResult:
    """Copy anything missing or size-mismatched from source to dest.

    The manifest grows on every capture, so it is always re-copied; the Parquet
    files are immutable once written, so a size match is treated as present.
    """
    result = BackupResult()
    for relative in _relative_files(source):
        src = source / relative
        dst = dest / relative
        is_manifest = relative.name == MANIFEST_NAME
        if dst.exists() and not is_manifest and dst.stat().st_size == src.stat().st_size:
            result.already_present += 1
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            result.copied.append(str(relative))
        if dst.stat().st_size == src.stat().st_size:
            result.verified += 1
        else:
            result.mismatched.append(str(relative))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--dest", type=Path, required=True, help="backup destination directory")
    args = parser.parse_args(argv)

    if not args.source.exists():
        print(f"nothing to back up: {args.source} does not exist")
        return 1

    result = back_up(args.source, dest=args.dest)
    print(f"copied          : {len(result.copied)}")
    print(f"already present : {result.already_present}")
    print(f"verified by size: {result.verified}")
    if result.mismatched:
        print(f"MISMATCHED      : {result.mismatched}")
    print(f"destination     : {args.dest}")
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
