.include "src/config/config.inc"

.struct vars
  buffer.window12Sel db
  buffer.windowObjSel db
  buffer.windowMainscreen db
.endst
		 
;zp-vars
.enum 0
  iterator INSTANCEOF iteratorStruct
  hdma INSTANCEOF hdmaStruct
  this INSTANCEOF vars
zpLen ds 0
.ende

;object class static flags, default properties and zero page 
.define CLASS.FLAGS OBJECT.FLAGS.Present
.define CLASS.PROPERTIES OBJECT.PROPERTIES.isHdma
.define CLASS.ZP_LENGTH zpLen

.base BSL
.bank 0 slot 0

.section "VideoMaskTable.pal" superfree

;direct, goes to W1L, W1R (window 1 position)
;224 visible lines: 16 top mask + 176 transparent + 32 bottom mask
VideoMaskTable.pal:
  .db $10, $00, $ff    ;16 lines: full-width window (black mask, top border)
  .db $7f, $01, $00    ;127 lines: empty window (transparent, video part 1)
  .db $31, $01, $00    ;49 lines: empty window (transparent, video part 2)
  .db $20, $00, $ff    ;32 lines: full-width window (black mask, bottom garbage)
  .db $00              ;end

.ends

.section "VideoMaskTable.ntsc" superfree

;224 visible lines: 16 top mask + 176 transparent + 32 bottom mask
VideoMaskTable.ntsc:
  .db $10, $00, $ff    ;16 lines: full-width window (black mask, top border)
  .db $7f, $01, $00    ;127 lines: empty window (transparent, video part 1)
  .db $31, $01, $00    ;49 lines: empty window (transparent, video part 2)
  .db $20, $00, $ff    ;32 lines: full-width window (black mask, bottom garbage)
  .db $00              ;end

.ends

