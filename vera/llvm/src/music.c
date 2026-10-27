/* Background music: raw PSG stream, or YM2151 (FM) + PSG percussion.
 *
 * With a YM2151 daughterboard the game loads MUSIC.VZM, a ZSM stream that the
 * VSYNC tick decodes directly:
 *
 *   $00-$7F  delay       consume this tick, wait N more
 *   $80-$BF  PSG write   register = byte & $3F, next byte value
 *   $C0-$DF  FM batch    count = (byte & $1F) + 1, then count x (reg, value)
 *   $E0-$FE  padding     skipped, consumes no tick
 *   $FF      end         loop back to offset 0
 *
 * Without the chip MUSIC.PSG (one frame per tick, 16 voices) is loaded
 * instead, so the game keeps its original music on stock machines.
 *
 * Both streams are preloaded into Aux RAM and Aux Language Card Bank 1 by
 * music_aux.S; playback never touches the disk.
 */
#include <stdint.h>
#include "apple2e.h"
#include "music.h"
#include "loading.h"
#define MUSIC_SETTING (*(volatile uint8_t *)0x03F2)
extern uint8_t mli_status;
extern void disk_read(uint16_t block,uint8_t *dest);
extern uint8_t disk_file(const char *name,uint8_t length,uint16_t *key,uint32_t *size);
extern void music_aux_init(void),music_aux_store(void),music_aux_page(void);
extern uint8_t music_aux_available(void);
uint8_t music_cache[256],music_page,music_aux_top;
uint8_t *music_source;
uint8_t music_destination_page;
uint8_t music_fm;

static uint8_t *const disk_buffer=(uint8_t *)0x0C00;
static uint16_t music_position;
static uint32_t music_size;
static uint8_t music_ready,music_on,cache_page,music_delay;

static void psg_write(uint8_t reg,uint8_t value) {
    VERA.address=(uint16_t)(0xF9C0u+reg);VERA.address_hi=1;VERA.data0=value;
}

/* ---------------------------- YM2151 helpers ----------------------------- */
static void fm_reg(uint8_t reg,uint8_t value) {
    VERA_YM_REG=reg;VERA_YM_DATA=value;
}
static void fm_key_off_all(void) {
    uint8_t channel;
    for(channel=0;channel<8;channel++)fm_reg(YM_KEY_REG,channel);
}
/* MUSIC.VZM was de-duplicated against an all-zero YM2151 register image, so
 * the chip has to be cleared before playback and whenever the stream loops. */
static void fm_silence(void) {
    uint16_t reg;
    fm_key_off_all();
    for(reg=0x20;reg<0x100;reg++)fm_reg((uint8_t)reg,0);
}

#include "fm_probe.h"
/* Runs the BUSY probe from page 3 scratch RAM; leaves the result at $02FF. */
static uint8_t fm_detect(void) {
    volatile uint8_t *scratch=(volatile uint8_t *)0x0300;
    uint8_t i;
    for(i=0;i<sizeof(fm_probe);i++)scratch[i]=fm_probe[i];
    ((void(*)(void))0x0300)();
    return *(volatile uint8_t *)0x02FF;
}

/* Zero the PSG (all sixteen voices) and the FM chip. */
static void music_clear(void) {
    uint8_t channel;
    VERA.address=0xF9C0;VERA.address_hi=VERA_INC_1|1;
    for(channel=0;channel<16;channel++){VERA.data0=0;VERA.data0=0;VERA.data0=0;VERA.data0=128;}
    if(music_fm)fm_silence();
}

static inline __attribute__((always_inline)) uint8_t event_byte(void) {
    uint8_t page=(uint8_t)(8u+(music_position>>8)),value;
    if((uint32_t)music_position>=music_size){music_ready=0;return 0;}
    if(page!=cache_page) {music_page=page;music_aux_page();cache_page=page;}
    value=music_cache[(uint8_t)music_position];++music_position;return value;
}

__attribute__((noinline)) void music_restart(void) {
    music_position=0;cache_page=255;music_delay=0;
}
void music_init(void) {
    uint16_t key=0;uint32_t size=0;uint8_t n,pages;
    music_ready=music_on=music_aux_top=0;music_delay=0;music_fm=0;
    if(!music_aux_available())return;
    if(fm_detect()) {
        if(disk_file("MUSIC.VZM",9,&key,&size)&&size>=3&&size<=63488u)music_fm=1;
    }
    if(!music_fm) {
        if(!disk_file("MUSIC.PSG",9,&key,&size)||size<3||size>63488u)return;
    }
    pages=(uint8_t)((size+511u)>>9);
    music_size=size;
    music_aux_init();music_destination_page=8;
    for(n=0;n<pages;n++) {
        disk_read(n,disk_buffer);if(mli_status)return;
        music_source=disk_buffer;music_aux_store();
        music_source=disk_buffer+256;music_aux_store();
        loading_step();
    }
    music_aux_top=music_destination_page;music_ready=1;music_restart();
}

__attribute__((noinline)) void music_stop(void) {
    uint8_t ctrl=VERA.control,hi;uint16_t address;
    VERA.control=0;address=VERA.address;hi=VERA.address_hi;
    music_clear();music_on=0;
    VERA.address=address;VERA.address_hi=hi;VERA.control=ctrl;
}

__attribute__((noinline)) void music_tick(void) {
    uint8_t ctrl,hi,command,count,reg,val;uint16_t address;
    if(!music_ready||!MUSIC_SETTING) {if(music_on)music_stop();return;}
    ctrl=VERA.control;VERA.control=0;address=VERA.address;hi=VERA.address_hi;
    if(!music_on) {
        music_clear();
        music_restart();music_on=1;
    }
    while(music_ready) {
        if(music_fm) {
            if(music_delay){--music_delay;break;}
            command=event_byte();
            if(command==255) {
                music_clear();
                music_restart();
                continue;
            }
            if(command<0x80){music_delay=command;break;}
            if(command<0xC0){psg_write((uint8_t)(command&0x3Fu),event_byte());continue;}
            if(command<0xE0) {
                count=(uint8_t)((command&0x1Fu)+1);
                while(count-- && music_ready){reg=event_byte();val=event_byte();fm_reg(reg,val);}
                continue;
            }
            continue;                       /* $E0-$FE: block padding */
        }
        count=event_byte();
        if(count==255) {
            music_clear();
            music_restart();
            continue;
        }
        while(count-- && music_ready) {
            reg=event_byte();
            val=event_byte();
            psg_write(reg, val);
        }
        break;
    }
    VERA.address=address;VERA.address_hi=hi;VERA.control=ctrl;
}
