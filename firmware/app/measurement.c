#include "core.h"
#include <math.h>
#include <string.h>

void moments_reset(Moments *m) { memset(m,0,sizeof(*m)); m->min=4095; }
void moments_add(Moments *m, const volatile uint16_t *v, unsigned n) {
    for (unsigned i=0;i<n;i++) {
        uint32_t x=v[i]; m->sum+=x; m->squares+=(uint64_t)x*x; m->n++;
        if(x<m->min) m->min=(uint16_t)x;
        if(x>m->max) m->max=(uint16_t)x;
    }
}
float moments_rms(const Moments *m) {
    if(!m->n) return 0;
    /* Integer cancellation avoids loss of precision around the DC midpoint. */
    uint64_t a=m->squares*m->n, b=m->sum*m->sum;
    return sqrtf((float)(a>b?a-b:0))/(float)m->n;
}
float current_ma(float rms, const Config *c) {
    float noise=c->v[C_CURRENT_NOISE_C100]*0.01f;
    float square=rms*rms-noise*noise;
    float ma=sqrtf(fmaxf(0,square))*c->v[C_CURRENT_GAIN_UA]*0.001f
             +config_value(c,C_CURRENT_OFFSET_MA);
    return fmaxf(0,ma);
}
bool external_capture_frequency(const uint16_t *periods, unsigned count, float *hz) {
    *hz=0;
    if(!periods || !count || count>128) return false;
    uint32_t sum=0;bool valid=true;
    /* AD7741 is synchronous: individual intervals alternate between integer
       CLKIN periods. Near full scale a legal interval is 2/500 kHz = 192
       timer ticks at 48 MHz, even when the mean frequency is below 225 kHz.
       The former 200-tick limit falsely rejected these captures. Keep a
       small clock/edge tolerance here; external_convert still checks the
       mean conversion range and configured loop-current limits. */
    for(unsigned i=0;i<count;i++) {
        sum+=periods[i];
        if(periods[i]<180 || periods[i]>2100) valid=false;
    }
    if(sum) *hz=48000000.0f*count/sum;
    return valid && sum!=0;
}
bool external_convert(float hz, const Config *c, float *mv, float *ua, float *temp) {
    *mv=(hz/500000.0f-0.05f)*(2500.0f/0.40f);
    *ua=4000+(*mv-c->v[C_EXT_VOLT_4_MV])*16000.0f/
        (c->v[C_EXT_VOLT_20_MV]-c->v[C_EXT_VOLT_4_MV])+config_value(c,C_EXT_OFFSET_UA);
    float lo=config_value(c,C_EXT_TEMP_4_C10)*0.1f;
    float hi=config_value(c,C_EXT_TEMP_20_C10)*0.1f;
    *temp=lo+(*ua-4000)*(hi-lo)/16000+config_value(c,C_EXT_TEMP_OFFSET_C100)*0.01f;
    return isfinite(*temp) && hz>25000 && hz<225000 &&
        *ua>=c->v[C_EXT_LOW_UA] && *ua<=c->v[C_EXT_HIGH_UA];
}
float max_tc_decode(const uint8_t d[3]) {
    int32_t raw=((int32_t)d[0]<<16)|((int32_t)d[1]<<8)|(d[2]&0xE0);
    if(raw&0x800000) raw-=0x1000000;
    return raw/4096.0f;
}
float max_cj_decode(const uint8_t d[2]) {
    return (int16_t)(((uint16_t)d[0]<<8)|d[1])/256.0f;
}
bool max_cj_encode(float t,uint8_t d[2]) {
    if(!isfinite(t)||t< -64 || t>127.984375f) return false;
    int16_t raw=(int16_t)(lroundf(t*64)*4);
    d[0]=(uint8_t)((uint16_t)raw>>8); d[1]=(uint8_t)raw;
    return true;
}
bool max_cj_usable(uint16_t type,float t) {
    float minimum=type==0?0.0f:((type==5 || type==6)?-50.0f:-55.0f);
    return isfinite(t) && t>=minimum && t<=125;
}
uint8_t rotary_decode(uint16_t pins) {
    return (uint8_t)~(((pins&0x03F8u)>>3)|((pins&0x2000u)>>6));
}
bool rotary_update(Rotary *r,uint8_t raw,uint32_t now) {
    bool change=!r->initialized || raw!=r->raw;
    if(change) { r->raw=raw; r->since=now; r->initialized=true; r->stable=false; }
    if(!r->stable && (uint32_t)(now-r->since)>=250) {
        r->address=(raw>=1 && raw<=247)?raw:0; r->stable=true;
    }
    return change;
}
