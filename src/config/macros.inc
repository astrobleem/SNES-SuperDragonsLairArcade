.ifndef MACROS_INC
.define MACROS_INC

;dispatch obj method. parameters: \1 pointer to obj hash \2 method .ptr to execute \3-\9 parameters(optional)
;assumes accu 16bit
.macro CALL

.if NARGS < 2
	.fail
.endif

ldx #\2
ldy #\1

.ifdefm \9
pea \9
.endif

.ifdefm \8
pea \8
.endif

.ifdefm \7
pea \7
.endif

.ifdefm \6
pea \6
.endif

.ifdefm \5
pea \5
.endif

.ifdefm \4
pea \4
.endif


.ifdefm \3
pea \3
.endif

jsr core.object.call

.ifdefm \9
pla
.endif

.ifdefm \8
pla
.endif

.ifdefm \7
pla
.endif

.ifdefm \6
pla
.endif

.ifdefm \5
pla
.endif

.ifdefm \4
pla
.endif

.ifdefm \3
pla
.endif

.endm

;create reference pointer to routine so that it can be properly be jumped at by jsr(0),x. only used for callbacks so far. should be used inside seperate callback section
.macro REGISTER_CALLBACK
.if NARGS != 1
	.fail
.endif
\1.CLB:
.dw \1
.endm

;create instance of class. parameters: \1 class pointer \2 pointer to obj hash \3 parameter to pass to class init routine(optional)
.macro NEW

.if NARGS < 2
	.fail
.endif

ldy #\1
ldx #\2


.ifdefm \9
pea \9
.endif

.ifdefm \8
pea \8
.endif

.ifdefm \7
pea \7
.endif

.ifdefm \6
pea \6
.endif

.ifdefm \5
pea \5
.endif

.ifdefm \4
pea \4
.endif

.ifdefm \3
pea \3
.endif

jsr core.object.create

.ifdefm \9
pla
.endif

.ifdefm \8
pla
.endif

.ifdefm \7
pla
.endif

.ifdefm \6
pla
.endif

.ifdefm \5
pla
.endif

.ifdefm \4
pla
.endif

.ifdefm \3
pla
.endif

.endm

;create instance of class. parameters: \1 class pointer \2 pointer to obj hash \3 parameter to pass to class init routine(optional)
;this version does not pass a pointer to the object hash, but uses the object hash directly
.macro NEW_NOPTR

.if NARGS < 2
	.fail
.endif

ldy #\1
ldx \2


.ifdefm \9
pea \9
.endif

.ifdefm \8
pea \8
.endif

.ifdefm \7
pea \7
.endif

.ifdefm \6
pea \6
.endif

.ifdefm \5
pea \5
.endif

.ifdefm \4
pea \4
.endif

.ifdefm \3
pea \3
.endif

jsr core.object.create

.ifdefm \9
pla
.endif

.ifdefm \8
pla
.endif

.ifdefm \7
pla
.endif

.ifdefm \6
pla
.endif

.ifdefm \5
pla
.endif

.ifdefm \4
pla
.endif

.ifdefm \3
pla
.endif

.endm

;delete object. parameters: \1 pointer to obj hash
.macro DELETE
.if NARGS != 1
	.fail
.endif

ldx #\1
jsr core.object.delete
.endm

;terminate script, do some garbage collection aswell
.macro DIE
	jmp terminateScript
.endm

;terminate call, don't do any garbage collection
.macro RETURN
	rts

.endm

;wait for equation(two variables) to become true. If not true, save current PC and return, then try again next frame
.macro WAIT
.if NARGS != 3
	.fail
.endif
	jsr SavePC
	lda.w \1
	cmp.w \3

.if ">" == \2
	bcc Wait\@
	
WaitOkStep\@:
	bne WaitOk\@
.endif

.if ">=" == \2
	bcs WaitOk\@
.endif

.if "<=" == \2
	beq WaitOk\@
	bcc WaitOk\@
.endif

.if "<" == \2
	bcc WaitOk\@
.endif

.if "==" == \2
	beq WaitOk\@
.endif

.if "!=" == \2
	bne WaitOk\@
.endif

Wait\@:
	rts
	
WaitOk\@:
.endm

;yet another hack because wla is too fucking, fucking stupid to differentiate between immediate and adress values supplied as macro arguments
;no idea how long I can still take this crap...
;wait for equation(two variables) to become true. If not true, save current PC and return, then try again next frame
.macro WAIT_IMMEDIATE
.if NARGS != 3
	.fail
