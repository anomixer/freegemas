/* FREEGEMAS.SYSTEM: resident ProDOS loader.  It is intentionally tiny: it
 * loads segmented images at $3000 through a page-3 trampoline.
 * The loaded program may return here because this SYS image remains at $2000.
 */
#include <stdint.h>
#include "hiscore.h"

extern uint8_t mli_unit, mli_buf_lo, mli_buf_hi, mli_blk_lo, mli_blk_hi, mli_status;
extern void mli_read_block(void);
extern void mli_write_block(void);
extern void mli_quit(void);
extern const uint8_t trampoline_src[], trampoline_src_end[];
extern void launch_image(void);
extern uint16_t scene_src, scene_count, scene_data_port;
extern void scene_copy(void);
extern void clear_text(void);

#define BOOT_UNIT (*(volatile uint8_t *)0xBF30)
#define NEXT_IMAGE (*(volatile uint8_t *)0x03F0)
#define LOAD_GAME_MAGIC 0xA5u
#define LOAD_HOWTO_MAGIC 0xA6u
#define LOAD_OPTIONS_MAGIC 0xA7u
#define QUIT_MAGIC 0xA8u
#define LOAD_INTRO_MAGIC 0xA9u
#define SETTINGS_INIT (*(volatile uint8_t *)0x03F4)
#define DETECTED_VERA (*(volatile uint8_t *)0x03EC)

static uint8_t * const buf = (uint8_t *)0x0C00;
static uint8_t * const index_buf = (uint8_t *)0xB800;

/* Keep loader failures observable even before VERA is initialized. */
static void status(const char *s) {
    volatile uint8_t *p = (volatile uint8_t *)0x0400;
    *(volatile uint8_t *)0xC051 = 0; *(volatile uint8_t *)0xC054 = 0;
    clear_text();
    while (*s) *p++ = (uint8_t)(*s++ | 0x80);
}
static void fail(const char *s) { status(s); for (;;) {} }

static uint8_t probe_vera(uint16_t base) {
    volatile uint8_t *r = (volatile uint8_t *)base;
    r[5] = 0;
    /* ROM shadows/plain RAM can echo writes too. Real VERA must advance
     * its VRAM address after a DATA0 read with increment 1 enabled. */
    r[0]=r[1]=0;r[2]=0x10;
    (void)r[3];
    return r[0]==1;
}

static void read_block(uint8_t unit, uint16_t block, uint8_t *dest) {
    mli_unit = unit;
    mli_buf_lo = (uint8_t)(uint16_t)dest;
    mli_buf_hi = (uint8_t)((uint16_t)dest >> 8);
    mli_blk_lo = (uint8_t)block;
    mli_blk_hi = (uint8_t)(block >> 8);
    mli_read_block();
}

static uint8_t equal_name(const uint8_t *entry, const char *name) {
    uint8_t i, n = entry[0] & 15u;
    for (i = 0; name[i]; ++i)
        if (i >= n || (entry[1u + i] & 0x7Fu) != (uint8_t)name[i]) return 0;
    return i == n;
}

static uint8_t find_file(uint8_t unit, const char *name, uint8_t *storage,
                         uint16_t *key, uint32_t *eof) {
    uint16_t block = 2;
    while (block) {
        uint8_t i;
        read_block(unit, block, buf);
        if (mli_status) return 0;
        for (i = block == 2 ? 1 : 0; i < 13; ++i) {
            const uint8_t *entry = buf + 4u + (uint16_t)i * 39u;
            if (!(entry[0] >> 4) || !equal_name(entry, name)) continue;
            *storage = entry[0] >> 4;
            *key = (uint16_t)entry[0x11] | ((uint16_t)entry[0x12] << 8);
            *eof = (uint32_t)entry[0x15] | ((uint32_t)entry[0x16] << 8) | ((uint32_t)entry[0x17] << 16);
            return 1;
        }
        block = (uint16_t)buf[2] | ((uint16_t)buf[3] << 8);
    }
    return 0;
}

/* The title art is streamed while the SYS image still owns the MLI state.
 * TITLE.BIN is then only a small palette/input program below $2000. */
static uint8_t stream_scene(uint8_t unit, uint8_t vera_slot, const char *scene) {
    uint8_t storage, run = 0, need_count = 1, entry = 0, raw = 0;
    uint16_t key, p, i;
    uint32_t eof, done = 0;
    volatile uint8_t *v = (volatile uint8_t *)(vera_slot == 2 ? 0xC200 : 0xC400);
    if (!find_file(unit, scene, &storage, &key, &eof) || storage != 2) return 0;
    read_block(unit, key, buf); if (mli_status) return 0;
    for (i = 0; i < 512; ++i) index_buf[i] = buf[i];
    v[5] = 0; v[2] = 0x10; v[1] = 0; v[0] = 0; /* DATA0, VRAM $00000, +1 */
    scene_data_port=(uint16_t)(v+3);
    while (done < eof) {
        uint16_t block = (uint16_t)index_buf[entry] | ((uint16_t)index_buf[256u + entry] << 8);
        uint16_t n = eof - done > 512u ? 512u : (uint16_t)(eof - done);
        read_block(unit, block, buf); if (mli_status) return 0;
        if(raw){scene_src=(uint16_t)buf;scene_count=n;scene_copy();}
        else for (p = 0; p < n; ++p) {
            uint8_t byte = buf[p];
            if(raw) v[3]=byte;
            else if (need_count) { run = byte; need_count = 0; }
            else if(!run && done==0 && p==1 && byte==0){
                raw=1;need_count=1;
                scene_src=(uint16_t)(buf+2);scene_count=n-2u;scene_copy();break;
            }
            else { while (run--) v[3] = byte; need_count = 1; }
        }
        done += n; ++entry;
    }
    return need_count;
}

