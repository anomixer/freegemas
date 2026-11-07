/* Preprocessed so VERA_BASE follows the selected slot.
 *
 * pcm_copy    copy pcm_count bytes from pcm_pointer into the PCM FIFO.  The
 *             count is 16-bit because one 16-bit music run is 266/268 bytes.
 * pcm_mix     add pcm_count effect bytes at pcm_effect to the 8-bit music bytes
 *             at pcm_pointer (effects-only mode).
 * pcm_mix16   add an 8-bit effect byte (as the high byte of a signed 16-bit
 *             sample) to each little-endian 16-bit music sample.  Music gain
 *             0.55 and effects <=0.29 leave headroom, so no clipping is needed.
 *
 * The runs may straddle a 256-byte page: X/Y carry the low byte and the patched
 * high byte is incremented when the index wraps.  The FIFO is probed before
 * every byte so a near-full FIFO cannot overrun; pcm_count keeps what was not
 * sent and the caller retries it.
 */
        .section .text
        .global pcm_copy
        .global pcm_mix
        .global pcm_mix16
pcm_copy:
        ; A 16-bit FIFO accepts complete two-byte samples.  Check for room only
        ; before each pair and never split a pair across calls: splitting a
        ; sample shifted every later word and produced the loud noise bursts.
        LDA pcm_pointer
        STA pcm_src_lo
        LDA pcm_pointer+1
        STA pcm_src_hi
        LDA pcm_count
        STA pcm_left
        LDA pcm_count+1
        STA pcm_left+1

copy_loop:
        LDA pcm_left+1
        BNE copy_have_word
        LDA pcm_left
        CMP #2
        BCC copy_done
copy_have_word:
        LDA VERA_BASE+27
        BMI copy_done
        JSR pcm_byte
        JSR pcm_byte
        LDA pcm_left
        SEC
        SBC #2
        STA pcm_left
        LDA pcm_left+1
        SBC #0
        STA pcm_left+1
        JMP copy_loop

copy_done:
        LDA pcm_left
        STA pcm_count
        LDA pcm_left+1
        STA pcm_count+1
        RTS

pcm_byte:
        LDA pcm_src_hi
        STA pcm_byte_load+2
        LDY pcm_src_lo
pcm_byte_load:
        LDA $FF00,Y
        STA VERA_BASE+29
        INC pcm_src_lo
        BNE pcm_byte_done
        INC pcm_src_hi
pcm_byte_done:
        RTS

pcm_mix:
        LDA pcm_pointer+1
        STA mix_load+2
        LDA pcm_effect+1
        STA mix_eff+2
        LDY pcm_pointer
        LDX pcm_effect
        LDA pcm_count
        STA pcm_left
        LDA #0
        STA pcm_left+1
        LDA pcm_count
        BEQ mix_done
        LDA VERA_BASE+27
        BMI mix_done
mix_next:
mix_load:
        LDA $FF00,Y
        CLC
mix_eff:
        ADC $FF00,X
        STA VERA_BASE+29
        INY
        BNE mix_no_y_wrap
        INC mix_load+2
mix_no_y_wrap:
        INX
        BNE mix_no_x_wrap
        INC mix_eff+2
mix_no_x_wrap:
        DEC pcm_left
        BNE mix_next
mix_done:
        LDA pcm_left
        STA pcm_count
        RTS

; One iteration consumes two music bytes and one effect byte in the RAM
; staging run.  The effect is added to the *high* byte in memory; the caller
; then uses pcm_copy for the FIFO write.  Writing the two sample bytes here
; would overrun the FIFO when only one byte is free and permanently shift the
; 16-bit stream, which is heard as white noise.
pcm_mix16:
        LDA pcm_pointer+1
        STA mix16_load+2
        STA mix16_store+2
        LDA pcm_effect+1
        STA mix16_eff+2
        LDY pcm_pointer
        LDX pcm_effect
        LDA pcm_count
        STA pcm_left
        LDA pcm_count+1
        STA pcm_left+1
        ORA pcm_left
        BEQ mix16_done
mix16_next:
        LDA pcm_left
        ORA pcm_left+1
        BEQ mix16_done
        INY                          ; high byte of the little-endian sample
        BNE mix16_no_low_wrap
        INC mix16_load+2
        INC mix16_store+2
mix16_no_low_wrap:
mix16_load:
        LDA $FF00,Y                  ; sample high byte
        CLC
mix16_eff:
        ADC $FF00,X                  ; effect byte = high byte of effect<<8
mix16_store:
        STA $FF00,Y
        INY                          ; next sample low byte
        BNE mix16_no_high_wrap
        INC mix16_load+2
        INC mix16_store+2
mix16_no_high_wrap:
        INX
        BNE mix16_no_x_wrap
        INC mix16_eff+2
mix16_no_x_wrap:
        LDA pcm_left
        SEC
        SBC #1
        STA pcm_left
        LDA pcm_left+1
        SBC #0
        STA pcm_left+1
        JMP mix16_next
mix16_done:
        LDA pcm_left
        STA pcm_count
        LDA pcm_left+1
        STA pcm_count+1
        RTS
        .section .bss
pcm_left: .space 2
pcm_src_lo: .byte 0
pcm_src_hi: .byte 0
        .global pcm_half
pcm_half: .byte 0