.endif
	jsr SavePC
	lda.w \1
	cmp.w #\3

.if ">" == \2
	bcc WaitI\@
	
WaitIOkStep\@:
	bne WaitIOk\@
.endif

.if ">=" == \2
	bcs WaitIOk\@
.endif

.if "<=" == \2
	beq WaitIOk\@
	bcc WaitIOk\@
.endif

.if "<" == \2
	bcc WaitIOk\@
.endif

.if "==" == \2
	beq WaitIOk\@
.endif

.if "!=" == \2
	bne WaitIOk\@
.endif

WaitI\@:
	rts
	
WaitIOk\@:
.endm

;1 parameter, song file
.macro SONG
.if NARGS != 1
	.fail
.endif

Song.\1:
	.dw Song.\1.EOF - Song.\1
	;.dw 0
	.incbin "build/data/songs/\1.spcmod"
Song.\1.EOF:
.endm

;creates a 3-byte pointer and a definition of pointernumber in table: label.PTR
;params: 1=pointer table base 2=target label
.macro PTRLONG
PtrLong\1\@:
	.dw \2
	.db :\2 
.ifndef \2.PTR	;define only once 
	.define "\2.PTR" (PtrLong\1\@ - \1 )/3
	.export \2.PTR
.endif
.endm

;creates a 2-byte pointer and a definition of pointernumber in table: label.PTR
;params: 1=pointer table base 2=target label
.macro PTRNORM
PtrNorm\1\@:
	.dw \2 
	.define "\2.PTR" (PtrNorm\1\@ - \1 )/2
	.export \2.PTR
.endm

