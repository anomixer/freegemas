        .section .text
        .global music_aux_init, music_aux_store, music_aux_page
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
        CMP #$C0
        BCC .read_aux_ram
        TAX
        CPX #$D0
        BCS .bank1
        LDA $C083
        TXA
        CLC
        ADC #$10
        BNE .set_high
.bank1:
        LDA $C08B
        TXA
.set_high:
        STA .load_lc+2
        STA $C009
        LDY #0
.load_lc:
        LDA $D000,Y
        STA music_cache,Y
        INY
        BNE .load_lc
        STA $C008
        LDA $C081
        LDA $C081
        LDA $C082
        PLP
        RTS
.read_aux_ram:
        STA $0307
        STA $C005
        STA $0307
        STA $C004
        JSR $0300
        PLP
        RTS

music_aux_store:
        PHP
        SEI
        LDA music_source
        STA .store_load+1
        STA .store_lc_load+1
        LDA music_source+1
        STA .store_load+2
        STA .store_lc_load+2

        LDA music_destination_page
        CMP #$C0
        BCC .store_aux_ram

        TAX
        CPX #$D0
        BCS .store_bank1
        LDA $C083
        LDA $C083
        TXA
        CLC
        ADC #$10
        BNE .set_store_high
.store_bank1:
        LDA $C08B
        LDA $C08B
        TXA
.set_store_high:
        STA .store_lc_write+2
        STA $C009
        LDY #0
.store_lc_loop:
.store_lc_load:
        LDA $FFFF,Y
.store_lc_write:
        STA $D000,Y
        INY
        BNE .store_lc_loop
        STA $C008
        LDA $C081
        LDA $C081
        LDA $C082
        INC music_destination_page
        PLP
        RTS

.store_aux_ram:
        STA .store_write+2
        STA $C005
        LDY #0
.store_loop:
.store_load:
        LDA $FFFF,Y
.store_write:
        STA $0800,Y
        INY
        BNE .store_loop
        STA $C004
        INC music_destination_page
        PLP
        RTS
