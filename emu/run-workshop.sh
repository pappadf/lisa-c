#!/usr/bin/env bash
# Boot the Lisa Workshop 3.0 headless, insert a floppy and run a program from
# it with the Workshop's Run command.
#
#   emu/run-workshop.sh floppy.dc42 progname [out-dir]
#
# progname is the Lisa file name without ".obj" (Run appends it); the floppy's
# volume is assumed to be "LisaC" (tools/mkdisk.sh).  Screenshots go to
# <out-dir>/{shell,run}.png (default build/emu-ws/).
#   INPUT="text\\n"   type text into the program after it has started
#   RUN_INSTR=N      instructions to run before the final screenshot
# Emulator, ROM and Workshop image: see emu/env.sh.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
need_emulator
need "$LISA_ROM" "Lisa ROM (LISA_ROM)"
need "$WORKSHOP_IMAGE" "Workshop ProFile image (WORKSHOP_IMAGE)"

FLOPPY="$(realpath "$1")"
PROG="$2"
OUT="$(realpath -m "${3:-$LISA_C/build/emu-ws}")"
VOL="${VOL:-lisac}"
RUN_INSTR="${RUN_INSTR:-60000000}"

mkdir -p "$OUT"
cp "$FLOPPY" "$OUT/floppy.dc42"

# The Lisa COPS FIFO takes at most 12 characters per keyboard.type call.
type_text() {
    local s="$1"
    while [ -n "$s" ]; do
        printf 'machine.adb.keyboard.type("%s")\nscheduler.run 3000000\n' "${s:0:10}"
        s="${s:10}"
    done
}

{
  echo "machine.boot model=\"lisa\" ram=2048 rom=\"$LISA_ROM\""
  # The image is used as-is: granny-smith keeps writes in a delta, not the file.
  echo "machine.hd.attach \"$WORKSHOP_IMAGE\""
  echo 'assert machine.hd.pram_init(2, false) "pram_init failed"'   # boot from the ProFile
  echo 'scheduler.run 160000000'                       # boot to the Workshop prompt
  echo "machine.floppy.drive.0.insert \"$OUT/floppy.dc42\""
  echo 'scheduler.run 30000000'
  echo "machine.screen.save \"$OUT/shell.png\""
  type_text "r"                                         # Run
  echo 'scheduler.run 5000000'
  type_text "-$VOL-$PROG"
  type_text '\n'
  if [ -n "${INPUT:-}" ]; then                         # text typed into the running program
    echo 'scheduler.run 20000000'
    type_text "$INPUT"
  fi
  echo "scheduler.run $RUN_INSTR"
  echo "machine.screen.save \"$OUT/run.png\""
  echo 'quit'
} > "$OUT/run.script"

"$GS_HEADLESS" --speed=turbo rom="$LISA_ROM" model=lisa script="$OUT/run.script" > "$OUT/run.log" 2>&1
grep -E 'Screenshot saved|rror' "$OUT/run.log" || true
