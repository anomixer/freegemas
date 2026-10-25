#include "video.h"
#include "assets.h"
#include <string.h>

/* Inline assembly helper to write 1 byte to a 24-bit address (Bank $E1) */
static inline void poke_e1(unsigned int offset, unsigned char val) {
    /* llvm-mos uses standard 6502 but can emit 65816 via .byte or if configured.
       To be completely safe with llvm-mos 6502 assembler, we can use the 
       65816 long addressing 'STA al' which is opcode 0x8F.
       STA long = 8F ll hh bb. So to store A to $E1:hhll:
    */
    __asm__ volatile (
        ".byte $8F\n\t"
        ".word %0\n\t"
        ".byte $E1"
        : 
        : "i" (offset), "a" (val)
    );
    // Note: 'i' constraint works if offset is a compile-time constant.
    // If offset is a variable, we need a different approach or a tiny self-modifying routine.
}

/* Helper for variable offsets using self-modifying code in zero page or data segment,
   or just a simple routine if llvm-mos doesn't support 'STA long,x' natively. 
   Wait, 'STA long,X' is opcode 0x9F.
   We can do:
*/


__attribute__((section(".zp"))) static volatile unsigned char zp_ptr[3];

static unsigned char smc_code[6] = {
    0x8F, /* STA al */
    0x00, 0x00, 0x00, /* 24-bit address */
    0x38, /* SEC */
    0x60  /* RTS */
};

static inline void iigs_poke(unsigned char bank, unsigned int offset, unsigned char val) {
    /* Self-modify the STA al instruction's address */
    smc_code[1] = offset & 0xFF;
    smc_code[2] = offset >> 8;
    smc_code[3] = bank;
    
    __asm__ volatile (
        "clc\n\t"
        ".byte $FB\n\t" /* xce (Native Mode) */
        "jsr %v1\n\t"   /* Call the SMC code */
        ".byte $FB\n\t" /* xce (Emulation Mode) (SEC is executed inside smc_code) */
        : 
        : "a" (val), "p" (smc_code)
        : "memory"
    );
}

static inline void poke_e1_var(unsigned int offset, unsigned char val) {
    iigs_poke(0xE1, offset, val);
}


extern void toolbox_video_init(void);
extern void toolbox_draw_gem(int x, int y, const unsigned char *gem_data);

void video_init(void) {
    unsigned int i;
    
    /* We also must turn off Text Mode and enable Graphics Mode! (Write to Bank 00 for Mega II) */
    *(volatile unsigned char*)0xC050 = 0x00; /* TXTCLR: Enable Graphics */
    *(volatile unsigned char*)0xC052 = 0x00; /* MIXCLR: Full screen graphics */
    *(volatile unsigned char*)0xC054 = 0x00; /* TXTPAGE1: Page 1 */
    *(volatile unsigned char*)0xC057 = 0x00; /* HIRES: High-res graphics mode */
    
    /* VERY IMPORTANT: Inhibit SHR Shadowing (Bit 3) */
    *(volatile unsigned char*)0xC035 = 0x08;

    /* Set SCB to 0 (Palette 0, 320x200) */
    for (i = 0; i < 200; i++) {
        poke_e1_var(0x9D00 + i, 0x00);
    }
    
    /* Set Palette 0 */
    for (i = 0; i < 16; i++) {
        unsigned int c = game_palette[i];
        poke_e1_var(0x9E00 + i*2, c & 0xFF);
        poke_e1_var(0x9E00 + i*2 + 1, c >> 8);
    }
    
    /* Clear VRAM */
    for(i = 0; i < 32000; i++) {
        poke_e1_var(0x2000 + i, 0x00); /* $E12000 + i */
    }
    
    /* Turn on SHR Mode in the New Video Register ($E0C029) */
    /* Bit 7 = SHR Enable, Bit 6 = Linearize */
    *(volatile unsigned char*)0xC029 = 0xC0;
}

void video_update(void) {
}

/* Helper to map a linear Y coordinate to the Apple II HGR non-linear offset */
static unsigned int get_hgr_offset(int y) {
    unsigned int offset;
    /* Apple II HGR interleaving:
       y = 0..191
       Address = Base + (y / 64) * 40 + ((y % 64) / 8) * 128 + (y % 8) * 1024
       Since SHR scanlines are 160 bytes wide, we multiply the offsets by 4 (160 / 40 = 4)
    */
    offset = (y / 64) * 160 + ((y % 64) / 8) * 512 + (y % 8) * 4096;
    return 0x2000 + offset;
}

void video_draw_gem(int x, int y, int gem_type) {
    int row, col;
    unsigned int offset;
    const unsigned char *src;
    
    const unsigned char *gems[7] = {
        gem1_data, gem2_data, gem3_data, gem4_data,
        gem5_data, gem6_data, gem7_data
    };

    if (gem_type < 1 || gem_type > 7) return;
    if (x < 0 || x > 320 - 32 || y < 0 || y > 200 - 32) return;

    src = gems[gem_type - 1];

    for (row = 0; row < 32; row++) {
        /* Map each row individually using the HGR interleaving formula */
        offset = get_hgr_offset(y + row) + (x / 2);
        for (col = 0; col < 16; col++) {
            poke_e1_var(offset + col, src[row * 16 + col]);
        }
    }
}

void video_draw_text(int x, int y, const char* str) {}
void video_hide_sprite(int slot) {}
