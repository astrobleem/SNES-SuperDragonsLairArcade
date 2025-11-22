.include "src/config/config.inc"

.struct vars
  transitionId dw
  branchImmediate db
  hasTriggered db
.endst

.define ROOM_TRANSITION_TYPE.enter_room 0
.define ROOM_TRANSITION_TYPE.enter_room_left 1
.define ROOM_TRANSITION_TYPE.enter_room_right 2
.define ROOM_TRANSITION_TYPE.enter_room_up 3
.define ROOM_TRANSITION_TYPE.enter_room_down 4
.define ROOM_TRANSITION_TYPE.enter_room_upleft 5
.define ROOM_TRANSITION_TYPE.start_alive 6
.define ROOM_TRANSITION_TYPE.start_dead 7

;zp-vars
.enum 0
  iterator INSTANCEOF iteratorStruct
  event INSTANCEOF eventStruct
  this INSTANCEOF vars
  zpLen ds 0
.ende

;object class static flags, default properties and zero page
.define CLASS.FLAGS OBJECT.FLAGS.Present
.define CLASS.PROPERTIES OBJECT.PROPERTIES.isEvent
.define CLASS.ZP_LENGTH zpLen

.base BSL
.bank 0 slot 0

