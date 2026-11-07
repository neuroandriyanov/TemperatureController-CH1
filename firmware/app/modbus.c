#include "modbus.h"
#include <string.h>
uint16_t modbus_crc(const uint8_t *p,size_t n) {
    uint16_t crc=0xFFFF;
    while(n--) { crc^=*p++; for(unsigned j=0;j<8;j++) crc=(crc&1)?(uint16_t)((crc>>1)^0xA001):(uint16_t)(crc>>1); }
    return crc;
}
static uint16_t be16(const uint8_t *p) { return (uint16_t)(((uint16_t)p[0]<<8)|p[1]); }
static void put16(uint8_t *p,uint16_t v) { p[0]=(uint8_t)(v>>8);p[1]=(uint8_t)v; }
size_t modbus_process(Controller *s,const uint8_t *q,size_t n,uint8_t r[RTU_MAX],uint32_t now,bool gate,bool relay,ModbusStats *stats) {
    if(n<4 || n>RTU_MAX) { stats->malformed++; return 0; }
    uint16_t crc=modbus_crc(q,n-2);
    if(q[n-2]!=(uint8_t)crc || q[n-1]!=(uint8_t)(crc>>8)) { stats->crc_errors++; return 0; }
    bool broadcast=q[0]==0;
    if(!broadcast && (!s->rotary.stable || !s->rotary.address || q[0]!=s->rotary.address)) return 0;
    uint8_t fc=q[1],error=0; size_t out=0;
    uint16_t values[125],a=0,count=0;
    if(fc==3 || fc==4 || fc==6) {
        if(n!=8) { stats->malformed++; return 0; }
        a=be16(q+2); count=be16(q+4);
        if(fc==6) { values[0]=count; error=controller_write(s,a,1,values,broadcast,now); }
        else {
            if(broadcast) return 0;
            if(count<1 || count>125) error=3;
            else error=controller_read(s,fc==4,a,count,values,now,gate,relay);
            if(!error) {
                /* Per-transport counters occupy input registers 48..57. */
                const uint32_t counters[5]={stats->valid,stats->crc_errors,stats->malformed,stats->exceptions,stats->framing_errors};
                if(fc==4) for(unsigned i=0;i<count;i++) if(a+i>=48 && a+i<58) {
                    unsigned index=a+i-48;
                    values[i]=(uint16_t)(counters[index/2]>>((index&1)?0:16));
                }
                r[0]=q[0];r[1]=fc;r[2]=(uint8_t)(count*2);
                for(unsigned i=0;i<count;i++) put16(r+3+2*i,values[i]);
                out=3+2*count;
            }
        }
    } else if(fc==16) {
        if(n<9) { stats->malformed++; return 0; }
        a=be16(q+2);count=be16(q+4);
        if(count<1 || count>123 || q[6]!=count*2u || n!=9u+count*2u) error=3;
        else {
            for(unsigned i=0;i<count;i++) values[i]=be16(q+7+2*i);
            error=controller_write(s,a,count,values,broadcast,now);
        }
    } else error=1;
    if(error) { stats->exceptions++;r[0]=q[0];r[1]=fc|0x80;r[2]=error;out=3; }
    else {
        stats->valid++;
        if(!broadcast) { s->last_contact=now;s->contact_seen=true; }
        if(fc==6 || fc==16) { memcpy(r,q,6);out=6; }
    }
    if(broadcast) return 0;
    crc=modbus_crc(r,out);r[out++]=(uint8_t)crc;r[out++]=(uint8_t)(crc>>8);return out;
}
void rtu_error(RtuFramer *f,uint32_t us) { f->discard=true;f->started=true;f->last_us=us;f->errors++; }
void rtu_poll(RtuFramer *f,uint32_t us) {
    if(f->ready || !f->started || (uint32_t)(us-f->last_us)<1750) return;
    if(f->discard) { f->length=0; f->discard=false; f->started=false; }
    else { f->ready=true;f->started=false; }
}
void rtu_byte(RtuFramer *f,uint8_t b,uint32_t us) {
    if(f->ready) { f->errors++; return; } /* Master must wait for the reply. */
    /* RXNE timestamps the END of a character. Subtract one 11-bit character
       (ceil(11e6/38400) = 287 us) when measuring the silence before it. */
    if(f->started) {
        uint32_t delta=us-f->last_us;
        uint32_t gap=delta>287?delta-287:0;
        if(gap>=1750) {
            if(f->discard) { f->length=0;f->discard=false;f->started=false; }
            else { f->ready=true;f->started=false;f->errors++;return; }
        } else if(gap>750 && !f->discard) { f->discard=true;f->errors++; }
    }
    f->started=true;f->last_us=us;
    if(f->discard) return;
    if(f->length==RTU_MAX) { f->discard=true;f->errors++; return; }
    f->bytes[f->length++]=b;
}
void rtu_release(RtuFramer *f) { f->length=0;f->ready=false;f->started=false;f->discard=false; }
