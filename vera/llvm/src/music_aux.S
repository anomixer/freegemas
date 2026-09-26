/* RAMRD switches instruction fetch too. Mirror this small $0300 reader in
 * MAIN/AUX; keep ALTZP and RAMWRT off while it runs. Loader replaces MAIN
 * $0300 on the next segment launch, after music_stop. No ProDOS vectors used.
 */
        .section .text
        .global music_aux_init, music_aux_store, music_aux_page
        .global music_read_bits
        .global music_aux_available
music_aux_available:
        PHP
        SEI
        STA $C000
        STA $C002
        STA $C004
        LDA $0800
        TAX
        EOR #$FF
        STA $C005
        STA $0800
        STA $C004
        CMP $0800
        BEQ music_no_aux
        LDA #1
        PLP
        RTS
music_no_aux:
        TXA
        STA $0800
        LDA #0
        PLP
        RTS
music_read_bits:
        TAX
        STZ music_bit_result
music_bit_loop:
        LDA music_bit_left
        BNE music_have_byte
        PHX
        JSR music_read_byte
        PLX
        STA music_bit_byte
        LDA #8
        STA music_bit_left
music_have_byte:
        ASL music_bit_byte
        ROL music_bit_result
        DEC music_bit_left
        DEX
        BNE music_bit_loop
        LDA music_bit_result
        RTS
music_aux_init:
        PHP
        SEI
        STA $C000
        STA $C002
        STA $C004
        LDX #17
music_mirror:
        LDA music_reader,X
        STA $0300,X
        STA $C005
        STA $0300,X
        STA $C004
        DEX
        BPL music_mirror
        PLP
        RTS
music_reader:
        STA $C003
        LDY #0
        LDA $0800,Y
        STA music_cache,Y
        INY
        BNE music_reader+5
        STA $C002
        RTS
music_aux_page:
        PHP
        SEI
        LDA music_page
        STA $0307
        LDA music_target
        STA $0309
        LDA music_target+1
        STA $030A
        STA $C005
        LDA music_page
        STA $0307
        LDA music_target
        STA $0309
        LDA music_target+1
        STA $030A
        STA $C004
        JSR $0300
        PLP
        RTS
music_aux_store:
        PHP
        SEI
        LDA music_source
        STA music_load+1
        LDA music_source+1
        STA music_load+2
        LDA music_destination_page
        STA music_store+2
        LDY #0
        STA $C005
music_load:
        LDA $FFFF,Y
music_store:
        STA $0800,Y
        INY
        BNE music_load
        STA $C004
        INC music_destination_page
        PLP
        RTS
        .section .bss
music_bit_result: .byte 0