;creates oop object class. parameters: 1=class name 2-9: additional routines
;object id = \1.OBJID
.macro CLASS
	.if NARGS < 1
		.printt "Fatal error in macro CLASS, not enough arguments for class \n"
		.fail
	.endif
  .ifdef CLASS.IMPLEMENTS
    .if CLASS.IMPLEMENTS == interface.dimension
    \1.CLS:
    relative\1:
	    .db CLASS.FLAGS
	    .dw OBJID.\1	;object id
	    .db CLASS.ZP_LENGTH	;zero page ram buffer length
	    .dw CLASS.PROPERTIES	;default properties, disabled for now.
	    .db NARGS + 2 + 4
	    .db T_CLSS_\1-relative\1
	
	    .define \1.init.MTD 0
	    .export \1.init.MTD
      ;fall back to default interface routine if not defined in current class scope
      .ifndef __init
        .dw interface.default.init
      .else
	      .dw _init
      .endif
	    .db T_CLSS_init_\1-relative\1

	    .define \1.play.MTD 1
	    .export \1.play.MTD
      ;fall back to default interface routine if not defined in current class scope
      .ifndef __play
        .dw interface.default.play
      .else
	      .dw _play
      .endif
	    .db T_CLSS_play_\1-relative\1

	    .define \1.kill.MTD 2
	    .export \1.kill.MTD
      ;fall back to default interface routine if not defined in current class scope
      .ifndef __kill
        .dw interface.default.kill
      .else
	      .dw _kill
      .endif
	    .db T_CLSS_kill_\1-relative\1

	    .define \1.getDimension.MTD 3
	    .export \1.getDimension.MTD
      ;fall back to default interface routine if not defined in current class scope
      .ifndef __getDimension
        .dw interface.dimension.getSize
      .else
	      .dw _getDimension
      .endif
	    .db T_CLSS_getDimension_\1-relative\1

	    .define \1.setDimension.MTD 4
	    .export \1.setDimension.MTD
      ;fall back to default interface routine if not defined in current class scope
      .ifndef __setDimension
        .dw interface.dimension.setSize
      .else
	      .dw _setDimension
      .endif
	    .db T_CLSS_setDimension_\1-relative\1

	    .define \1.setPosition.MTD 5
	    .export \1.setPosition.MTD
      ;fall back to default interface routine if not defined in current class scope
      .ifndef __setPosition
        .dw interface.dimension.setPosition
      .else
	      .dw _setPosition
      .endif
	    .db T_CLSS_setPosition_\1-relative\1

	    .define \1.getPosition.MTD 6
	    .export \1.getPosition.MTD
      ;fall back to default interface routine if not defined in current class scope
      .ifndef __getPosition
        .dw interface.dimension.getPosition
      .else
	      .dw _getPosition
      .endif
	    .db T_CLSS_getPosition_\1-relative\1
        
        .define \1.translate.MTD 16
        .export \1.translate.MTD
        .dw interface.dimension.translate
        .db T_CLSS_translate_\1-relative\1

      ;additional methods
	    .ifdefm \2
        .define \1.\2.MTD 7
        .export \1.\2.MTD
	      .dw _\2
	      .db T_CLSS_\2_\1-relative\1
	    .endif
	    .ifdefm \3
        .define \1.\3.MTD 8
        .export \1.\3.MTD
	      .dw _\3
	      .db T_CLSS_\3_\1-relative\1
	    .endif
	    .ifdefm \4
        .define \1.\4.MTD 9
        .export \1.\4.MTD
	      .dw _\4
	      .db T_CLSS_\4_\1-relative\1
	    .endif
	    .ifdefm \5
        .define \1.\5.MTD 10
        .export \1.\5.MTD
	      .dw _\5
	      .db T_CLSS_\5_\1-relative\1
	    .endif
	    .ifdefm \6
        .define \1.\6.MTD 11
        .export \1.\6.MTD
	      .dw _\6
	      .db T_CLSS_\6_\1-relative\1
	    .endif
	    .ifdefm \7
        .define \1.\7.MTD 12
        .export \1.\7.MTD
	      .dw _\7
	      .db T_CLSS_\7_\1-relative\1
	    .endif
	    .ifdefm \8
        .define \1.\8.MTD 13
        .export \1.\8.MTD
	      .dw _\8
	      .db T_CLSS_\8_\1-relative\1
	    .endif
	    .ifdefm \9
        .define \1.\9.MTD 14
        .export \1.\9.MTD
	      .dw _\9
	      .db T_CLSS_\9_\1-relative\1
	    .endif

    T_CLSS_\1:
	    .db "\1",0

    T_CLSS_init_\1:
	    .db "init",0

    T_CLSS_play_\1:
	    .db "play",0

    T_CLSS_kill_\1:
	    .db "kill",0

    T_CLSS_getDimension_\1:
      .db "getDimension",0
    T_CLSS_setDimension_\1:
      .db "setDimension",0
    T_CLSS_setPosition_\1:
      .db "setPosition",0
    T_CLSS_getPosition_\1:
      .db "getPosition",0
    T_CLSS_translate_\1:
      .db "translate",0

	    .ifdefm \2
    T_CLSS_\2_\1:
	    .db "\2",0
	    .endif

	    .ifdefm \3
    T_CLSS_\3_\1:
	    .db "\3",0
	    .endif

	    .ifdefm \4
    T_CLSS_\4_\1:
	    .db "\4",0
	    .endif

	    .ifdefm \5
    T_CLSS_\5_\1:
	    .db "\5",0
	    .endif

	    .ifdefm \6
    T_CLSS_\6_\1:
	    .db "\6",0
	    .endif

	    .ifdefm \7
    T_CLSS_\7_\1:
	    .db "\7",0
	    .endif

	    .ifdefm \8
    T_CLSS_\8_\1:
	    .db "\8",0
	    .endif

	    .ifdefm \9
    T_CLSS_\9_\1:
	    .db "\9",0
	    .endif

    .endif
  .else
    ;default class implementation
    \1.CLS:
    relative\1:
	    .db CLASS.FLAGS
	    .dw OBJID.\1	;object id
	    .db CLASS.ZP_LENGTH	;zero page ram buffer length
	    .dw CLASS.PROPERTIES	;default properties, disabled for now.
	    .db NARGS + 2
	    .db T_CLSS_\1-relative\1
	
	    .define \1.init.MTD 0
	    .export \1.init.MTD
      ;fall back to default interface routine if not defined in current class scope
      .ifndef __init
        .dw interface.default.init
      .else
	      .dw _init
      .endif
	    .db T_CLSS_init_\1-relative\1

	    .define \1.play.MTD 1
	    .export \1.play.MTD
      ;fall back to default interface routine if not defined in current class scope
      .ifndef __play
        .dw interface.default.play
      .else
	      .dw _play
      .endif
	    .db T_CLSS_play_\1-relative\1

	    .define \1.kill.MTD 2
	    .export \1.kill.MTD
      ;fall back to default interface routine if not defined in current class scope
      .ifndef __kill
        .dw interface.default.kill
      .else
	      .dw _kill
      .endif
	    .db T_CLSS_kill_\1-relative\1

      ;additional methods
	    .ifdefm \2
		    .define \1.\2.MTD 3
		    .export \1.\2.MTD
		    .dw _\2
		    .db T_CLSS_\2_\1-relative\1
	    .endif

	    .ifdefm \3
		    .define \1.\3.MTD 4
		    .export \1.\3.MTD
		    .dw _\3
		    .db T_CLSS_\3_\1-relative\1
	    .endif
	
	    .ifdefm \4
		    .define \1.\4.MTD 5
		    .export \1.\4.MTD
		    .dw _\4
		    .db T_CLSS_\4_\1-relative\1
	    .endif
	
	    .ifdefm \5
		    .define \1.\5.MTD 6
		    .export \1.\5.MTD
		    .dw _\5
		    .db T_CLSS_\5_\1-relative\1
	    .endif

	    .ifdefm \6
		    .define \1.\6.MTD 7
		    .export \1.\6.MTD
		    .dw _\6
		    .db T_CLSS_\6_\1-relative\1
	    .endif

	    .ifdefm \7
		    .define \1.\7.MTD 8
		    .export \1.\7.MTD
		    .dw _\7
		    .db T_CLSS_\7_\1-relative\1
	    .endif

	    .ifdefm \8
		    .define \1.\8.MTD 9
		    .export \1.\8.MTD
		    .dw _\8
		    .db T_CLSS_\8_\1-relative\1
	    .endif

	    .ifdefm \9
		    .define \1.\9.MTD 10
		    .export \1.\9.MTD
		    .dw _\9
		    .db T_CLSS_\9_\1-relative\1
	    .endif


    T_CLSS_\1:
	    .db "\1",0

    T_CLSS_init_\1:
	    .db "init",0

    T_CLSS_play_\1:
	    .db "play",0

    T_CLSS_kill_\1:
	    .db "kill",0

	    .ifdefm \2
    T_CLSS_\2_\1:
	    .db "\2",0
	    .endif

	    .ifdefm \3
    T_CLSS_\3_\1:
	    .db "\3",0
	    .endif

	    .ifdefm \4
    T_CLSS_\4_\1:
	    .db "\4",0
	    .endif

	    .ifdefm \5
    T_CLSS_\5_\1:
	    .db "\5",0
	    .endif

	    .ifdefm \6
    T_CLSS_\6_\1:
	    .db "\6",0
	    .endif

	    .ifdefm \7
    T_CLSS_\7_\1:
	    .db "\7",0
	    .endif

	    .ifdefm \8
    T_CLSS_\8_\1:
	    .db "\8",0
	    .endif

	    .ifdefm \9
    T_CLSS_\9_\1:
	    .db "\9",0
	    .endif

  .endif
