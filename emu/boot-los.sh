#!/usr/bin/env bash
# Boot Lisa Office System 3.1 headless, optionally insert a floppy, and save
# screenshots.
#
#   emu/boot-los.sh [floppy.dc42] [out-dir]
#
# Screenshots: <out-dir>/desktop.png (after boot), <out-dir>/floppy.png (after
# the insert; default out-dir build/emu-los/).  Emulator, ROM and LOS image:
# see emu/env.sh.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
need_emulator
need "$LISA_ROM" "Lisa ROM (LISA_ROM)"
need "$LOS_IMAGE" "Office System ProFile image (LOS_IMAGE)"

FLOPPY="${1:-}"
OUT="$(realpath -m "${2:-$LISA_C/build/emu-los}")"
mkdir -p "$OUT"
cp "$LOS_IMAGE" "$OUT/profile.image"

{
  echo "machine.boot model=\"lisa\" ram=2048 rom=\"$LISA_ROM\""
  echo "machine.hd.attach \"$OUT/profile.image\""
  # BootVol=2 (ProFile); invalid checksum makes LOS restore config from the disk's MDDF
  echo 'assert machine.hd.pram_init(2, false) "pram_init failed"'
  echo 'scheduler.run 60000000'
  echo "machine.screen.save \"$OUT/desktop.png\""
  if [ -n "$FLOPPY" ]; then
    cp "$FLOPPY" "$OUT/floppy.dc42"
    echo "machine.floppy.drive.0.insert \"$OUT/floppy.dc42\""
    echo 'scheduler.run 30000000'
    echo "machine.screen.save \"$OUT/floppy.png\""
  fi
  echo 'quit'
} > "$OUT/boot.script"

"$GS_HEADLESS" --speed=turbo rom="$LISA_ROM" model=lisa script="$OUT/boot.script" > "$OUT/boot.log" 2>&1
grep -E 'Screenshot saved|rror' "$OUT/boot.log" || true
