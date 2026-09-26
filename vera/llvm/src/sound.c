/* Raw, unchanged PCM preloaded once into VRAM plus remaining aux RAM.
 * Runtime only copies memory to FIFO. Port 1 and all graphics state restored.
 */
#include "sound.h"
#include "loading.h"
#include "apple2e.h"
#define SOUND_SETTING (*(volatile uint8_t *)0x03F3)
#define VRAM_PAGES 109u
/* Short match sounds: retain ~300 ms, omit the problematic long tails. */
#define MATCH_SHORT_BYTES 6640u
extern uint8_t mli_status,music_aux_top,music_destination_page,music_page;
extern uint8_t *music_source,*music_target;
extern void music_aux_store(void),music_aux_page(void);
extern void disk_read(uint16_t block,uint8_t *dest);
extern uint8_t disk_file(const char *name,uint8_t len,uint16_t *key,uint32_t *size);
typedef struct {uint32_t offset;uint16_t length;} Sample;
static Sample samples[5];
/* Disk/PCM staging shares the reserved page with startup-only music reads.
 * Music runtime uses its own cache, so PCM refills cannot overwrite it. */
static uint8_t *const buffer=(uint8_t *)0x0C00;
static uint8_t preload_page[256];
static uint16_t blocks[48],remaining;
static uint32_t cursor;
static uint8_t ready,cached_aux,initial_fill;
extern void pcm_copy(void),pcm_vram_copy(void);
uint16_t pcm_count;
uint8_t *pcm_pointer;

