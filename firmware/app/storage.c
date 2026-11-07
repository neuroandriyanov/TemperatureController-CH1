#include "storage.h"
#include "modbus.h"
#include <string.h>
#define RECORD_SIZE (12u+CONFIG_COUNT*2u+2u)
static void encode(uint8_t *p,uint32_t v,unsigned n) { while(n) { p[--n]=(uint8_t)v;v>>=8; } }
static uint32_t decode(const uint8_t *p,unsigned n) { uint32_t v=0;while(n--) v=(v<<8)|*p++;return v; }
static bool read_record(Storage *st,int slot,Config *c,uint32_t *seq) {
    uint8_t r[RECORD_SIZE];
    if(!st->read(st->context,(uint16_t)(STORAGE_BASE+slot*STORAGE_SLOT_SIZE),r,sizeof(r))) return false;
    unsigned version=decode(r+4,2),count=decode(r+6,2);
    if(memcmp(r,"TC2!",4) || !((version==5 && count==CONFIG_COUNT) || (version==4 && count==46) || (version==3 && count==43) || (version==2 && count==41))) return false;
    unsigned size=12+count*2+2;
    if(modbus_crc(r,size-2)!=decode(r+size-2,2)) return false;
    config_defaults(c); /* Legacy records have no running state: migrate in STOP. */
    for(unsigned i=0;i<count;i++) c->v[i]=(uint16_t)decode(r+12+i*2,2);
    /* Older versions allowed 0.2..10 s; migrate sub-2-second periods to 2 s. */
    if(version<5 && c->v[C_BURST_PERIOD_MS]<2000) c->v[C_BURST_PERIOD_MS]=2000;
    *seq=decode(r+8,4);return config_valid(c);
}
bool storage_load(Storage *st,Config *c) {
    Config a,b;uint32_t sa=0,sb=0;
    bool va=read_record(st,0,&a,&sa),vb=read_record(st,1,&b,&sb);
    st->slot=-1;st->sequence=0;
    if(!va && !vb) return false;
    if(vb && (!va || (int32_t)(sb-sa)>0)) { *c=b;st->slot=1;st->sequence=sb; }
    else { *c=a;st->slot=0;st->sequence=sa; }
    return true;
}
bool storage_save(Storage *st,const Config *c) {
    if(!config_valid(c)) return false;
    uint8_t r[RECORD_SIZE],check[RECORD_SIZE],invalid[4]={0};
    uint32_t next=st->sequence+1; int slot=st->slot==0?1:0;
    uint16_t base=(uint16_t)(STORAGE_BASE+slot*STORAGE_SLOT_SIZE);
    memcpy(r,"TC2!",4);encode(r+4,5,2);encode(r+6,CONFIG_COUNT,2);encode(r+8,next,4);
    for(unsigned i=0;i<CONFIG_COUNT;i++) encode(r+12+i*2,c->v[i],2);
    encode(r+sizeof(r)-2,modbus_crc(r,sizeof(r)-2),2);
    /* Invalidate target before modifying data. Commit magic is written last.
       A valid previous slot is never touched. Platform write splits pages. */
    if(!st->write(st->context,base,invalid,4) ||
       !st->write(st->context,base+4,r+4,sizeof(r)-4) ||
       !st->read(st->context,base+4,check+4,sizeof(r)-4) ||
       memcmp(r+4,check+4,sizeof(r)-4) ||
       !st->write(st->context,base,r,4)) return false;
    Config verified;uint32_t seq;
    if(!read_record(st,slot,&verified,&seq) || seq!=next || memcmp(&verified,c,sizeof(*c))) return false;
    st->sequence=next;st->slot=slot;return true;
}
