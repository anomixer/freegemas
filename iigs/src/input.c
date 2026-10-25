#include "input.h"

__attribute__((section(".zp"))) static volatile unsigned char zp_ptr[3];

static inline unsigned char peek_e0(unsigned int offset) {
    unsigned char val;
    zp_ptr[0] = offset & 0xFF;
    zp_ptr[1] = offset >> 8;
    zp_ptr[2] = 0xE0;
    __asm__ volatile (
        "ldy #0\n\t"
        ".byte $A7\n\t" /* LDA [dp],y */
        ".byte %v1\n\t"
        "sta %0"
        : "=a" (val)
        : "p" (zp_ptr)
        : "y", "memory"
    );
    return val;
}

static inline void poke_e0(unsigned int offset, unsigned char val) {
    zp_ptr[0] = offset & 0xFF;
    zp_ptr[1] = offset >> 8;
    zp_ptr[2] = 0xE0;
    __asm__ volatile (
        "ldy #0\n\t"
        ".byte $87\n\t" /* STA [dp],y */
        ".byte %v1\n\t"
        : 
        : "a" (val), "p" (zp_ptr)
        : "y", "memory"
    );
}

static unsigned int mouse_x = 0;
static unsigned int mouse_y = 0;
static unsigned char mouse_down = 0;

void input_init(void) {
}

void input_update(void) {
    /* TODO: Read IIGS ADB Mouse registers */
}

unsigned char input_is_mouse_down(void) {
    return mouse_down;
}

unsigned int input_get_mouse_x(void) {
    return mouse_x;
}

unsigned char input_get_mouse_y(void) {
    return (unsigned char)mouse_y;
}

unsigned char input_get_key(void) {
    /* Keyboard polling via memory $C000 */
    unsigned char kbd = *(volatile unsigned char*)0xC000;
    if (kbd & 0x80) {
        *(volatile unsigned char*)0xC010 = 0; /* Clear strobe */
        return kbd & 0x7F;
    }
    return 0;
}
