#include "core.h"
#include <string.h>
#include <math.h>
static const int32_t limits[CONFIG_COUNT][3]={
#define X(n,d,l,h) {d,l,h},
#include "config.def"
#undef X
};
void config_defaults(Config *c) { for(unsigned i=0;i<CONFIG_COUNT;i++) c->v[i]=(uint16_t)limits[i][0]; }
int32_t config_value(const Config *c,unsigned i) {
    return limits[i][1]<0 ? (int16_t)c->v[i] : c->v[i];
}
uint32_t config_burst_period_ms(const Config *c) {
    return ((uint32_t)c->v[C_BURST_PERIOD_MS_HIGH]<<16)|c->v[C_BURST_PERIOD_MS];
}
uint32_t burst_on_time_ms(uint32_t period,uint16_t power) {
    if(period<2000u || period>300000u || power>10000u) return 0;
    return period*power/10000u; /* At most 3,000,000,000: fits uint32_t. */
}
bool config_valid(const Config *c) {
    for(unsigned i=0;i<CONFIG_COUNT;i++) {
        int32_t v=config_value(c,i);
        if(v<limits[i][1] || v>limits[i][2]) return false;
    }
    int32_t lo=config_value(c,C_PROCESS_MIN_C10),hi=config_value(c,C_PROCESS_MAX_C10);
    int32_t sp=config_value(c,C_SETPOINT);
    uint32_t period=config_burst_period_ms(c);
    return period>=2000u && period<=300000u && lo<hi && sp>=lo && sp<=hi &&
        c->v[C_EXT_VOLT_20_MV]>=c->v[C_EXT_VOLT_4_MV]+50 &&
        c->v[C_EXT_TEMP_20_C10]!=c->v[C_EXT_TEMP_4_C10] &&
        c->v[C_OFF_CURRENT_MA]<c->v[C_OVERCURRENT_MA] &&
        c->v[C_OPEN_CURRENT_MA]<c->v[C_OVERCURRENT_MA];
}
void controller_init(Controller *s) { memset(s,0,sizeof(*s)); config_defaults(&s->config); }
static void remember(Controller *s,unsigned reg,uint16_t value) {
    if(s->config.v[reg]!=value) {
        s->config.v[reg]=value;s->dirty=true;s->config_revision++;
        s->save_requested=true;s->storage_status=1;
    }
}
void controller_stop(Controller *s) {
    s->mode=MODE_STOP; s->output=0; s->manual=0; pid_reset(&s->pid);
    s->open_timing=false;s->open_elapsed=0;s->soak_started=s->soak_ready=false;
    if(s->boot_status==1) s->boot_status=3;
    remember(s,C_POWERUP_MODE,MODE_STOP);
}
void controller_powerup(Controller *s,uint32_t now) {
    s->boot_since=now;s->boot_status=s->config.v[C_POWERUP_MODE]?1:0;
}
void controller_boot_update(Controller *s,uint32_t now) {
    if(s->boot_status!=1 || (uint32_t)(now-s->boot_since)<1000) return;
    if(!s->active && !s->latched && !s->save_requested) {
        s->manual=s->config.v[C_MANUAL_PRESET_100];
        bool contacted=s->contact_seen;
        if(!controller_mode(s,s->config.v[C_POWERUP_MODE],now)) {
            s->boot_status=2;s->contact_seen=contacted;
        }
    } else if(s->latched || (s->active&(F_CALIBRATION|F_STORAGE)) ||
              (uint32_t)(now-s->boot_since)>=15000) {
        controller_stop(s); /* No deferred restart after a startup failure. */
    }
}
static bool in_tolerance(const Controller *s) {
    float target=config_value(&s->config,C_SETPOINT)*0.1f;
    return s->mode && s->mode!=MODE_CURRENT_TEST && !s->save_requested && !s->active && !s->latched && s->m.tc_valid &&
        s->m.pv>=target-s->config.v[C_TOLERANCE_LOW_C10]*0.1f &&
        s->m.pv<=target+s->config.v[C_TOLERANCE_HIGH_C10]*0.1f;
}
bool controller_relay(const Controller *s) {
    uint32_t faults=s->active|s->latched;
    switch(s->config.v[C_RELAY_FUNCTION]) {
    case RELAY_TOLERANCE:return in_tolerance(s);
    case RELAY_SOAK:return in_tolerance(s) && s->soak_ready;
    case RELAY_ERROR:return faults!=0;
    case RELAY_OVERCURRENT:return (faults&F_OVERCURRENT)!=0;
    case RELAY_HEATER:return (faults&F_OPEN_HEATER)!=0;
    case RELAY_DEVICE:return (faults&~(F_TEMPERATURE|F_OVERCURRENT|F_OPEN_HEATER))!=0;
    default:return false;
    }
}
static bool delay_fault(bool condition,bool *timing,uint32_t *since,uint32_t now,uint16_t delay) {
    if(!condition) { *timing=false; return false; }
    if(!*timing) { *since=now; *timing=true; }
    return (uint32_t)(now-*since)>=delay;
}
void controller_update(Controller *s,uint32_t now,bool gate,uint32_t changed) {
    Config *c=&s->config; Measurements *m=&s->m;
    if(s->mode==MODE_CURRENT_TEST && (uint32_t)(now-s->current_test_since)>=CURRENT_TEST_MS)
        controller_stop(s);
    bool current_test=s->mode==MODE_CURRENT_TEST;
    uint32_t faults=0;
    if(s->storage_status==4) faults|=F_STORAGE;
    if(!s->rotary.stable || !s->rotary.address) faults|=F_ADDRESS;
    if(!m->tc_valid) faults|=F_TC;
    if(!m->tc_valid || (uint32_t)(now-m->tc_at)>c->v[C_TC_TIMEOUT_MS]) faults|=F_TC_STALE;
    if(!m->current_valid) faults|=F_CURRENT;
    if(!m->current_valid || (uint32_t)(now-m->current_at)>c->v[C_CURRENT_TIMEOUT_MS]) faults|=F_CURRENT_STALE;
    if(!(c->v[C_CALIBRATION_FLAGS]&1) && !current_test) faults|=F_CALIBRATION;
    if(c->v[C_CJ_MODE]) {
        if(!(c->v[C_CALIBRATION_FLAGS]&2)) faults|=F_CALIBRATION;
        if(!m->ext_valid || !max_cj_usable(c->v[C_TC_TYPE],m->external_c)) faults|=F_EXTERNAL;
        if(!m->ext_valid || (uint32_t)(now-m->ext_at)>c->v[C_EXT_TIMEOUT_MS]) faults|=F_EXTERNAL_STALE;
    }
    if(m->tc_valid && (m->pv<config_value(c,C_PROCESS_MIN_C10)*0.1f ||
       m->pv>config_value(c,C_PROCESS_MAX_C10)*0.1f)) faults|=F_TEMPERATURE;
    /* Commissioning is a separate, volatile, bounded mode. Its raw ceiling
       does not depend on the gain/offset being calibrated. */
    if(current_test) {
        if(!isfinite(m->pv) || m->pv>=CURRENT_TEST_MAX_C) faults|=F_TEMPERATURE;
        if(!isfinite(m->adc_rms) || m->adc_rms>CURRENT_TEST_MAX_RMS) faults|=F_OVERCURRENT;
        if((uint32_t)(now-s->last_contact)>CURRENT_TEST_LINK_MS) faults|=F_COMMUNICATION;
    }
    if(delay_fault(m->current_valid && m->current_ma>c->v[C_OVERCURRENT_MA],
       &s->over_timing,&s->over_since,now,c->v[C_OVERCURRENT_MS])) faults|=F_OVERCURRENT;
    /* Ignore mixed RMS windows for 250 ms after a gate transition. */
    bool steady=(uint32_t)(now-changed)>=250 && m->current_valid &&
        (uint32_t)(now-m->current_at)<=c->v[C_CURRENT_TIMEOUT_MS] &&
        (int32_t)(m->current_at-changed)>=200;
    if(delay_fault(steady && !gate && m->current_ma>c->v[C_OFF_CURRENT_MA],
       &s->off_timing,&s->off_since,now,c->v[C_OFF_CURRENT_MS])) faults|=F_STUCK_OUTPUT;
    /* Sum valid ON time across burst cycles; exclude OFF and mixed RMS windows.
       A good ON current clears the timer. Very short pulses cannot be tested. */
    bool on_sample=s->mode && steady && gate && c->v[C_OPEN_CURRENT_MA];
    if(!s->mode || !c->v[C_OPEN_CURRENT_MA] || (on_sample && m->current_ma>=c->v[C_OPEN_CURRENT_MA])) {
        s->open_timing=false;s->open_elapsed=0;
    } else if(on_sample) {
        if(s->open_timing) {
            uint32_t dt=now-s->open_since,limit=c->v[C_OPEN_CURRENT_MS];
            s->open_elapsed=dt>=limit-s->open_elapsed?limit:s->open_elapsed+dt;
        }
        s->open_since=now;s->open_timing=true;
        if(s->open_elapsed>=c->v[C_OPEN_CURRENT_MS]) faults|=F_OPEN_HEATER;
    } else s->open_timing=false;
    if(s->mode && s->contact_seen && c->v[C_COMM_TIMEOUT_MS] &&
       (uint32_t)(now-s->last_contact)>c->v[C_COMM_TIMEOUT_MS]) faults|=F_COMMUNICATION;
    s->active=faults;
    if(s->mode && faults) { s->latched|=faults; controller_stop(s); }
    /* Dangerous measured conditions remain latched even in STOP. */
    s->latched|=faults&(F_TEMPERATURE|F_OVERCURRENT|F_STUCK_OUTPUT);
    if(!s->mode || faults || s->latched) { s->soak_started=s->soak_ready=false;s->output=0; return; }
    if(!s->soak_started && in_tolerance(s)) { s->soak_started=true;s->soak_since=now; }
    if(s->soak_started && (uint32_t)(now-s->soak_since)>=(uint32_t)c->v[C_SOAK_SECONDS]*1000u) s->soak_ready=true;
    if(s->save_requested) { s->output=0; return; } /* Commit mode before energizing. */
    if(current_test) { s->output=100.0f; return; }
    if(s->mode==MODE_MANUAL) { s->output=fminf(s->manual*0.01f,c->v[C_OUTPUT_LIMIT_100]*0.01f); return; }
    if((uint32_t)(now-s->pid_at)<c->v[C_PID_INTERVAL_MS]) return;
    float dt=(uint32_t)(now-s->pid_at)*0.001f; s->pid_at=now;
    float target=config_value(c,C_SETPOINT)*0.1f;
    if(c->v[C_RAMP_C10_MIN]) {
        float step=c->v[C_RAMP_C10_MIN]*dt/600.0f;
        s->working_sp+=fmaxf(-step,fminf(step,target-s->working_sp));
    } else s->working_sp=target;
    s->output=pid_step(&s->pid,s->working_sp,m->pv,dt,c->v[C_KP_1000]*0.001f,
        c->v[C_KI_1000]*0.001f,c->v[C_KD_100]*0.01f,c->v[C_D_FILTER_MS]*0.001f,
        c->v[C_OUTPUT_LIMIT_100]*0.01f);
}
uint8_t controller_mode(Controller *s,uint16_t mode,uint32_t now) {
    if(mode>MODE_MANUAL) return 3;
    if(mode==MODE_STOP) { controller_stop(s); return 0; }
    if(s->mode==MODE_CURRENT_TEST) return 6; /* No conversion to an unbounded RUN. */
    if(s->active || s->latched || s->save_requested) return 4;
    if(!s->m.tc_valid || !s->m.current_valid || !s->rotary.stable || !s->rotary.address ||
       !(s->config.v[C_CALIBRATION_FLAGS]&1) ||
       (uint32_t)(now-s->m.tc_at)>s->config.v[C_TC_TIMEOUT_MS] ||
       (uint32_t)(now-s->m.current_at)>s->config.v[C_CURRENT_TIMEOUT_MS]) return 4;
    if(s->config.v[C_CJ_MODE] && (!(s->config.v[C_CALIBRATION_FLAGS]&2) || !s->m.ext_valid ||
       !max_cj_usable(s->config.v[C_TC_TYPE],s->m.external_c) ||
       (uint32_t)(now-s->m.ext_at)>s->config.v[C_EXT_TIMEOUT_MS])) return 4;
    if(s->mode!=mode) {
        s->soak_started=s->soak_ready=false;
        pid_reset(&s->pid); s->working_sp=s->m.pv; s->pid_at=now;
        s->output=0; s->mode=mode;
    }
    if(s->boot_status==1) s->boot_status=0;
    remember(s,C_POWERUP_MODE,mode);
    if(mode==MODE_MANUAL) remember(s,C_MANUAL_PRESET_100,s->manual);
    s->contact_seen=true;s->last_contact=now; return 0;
}
uint8_t controller_write(Controller *s,uint16_t a,uint16_t n,const uint16_t *v,bool broadcast,uint32_t now) {
    if(!n) return 3;
    /* Broadcast only permits a single STOP command, never an unattended start. */
    if(broadcast && !(a==REG_MODE && n==1 && v[0]==0)) return 3;
    if(a==REG_WORKING_SETTINGS) {
        if(n!=3) return 3;
        if(s->save_requested || s->mode==MODE_CURRENT_TEST) return 6;
        Config candidate=s->config;
        candidate.v[C_SETPOINT]=v[0];candidate.v[C_TOLERANCE_LOW_C10]=v[1];candidate.v[C_TOLERANCE_HIGH_C10]=v[2];
        if(!config_valid(&candidate)) return 3;
        if(memcmp(&candidate,&s->config,sizeof(candidate))) {
            s->config=candidate;s->dirty=true;s->config_revision++;
            s->soak_started=s->soak_ready=false;
        }
        if(s->dirty) { s->save_requested=true;s->storage_status=1; }
        return 0;
    }
    if(a<CONFIG_COUNT) {
        if(n>CONFIG_COUNT-a) return 2;
        if(s->save_requested) return 6;
        Config candidate=s->config;
        for(unsigned i=0;i<n;i++) {
            unsigned reg=a+i;
            if(reg==C_POWERUP_MODE && v[i]!=s->config.v[reg]) return 3;
            if(s->mode && reg!=C_SETPOINT && reg!=C_TOLERANCE_LOW_C10 && reg!=C_TOLERANCE_HIGH_C10) return 6;
            candidate.v[reg]=v[i];
        }
        /* A legacy low-word write selects a short period, never stale high bits. */
        if(a<=C_BURST_PERIOD_MS && a+n>C_BURST_PERIOD_MS && a+n<=C_BURST_PERIOD_MS_HIGH)
            candidate.v[C_BURST_PERIOD_MS_HIGH]=0;
        if(!config_valid(&candidate)) return 3;
        /* Calibration edits revoke the corresponding confirmation bit unless
           it is explicitly supplied in this same atomic transaction. */
        bool flags_written=a<=C_CALIBRATION_FLAGS && a+n>C_CALIBRATION_FLAGS;
        if(!flags_written) {
            for(unsigned i=0;i<n;i++) if(candidate.v[a+i]!=s->config.v[a+i]) {
                if(a+i>=C_CURRENT_GAIN_UA && a+i<=C_CURRENT_NOISE_C100) candidate.v[C_CALIBRATION_FLAGS]&=~1u;
                if(a+i>=C_EXT_TEMP_4_C10 && a+i<=C_EXT_TEMP_OFFSET_C100) candidate.v[C_CALIBRATION_FLAGS]&=~2u;
            }
        }
        if(memcmp(&candidate,&s->config,sizeof(candidate))) {
            for(unsigned i=0;i<CONFIG_COUNT;i++) if(candidate.v[i]!=s->config.v[i]) {
                if(i>=C_TC_TYPE && i<=C_TC_OFFSET_C100) s->m.tc_valid=false;
                if(i>=C_CURRENT_GAIN_UA && i<=C_CURRENT_NOISE_C100) s->m.current_valid=false;
                if(i>=C_EXT_TEMP_4_C10 && i<=C_EXT_TEMP_OFFSET_C100) s->m.ext_valid=false;
                if(i==C_SETPOINT || i==C_TOLERANCE_LOW_C10 || i==C_TOLERANCE_HIGH_C10 ||
                   i==C_SOAK_SECONDS || i==C_RELAY_FUNCTION) s->soak_started=s->soak_ready=false;
            }
            s->config=candidate; s->dirty=true; s->config_revision++;
        }
        return 0;
    }
    if(a<REG_MODE || a>REG_CURRENT_TEST || n!=1) return 2;
    switch(a) {
    case REG_MODE: return controller_mode(s,v[0],now);
    case REG_MANUAL:
        if(v[0]>10000) return 3;
        if(s->save_requested || s->mode==MODE_CURRENT_TEST) return 6;
        s->manual=v[0];
        if(s->mode==MODE_MANUAL) remember(s,C_MANUAL_PRESET_100,v[0]);
        return 0;
    case REG_SAVE:
        if(v[0]!=SAVE_KEY) return 3;
        if(s->mode || s->save_requested) return 6;
        s->save_requested=true; s->storage_status=1; return 0;
    case REG_CLEAR:
        if(v[0]!=CLEAR_KEY) return 3;
        if(s->mode || s->active) return 4;
        s->latched=0; return 0;
    case REG_CURRENT_TEST:
        if(v[0]!=CURRENT_TEST_KEY) return 3;
        /* Requires an explicitly saved STOP configuration; never changes
           EEPROM, the confirmation flag, or the deadline on a retry. */
        if(s->mode || s->save_requested) return 6;
        if(s->dirty || s->config.v[C_POWERUP_MODE]!=MODE_STOP ||
           s->config.v[C_CJ_MODE] || s->config.v[C_OUTPUT_LIMIT_100]!=10000 ||
           s->latched || (s->active&~F_CALIBRATION) || s->storage_status==4 ||
           !s->rotary.stable || !s->rotary.address ||
           !s->m.tc_valid || !s->m.current_valid ||
           !isfinite(s->m.pv) || s->m.pv>=CURRENT_TEST_MAX_C ||
           !isfinite(s->m.adc_rms) || s->m.adc_rms>10.0f ||
           (uint32_t)(now-s->m.tc_at)>s->config.v[C_TC_TIMEOUT_MS] ||
           (uint32_t)(now-s->m.current_at)>s->config.v[C_CURRENT_TIMEOUT_MS]) return 4;
        s->mode=MODE_CURRENT_TEST;s->output=0;s->manual=0;pid_reset(&s->pid);
        s->current_test_since=now;s->last_contact=now;s->contact_seen=true;
        s->soak_started=s->soak_ready=false;
        return 0;
    default: return 2;
    }
}
static uint16_t u16(float v) { return (uint16_t)lroundf(fminf(65535,fmaxf(0,v))); }
static uint16_t s16(float v) { return (uint16_t)(int16_t)lroundf(fminf(32767,fmaxf(-32768,v))); }
static uint16_t age(uint32_t now,uint32_t at,bool valid) {
    uint32_t d=now-at; return !valid||d>65535?65535:(uint16_t)d;
}
uint8_t controller_read(const Controller *s,bool input,uint16_t a,uint16_t n,uint16_t *v,uint32_t now,bool gate,bool relay) {
    if(!input) {
        if(a>=REG_WORKING_SETTINGS && a<REG_WORKING_SETTINGS+3u && n<=REG_WORKING_SETTINGS+3u-a) {
            uint16_t work[3]={s->config.v[C_SETPOINT],s->config.v[C_TOLERANCE_LOW_C10],s->config.v[C_TOLERANCE_HIGH_C10]};
            memcpy(v,work+a-REG_WORKING_SETTINGS,n*2u);return 0;
        }
        if(a<CONFIG_COUNT && n<=CONFIG_COUNT-a) { memcpy(v,s->config.v+a,n*2u); return 0; }
        if(a>=REG_MODE && a<=REG_CURRENT_TEST && n<=REG_CURRENT_TEST+1u-a) {
            for(unsigned i=0;i<n;i++) {
                uint32_t elapsed=(uint32_t)(now-s->current_test_since);
                v[i]=(a+i==REG_MODE)?s->mode:(a+i==REG_MANUAL?s->manual:
                    (a+i==REG_CURRENT_TEST && s->mode==MODE_CURRENT_TEST && elapsed<CURRENT_TEST_MS
                     ? (uint16_t)(CURRENT_TEST_MS-elapsed):0));
            }
            return 0;
        }
        return 2;
    }
    if(a>=INPUT_COUNT || n>INPUT_COUNT-a) return 2;
    const Measurements *m=&s->m;
    uint16_t t[INPUT_COUNT]={0};
#define U32(i,x) do { uint32_t value_=(x);t[i]=(uint16_t)(value_>>16);t[(i)+1]=(uint16_t)value_; } while(0)
    t[0]=0x0205; t[1]=0x0204; t[2]=s->rotary.address; t[3]=s->rotary.raw;
    t[4]=s->mode; t[5]=gate; t[6]=relay; t[7]=s->config.v[C_CJ_MODE];
    U32(8,s->active); U32(10,s->latched); U32(12,now/1000); U32(14,s->sample_id);
    t[16]=s16(m->pv*10); t[17]=s16(m->cj*100); t[18]=s16(m->external_c*10);
    t[19]=s->config.v[C_SETPOINT]; t[20]=s16(s->working_sp*10); t[21]=u16(s->output*100);
    t[22]=u16(m->current_ma); t[23]=u16(m->adc_mean); t[24]=u16(m->adc_rms*10);
    t[25]=m->adc_min; t[26]=m->adc_max; t[27]=u16(m->external_mv);
    t[28]=u16(m->external_ua); U32(29,m->ext_hz); t[31]=m->max_status;
    t[32]=age(now,m->tc_at,m->tc_valid); t[33]=age(now,m->current_at,m->current_valid);
    t[34]=age(now,m->ext_at,m->ext_valid);
    t[35]=(m->tc_valid?1:0)|(m->current_valid?2:0)|(m->ext_valid?4:0);
    t[36]=s->dirty; t[37]=s->storage_status; U32(38,s->saved_sequence);
    U32(40,s->config_revision); U32(42,m->adc_overruns);
    t[44]=s16(s->pid.integral*100); t[45]=s16(s->pid.derivative*100);
    t[46]=30; t[47]=s->config.v[C_CALIBRATION_FLAGS];
    t[58]=s->config.v[C_RELAY_FUNCTION];
    t[59]=!s->mode?0:(s->soak_ready?3:(s->soak_started?2:1));
    uint32_t elapsed=s->soak_started?(uint32_t)(now-s->soak_since)/1000u:0;
    t[60]=s->soak_ready?0:(elapsed>=s->config.v[C_SOAK_SECONDS]?0:(uint16_t)(s->config.v[C_SOAK_SECONDS]-elapsed));
    t[61]=s->config.v[C_POWERUP_MODE];t[62]=s->boot_status;t[63]=CONFIG_COUNT;
    memcpy(v,t+a,n*2u);
#undef U32
    return 0;
}
