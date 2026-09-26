        .section .text
        .global clear_text
clear_text:
        LDA #$A0
        LDX #0
clear_text_loop:
        STA $0400,X
        STA $0500,X
        STA $0600,X
        STA $0700,X
        INX
        BNE clear_text_loop
        RTS

        .section .rodata
        .global trampoline_src, trampoline_src_end
trampoline_src:
        LDA #3
        STA $3C0
        LDX #0
loop:   LDA $B800,X
        STA $3C4
        LDA $B900,X
        STA $3C5
        LDA #0
        STA $3C2
        TXA
        ASL A
        CLC
        ADC #$30
        STA $3C3
        STX $3C9
        JSR $BF00
        .byte $80
        .word $3C0
        BCS fail
        LDX $3C9
        INX
        CPX $3C8
        BCC loop
        ; Segment calls never return. Discard their accumulated hardware
        ; return addresses as well as reinitializing the C soft stack.
        LDX #$FF
        TXS
        JMP $3000
fail:   LDA #$C6                ; visible MLI failure marker: "F"
        STA $0400
        JMP fail
trampoline_src_end:

        .section .text
        .global launch_image
launch_image:
        JMP $0300

        .section .bss
        .global scene_src, scene_count, scene_data_port
scene_src: .word 0
scene_count: .word 0
scene_data_port: .word 0

        .section .text
        .global scene_copy
; Raw scene blocks: 13 cycles/pixel for full 256-byte pages. No ZP scratch.
scene_copy:
        LDA scene_src
        STA scene_read+1
        LDA scene_src+1
        STA scene_read+2
        LDA scene_data_port
        STA scene_write+1
        LDA scene_data_port+1
        STA scene_write+2
        LDA scene_count+1
        BEQ scene_tail
scene_page:
        LDX #0
scene_page_loop:
scene_read:
        LDA $0C00,X
scene_write:
        STA $C203
        INX
        BNE scene_page_loop
        INC scene_read+2
        DEC scene_count+1
        BNE scene_page
scene_tail:
        LDA scene_count
        BEQ scene_done
        LDA scene_read+1
        STA scene_tail_read+1
        LDA scene_read+2
        STA scene_tail_read+2
        LDA scene_data_port
        STA scene_tail_write+1
        LDA scene_data_port+1
        STA scene_tail_write+2
        LDX #0
scene_tail_loop:
scene_tail_read:
        LDA $0C00,X
scene_tail_write:
        STA $C203
        INX
        CPX scene_count
        BNE scene_tail_loop
scene_done:
        RTS
