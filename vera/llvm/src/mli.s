; Minimal ProDOS READ_BLOCK bridge. C supplies unit, block and a 512-byte
; destination, so runtime assets can stream to VERA without entering RAM as
; linked data.
        .section .bss
        .global mli_unit, mli_buf_lo, mli_buf_hi, mli_blk_lo, mli_blk_hi, mli_status
mli_unit:   .byte 0
mli_buf_lo: .byte 0
mli_buf_hi: .byte 0
mli_blk_lo: .byte 0
mli_blk_hi: .byte 0
mli_status: .byte 0
mli_params: .byte 0,0,0,0,0,0,0,0
        .global mli_saved_zp
mli_saved_zp: .space 192

        .section .text
        .global mli_read_block
        .global mli_write_block
mli_write_block:
        LDA #$81
        BNE mli_setup
mli_read_block:
        LDA #$80
mli_setup:
        STA mli_command
        ; ProDOS and LLVM-MOS share zero page. Preserve compiler registers
        ; and ZP-allocated state across BOTH reads and writes.
        LDX #0
mli_save_zp:
        LDA $00,X
        STA mli_saved_zp,X
        INX
        CPX #$C0
        BNE mli_save_zp
        LDA #3
        STA mli_params
        LDA mli_unit
        STA mli_params+1
        LDA mli_buf_lo
        STA mli_params+2
        LDA mli_buf_hi
        STA mli_params+3
        LDA mli_blk_lo
        STA mli_params+4
        LDA mli_blk_hi
        STA mli_params+5
        JSR $BF00
mli_command:
        .byte $80
        .word mli_params
        STA mli_status
        LDX #0
mli_restore_zp:
        LDA mli_saved_zp,X
        STA $00,X
        INX
        CPX #$C0
        BNE mli_restore_zp
        LDA mli_status
        RTS

        ; Return control to the installed ProDOS quit handler (Bitsy Bye).
        ; No C state is needed after this non-returning operation.
        .global mli_quit
mli_quit:
        CLD
        LDX #$FF
        TXS
        LDA #0
        STA $C00C              ; 40-column text
        STA $C00E              ; primary character set
        STA $C051              ; text on
        STA $C054              ; page 1
        JSR $FB39              ; ROM SETTXT
        JSR $FC58              ; ROM HOME
        CLI
        JSR $BF00
        .byte $65
        .word quit_params
quit_returned:
        JMP quit_returned      ; QUIT does not return on success
        .section .rodata
quit_params:
        .byte 4,0
        .word 0
        .byte 0
        .word 0
