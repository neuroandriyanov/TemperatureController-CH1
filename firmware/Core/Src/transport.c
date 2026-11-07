#include "board.h"
#include "modbus.h"
#include <string.h>
typedef struct {
    UART_HandleTypeDef *uart; RtuFramer rx; ModbusStats stats;
    uint8_t byte,tx[RTU_MAX]; volatile bool busy;
    volatile uint32_t silence_until; uint32_t tx_at;
} Port;
static Port ports[2];
static Port *port_for(UART_HandleTypeDef *h) { return h==&huart1?&ports[0]:&ports[1]; }
void transport_init(void) {
    ports[0].uart=&huart1;ports[1].uart=&huart2;
    for(unsigned i=0;i<2;i++) if(HAL_UART_Receive_IT(ports[i].uart,&ports[i].byte,1)!=HAL_OK) Error_Handler();
}
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *h) {
    Port *p=port_for(h);uint32_t now=board_us();
    if(!p->busy && (int32_t)(now-p->silence_until)>=0) rtu_byte(&p->rx,p->byte,now);
    (void)HAL_UART_Receive_IT(h,&p->byte,1);
}
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *h) {
    Port *p=port_for(h);p->silence_until=board_us()+1750;p->busy=false;
}
void HAL_UART_ErrorCallback(UART_HandleTypeDef *h) {
    Port *p=port_for(h);rtu_error(&p->rx,board_us());
    (void)HAL_UART_Receive_IT(h,&p->byte,1);
}
bool transport_idle(void) { return !ports[0].busy && !ports[1].busy; }
void transport_poll(Controller *s) {
    for(unsigned i=0;i<2;i++) {
        Port *p=&ports[i];uint32_t now=HAL_GetTick();
        if(p->busy) {
            if((uint32_t)(now-p->tx_at)>150) {
                HAL_UART_AbortTransmit(p->uart);p->busy=false;p->stats.malformed++;
                p->silence_until=board_us()+1750;
            }
            continue;
        }
        uint32_t mask=__get_PRIMASK();__disable_irq();
        /* Do not finalize the previous frame while a new character is on wire. */
        if(!(p->uart->Instance->ISR&USART_ISR_BUSY)) rtu_poll(&p->rx,board_us());
        bool ready=p->rx.ready;__set_PRIMASK(mask);
        if(!ready) {
            if(p->uart->RxState==HAL_UART_STATE_READY) (void)HAL_UART_Receive_IT(p->uart,&p->byte,1);
            continue;
        }
        p->stats.framing_errors=p->rx.errors;
        size_t n=modbus_process(s,p->rx.bytes,p->rx.length,p->tx,now,board_gate(),board_relay(),&p->stats);
        if(s->mode==MODE_STOP) board_output(0,config_burst_period_ms(&s->config),controller_relay(s));
        mask=__get_PRIMASK();__disable_irq();rtu_release(&p->rx);
        if(n) {
            p->busy=true;p->tx_at=now;
            if(HAL_UART_Transmit_IT(p->uart,p->tx,(uint16_t)n)!=HAL_OK) p->busy=false;
        }
        __set_PRIMASK(mask);
    }
}
