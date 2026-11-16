    .text
    .global iigs_enable_shr

iigs_enable_shr:
    ; Switch to native mode but KEEP 8-bit accumulator
    clc
    .byte $FB       ; xce
    
    ; Turn on SHR Mode in $E0C029
    lda #$81
    .byte $8F       ; STA long
    .word $C029
    .byte $E0
    
    ; Switch back to 8-bit emulation mode
    sec
    .byte $FB       ; xce
    rts
