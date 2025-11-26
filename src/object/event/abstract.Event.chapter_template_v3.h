.include "src/config/config.inc"

; Shared state for parameterized chapter event handlers that lean on Event.template
.struct chapterHandlerVars
  param1 ds 2
  param2 ds 2
  param3 ds 2
  param4 ds 2
.endst

;zp-vars
.enum 0
  iterator INSTANCEOF iteratorStruct
  event INSTANCEOF eventStruct
  this INSTANCEOF chapterHandlerVars
  zpLen ds 0
.ende

;object class static flags, default properties and zero page
.define CLASS.FLAGS OBJECT.FLAGS.Present
.define CLASS.PROPERTIES OBJECT.PROPERTIES.isEvent
.define CLASS.ZP_LENGTH zpLen

; Copy common call arguments and optional parameters into the handler state
.macro CHAPTER_EVENT_INIT_PARAMS
  jsr Event.template.initCommon
  .if \1 >= 1
    lda OBJECT.CALL.ARG.5,s
    sta this.param1
  .endif
  .if \1 >= 2
    lda OBJECT.CALL.ARG.6,s
    sta this.param2
  .endif
  .if \1 >= 3
    lda OBJECT.CALL.ARG.7,s
    sta this.param3
  .endif
  .if \1 >= 4
    lda OBJECT.CALL.ARG.8,s
    sta this.param4
  .endif
.endm

.base BSL
.bank 0 slot 0
