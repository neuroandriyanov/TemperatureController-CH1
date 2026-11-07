#include "core.h"
#include "modbus.h"
#include "storage.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static unsigned checks;
#define TEST(x) do {checks++;if(!(x)) {fprintf(stderr,"FAIL %s:%d: %s\n",__FILE__,__LINE__,#x);assert(x);}} while(0)
static void near(float a,float b,float e) { TEST(fabsf(a-b)<e); }
static void committed(Controller *s) { s->save_requested=false;s->storage_status=2;s->dirty=false;s->saved_sequence++; }
static void fresh(Controller *s,uint32_t now) {
    s->m.tc_at=s->m.current_at=s->m.ext_at=now;
    controller_update(s,now,false,now);
}
static void ready(Controller *s,uint32_t now) {
    controller_init(s);s->config.v[C_CALIBRATION_FLAGS]=3;s->rotary.address=1;s->rotary.raw=1;s->rotary.stable=true;
    s->m.tc_valid=s->m.current_valid=s->m.ext_valid=true;
    s->m.pv=25;s->m.cj=25;s->m.external_c=25;
    s->m.tc_at=s->m.current_at=s->m.ext_at=now;s->last_contact=now;
    controller_update(s,now,false,now);TEST(s->active==0);
}
static size_t finish(uint8_t *q,size_t n) {uint16_t crc=modbus_crc(q,n);q[n++]=(uint8_t)crc;q[n++]=(uint8_t)(crc>>8);return n;}
static void word(uint8_t *p,uint16_t v) {p[0]=(uint8_t)(v>>8);p[1]=(uint8_t)v;}
static size_t command(uint8_t *q,uint8_t slave,uint8_t fc,uint16_t a,uint16_t v) {
    q[0]=slave;q[1]=fc;word(q+2,a);word(q+4,v);return finish(q,6);
}
static void test_modbus(void) {
    Controller s;ready(&s,100);ModbusStats stats={0};uint8_t q[256],r[256];
    const uint8_t vector[]={1,3,0,0,0,10};TEST(modbus_crc(vector,6)==0xCDC5);
    size_t n=command(q,1,3,0,CONFIG_COUNT);
    TEST(modbus_process(&s,q,n,r,100,false,false,&stats)==5+2*CONFIG_COUNT);
    TEST(r[3]==2 && r[4]==138); /* default 650 */
    q[7]^=1;TEST(modbus_process(&s,q,8,r,100,false,false,&stats)==0);
    q[7]^=1;TEST(modbus_process(&s,q,8,r,100,false,false,&stats)>0); /* recovery */
    for(size_t i=0;i<8;i++) TEST(modbus_process(&s,q,i,r,100,false,false,&stats)==0);
    n=command(q,1,3,65535,2);TEST(modbus_process(&s,q,n,r,100,false,false,&stats)==5 && r[2]==2);
    n=command(q,1,3,0,126);TEST(modbus_process(&s,q,n,r,100,false,false,&stats)==5 && r[2]==3);
    n=command(q,1,99,0,1);TEST(modbus_process(&s,q,n,r,100,false,false,&stats)==5 && r[2]==1);
    n=command(q,2,6,0,500);TEST(modbus_process(&s,q,n,r,100,false,false,&stats)==0 && s.config.v[0]==650);
    n=command(q,1,6,0,500);TEST(modbus_process(&s,q,n,r,100,false,false,&stats)==8 && s.config.v[0]==500);
    q[0]=1;q[1]=16;word(q+2,0);word(q+4,2);q[6]=4;word(q+7,600);word(q+9,9);n=finish(q,11);
    TEST(modbus_process(&s,q,n,r,100,false,false,&stats)==5 && r[2]==3 && s.config.v[0]==500);
    word(q+9,7);n=finish(q,11);TEST(modbus_process(&s,q,n,r,100,false,false,&stats)==8 && s.config.v[0]==600 && s.config.v[1]==7);
    q[6]=2;n=finish(q,11);TEST(modbus_process(&s,q,n,r,100,false,false,&stats)==5 && r[2]==3);
    word(q+2,CONFIG_COUNT-1);q[6]=4;n=finish(q,11);TEST(modbus_process(&s,q,n,r,100,false,false,&stats)==5 && r[2]==2);
    ready(&s,100);
    n=command(q,0,6,REG_MODE,MODE_AUTO);TEST(modbus_process(&s,q,n,r,100,false,false,&stats)==0 && s.mode==0);
    n=command(q,1,6,REG_MODE,MODE_AUTO);TEST(modbus_process(&s,q,n,r,100,false,false,&stats)==8 && s.mode==1);
    n=command(q,0,6,REG_MODE,MODE_STOP);TEST(modbus_process(&s,q,n,r,100,false,false,&stats)==0 && s.mode==0);
    uint32_t rng=1234567;
    struct {uint32_t before;uint8_t bytes[256];uint32_t after;} guarded={0x12345678,{0},0x87654321};
    for(unsigned i=0;i<50000;i++) {
        rng=rng*1664525u+1013904223u;n=4+(rng%253);
        for(size_t j=0;j<n;j++) {rng=rng*1664525u+1013904223u;q[j]=(uint8_t)(rng>>24);}
        q[0]=(i&1)?1:0;if(i%3==0) q[1]=16;
        if(i%4) finish(q,n-2);
        size_t out=modbus_process(&s,q,n,guarded.bytes,100,false,false,&stats);
        TEST(out<=256 && guarded.before==0x12345678 && guarded.after==0x87654321 && config_valid(&s.config));
    }
    puts("Modbus: CRC, lengths, bounds, atomic writes, broadcast, 50000 fuzz packets OK");
}
static void test_framer(void) {
    RtuFramer f={0};
    rtu_byte(&f,1,0);rtu_byte(&f,2,300);rtu_poll(&f,2049);TEST(!f.ready);
    rtu_poll(&f,2050);TEST(f.ready && f.length==2);rtu_release(&f);
    rtu_byte(&f,1,3000);rtu_byte(&f,2,4100);rtu_poll(&f,5850);TEST(!f.ready && !f.started);
    rtu_byte(&f,3,6000);rtu_poll(&f,7750);TEST(f.ready && f.bytes[0]==3);rtu_release(&f);
    for(unsigned i=0;i<257;i++) rtu_byte(&f,0,(uint32_t)(8000+i*286));
    TEST(f.discard);rtu_poll(&f,100000);TEST(!f.ready && f.length==0);
    rtu_byte(&f,1,UINT32_MAX-100);rtu_poll(&f,1649);TEST(f.ready);rtu_release(&f);
    rtu_error(&f,2000);rtu_byte(&f,1,2100);rtu_poll(&f,4000);TEST(!f.ready && !f.discard);
    rtu_byte(&f,1,5000);rtu_byte(&f,2,6020);TEST(!f.discard);rtu_poll(&f,7770);TEST(f.ready);rtu_release(&f);
    puts("RTU framing: timing, gaps, overflow, wraparound, UART errors OK");
}
static void test_measurements(void) {
    uint8_t b[3];TEST(max_cj_encode(-10,b));near(max_cj_decode(b),-10,0.001f);
    TEST(max_cj_encode(127.984375f,b));near(max_cj_decode(b),127.984375f,0.001f);
    TEST(!max_cj_encode(128,b) && !max_cj_encode(-64.1f,b));
    TEST(!max_cj_usable(3,126) && max_cj_usable(3,-55) && !max_cj_usable(0,-1) && !max_cj_usable(5,-51));
    b[0]=0xFF;b[1]=0x60;b[2]=0;near(max_tc_decode(b),-10,0.001f);
    b[2]=31;near(max_tc_decode(b),-10,0.001f); /* Datasheet X bits must be ignored. */
    uint16_t adc[1000];Moments m;moments_reset(&m);
    for(unsigned i=0;i<1000;i++) adc[i]=(uint16_t)lroundf(2000+500*sinf(2*3.14159265358979323846f*50*i/5000));
    moments_add(&m,adc,1000);near(moments_rms(&m),500/sqrtf(2),0.1f);
    Config c;config_defaults(&c);near(current_ma(moments_rms(&m),&c),7194.812f,3);
    c.v[C_CURRENT_OFFSET_MA]=(uint16_t)-100;near(current_ma(0,&c),0,0.01f);
    c.v[C_CURRENT_NOISE_C100]=1000;near(current_ma(10,&c),0,0.01f);
    c.v[C_CURRENT_OFFSET_MA]=0;c.v[C_CURRENT_GAIN_UA]=25000;c.v[C_CURRENT_NOISE_C100]=0;
    near(current_ma(400,&c),10000,0.01f);
    config_defaults(&c);float mv,ua,temp;
    float hz=(c.v[C_EXT_VOLT_4_MV]/2500.0f*0.4f+0.05f)*500000;
    TEST(external_convert(hz,&c,&mv,&ua,&temp));near(ua,4000,0.1f);near(temp,-10,0.01f);
    hz=(c.v[C_EXT_VOLT_20_MV]/2500.0f*0.4f+0.05f)*500000;
    TEST(external_convert(hz,&c,&mv,&ua,&temp));near(ua,20000,0.1f);near(temp,150,0.01f);
    c.v[C_EXT_OFFSET_UA]=100;c.v[C_EXT_TEMP_OFFSET_C100]=(uint16_t)-250;
    TEST(external_convert(hz,&c,&mv,&ua,&temp));near(temp,148.5f,0.01f);
    TEST(!external_convert(225000,&c,&mv,&ua,&temp));
    /* Synchronous VFC intervals are not a uniform-period square wave.
       A 192/288-tick stream is legal below full scale (AD7741 fig. 7). */
    uint16_t periods[126];
    for(unsigned i=0;i<126;i++) periods[i]=(i%3==2)?288:192;
    TEST(external_capture_frequency(periods,126,&hz));near(hz,214285.714f,0.1f);
    config_defaults(&c);
    TEST(external_convert(hz,&c,&mv,&ua,&temp));
    periods[19]=179;TEST(!external_capture_frequency(periods,126,&hz));
    periods[19]=2101;TEST(!external_capture_frequency(periods,126,&hz));
    periods[19]=0;TEST(!external_capture_frequency(periods,126,&hz));
    TEST(!external_capture_frequency(periods,0,&hz));near(hz,0,0.001f);
    TEST(!external_capture_frequency(NULL,126,&hz));
    TEST(!external_capture_frequency(periods,129,&hz));
    for(unsigned i=0;i<126;i++) periods[i]=192;
    TEST(external_capture_frequency(periods,126,&hz));near(hz,250000,0.1f);
    TEST(!external_convert(hz,&c,&mv,&ua,&temp)); /* Mean overrange is still rejected. */
    for(unsigned a=0;a<256;a++) {
        uint16_t inv=(uint16_t)(~a&255u);
        uint16_t pins=(uint16_t)(((inv&127)<<3)|((inv&128)<<6));
        TEST(rotary_decode(pins)==a);
        Rotary r={0};TEST(rotary_update(&r,(uint8_t)a,0));TEST(!r.stable);
        rotary_update(&r,(uint8_t)a,249);TEST(!r.stable);
        rotary_update(&r,(uint8_t)a,250);TEST(r.stable && r.address==(a>=1 && a<=247?a:0));
    }
    Rotary r={0};rotary_update(&r,5,0);rotary_update(&r,4,249);rotary_update(&r,5,250);
    rotary_update(&r,5,499);TEST(!r.stable);rotary_update(&r,5,500);TEST(r.address==5);
    puts("Measurements: RMS, scaling, signed temperatures, 4-20 mA, 256 rotary codes OK");
}
static void test_control(void) {
    Pid p;pid_reset(&p);near(pid_step(&p,10,0,1,0,1,0,0,100),10,0.001f);
    near(pid_step(&p,10,0,0.5f,0,1,0,0,100),15,0.001f);
    pid_reset(&p);for(unsigned i=0;i<100;i++) near(pid_step(&p,200,0,1,2,1,0,0,100),100,0.001f);
    near(p.integral,0,0.001f);near(pid_step(&p,0,10,1,2,1,0,0,100),0,0.001f);
    pid_reset(&p);pid_step(&p,20,20,1,1,0,2,0,100);pid_step(&p,40,20,1,1,0,2,0,100);near(p.derivative,0,0.001f);
    pid_reset(&p);float plant=25;
    for(unsigned i=0;i<2400;i++) {
        float out=pid_step(&p,65,plant,0.25f,2.7f,0.1f,0,1,100);
        TEST(isfinite(out) && out>=0 && out<=100);
        plant+=(25+0.8f*out-plant)*0.25f/30;
    }
    near(plant,65,0.2f);
    Controller s;ready(&s,1000);s.manual=5000;TEST(controller_mode(&s,MODE_MANUAL,1000)==0);committed(&s);
    controller_update(&s,1000,false,1000);near(s.output,50,0.001f);
    controller_stop(&s);near(s.output,0,0.001f);committed(&s);
    TEST(controller_mode(&s,MODE_AUTO,1000)==0);committed(&s);
    controller_update(&s,5000,true,1000);TEST(!s.mode && !s.output && (s.latched&F_TC_STALE));
    ready(&s,1000);s.config.v[C_CJ_MODE]=1;s.m.external_c=150;
    controller_update(&s,1000,false,1000);TEST(s.active&F_EXTERNAL);TEST(controller_mode(&s,1,1000)==4);
    ready(&s,1000);TEST(controller_mode(&s,1,1000)==0);s.config.v[C_COMM_TIMEOUT_MS]=100;
    controller_update(&s,1101,false,1000);TEST(!s.mode && (s.latched&F_COMMUNICATION));
    ready(&s,1000);s.m.current_ma=20000;controller_update(&s,1000,true,0);
    controller_update(&s,1200,true,0);TEST(s.latched&F_OVERCURRENT);
    ready(&s,1000);s.m.current_ma=1000;s.config.v[C_OFF_CURRENT_MS]=300;
    controller_update(&s,1000,false,0);controller_update(&s,1300,false,0);TEST(s.latched&F_STUCK_OUTPUT);
    ready(&s,1000);s.config.v[C_OPEN_CURRENT_MA]=100;s.config.v[C_OPEN_CURRENT_MS]=300;
    TEST(controller_mode(&s,2,1000)==0);controller_update(&s,1000,true,0);controller_update(&s,1300,true,0);
    TEST(s.latched&F_OPEN_HEATER);
    ready(&s,1000);s.config.v[C_COMM_TIMEOUT_MS]=0;s.config.v[C_OPEN_CURRENT_MA]=100;s.config.v[C_OPEN_CURRENT_MS]=600;
    TEST(controller_mode(&s,2,1000)==0);committed(&s);
    controller_update(&s,1000,true,0);s.m.tc_at=s.m.current_at=1300;controller_update(&s,1300,true,0);
    TEST(s.open_elapsed==300 && !s.latched);
    s.m.tc_at=s.m.current_at=2000;controller_update(&s,2000,false,1400);TEST(s.open_elapsed==300);
    s.m.tc_at=s.m.current_at=3000;controller_update(&s,3000,true,2700);TEST(!s.latched && s.open_elapsed==300);
    s.m.tc_at=s.m.current_at=3300;controller_update(&s,3300,true,2700);TEST(s.latched&F_OPEN_HEATER);
    ready(&s,1000);s.config.v[C_OPEN_CURRENT_MA]=100;s.config.v[C_OPEN_CURRENT_MS]=600;
    TEST(controller_mode(&s,2,1000)==0);committed(&s);controller_update(&s,1000,true,0);
    s.m.tc_at=s.m.current_at=1300;controller_update(&s,1300,true,0);TEST(s.open_elapsed==300);
    s.m.current_ma=200;controller_update(&s,1301,true,0);TEST(!s.open_elapsed);
    s.m.current_ma=0;s.m.current_at=1400;controller_update(&s,1600,true,1399);TEST(!s.open_timing);
    ready(&s,1000);uint16_t gain=22000;TEST(controller_write(&s,C_CURRENT_GAIN_UA,1,&gain,false,1000)==0);
    TEST(!(s.config.v[C_CALIBRATION_FLAGS]&1));controller_update(&s,1000,false,0);TEST(s.active&F_CALIBRATION);
    TEST(!s.m.current_valid && controller_mode(&s,1,1000)==4);
    ready(&s,1000);TEST(controller_mode(&s,1,1000)==0);TEST(controller_write(&s,C_CURRENT_GAIN_UA,1,&gain,false,1000)==6);
    puts("Control: PID dt, anti-windup, derivative, STOP, stale data, trips, calibration gates OK");
}
static void test_resume_relay(void) {
    Controller s;ready(&s,1000);s.manual=3750;
    TEST(controller_mode(&s,MODE_MANUAL,1000)==0);
    TEST(s.save_requested && s.config.v[C_POWERUP_MODE]==MODE_MANUAL && s.config.v[C_MANUAL_PRESET_100]==3750);
    fresh(&s,1000);TEST(s.output==0); /* No heat before EEPROM commit. */
    committed(&s);fresh(&s,1000);near(s.output,37.5f,0.001f);
    uint16_t power=2500;TEST(controller_write(&s,REG_MANUAL,1,&power,false,1000)==0);
    TEST(s.save_requested && s.config.v[C_MANUAL_PRESET_100]==2500);
    fresh(&s,1001);TEST(s.output==0);committed(&s);fresh(&s,1002);near(s.output,25,0.001f);
    controller_stop(&s);TEST(s.output==0 && s.config.v[C_POWERUP_MODE]==0 && s.save_requested);
    committed(&s);controller_stop(&s);TEST(!s.save_requested); /* No wear on repeated STOP. */
    uint16_t bad=1;TEST(controller_write(&s,C_POWERUP_MODE,1,&bad,false,1003)==3);

    ready(&s,1000);s.config.v[C_POWERUP_MODE]=MODE_MANUAL;s.config.v[C_MANUAL_PRESET_100]=3750;
    controller_powerup(&s,0);controller_boot_update(&s,999);TEST(s.mode==0 && s.boot_status==1);
    controller_boot_update(&s,1000);TEST(s.mode==MODE_MANUAL && s.boot_status==2 && !s.contact_seen);
    fresh(&s,6001);near(s.output,37.5f,0.001f);TEST(!s.active && !s.save_requested);
    s.contact_seen=true;s.last_contact=6001;fresh(&s,11002);
    TEST(s.mode==0 && (s.latched&F_COMMUNICATION) && s.config.v[C_POWERUP_MODE]==0);

    ready(&s,1000);s.config.v[C_POWERUP_MODE]=MODE_AUTO;controller_powerup(&s,0);
    controller_boot_update(&s,1000);TEST(s.mode==MODE_AUTO && s.boot_status==2);
    ready(&s,1000);controller_powerup(&s,0);controller_boot_update(&s,1000);TEST(!s.mode && !s.boot_status);
    ready(&s,1000);s.config.v[C_POWERUP_MODE]=MODE_AUTO;controller_powerup(&s,0);controller_stop(&s);
    TEST(s.boot_status==3 && s.config.v[C_POWERUP_MODE]==0);
    ready(&s,1000);s.config.v[C_POWERUP_MODE]=MODE_AUTO;controller_powerup(&s,0);s.m.tc_valid=false;
    fresh(&s,1000);controller_boot_update(&s,1000);TEST(!s.mode && s.boot_status==1);
    fresh(&s,15000);controller_boot_update(&s,15000);TEST(!s.mode && s.boot_status==3 && s.save_requested);
    committed(&s);s.m.tc_valid=true;fresh(&s,16000);controller_boot_update(&s,16000);TEST(!s.mode);
    ready(&s,1000);s.config.v[C_POWERUP_MODE]=1;controller_powerup(&s,0);s.config.v[C_CALIBRATION_FLAGS]=0;
    fresh(&s,1000);controller_boot_update(&s,1000);TEST(!s.mode && s.boot_status==3);
    ready(&s,1000);s.config.v[C_POWERUP_MODE]=1;controller_powerup(&s,0);s.storage_status=4;
    fresh(&s,1000);controller_boot_update(&s,1000);TEST(!s.mode && s.boot_status==3);

    ready(&s,1000);s.config.v[C_COMM_TIMEOUT_MS]=0;s.config.v[C_RELAY_FUNCTION]=RELAY_SOAK;
    TEST(controller_mode(&s,MODE_MANUAL,1000)==0);committed(&s);fresh(&s,1000);
    TEST(!s.soak_started && !controller_relay(&s));
    s.m.pv=65;fresh(&s,2000);TEST(s.soak_started && !s.soak_ready && !controller_relay(&s));
    fresh(&s,601999);TEST(!controller_relay(&s));s.m.pv=40;fresh(&s,602000);
    TEST(s.soak_ready && !controller_relay(&s));s.m.pv=65;fresh(&s,602001);TEST(controller_relay(&s));
    s.config.v[C_RELAY_FUNCTION]=RELAY_TOLERANCE;TEST(controller_relay(&s));
    uint16_t sp=700;TEST(controller_write(&s,C_SETPOINT,1,&sp,false,602001)==0);TEST(!s.soak_started && !s.soak_ready);
    controller_stop(&s);TEST(!controller_relay(&s) && !s.soak_ready);
    /* Tick wrap and zero delay; MANUAL zero power still permits in-band indication. */
    ready(&s,UINT32_MAX-1000);s.config.v[C_COMM_TIMEOUT_MS]=0;s.config.v[C_SOAK_SECONDS]=2;
    s.config.v[C_RELAY_FUNCTION]=RELAY_SOAK;s.m.pv=65;
    TEST(controller_mode(&s,MODE_MANUAL,UINT32_MAX-1000)==0);committed(&s);
    fresh(&s,UINT32_MAX-1000);fresh(&s,999);TEST(controller_relay(&s));
    ready(&s,1000);s.config.v[C_SOAK_SECONDS]=0;s.config.v[C_RELAY_FUNCTION]=RELAY_SOAK;s.m.pv=65;
    TEST(controller_mode(&s,MODE_MANUAL,1000)==0);committed(&s);fresh(&s,1000);TEST(controller_relay(&s));
    s.m.tc_valid=false;fresh(&s,1001);TEST(!controller_relay(&s) && !s.soak_ready && !s.mode);
    /* Alarm relays work in STOP, and latched alarms remain indicated. */
    ready(&s,1000);
    const uint32_t triggers[]={F_TC,F_OVERCURRENT,F_OPEN_HEATER,F_STORAGE,F_TEMPERATURE,F_STUCK_OUTPUT};
    for(unsigned i=0;i<sizeof(triggers)/sizeof(triggers[0]);i++) {
        s.active=0;s.latched=triggers[i];s.config.v[C_RELAY_FUNCTION]=RELAY_ERROR;TEST(controller_relay(&s));
        s.config.v[C_RELAY_FUNCTION]=RELAY_OVERCURRENT;TEST(controller_relay(&s)==(triggers[i]==F_OVERCURRENT));
        s.config.v[C_RELAY_FUNCTION]=RELAY_HEATER;TEST(controller_relay(&s)==(triggers[i]==F_OPEN_HEATER));
        s.config.v[C_RELAY_FUNCTION]=RELAY_DEVICE;TEST(controller_relay(&s)==((triggers[i]&(F_TC|F_STORAGE|F_STUCK_OUTPUT))!=0));
        s.config.v[C_RELAY_FUNCTION]=RELAY_OFF;TEST(!controller_relay(&s));
    }
    uint16_t regs[6];TEST(controller_read(&s,true,58,6,regs,1000,false,false)==0);
    TEST(regs[0]==RELAY_OFF && regs[1]==0 && regs[5]==CONFIG_COUNT);
    puts("2.2: EEPROM-gated mode, power restore, startup faults, autonomous boot, relay modes, soak and tick wrap OK");
}
typedef struct {uint8_t memory[2048];int budget;} Memory;
static bool mem_read(void *ctx,uint16_t a,uint8_t *d,size_t n) {
    Memory *m=ctx;if((size_t)a+n>sizeof(m->memory)) return false;memcpy(d,m->memory+a,n);return true;
}
static bool mem_write(void *ctx,uint16_t a,const uint8_t *d,size_t n) {
    Memory *m=ctx;if((size_t)a+n>sizeof(m->memory)) return false;
    for(size_t i=0;i<n;i++) {if(m->budget==0) return false;if(m->budget>0) m->budget--;m->memory[a+i]=d[i];}return true;
}
static void test_storage(void) {
    Memory m;memset(&m,0xFF,sizeof(m));m.budget=-1;
    Storage st={&m,mem_read,mem_write,0,-1};Config c,read;config_defaults(&c);
    TEST(!storage_load(&st,&read));TEST(storage_save(&st,&c));
    TEST(storage_load(&st,&read) && !memcmp(&c,&read,sizeof(c)));
    Memory original=m;c.v[C_SETPOINT]=700;
    for(int cut=0;cut<120;cut++) {
        m=original;m.budget=cut;st.sequence=1;st.slot=0;
        bool success=storage_save(&st,&c);m.budget=-1;
        Storage reboot={&m,mem_read,mem_write,0,-1};TEST(storage_load(&reboot,&read));
        TEST(read.v[C_SETPOINT]==650 || read.v[C_SETPOINT]==700);
        if(success) TEST(read.v[C_SETPOINT]==700);
        TEST(!memcmp(m.memory+STORAGE_BASE,original.memory+STORAGE_BASE,STORAGE_SLOT_SIZE));
    }
    m=original;m.budget=-1;st.slot=0;st.sequence=1;TEST(storage_save(&st,&c));
    m.memory[STORAGE_BASE+STORAGE_SLOT_SIZE+20]^=1;TEST(storage_load(&st,&read) && read.v[C_SETPOINT]==650);
    /* Migration of a real-format 2.0 record: 41 registers, version 2. */
    memset(m.memory,0xFF,sizeof(m.memory));uint8_t *old=m.memory+STORAGE_BASE;
    memcpy(old,"TC2!",4);word(old+4,2);word(old+6,41);memset(old+8,0,4);old[11]=7;
    for(unsigned i=0;i<41;i++) word(old+12+2*i,c.v[i]);
    word(old+94,modbus_crc(old,94));TEST(storage_load(&st,&read));
    TEST(read.v[C_SETPOINT]==700 && read.v[C_PREFERRED_MODE]==1 && read.v[C_MANUAL_PRESET_100]==0);
    read.v[C_PREFERRED_MODE]=2;read.v[C_MANUAL_PRESET_100]=3750;TEST(storage_save(&st,&read));
    TEST(storage_load(&st,&read) && read.v[C_PREFERRED_MODE]==2 && read.v[C_MANUAL_PRESET_100]==3750);
    Controller reboot;controller_init(&reboot);reboot.config=read;TEST(reboot.mode==MODE_STOP && reboot.output==0);
    /* 2.1 migration retains settings but never infers a previous running state. */
    memset(m.memory,0xFF,sizeof(m.memory));old=m.memory+STORAGE_BASE;
    memcpy(old,"TC2!",4);word(old+4,3);word(old+6,43);memset(old+8,0,4);old[11]=8;
    for(unsigned i=0;i<43;i++) word(old+12+2*i,read.v[i]);
    word(old+98,modbus_crc(old,98));TEST(storage_load(&st,&read));
    TEST(read.v[C_POWERUP_MODE]==0 && read.v[C_RELAY_FUNCTION]==1 && read.v[C_SOAK_SECONDS]==600);
    read.v[C_POWERUP_MODE]=MODE_MANUAL;read.v[C_RELAY_FUNCTION]=RELAY_SOAK;read.v[C_SOAK_SECONDS]=900;
    TEST(storage_save(&st,&read));Config restored;TEST(storage_load(&st,&restored));
    TEST(!memcmp(&read,&restored,sizeof(read)));
    /* Version 4 migrates ALL calibration and last-mode fields, then version 5 persists 300 s. */
    memset(m.memory,0xFF,sizeof(m.memory));old=m.memory+STORAGE_BASE;
    memcpy(old,"TC2!",4);word(old+4,4);word(old+6,46);memset(old+8,0,4);old[11]=17;
    read.v[C_CURRENT_GAIN_UA]=20449;read.v[C_CURRENT_OFFSET_MA]=(uint16_t)-9;
    read.v[C_BURST_PERIOD_MS]=500;
    for(unsigned i=0;i<46;i++) word(old+12+2*i,read.v[i]);
    word(old+104,modbus_crc(old,104));TEST(storage_load(&st,&restored));
    TEST(config_burst_period_ms(&restored)==2000 && restored.v[C_POWERUP_MODE]==MODE_MANUAL);
    TEST(restored.v[C_CURRENT_GAIN_UA]==20449 && config_value(&restored,C_CURRENT_OFFSET_MA)==-9);
    restored.v[C_BURST_PERIOD_MS]=300000u&65535u;restored.v[C_BURST_PERIOD_MS_HIGH]=300000u>>16;
    TEST(storage_save(&st,&restored));TEST(storage_load(&st,&read));
    TEST(!memcmp(&read,&restored,sizeof(read)) && config_burst_period_ms(&read)==300000u);
    puts("EEPROM: CRC, dual slots, 120 byte-level power-loss points, legacy migration, 300 s period OK");
}
static void test_extended_period_and_working(void) {
    Controller s;ready(&s,1000);
    const uint32_t periods[]={2000,65535,65536,120000,300000};
    for(unsigned i=0;i<sizeof(periods)/sizeof(periods[0]);i++) {
        Config c=s.config;c.v[C_BURST_PERIOD_MS]=(uint16_t)periods[i];c.v[C_BURST_PERIOD_MS_HIGH]=(uint16_t)(periods[i]>>16);
        TEST(controller_write(&s,0,CONFIG_COUNT,c.v,false,1000)==0);
        TEST(config_burst_period_ms(&s.config)==periods[i]);
        TEST(burst_on_time_ms(periods[i],10000)==periods[i]);
        TEST(burst_on_time_ms(periods[i],5000)==periods[i]/2);
        TEST(burst_on_time_ms(periods[i],0)==0);
    }
    uint16_t low=2000;TEST(controller_write(&s,C_BURST_PERIOD_MS,1,&low,false,1000)==0);
    TEST(config_burst_period_ms(&s.config)==2000);low=1999;
    TEST(controller_write(&s,C_BURST_PERIOD_MS,1,&low,false,1000)==3);
    Config invalid=s.config;invalid.v[C_BURST_PERIOD_MS]=(uint16_t)(300001u&65535u);invalid.v[C_BURST_PERIOD_MS_HIGH]=4;
    TEST(!config_valid(&invalid));TEST(burst_on_time_ms(300001,10000)==0);
    TEST(burst_on_time_ms(300000,10001)==0);
    s.config.v[C_COMM_TIMEOUT_MS]=0;committed(&s);
    TEST(controller_mode(&s,MODE_AUTO,1000)==0);committed(&s);
    uint16_t work[]={1000,1000,1000}; /* 100 C, -100 / +100. */
    TEST(controller_write(&s,REG_WORKING_SETTINGS,3,work,false,1100)==0);
    TEST(s.mode==MODE_AUTO && s.config.v[C_POWERUP_MODE]==MODE_AUTO && s.save_requested);
    fresh(&s,1101);TEST(s.output==0);committed(&s);fresh(&s,10000);
    TEST(s.mode==MODE_AUTO && !s.active && s.output>0); /* PC not needed, sensors remain fresh. */
    TEST(controller_write(&s,REG_WORKING_SETTINGS,3,work,false,10001)==0 && !s.save_requested);
    Config previous=s.config;work[1]=18001;
    TEST(controller_write(&s,REG_WORKING_SETTINGS,3,work,false,10002)==3);
    TEST(!memcmp(&s.config,&previous,sizeof(previous)));
    work[1]=18000;TEST(controller_write(&s,REG_WORKING_SETTINGS,3,work,false,10002)==0);
    committed(&s);TEST(controller_write(&s,REG_WORKING_SETTINGS,3,work,true,10003)==3);
    uint16_t read[3];TEST(controller_read(&s,false,REG_WORKING_SETTINGS,3,read,10003,false,false)==0);
    TEST(read[0]==1000 && read[1]==18000 && read[2]==1000);
    puts("2.5: full-width PWM, boundaries, atomic saved working settings, autonomous PID OK");
}
static void test_current_commissioning(void) {
    Controller s;uint16_t key=CURRENT_TEST_KEY,out=0;
    ready(&s,1000);s.config.v[C_CALIBRATION_FLAGS]=2;
    fresh(&s,1000);TEST(s.active==F_CALIBRATION);
    TEST(controller_mode(&s,MODE_AUTO,1000)==4);
    TEST(controller_mode(&s,MODE_MANUAL,1000)==4);
    TEST(controller_mode(&s,MODE_CURRENT_TEST,1000)==3);
    uint16_t wrong=0;TEST(controller_write(&s,REG_CURRENT_TEST,1,&wrong,false,1000)==3);
    TEST(controller_write(&s,REG_CURRENT_TEST,1,&key,true,1000)==3);
    TEST(controller_write(&s,REG_CURRENT_TEST,1,&key,false,1000)==0);
    TEST(s.mode==MODE_CURRENT_TEST && s.config.v[C_CALIBRATION_FLAGS]==2);
    TEST(!s.dirty && !s.save_requested && s.config.v[C_POWERUP_MODE]==MODE_STOP);
    fresh(&s,1000);near(s.output,100,0.001f);TEST(!s.active);
    s.config.v[C_RELAY_FUNCTION]=RELAY_TOLERANCE;s.m.pv=65;
    TEST(!controller_relay(&s));s.m.pv=25;
    TEST(controller_mode(&s,MODE_AUTO,1000)==6);
    TEST(controller_write(&s,REG_MANUAL,1,&wrong,false,1000)==6);
    TEST(controller_write(&s,REG_CURRENT_TEST,1,&key,false,2000)==6);
    TEST(s.current_test_since==1000);
    TEST(controller_read(&s,false,REG_CURRENT_TEST,1,&out,2000,true,false)==0 && out==9000);
    for(uint32_t now=1100;now<11000;now+=100) {
        s.last_contact=now;fresh(&s,now);TEST(s.mode==MODE_CURRENT_TEST && s.output==100);
    }
    s.last_contact=11000;fresh(&s,11000);TEST(s.mode==MODE_STOP && s.output==0);
    TEST(s.active==F_CALIBRATION && s.config.v[C_CALIBRATION_FLAGS]==2 && !s.save_requested);
    TEST(controller_read(&s,false,REG_CURRENT_TEST,1,&out,11000,false,false)==0 && out==0);
    for(unsigned failure=0;failure<10;failure++) {
        ready(&s,1000);s.config.v[C_CALIBRATION_FLAGS]=2;fresh(&s,1000);
        switch(failure) {
        case 0:s.dirty=true;break;
        case 1:s.config.v[C_POWERUP_MODE]=MODE_AUTO;break;
        case 2:s.config.v[C_CJ_MODE]=1;break;
        case 3:s.config.v[C_OUTPUT_LIMIT_100]=5000;break;
        case 4:s.m.pv=65;break;
        case 5:s.m.adc_rms=11;break;
        case 6:s.m.current_valid=false;break;
        case 7:s.latched=F_LOOP;break;
        case 8:s.storage_status=4;break;
        case 9:s.rotary.stable=false;break;
        }
        TEST(controller_write(&s,REG_CURRENT_TEST,1,&key,false,1000)==4);
        TEST(s.mode==MODE_STOP && s.output==0);
    }
    const uint32_t fault_bits[]={F_TC,F_CURRENT,F_TEMPERATURE,F_OVERCURRENT,F_COMMUNICATION,F_EXTERNAL};
    for(unsigned i=0;i<6;i++) {
        ready(&s,1000);s.config.v[C_CALIBRATION_FLAGS]=2;fresh(&s,1000);
        TEST(controller_write(&s,REG_CURRENT_TEST,1,&key,false,1000)==0);
        s.config.v[C_COMM_TIMEOUT_MS]=0; /* Dedicated link timeout cannot be disabled. */
        uint32_t now=1100;
        switch(i) {
        case 0:s.m.tc_valid=false;break;
        case 1:s.m.current_valid=false;break;
        case 2:s.m.pv=65;break;
        case 3:s.m.adc_rms=401;break;
        case 4:now=2001;break;
        case 5:s.config.v[C_CJ_MODE]=1;s.m.ext_valid=false;break;
        }
        fresh(&s,now);TEST(s.mode==MODE_STOP && s.output==0 && (s.latched&fault_bits[i]));
    }
    ready(&s,1000);TEST(controller_write(&s,REG_CURRENT_TEST,1,&key,false,1000)==0);
    TEST(controller_mode(&s,MODE_STOP,1001)==0 && s.output==0 && s.mode==MODE_STOP);
    ready(&s,UINT32_MAX-500);s.config.v[C_CALIBRATION_FLAGS]=2;fresh(&s,UINT32_MAX-500);
    TEST(controller_write(&s,REG_CURRENT_TEST,1,&key,false,UINT32_MAX-500)==0);
    s.last_contact=9498;fresh(&s,9498);TEST(s.mode==MODE_CURRENT_TEST);
    s.last_contact=9499;fresh(&s,9499);TEST(s.mode==MODE_STOP && s.output==0);
    Controller reboot;controller_init(&reboot);reboot.config=s.config;
    controller_powerup(&reboot,0);TEST(reboot.mode==MODE_STOP && reboot.boot_status==0);
    puts("Current commissioning: bounded time, STOP, no persistence, raw ceiling, faults, retry, wraparound OK");
}
int main(void) {
    test_modbus();test_framer();test_measurements();test_control();test_resume_relay();test_storage();test_current_commissioning();test_extended_period_and_working();
    printf("PASS: %u assertions\n",checks);return 0;
}