.endm

;creates oop object class. parameters: 1=class name 2-9: additional routines
;object id = \1.OBJID
;this version does not export the method definitions, useful for private classes
.macro CLASS_NOEXPORT
	.if NARGS < 1
		.printt "Fatal error in macro CLASS, not enough arguments for class \n"
		.fail
	.endif
  .ifdef CLASS.IMPLEMENTS
    .if CLASS.IMPLEMENTS == interface.dimension
    \1.CLS:
    relative\1:
	    .db CLASS.FLAGS
	    .dw OBJID.\1	;object id
	    .db CLASS.ZP_LENGTH	;zero page ram buffer length
	    .dw CLASS.PROPERTIES	;default properties, disabled for now.
	    .db NARGS + 2 + 4
	    .db T_CLSS_\1-relative\1
	
      ;fall back to default interface routine if not defined in current class scope
      .ifndef __init
        .dw interface.default.init
      .else
	      .dw _init
      .endif
	    .db T_CLSS_init_\1-relative\1

      ;fall back to default interface routine if not defined in current class scope
      .ifndef __play
        .dw interface.default.play
      .else
	      .dw _play
      .endif
	    .db T_CLSS_play_\1-relative\1

      ;fall back to default interface routine if not defined in current class scope
      .ifndef __kill
        .dw interface.default.kill
      .else
	      .dw _kill
      .endif
	    .db T_CLSS_kill_\1-relative\1

      ;fall back to default interface routine if not defined in current class scope
      .ifndef __getDimension
        .dw interface.dimension.getDimension
      .else
	      .dw _getDimension
      .endif
	    .db T_CLSS_getDimension_\1-relative\1

      ;fall back to default interface routine if not defined in current class scope
      .ifndef __setDimension
        .dw interface.dimension.setDimension
      .else
	      .dw _setDimension
      .endif
	    .db T_CLSS_setDimension_\1-relative\1

      ;fall back to default interface routine if not defined in current class scope
      .ifndef __setPosition
        .dw interface.dimension.setPosition
      .else
	      .dw _setPosition
      .endif
	    .db T_CLSS_setPosition_\1-relative\1

      ;fall back to default interface routine if not defined in current class scope
      .ifndef __getPosition
        .dw interface.dimension.getPosition
      .else
	      .dw _getPosition
      .endif
	    .db T_CLSS_getPosition_\1-relative\1

      ;additional methods
	    .ifdefm \2
	      .dw _\2
	      .db T_CLSS_\2_\1-relative\1
	    .endif
	    .ifdefm \3
	      .dw _\3
	      .db T_CLSS_\3_\1-relative\1
	    .endif
	    .ifdefm \4
	      .dw _\4
	      .db T_CLSS_\4_\1-relative\1
	    .endif
	    .ifdefm \5
	      .dw _\5
	      .db T_CLSS_\5_\1-relative\1
	    .endif
	    .ifdefm \6
	      .dw _\6
	      .db T_CLSS_\6_\1-relative\1
	    .endif
	    .ifdefm \7
	      .dw _\7
	      .db T_CLSS_\7_\1-relative\1
	    .endif
	    .ifdefm \8
	      .dw _\8
	      .db T_CLSS_\8_\1-relative\1
	    .endif
	    .ifdefm \9
	      .dw _\9
	      .db T_CLSS_\9_\1-relative\1
	    .endif

    T_CLSS_\1:
	    .db "\1",0

    T_CLSS_init_\1:
	    .db "init",0

    T_CLSS_play_\1:
	    .db "play",0

    T_CLSS_kill_\1:
	    .db "kill",0

    T_CLSS_getDimension_\1:
      .db "getDimension",0
    T_CLSS_setDimension_\1:
      .db "setDimension",0
    T_CLSS_setPosition_\1:
      .db "setPosition",0
    T_CLSS_getPosition_\1:
      .db "getPosition",0

	    .ifdefm \2
    T_CLSS_\2_\1:
	    .db "\2",0
	    .endif

	    .ifdefm \3
    T_CLSS_\3_\1:
	    .db "\3",0
	    .endif

	    .ifdefm \4
    T_CLSS_\4_\1:
	    .db "\4",0
	    .endif

	    .ifdefm \5
    T_CLSS_\5_\1:
	    .db "\5",0
	    .endif

	    .ifdefm \6
    T_CLSS_\6_\1:
	    .db "\6",0
	    .endif

	    .ifdefm \7
    T_CLSS_\7_\1:
	    .db "\7",0
	    .endif

	    .ifdefm \8
    T_CLSS_\8_\1:
	    .db "\8",0
	    .endif

	    .ifdefm \9
    T_CLSS_\9_\1:
	    .db "\9",0
	    .endif
    
    .endif
  .else
    ;default class implementation
    \1.CLS:
    relative\1:
	    .db CLASS.FLAGS
	    .dw OBJID.\1	;object id
	    .ifdefm \7
    T_CLSS_\7_\1:
	    .db "\7",0
	    .endif

	    .ifdefm \8
    T_CLSS_\8_\1:
	    .db "\8",0
	    .endif

	    .ifdefm \9
    T_CLSS_\9_\1:
	    .db "\9",0
	    .endif

  .endif
