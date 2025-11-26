.include "src/config/config.inc"

;defines

.def NumOfHashptr 9





.struct vars
  _tmp ds 16
  currPC	dw	;current exec address in script
  buffFlags db	;flags.
  buffBank db		;bank. unused, just for convenience
  buffA	dw
  buffX	dw
  buffY	dw
  buffStack dw	;used to check for stack trashes
.endst
		 
;zp-vars
.enum 0
  iterator INSTANCEOF iteratorStruct
  script INSTANCEOF scriptStruct
  this INSTANCEOF vars
  hashPtr INSTANCEOF oopObjHash NumOfHashptr  
  zpLen ds 0
.ende

.def objFameText hashPtr+8
.def objBackground2 hashPtr+4
.def objFameBrightness hashPtr+12
.def objPlayer hashPtr+16
.def objBrightness hashPtr+12
.def irq.buffer.x this._tmp
.def irq.buffer.y this._tmp+2
.def currentLevel this._tmp+4
.def nextLevel this._tmp+6


;object class static flags, default properties and zero page 
.define CLASS.FLAGS OBJECT.FLAGS.Present
.define CLASS.PROPERTIES OBJECT.PROPERTIES.isScript
.define CLASS.ZP_LENGTH zpLen


.base BSL
.bank 0 slot 0


.section "scripts"
.accu 16
.index 16


.include "src/main.script"
.include "src/none.script"
.include "src/title_screen.script"
.include "src/logo_intro.script"
.include "src/hall_of_fame.script"
.include "src/msu1.script"
.include "src/score_entry.script"
.include "src/game_over.script"
.include "src/level_complete.script"
.include "data/chapters/chapter.include"
.include "src/level1.script"
.include "src/level2.script"
.include "src/level3.script"
.include "src/level4.script"
.include "src/level5.script"
.include "src/level6.script"
.include "src/level7.script"
.include "src/level8.script"
.include "src/level9.script"

.ends