static uint32_t vram_page(uint16_t page) {
    if(page<72u)return 0x14800u+((uint32_t)page<<8);
    if(page<77u)return 0x1A300u+((uint32_t)(page-72u)<<8);
    if(page<101u)return 0x1D840u+((uint32_t)(page-77u)<<8);
    return 0x1F100u+((uint32_t)(page-101u)<<8);
}
static uint8_t store_page(uint16_t page) {
    if(page<VRAM_PAGES) {
        uint16_t i;uint32_t address=vram_page(page);
        VERA.control=0;VERA.address=(uint16_t)address;VERA.address_hi=(uint8_t)(VERA_INC_1|(address>>16));
        for(i=0;i<256;i++)VERA.data0=preload_page[i];
    } else {
        uint16_t destination=music_aux_top+page-VRAM_PAGES;
        if(destination>=192u)return 0;
        music_source=preload_page;music_destination_page=(uint8_t)destination;music_aux_store();
    }
    return 1;
}
__attribute__((noinline)) void sound_stop(void) {
    /* Hard replacement, never mix or resume the previous effect. Mute first
       because stopping the rate alone can retain the last rendered sample. */
    VERA.audio.control=0x20;
    VERA.audio.rate=0;
    VERA.audio.control=0xA0;
    remaining=0;cursor=0;cached_aux=0;initial_fill=0;
    pcm_count=0;pcm_pointer=buffer;
}
void sound_init(void) {
    static const char *const names[]={"SELECT.PCM","FALL.PCM","MATCH1.PCM","MATCH2.PCM","MATCH3.PCM"};
    uint8_t n,index,fill=0;uint16_t page=0;uint32_t total=0;
    ready=0;cached_aux=0;sound_stop();
    if(music_aux_top<8u||music_aux_top>=192u)return;
    for(n=0;n<5;n++) {
        uint16_t key;uint32_t size,done=0;
        if(!disk_file(names[n],n==1?8u:10u,&key,&size)||size>24576u||(size&1u))return;
        /* Keep each sample on one side of the VRAM/aux boundary. Padding is
           storage only: it is never included in a sample's playback length. */
        if(total<((uint32_t)VRAM_PAGES<<8) &&
           total+size>((uint32_t)VRAM_PAGES<<8)) {
            while(total<((uint32_t)VRAM_PAGES<<8)) {
                preload_page[fill++]=0;++total;
                if(!fill){if(!store_page(page++))return;}
            }
        }
        if(total+size>((uint32_t)(VRAM_PAGES+192u-music_aux_top)<<8))return;
        samples[n].length=(uint16_t)size;samples[n].offset=total;
        disk_read(key,buffer);if(mli_status)return;
        for(index=0;index<48;index++)blocks[index]=(uint16_t)buffer[index]|((uint16_t)buffer[256u+index]<<8);
        index=0;
        while(done<size) {
            uint16_t count=size-done>512u?512u:(uint16_t)(size-done),i;
            disk_read(blocks[index++],buffer);if(mli_status)return;
            for(i=0;i<count;i++) {
                preload_page[fill++]=buffer[i];
                if(!fill){if(!store_page(page++))return;}
            }
            done+=count;
            loading_step();
        }
        total+=size;
    }
    if(fill) {
        uint16_t i;for(i=fill;i<256;i++)preload_page[i]=0;
        if(!store_page(page))return;
    }
    ready=1;
}
__attribute__((noinline)) void sound_tick(void) {
    /* Prime the full FIFO before starting playback. Slow match resolution can
       exceed one VSYNC; 512 bytes per tick cannot sustain that at 1 MHz. */
    uint8_t ctrl,hi,resume_rate=0;uint16_t address,budget=initial_fill?4096u:1024u;
    if(!SOUND_SETTING){if(VERA.audio.rate)sound_stop();return;}
    if(!remaining){if(VERA.audio.control&0x40u)sound_stop();return;}
    ctrl=VERA.control;VERA.control=1;address=VERA.address;hi=VERA.address_hi;
    while(remaining && budget && !(VERA.audio.control&0x80u)) {
        uint16_t page,available,sent;
        /* EMPTY recovery must happen with playback stopped. Otherwise the
           renderer can discard our first low byte before its high arrives. */
        if(VERA.audio.rate && (VERA.audio.control&0x40u)) {
            resume_rate=VERA.audio.rate;VERA.audio.rate=0;budget=4096u;
        }
        /* FULL can stop after a low byte (FIFO capacity is 4095). If playback
           drains it, AppleWin discards that orphan byte. Replay it rather
           than feeding the high byte as a new low byte: that corrupts every
           subsequent signed 16-bit sample, producing sustained loud noise. */
        if((VERA.audio.control&0x40u) && (cursor&1u)) {--cursor;++remaining;}
        page=(uint16_t)(cursor>>8);available=256u-(uint8_t)cursor;
        if(available>remaining)available=remaining;if(available>budget)available=budget;
        pcm_count=available;
        if(page<VRAM_PAGES) {
            uint32_t at=vram_page(page)+(uint8_t)cursor;
            VERA.address=(uint16_t)at;VERA.address_hi=(uint8_t)(VERA_INC_1|(at>>16));pcm_vram_copy();
        } else {
            uint8_t aux=(uint8_t)(music_aux_top+page-VRAM_PAGES);
            if(aux!=cached_aux){music_page=aux;music_target=buffer;music_aux_page();cached_aux=aux;}
            /* The FIFO can drain during the aux-to-main page copy too. */
            if(VERA.audio.rate && (VERA.audio.control&0x40u))continue;
            pcm_pointer=buffer+(uint8_t)cursor;pcm_copy();
        }
        sent=available-pcm_count;cursor+=sent;remaining-=sent;budget-=sent;
        if(!sent)break;
    }
    VERA.address=address;VERA.address_hi=hi;VERA.control=ctrl;
    if(resume_rate && !(VERA.audio.control&0x40u))VERA.audio.rate=resume_rate;
    if(!remaining && (VERA.audio.control&0x40u))sound_stop();
}
__attribute__((noinline)) void sound_play(uint8_t effect) {
    uint8_t sample;
    if(!ready||!SOUND_SETTING)return;
    switch(effect) {
        case SFX_SELECT:sample=0;break;
        case SFX_FALL:sample=1;break;
        case SFX_MATCH1:sample=2;break;
        case SFX_MATCH2:sample=3;break;
        case SFX_MATCH3:sample=4;break;
        default:return;
    }
    sound_stop();cursor=samples[sample].offset;remaining=samples[sample].length;cached_aux=0;
    if(sample>=2u && remaining>MATCH_SHORT_BYTES)remaining=MATCH_SHORT_BYTES;
    VERA.audio.control=0x2F;initial_fill=1;sound_tick();initial_fill=0;
    if(remaining||!(VERA.audio.control&0x40u))VERA.audio.rate=29;
}