.endm

;creates oop object class. parameters: 1=class name 2-9: additional routines
;object id = \1.OBJID
;this version does not export the method definitions, useful for private classes

;creates oop object class. parameters: 1=class name 2-9: additional routines
;object id = \1.OBJID
;this version does not export the method definitions, useful for private classes
;this version does not generate the class header, useful for classes that are just a collection of methods
.macro CLASS_NOHEADER
	.if NARGS < 1
		.printt "Fatal error in macro CLASS, not enough arguments for class \n"
		.fail
	.endif
  .ifdef CLASS.IMPLEMENTS
    .if CLASS.IMPLEMENTS == interface.dimension
    \1.CLS:
    relative\1:
	    .db CLASS.FLAGS
	    .dw OBJID.\1	;object id
	    .db CLASS.ZP_LENGTH	;zero page ram buffer length
	    .dw CLASS.PROPERTIES	;default properties, disabled for now.
	    .db NARGS + 2 + 4
	    .db T_CLSS_\1-relative\1
	
      ;fall back to default interface routine if not defined in current class scope
      .ifndef __init
        .dw interface.default.init
      .else
	      .dw _init
      .endif
	    .db T_CLSS_init_\1-relative\1

      ;fall back to default interface routine if not defined in current class scope
      .ifndef __play
        .dw interface.default.play
      .else
	      .dw _play
      .endif
	    .db T_CLSS_play_\1-relative\1

      ;fall back to default interface routine if not defined in current class scope
      .ifndef __kill
        .dw interface.default.kill
      .else
	      .dw _kill
      .endif
	    .db T_CLSS_kill_\1-relative\1

      ;fall back to default interface routine if not defined in current class scope
      .ifndef __getDimension
        .dw interface.dimension.getDimension
      .else
	      .dw _getDimension
      .endif
	    .db T_CLSS_getDimension_\1-relative\1

      ;fall back to default interface routine if not defined in current class scope
      .ifndef __setDimension
        .dw interface.dimension.setDimension
      .else
	      .dw _setDimension
      .endif
	    .db T_CLSS_setDimension_\1-relative\1

      ;fall back to default interface routine if not defined in current class scope
      .ifndef __setPosition
        .dw interface.dimension.setPosition
      .else
	      .dw _setPosition
      .endif
	    .db T_CLSS_setPosition_\1-relative\1

      ;fall back to default interface routine if not defined in current class scope
      .ifndef __getPosition
        .dw interface.dimension.getPosition
      .else
	      .dw _getPosition
      .endif
	    .db T_CLSS_getPosition_\1-relative\1

      ;additional methods
	    .ifdefm \2
	      .dw _\2
	      .db T_CLSS_\2_\1-relative\1
	    .endif
	    .ifdefm \3
	      .dw _\3
	      .db T_CLSS_\3_\1-relative\1
	    .endif
	    .ifdefm \4
	      .dw _\4
	      .db T_CLSS_\4_\1-relative\1
	    .endif
	    .ifdefm \5
	      .dw _\5
	      .db T_CLSS_\5_\1-relative\1
	    .endif
	    .ifdefm \6
	      .dw _\6
	      .db T_CLSS_\6_\1-relative\1
	    .endif
	    .ifdefm \7
	      .dw _\7
	      .db T_CLSS_\7_\1-relative\1
	    .endif
	    .ifdefm \8
	      .dw _\8
	      .db T_CLSS_\8_\1-relative\1
	    .endif
	    .ifdefm \9
	      .dw _\9
	      .db T_CLSS_\9_\1-relative\1
	    .endif

    T_CLSS_\1:
	    .db "\1",0

    T_CLSS_init_\1:
	    .db "init",0

    T_CLSS_play_\1:
	    .db "play",0

    T_CLSS_kill_\1:
	    .db "kill",0

    T_CLSS_getDimension_\1:
      .db "getDimension",0
    T_CLSS_setDimension_\1:
      .db "setDimension",0
    T_CLSS_setPosition_\1:
      .db "setPosition",0
    T_CLSS_getPosition_\1:
      .db "getPosition",0

	    .ifdefm \2
    T_CLSS_\2_\1:
	    .db "\2",0
	    .endif

	    .ifdefm \3
    T_CLSS_\3_\1:
	    .db "\3",0
	    .endif

	    .ifdefm \4
    T_CLSS_\4_\1:
	    .db "\4",0
	    .endif

	    .ifdefm \5
    T_CLSS_\5_\1:
	    .db "\5",0
	    .endif

	    .ifdefm \6
    T_CLSS_\6_\1:
	    .db "\6",0
	    .endif

	    .ifdefm \7
    T_CLSS_\7_\1:
	    .db "\7",0
	    .endif

	    .ifdefm \8
    T_CLSS_\8_\1:
	    .db "\8",0
	    .endif

	    .ifdefm \9
    T_CLSS_\9_\1:
	    .db "\9",0
	    .endif
    
    .endif
  .else
    ;default class implementation
    \1.CLS:
    relative\1:
	    .db CLASS.FLAGS
	    .dw OBJID.\1	;object id
	
      ;fall back to default interface routine if not defined in current class scope
      .ifndef __init
        .dw interface.default.init
      .else
	      .dw _init
      .endif
	    .db T_CLSS_init_\1-relative\1

      ;fall back to default interface routine if not defined in current class scope
      .ifndef __play
        .dw interface.default.play
      .else
	      .dw _play
      .endif
	    .db T_CLSS_play_\1-relative\1

      ;fall back to default interface routine if not defined in current class scope
      .ifndef __kill
        .dw interface.default.kill
      .else
	      .dw _kill
      .endif
	    .db T_CLSS_kill_\1-relative\1

      ;additional methods
	    .ifdefm \2
	      .dw _\2
	      .db T_CLSS_\2_\1-relative\1
	    .endif
	    .ifdefm \3
	      .dw _\3
	      .db T_CLSS_\3_\1-relative\1
	    .endif
	    .ifdefm \4
	      .dw _\4
	      .db T_CLSS_\4_\1-relative\1
	    .endif
	    .ifdefm \5
	      .dw _\5
	      .db T_CLSS_\5_\1-relative\1
	    .endif
	    .ifdefm \6
	      .dw _\6
	      .db T_CLSS_\6_\1-relative\1
	    .endif
	    .ifdefm \7
	      .dw _\7
	      .db T_CLSS_\7_\1-relative\1
	    .endif
	    .ifdefm \8
	      .dw _\8
	      .db T_CLSS_\8_\1-relative\1
	    .endif
	    .ifdefm \9
	      .dw _\9
	      .db T_CLSS_\9_\1-relative\1
	    .endif

    T_CLSS_\1:
	    .db "\1",0

    T_CLSS_init_\1:
	    .db "init",0

    T_CLSS_play_\1:
	    .db "play",0

    T_CLSS_kill_\1:
	    .db "kill",0

	    .ifdefm \2
    T_CLSS_\2_\1:
	    .db "\2",0
	    .endif

	    .ifdefm \3
    T_CLSS_\3_\1:
	    .db "\3",0
	    .endif

	    .ifdefm \4
    T_CLSS_\4_\1:
	    .db "\4",0
	    .endif

	    .ifdefm \5
    T_CLSS_\5_\1:
	    .db "\5",0
	    .endif

	    .ifdefm \6
    T_CLSS_\6_\1:
	    .db "\6",0
	    .endif

	    .ifdefm \7
    T_CLSS_\7_\1:
	    .db "\7",0
	    .endif

	    .ifdefm \8
    T_CLSS_\8_\1:
	    .db "\8",0
	    .endif

	    .ifdefm \9
    T_CLSS_\9_\1:
	    .db "\9",0
	    .endif
  .endif
