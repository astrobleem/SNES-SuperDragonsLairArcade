.include "src/config/config.inc"

.base BSL
.bank 0 slot 0

;all chapter event data in one superfree section (linker places in any bank)
.section "chapter_event_data" superfree
.include "data/chapters/chapter_data.include"
.ends
