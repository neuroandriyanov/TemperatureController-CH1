#include "board.h"
#include <string.h>
#include <math.h>
static volatile uint16_t adc_data[1000];
static volatile uint32_t adc_sequence;
static volatile bool adc_error,capture_done;
static uint16_t capture_data[128];
static uint32_t adc_seen,capture_started,capture_next,tc_started,tc_next;
static bool capturing,tc_waiting,tc_configured;
static uint16_t tc_settings[7];
static Moments accumulated;

void HAL_ADC_ConvHalfCpltCallback(ADC_HandleTypeDef *h) { if(h==&hadc) adc_sequence++; }
void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *h) { if(h==&hadc) adc_sequence++; }
void HAL_ADC_ErrorCallback(ADC_HandleTypeDef *h) { (void)h;adc_error=true; }
void HAL_TIM_IC_CaptureCallback(TIM_HandleTypeDef *h) { if(h==&htim1) capture_done=true; }
static bool max_io(uint8_t address,uint8_t *data,uint16_t n,bool write) {
    uint8_t tx[16]={0},rx[16]={0};
    if(n>15) return false;
    tx[0]=address|(write?0x80:0);if(write) memcpy(tx+1,data,n);
    HAL_GPIO_WritePin(GPIOA,GPIO_PIN_4,GPIO_PIN_RESET);
    HAL_StatusTypeDef result=HAL_SPI_TransmitReceive(&hspi1,tx,rx,n+1,5);
    HAL_GPIO_WritePin(GPIOA,GPIO_PIN_4,GPIO_PIN_SET);
    if(result!=HAL_OK) return false;
    if(!write) memcpy(data,rx+1,n);
    return true;
}
static uint8_t max_cr0(const Config *c) { return (uint8_t)(0x20 | (c->v[C_CJ_MODE]?8:0) | (c->v[C_FILTER_60HZ]?0:1)); }
static bool max_setup(const Config *c) {
    uint8_t d[10]={0};d[0]=max_cr0(c);d[1]=(uint8_t)((c->v[C_AVERAGE_LOG2]<<4)|c->v[C_TC_TYPE]);
    d[2]=0;d[3]=127;d[4]=0xC0;d[5]=0x7F;d[6]=0xFF;d[7]=0x80;d[8]=0;
    /* Offset is only applicable to internal cold-junction measurement. */
    d[9]=c->v[C_CJ_MODE]?0:(uint8_t)(int8_t)lroundf(config_value(c,C_CJ_OFFSET_C100)*0.16f);
    if(!max_io(0,d,sizeof(d),true)) return false;
    uint8_t verify[10];if(!max_io(0,verify,sizeof(verify),false) || memcmp(d,verify,sizeof(d))) return false;
    uint8_t discarded[6];return max_io(0x0A,discarded,6,false);
}
void sensors_init(Controller *c) {
    (void)c;moments_reset(&accumulated);
    if(HAL_ADC_Start_DMA(&hadc,(uint32_t *)(uintptr_t)adc_data,1000)!=HAL_OK ||
       HAL_TIM_Base_Start(&htim3)!=HAL_OK) Error_Handler();
}
static void poll_current(Controller *s,uint32_t now) {
    uint32_t seq=adc_sequence;
    if(adc_error) { s->m.current_valid=false;return; }
    if(seq==adc_seen) return;
    if(seq-adc_seen!=1) { s->m.adc_overruns++;moments_reset(&accumulated);s->m.current_valid=false; }
    adc_seen=seq;
    Moments part;moments_reset(&part);
    unsigned half=(seq&1u)?0:500;
    moments_add(&part,adc_data+half,500);
    __DMB();
    uint32_t remaining=__HAL_DMA_GET_COUNTER(&hdma_adc);
    bool safe_half=(seq&1u)?(remaining<=500 && remaining>0):(remaining>500);
    if(seq!=adc_sequence || !safe_half) {
        moments_reset(&accumulated);s->m.current_valid=false;s->m.adc_overruns++;return;
    }
    accumulated.sum+=part.sum;accumulated.squares+=part.squares;accumulated.n+=part.n;
    if(part.min<accumulated.min) accumulated.min=part.min;
    if(part.max>accumulated.max) accumulated.max=part.max;
    if(accumulated.n==1000) {
        s->m.adc_mean=(float)accumulated.sum/1000;
        s->m.adc_rms=moments_rms(&accumulated);
        s->m.current_ma=current_ma(s->m.adc_rms,&s->config);
        s->m.adc_min=accumulated.min;s->m.adc_max=accumulated.max;
        s->m.current_valid=accumulated.min>2 && accumulated.max<4093;
        s->m.current_at=now;moments_reset(&accumulated);
    }
}
static void poll_external(Controller *s,uint32_t now) {
    if(capturing && capture_done) {
        HAL_TIM_IC_Stop_DMA(&htim1,TIM_CHANNEL_1);capturing=false;capture_done=false;
        float hz;
        bool valid=external_capture_frequency(capture_data+2,126,&hz);
        s->m.ext_hz=(uint32_t)hz;
        bool converted=external_convert(hz,&s->config,&s->m.external_mv,&s->m.external_ua,&s->m.external_c);
        s->m.ext_valid=valid && converted;s->m.ext_at=now;capture_next=now+50;
    }
    if(capturing && (uint32_t)(now-capture_started)>200) {
        HAL_TIM_IC_Stop_DMA(&htim1,TIM_CHANNEL_1);capturing=false;s->m.ext_valid=false;capture_next=now+100;
    }
    if(!capturing && (int32_t)(now-capture_next)>=0) {
        capture_done=false;__HAL_TIM_SET_COUNTER(&htim1,0);capture_started=now;capture_next=now+100;
        capturing=HAL_TIM_IC_Start_DMA(&htim1,TIM_CHANNEL_1,(uint32_t *)capture_data,128)==HAL_OK;
        if(!capturing) s->m.ext_valid=false;
    }
}
static void poll_tc(Controller *s,uint32_t now) {
    Config *c=&s->config;
    uint16_t settings[7]={c->v[C_TC_TYPE],c->v[C_CJ_MODE],c->v[C_FILTER_60HZ],c->v[C_AVERAGE_LOG2],
                          c->v[C_CJ_OFFSET_C100],c->v[C_TC_OFFSET_C100],c->v[C_CALIBRATION_FLAGS]};
    if(memcmp(settings,tc_settings,sizeof(settings))) {
        tc_configured=false;tc_waiting=false;tc_next=now;s->m.tc_valid=false;
        memcpy(tc_settings,settings,sizeof(settings));
    }
    if((int32_t)(now-tc_next)<0) return;
    if(!tc_configured) {
        tc_configured=max_setup(c);tc_waiting=false;
        if(!tc_configured) { s->m.tc_valid=false;s->m.max_status=0x100;tc_next=now+500;return; }
    }
    if(tc_waiting) {
        if(HAL_GPIO_ReadPin(GPIOB,GPIO_PIN_1)==GPIO_PIN_RESET) {
            uint8_t status;
            if(!max_io(0x0F,&status,1,false)) {
                s->m.tc_valid=false;s->m.max_status=0x100;tc_configured=false;tc_waiting=false;tc_next=now+100;return;
            }
            if(status) { s->m.tc_valid=false;s->m.max_status=status; }
        }
        if(HAL_GPIO_ReadPin(GPIOB,GPIO_PIN_0)==GPIO_PIN_RESET) {
            uint8_t d[6];tc_waiting=false;
            if(!max_io(0x0A,d,6,false)) { s->m.tc_valid=false;s->m.max_status=0x100;tc_configured=false;tc_next=now+100;return; }
            s->m.max_status=d[5];s->m.cj=max_cj_decode(d);
            s->m.pv=max_tc_decode(d+2)+config_value(c,C_TC_OFFSET_C100)*0.01f;
            s->m.tc_valid=d[5]==0 && isfinite(s->m.pv);
            s->m.tc_at=now;s->sample_id++;
        } else if((uint32_t)(now-tc_started)>c->v[C_TC_TIMEOUT_MS]) {
            s->m.tc_valid=false;s->m.max_status=0x200;tc_configured=false;tc_waiting=false;tc_next=now+100;return;
        } else { tc_next=now+5;return; }
    }
    if(c->v[C_CJ_MODE]) {
        uint8_t cj[2];
        if(!s->m.ext_valid || (uint32_t)(now-s->m.ext_at)>c->v[C_EXT_TIMEOUT_MS] ||
           !max_cj_usable(c->v[C_TC_TYPE],s->m.external_c) ||
           !max_cj_encode(s->m.external_c,cj)) { s->m.tc_valid=false;tc_next=now+20;return; }
        if(!max_io(0x0A,cj,2,true)) { s->m.tc_valid=false;tc_configured=false;tc_next=now+100;return; }
    }
    uint8_t cr0=max_cr0(c)|0x40;
    if(!max_io(0,&cr0,1,true)) { s->m.tc_valid=false;tc_configured=false;tc_next=now+100;return; }
    tc_waiting=true;tc_started=now;tc_next=now+20;
}
void sensors_poll(Controller *s,uint32_t now) {
    poll_current(s,now);poll_external(s,now);poll_tc(s,now);
}