.endm

;parameters: 1=file label 2=file path 3=read length
;returns \1.LEN filelength
.macro FILEINC
\1:
	.ifdefm \3
		.incbin \2 read \3 fsize \1.LEN
	.else
		.incbin \2 fsize \1.LEN
	.endif
	.export \1.LEN
.endm

;sa1 manual filler
.macro FILLMACRO
sta.w (\@~$ff)&$ff,x
.endm

.macro FILLMACRO16BIT
sta.w ((\@*2)~$ff)&$ff,x
.endm

;sa1 dma color fill
.macro DMAFILL
.rept 256
.db \@
.endr
.endm

;self-modifying sa1 code \1:target adress label \2:opcode \3:parameter. Warning! Keep in mind different length depending on accu mode!
.macro SA1_SELFMOD_16BIT
  .if NARGS > 3
	  .fail
  .endif
  .if NARGS < 2
	  .fail
  .endif

	lda.w #\2
	sta.w \1 -Sa1CodeStart +IramCodeDummy

  .if NARGS == 3	;only write parameter if supplied
	lda.w #\3
	sta.w \1 +1 -Sa1CodeStart +IramCodeDummy
  .endif
.endm

;self-modifying sa1 code \1:target adress label \2:opcode \3:parameter. Warning! Keep in mind different length depending on accu mode!
.macro SA1_SELFMOD_8BIT
  .if NARGS > 3
	  .fail
  .endif
  .if NARGS < 2
	  .fail
  .endif

	lda.b #\2
	sta.w \1 -Sa1CodeStart +IramCodeDummy

  .if NARGS == 3	;only write parameter if supplied
	lda.b # < \3
	sta.w \1 +1 -Sa1CodeStart +IramCodeDummy
