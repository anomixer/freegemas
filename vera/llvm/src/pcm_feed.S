/* Preprocessed so VERA_BASE follows the selected slot. */
        .section .text
        .global pcm_copy
        .global pcm_vram_copy
pcm_vram_copy:
        LDX pcm_count
        LDY #0
pcm_vram_next:
        LDA VERA_BASE+27
        BMI pcm_vram_done
        LDA VERA_BASE+4
        STA VERA_BASE+29
        INY
        DEX
        BNE pcm_vram_next
        CPY #0
        BNE pcm_partial
        DEC pcm_count+1
        RTS
pcm_vram_done:
        CPY #0
        BNE pcm_partial
        RTS
pcm_copy:
        LDA pcm_pointer
        STA pcm_load+1
        LDA pcm_pointer+1
        STA pcm_load+2
pcm_page:
        LDX #0
        LDA pcm_count+1
        BNE pcm_begin
        LDX pcm_count
        BEQ pcm_done
pcm_begin:
        LDY #0
pcm_next:
        LDA VERA_BASE+27
        BMI pcm_done
pcm_load:
        LDA $FFFF,Y
        STA VERA_BASE+29
        INY
        DEX
        BNE pcm_next
        CPY #0
        BNE pcm_partial
        DEC pcm_count+1
        INC pcm_load+2
        JMP pcm_page
pcm_done:
        CPY #0
        BEQ pcm_return
pcm_partial:
        TYA
        STA pcm_sent
        LDA pcm_count
        SEC
        SBC pcm_sent
        STA pcm_count
        LDA pcm_count+1
        SBC #0
        STA pcm_count+1
pcm_return:
        RTS
        .section .bss
pcm_sent: .byte 0
