#!/usr/bin/env bash
# Install and start an Office System tool from a floppy in granny-smith.
#
#   emu/run-los-tool.sh floppy.dc42 [out-dir]
#
# The floppy holds {Tn}obj, {Tn}PHRASE and the desktop catalog that
# tools/mklisafs.py writes (make tool), which registers the tool with a
# "<name> Paper" stationery pad.  The script opens the diskette, tears off a
# document and opens it, which starts the tool with Make_Process.
#
# TOOLONLY=1: the tool has no stationery (make tool TOOLONLY=1): the script
# opens the tool's icon instead (fcNone), which on such a diskette is the
# first icon, at (70, 58); there is no 4-torn-off.png.
# Icon positions are those of a single-tool diskette (the emulator is
# deterministic).  Objects with no saved position are laid out in reverse
# catalog (name) order, so these hold for a tool whose name sorts after
# "Empty Folders": the pad at (70, 58), the tool icon at (191, 58) (opening
# that would start the tool without a document: fcNone), and the torn-off
# document "<name> Paper <date>" at (36, 55).  Screenshots: <out-dir>/{1-inserted,
# 3-diskette,4-torn-off,5-opened,6-later}.png (default build/emu-tool/).
# CLOSE=1 then chooses the tool's File/Print > "Set Aside" item (menu 1,
# item 2) and saves 7-menu.png and 8-closed.png.  PRE=file.script adds the
# file's granny-smith commands right after the machine boots, for example
# appletalk.afp.volumes.add("Name", "/host/dir") to publish a share on the
# emulated AppleTalk network.  POST=file adds commands after 6-later.png (the
# script's click(x, y) and dclick(x, y) are available).  SAVE=file.dc42 finally saves
# the diskette as the Lisa left it (granny-smith's machine.floppy.drive.0.export).
# Emulator, ROM and LOS image: see emu/env.sh.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
need_emulator
need "$LISA_ROM" "Lisa ROM (LISA_ROM)"
need "$LOS_IMAGE" "Office System ProFile image (LOS_IMAGE)"
ROM="$LISA_ROM"
OUT="$(realpath -m "${2:-$LISA_C/build/emu-tool}")"
LATER="${LATER:-200000000}"

mkdir -p "$OUT"
cp "$LOS_IMAGE" "$OUT/profile.image"
cp "$1" "$OUT/floppy.dc42"

# Opening: tear off a sheet from the pad and open it; or, for a tool without
# stationery (TOOLONLY=1, make tool's TOOLONLY), open the tool's own icon,
# the first in the diskette's window when there is no pad.
if [ -n "${TOOLONLY:-}" ]; then
  OPEN_LINES='dclick(70, 58)
scheduler.run 60000000'
else
  OPEN_LINES="dclick(70, 58)
scheduler.run 60000000
machine.screen.save \"$OUT/4-torn-off.png\"
scheduler.run 10000000
dclick(36, 55)
scheduler.run 60000000"
fi
PRE_LINES=""
if [ -n "${PRE:-}" ]; then PRE_LINES="$(cat "$PRE")"; fi
cat > "$OUT/tool.script" <<EOF
machine.boot model="lisa" ram=2048 rom="$ROM"
machine.hd.attach "$OUT/profile.image"
assert machine.hd.pram_init(2, false) "pram_init failed"
def click(x, y) {
  machine.adb.mouse.move \$x \$y "global"
  scheduler.run 2000000
  machine.adb.mouse.click true
  scheduler.run 80000
  machine.adb.mouse.click false
}
def dclick(x, y) {
  click(\$x, \$y)
  scheduler.run 120000
  machine.adb.mouse.click true
  scheduler.run 80000
  machine.adb.mouse.click false
}
$PRE_LINES
scheduler.run 60000000
machine.floppy.drive.0.insert "$OUT/floppy.dc42"
scheduler.run 40000000
machine.screen.save "$OUT/1-inserted.png"
dclick(181, 336)
scheduler.run 40000000
machine.screen.save "$OUT/3-diskette.png"
$OPEN_LINES
machine.screen.save "$OUT/5-opened.png"
scheduler.run $LATER
machine.screen.save "$OUT/6-later.png"
EOF
if [ -n "${POST:-}" ]; then
  cat "$POST" >> "$OUT/tool.script"
fi
if [ -n "${CLOSE:-}" ]; then
  cat >> "$OUT/tool.script" <<EOF
machine.adb.mouse.move 100 7 "global"
scheduler.run 3000000
machine.adb.mouse.click true
scheduler.run 3000000
machine.adb.mouse.move 120 38 "global"
scheduler.run 3000000
machine.screen.save "$OUT/7-menu.png"
machine.adb.mouse.click false
scheduler.run 150000000
machine.screen.save "$OUT/8-closed.png"
EOF
fi
if [ -n "${SAVE:-}" ]; then
  echo "machine.floppy.drive.0.export \"$(realpath -m "$SAVE")\"" >> "$OUT/tool.script"
fi
echo quit >> "$OUT/tool.script"

"$GS_HEADLESS" --speed=turbo rom="$ROM" model=lisa script="$OUT/tool.script" \
  > "$OUT/tool.log" 2>&1
grep -E 'Screenshot saved|rror' "$OUT/tool.log" || true