;	lda.b # > \3
;	sta.w \1 +2 -Sa1CodeStart +IramCodeDummy

  .endif
.endm

;the only reason this exists is because wla dx's conditional functions are unable to detect whether a label has been previously declared/defined or not.
;declares label in local scope, then does a (normally redundant) define so that already-defined labels can be detected.
.macro METHOD
  .if NARGS != 1
	.fail
  .endif

  .define __\1
  _\1:

.endm

.macro DEFAULT_METHOD
  .if NARGS != 1
	.fail
  .endif

  .ifndef __\1
	.define __\1
	_\1:
;  .endif
.endm

;nope, no includes inside macros for you, sir!
/*.macro INHERIT_DEFAULT_OBJECT_METHODS
  .include "src/object/default.inheritance"
.endm*/

;script definition
.macro SCRIPT
  .if NARGS != 1
	.fail
  .endif
  \1:
  .dw SCRIPT_MAGIC
.endm

;msu1 chapter definition for auto-generated chapter event script files
;defines chapter name 
.macro CHAPTER
  .if NARGS != 1
	.fail
  .endif
	.ACCU 16
	;using below macro crashes wla-dx, stupid piece of junk
	;SCRIPT \1
	\1:
	.dw SCRIPT_MAGIC

 
  lda.w #OBJECT.PROPERTIES.isChapter
  jsr abstract.Iterator.setProperties
  ;kill all pending scripts except for the one that instanciated this chapter. maybe do this inside the CHAPTER macro instead?
  ;lda.w #OBJECT.PROPERTIES.isChapter
  jsr abstract.Iterator.killOthers


