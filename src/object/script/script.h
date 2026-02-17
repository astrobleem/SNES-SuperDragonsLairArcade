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
.def objFameBrightness hashPtr+20
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

;shared helper for CHAPTER macro: sets up chapter properties, reads 24-bit pointer
;to event data table from inline data after jsr, creates all event objects, returns past pointer.
;inline data after jsr: .dw eventTableAddr, .db :eventTableAddr (3 bytes)
;event data table (in superfree section): 7 words per event, terminated by .dw 0
_CHAPTER.init:
  rep #$31

  ;kill all events from previous chapter
  lda.w #OBJECT.PROPERTIES.isEvent
  jsr abstract.Iterator.kill.byProperties

  ;set chapter properties and kill other chapter scripts
  lda.w #OBJECT.PROPERTIES.isChapter
  jsr abstract.Iterator.setProperties
  jsr abstract.Iterator.killOthers

  ;read 24-bit pointer to event data table from inline data after jsr
  ;return address on stack points to last byte of jsr instruction
  lda 1,s
  inc a
  tax
  lda.l (BSL << 16),x ;low 16 bits of data table address
  sta.b this._tmp+8
  sep #$20
  lda.l (BSL << 16)+2,x ;bank byte
  sta.b this._tmp+10
  rep #$20

  ;Y = offset in data table
  ldy #0

_CHAPTER.init.eventLoop:
  ;check classPtr at current offset (24-bit indirect indexed)
  lda [this._tmp+8],y
  beq _CHAPTER.init.done

  ;save base offset and classPtr
  sty.b this._tmp+12
  sta.b this._tmp+14

  ;push 6 args in reverse order: arg1, arg0, resultTarget, result, endframe, startframe
  ;start at Y_base + 12 (arg1) and decrement by 2 for each field
  tya
  clc
  adc #12
  tay
  lda [this._tmp+8],y     ;arg1
  pha
  dey
  dey
  lda [this._tmp+8],y     ;arg0
  pha
  dey
  dey
  lda [this._tmp+8],y     ;resultTarget
  pha
  dey
  dey
  lda [this._tmp+8],y     ;result
  pha
  dey
  dey
  lda [this._tmp+8],y     ;endframe
  pha
  dey
  dey
  lda [this._tmp+8],y     ;startframe
  pha

  ;Y = classPtr, X = oopCreateNoPtr
  ldy.b this._tmp+14
  ldx.w #oopCreateNoPtr
  jsr core.object.create

  ;pop 6 args
  pla
  pla
  pla
  pla
  pla
  pla

  ;advance to next event (14 bytes per event)
  ldy.b this._tmp+12
  tya
  clc
  adc #14
  tay

  bra _CHAPTER.init.eventLoop

_CHAPTER.init.done:
  ;adjust return address past inline 3-byte pointer (.dw + .db)
  ;rts adds 1 to the address, so store retaddr+3
  lda 1,s
  clc
  adc #3
  sta 1,s
  rts


.include "src/main.script"
.include "src/none.script"
.include "src/title_screen.script"
.include "src/logo_intro.script"
.include "src/hall_of_fame.script"
.include "src/losers.script"
.include "src/msu1.script"
.include "src/score_entry.script"
.include "src/game_over.script"
.include "src/continue_screen.script"
.include "data/chapters/chapter.include"
.include "src/level1.script"

.ends
