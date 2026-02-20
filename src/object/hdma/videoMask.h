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
;224 visible lines: 32 top border + 160 video + 32 bottom border (centered)
;V_SCROLL=224 shifts BG up 32px so video row 0 aligns with screen line 32
VideoMaskTable.pal:
  .db $20, $00, $ff    ;32 lines: full-width window (black mask, top border)
  .db $7f, $01, $00    ;127 lines: empty window (transparent, video part 1)
  .db $21, $01, $00    ;33 lines: empty window (transparent, video part 2)
  .db $20, $00, $ff    ;32 lines: full-width window (black mask, bottom border)
  .db $00              ;end

.ends

.section "VideoMaskTable.ntsc" superfree

;224 visible lines: 32 top border + 160 video + 32 bottom border (centered)
;V_SCROLL=224 shifts BG up 32px so video row 0 aligns with screen line 32
VideoMaskTable.ntsc:
  .db $20, $00, $ff    ;32 lines: full-width window (black mask, top border)
  .db $7f, $01, $00    ;127 lines: empty window (transparent, video part 1)
  .db $21, $01, $00    ;33 lines: empty window (transparent, video part 2)
  .db $20, $00, $ff    ;32 lines: full-width window (black mask, bottom border)
  .db $00              ;end

.ends