.endm

;msu1 chapter event definition for auto-generated chapter event script files
;calls event
;macro parameters: \1: event name \2: event startframe(chapter-relative) \3: event endframe(chapter-relative) \4: result(what action to trigger when event completes) \5: result target(parameter to \4) \6,\7,\8: parameters, 0 if void
;argument order inside event instances is always:
;  startframe (OBJECT.CALL.ARG.1,s)
;  endframe   (OBJECT.CALL.ARG.2,s)
;  result     (OBJECT.CALL.ARG.3,s)
;  resultTarget (OBJECT.CALL.ARG.4,s)
.macro EVENT

  lda.w #\2
  jsr GLOBAL.checkFrameReachedSavePc

.endm


;helper macros to reduce script boilerplate for common event patterns
.macro EVENT_ACTION_PRIMARY startframe endframe result target
  ; Dirk's signature sword/interaction cue (button A)
  EVENT Event.accelerate \1 \2 \3 \4
.endm

.macro EVENT_ACTION_DEFEND startframe endframe result target
  ; Dirk's defensive/duck cue (button B)
  EVENT Event.brake \1 \2 \3 \4
.endm

.macro EVENT_DIRECTION dir startframe endframe result target
  EVENT Event.direction_\1 \2 \3 \4 \5
.endm

.macro EVENT_CUTSCENE_FIRE_AND_FORGET name startframe endframe
  EVENT Event.\1 \2 \3 EventResult.none 0
.endm

.macro EVENT_RESTART_FROM_CHECKPOINT startframe endframe
  EVENT Event.cutscene.start_dead \1 \2 EventResult.lastcheckpoint 0
.endm


.macro IRQ
  .if NARGS != 3
      .printt "Invalid parameter count in irq macro\n."
      .fail
  .endif
  \1.IRQ:
    .dw IRQ_MAGIC
    .dw \2  ;v-pos
    .dw \3  ;h-pos
    .ACCU 16
    .INDEX 16
.endm

.macro SPRITE_ANIMATION
  .Section "\1.gfx_sprite.animation" superfree
	  SPRITE.\1:
	  .incbin "build/data/sprites/\1.gfx_sprite.animation"

  .ends
.endm

.macro BG_ANIMATION
  .Section "\1.\2.animation" superfree
	  BG.\1:
	  .incbin "build/data/backgrounds/\1.\2.animation"

  .ends
.endm

;shorthand for error handler
.macro TRIGGER_ERROR
    .if NARGS != 1
        .printt "Fatal error in macro TRIGGER_ERROR, must have exactly one argument \n"
        .fail
    .endif
    pea \1
    jsr core.error.trigger
.endm

.endif
