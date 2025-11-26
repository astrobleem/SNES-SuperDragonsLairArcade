
file_path = 'src/config/macros.inc'

missing_macros = """
;helper macros to reduce script boilerplate for common event patterns
.macro EVENT_ACTION_PRIMARY startframe endframe result target
  ; Dirk's signature sword/interaction cue (button A)
  EVENT Event.accelerate \\1 \\2 \\3 \\4
.endm

.macro EVENT_ACTION_DEFEND startframe endframe result target
  ; Dirk's defensive/duck cue (button B)
  EVENT Event.brake \\1 \\2 \\3 \\4
.endm

.macro EVENT_DIRECTION dir startframe endframe result target
  EVENT Event.direction_\\1 \\2 \\3 \\4 \\5
.endm

.macro EVENT_CUTSCENE_FIRE_AND_FORGET name startframe endframe
  EVENT Event.\\1 \\2 \\3 EventResult.none 0
.endm

.macro EVENT_RESTART_FROM_CHECKPOINT startframe endframe
  EVENT Event.cutscene.start_dead \\1 \\2 EventResult.lastcheckpoint 0
.endm


.macro IRQ
  .if NARGS != 3
      .printt "Invalid parameter count in irq macro\\n."
      .fail
  .endif
  \\1.IRQ:
    .dw IRQ_MAGIC
    .dw \\2  ;v-pos
    .dw \\3  ;h-pos
    .ACCU 16
    .INDEX 16
.endm

.macro SPRITE_ANIMATION
  .Section "\\1.gfx_sprite.animation" superfree
	  SPRITE.\\1:
	  .incbin "build/data/sprites/\\1.gfx_sprite.animation"

  .ends
.endm

.macro BG_ANIMATION
  .Section "\\1.\\2.animation" superfree
	  BG.\\1:
	  .incbin "build/data/backgrounds/\\1.\\2.animation"

  .ends
.endm

;shorthand for error handler
.macro TRIGGER_ERROR
    .if NARGS != 1
        .printt "Fatal error in macro TRIGGER_ERROR, must have exactly one argument \\n"
        .fail
    .endif
    pea \\1
    jsr core.error.trigger
.endm

.endif
"""

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Final fix for macros.inc, truncating and appending missing macros.")
    parser.parse_args()

    with open(file_path, 'r') as f:
        lines = f.readlines()

    # Truncate at line 1330 (index 1330, since 0-indexed, line 1331 is index 1330)
    # Line 1330 in file is index 1329.
    # I want to keep lines 0 to 1329 (inclusive).
    # So lines[:1330].

    # Let's verify line 1329 (index 1329).
    # In Step 2224, line 1329 is `.endm` (closing EVENT).
    # So I want to keep up to line 1329.
    # lines[1329] is the last line I want.
    # So lines[:1330].

    new_content = lines[:1330]
    with open(file_path, 'w') as f:
        f.writelines(new_content)
        f.write(missing_macros)

    print("Fixed macros.inc")
