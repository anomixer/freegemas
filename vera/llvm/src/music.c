/* Raw PSG player in aux RAM and Aux LC.
 * Frees main RAM, supports all PSG features.
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

static uint8_t *const disk_buffer=(uint8_t *)0x0C00;
static uint16_t disk_blocks[126];
static uint16_t music_position;
static uint32_t music_size;
static uint8_t music_ready,music_on,cache_page;

static void psg_write(uint8_t reg,uint8_t value) {
    VERA.address=(uint16_t)(0xF9C0u+reg);VERA.address_hi=1;VERA.data0=value;
}
static void silence(void) {
    uint8_t channel;VERA.address=0xF9C2;VERA.address_hi=VERA_INC_4|1;
    for(channel=0;channel<16;channel++)VERA.data0=0;
}

static uint8_t event_byte(void) {
    uint8_t page=(uint8_t)(8u+(music_position>>8)),value;
    if((uint32_t)music_position>=music_size){music_ready=0;return 0;}
    if(page!=cache_page) {music_page=page;music_aux_page();cache_page=page;}
    value=music_cache[(uint8_t)music_position];++music_position;return value;
}

__attribute__((noinline)) void music_restart(void) {
    music_position=0;cache_page=255;
}
static uint8_t index_file(uint16_t key, uint8_t count) {
    uint8_t i;disk_read(key,disk_buffer);if(mli_status)return 0;
    for(i=0;i<count;i++)disk_blocks[i]=(uint16_t)disk_buffer[i]|((uint16_t)disk_buffer[256u+i]<<8);
    return 1;
}

void music_init(void) {
    uint16_t key;uint32_t size;uint8_t n,pages;
    music_ready=music_on=music_aux_top=0;
    if(!music_aux_available())return;
    if(!disk_file("MUSIC.PSG",9,&key,&size)||size<3||size>63488u)return;
    pages=(uint8_t)((size+511u)>>9);
    if(!index_file(key, pages))return;
    music_size=size;
    music_aux_init();music_destination_page=8;
    for(n=0;n<pages;n++) {
        disk_read(disk_blocks[n],disk_buffer);if(mli_status)return;
        music_source=disk_buffer;music_aux_store();
        music_source=disk_buffer+256;music_aux_store();
        loading_step();
    }
    music_aux_top=music_destination_page;music_ready=1;music_restart();
}

__attribute__((noinline)) void music_stop(void) {
    uint8_t ctrl=VERA.control,hi;uint16_t address;
    VERA.control=0;address=VERA.address;hi=VERA.address_hi;
    silence();music_on=0;
    VERA.address=address;VERA.address_hi=hi;VERA.control=ctrl;
}

__attribute__((noinline)) void music_tick(void) {
    uint8_t ctrl,hi,channel;uint16_t address;
    if(!music_ready||!MUSIC_SETTING) {if(music_on)music_stop();return;}
    ctrl=VERA.control;VERA.control=0;address=VERA.address;hi=VERA.address_hi;
    if(!music_on) {
        VERA.address=0xF9C0;VERA.address_hi=VERA_INC_1|1;
        for(channel=0;channel<16;channel++){VERA.data0=0;VERA.data0=0;VERA.data0=0;VERA.data0=128;}
        music_restart();music_on=1;
    }
    while(music_ready) {
        uint8_t count=event_byte();
        if(count==255) {
            VERA.address=0xF9C0;VERA.address_hi=VERA_INC_1|1;
            for(channel=0;channel<16;channel++){VERA.data0=0;VERA.data0=0;VERA.data0=0;VERA.data0=128;}
            music_restart();
            continue;
        }
        while(count-- && music_ready) {
            uint8_t reg=event_byte();
            uint8_t val=event_byte();
            psg_write(reg, val);
        }
        break;
    }
    VERA.address=address;VERA.address_hi=hi;VERA.control=ctrl;
}