static void scores(void) {
    uint8_t storage, i;
    uint16_t key;
    uint32_t eof;
    if (!find_file(BOOT_UNIT, "HISCORE.DAT", &storage, &key, &eof) || storage != 1 || eof != 12) return;
    read_block(BOOT_UNIT, key, buf);
    if (mli_status) return;
    if (HISCORE_INIT != 0xA5u) {
        HIGH_SCORES[0] = HIGH_SCORES[1] = 0;
        if (buf[0]=='F' && buf[1]=='G' && buf[2]=='H' && buf[3]==1)
            for(i=0;i<8;i++) ((volatile uint8_t *)0x03E0)[i]=buf[4+i];
        HISCORE_DIRTY=0; HISCORE_INIT=0xA5u;
    } else if(HISCORE_DIRTY) {
        buf[0]='F';buf[1]='G';buf[2]='H';buf[3]=1;
        for(i=0;i<8;i++)buf[4+i]=((volatile uint8_t *)0x03E0)[i];
        mli_write_block();
        if(!mli_status) HISCORE_DIRTY=0;
    }
}

int main(void) {
    uint8_t slot, storage, count, image;
    uint16_t i;
    uint16_t key, blocks;
    uint32_t eof;
    const char *name;
    uint8_t *trampoline;
    volatile uint8_t *vera;
    status("FREEGEMAS LOADER");
    if (SETTINGS_INIT != 0xA5u) {
        HISCORE_INIT=0; HISCORE_DIRTY=0;
        HIGH_SCORES[0]=HIGH_SCORES[1]=0;
        SETTINGS_INIT = 0xA5u;
        *(volatile uint8_t *)0x03F2 = 1;
        *(volatile uint8_t *)0x03F3 = 1;
        if(NEXT_IMAGE!=LOAD_GAME_MAGIC && NEXT_IMAGE!=LOAD_HOWTO_MAGIC &&
           NEXT_IMAGE!=LOAD_OPTIONS_MAGIC && NEXT_IMAGE!=QUIT_MAGIC)
            NEXT_IMAGE=LOAD_INTRO_MAGIC;
    }
    if (probe_vera(0xC200)) slot = 2;
    else if (probe_vera(0xC400)) slot = 4;
    else {slot=0;NEXT_IMAGE=LOAD_INTRO_MAGIC;}
    DETECTED_VERA=slot;

    /* Hide the previous VERA frame before either scene is streamed.  Without
       this, returning from game shows title pixels through the game palette. */
    if(slot){
    vera = (volatile uint8_t *)(slot == 2 ? 0xC200 : 0xC400);
    vera[5] = 0;                    /* DCSEL 0 */
    vera[9] = 0;                    /* DC_VIDEO: output/layers/sprites off */
    scores();
    }

    image = NEXT_IMAGE;
    if(image==QUIT_MAGIC){
        if(HISCORE_DIRTY) fail("HIGH SCORE SAVE FAILED");
        NEXT_IMAGE=0;
        SETTINGS_INIT=0;        /* A later launch from Bitsy Bye is a new boot. */
        mli_quit();
    }
    if(image==LOAD_GAME_MAGIC){status("LOADING GAME...");name=slot==4?"GAME4.BIN":"GAME.BIN";}
    else if(image==LOAD_HOWTO_MAGIC){status("LOADING HOW TO PLAY...");name=slot==4?"HOWTO4.BIN":"HOWTO.BIN";}
    else if(image==LOAD_OPTIONS_MAGIC){status("LOADING OPTIONS...");name=slot==4?"OPTION4.BIN":"OPTION.BIN";}
    else if(image==LOAD_INTRO_MAGIC){name=slot==4?"INTRO4.BIN":"INTRO.BIN";}
    else{status("LOADING TITLE...");name=slot==4?"TITLE4.BIN":"TITLE.BIN";}
    NEXT_IMAGE = 0;
    if(image!=LOAD_GAME_MAGIC && image!=LOAD_INTRO_MAGIC){const char *scene=image==LOAD_HOWTO_MAGIC?"HOWTO.RLE":image==LOAD_OPTIONS_MAGIC?"OPTION.RLE":"TITLE.RLE";if(!stream_scene(BOOT_UNIT,slot,scene))fail(" SCENE");}
    if (!find_file(BOOT_UNIT, name, &storage, &key, &eof) || eof == 0) fail(" FILE");
    if(eof > 0x8800u) fail(" IMAGE TOO LARGE");
    blocks = (uint16_t)((eof + 511u) / 512u);
    if (blocks == 0 || blocks > 255) fail(" SIZE");
    if (storage == 1) {
        for (i = 0; i < 512; ++i) index_buf[i] = 0;
        index_buf[0] = (uint8_t)key; index_buf[256] = (uint8_t)(key >> 8);
        blocks = 1;
    } else if (storage == 2) {
        read_block(BOOT_UNIT, key, buf); if (mli_status) fail(" INDEX");
        for (i = 0; i < 512; ++i) index_buf[i] = buf[i];
    } else fail(" TYPE");

    /* Permit MLI reads into the $0800-$B7FF image range. */
    for (i = 1; i < 23; ++i) ((volatile uint8_t *)0xBF58)[i] = 0;
    count = (uint8_t)(trampoline_src_end - trampoline_src);
    trampoline = (uint8_t *)0x0300;
    for (i = 0; i < count; ++i) trampoline[i] = trampoline_src[i];
    *(volatile uint8_t *)0x03C1 = BOOT_UNIT;
    *(volatile uint8_t *)0x03C8 = (uint8_t)blocks;
    launch_image();
    return 0;
}
