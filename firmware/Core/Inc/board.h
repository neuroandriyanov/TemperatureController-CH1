#ifndef TC_BOARD_H
#define TC_BOARD_H
#include "stm32f0xx_hal.h"
#include "core.h"
extern ADC_HandleTypeDef hadc;
extern DMA_HandleTypeDef hdma_adc,hdma_capture;
extern TIM_HandleTypeDef htim1,htim3,htim14;
extern SPI_HandleTypeDef hspi1;
extern I2C_HandleTypeDef hi2c2;
extern IWDG_HandleTypeDef hiwdg;
extern UART_HandleTypeDef huart1,huart2;
void Error_Handler(void);
void board_init(void);
uint32_t board_us(void);
void board_tick(void);
void board_output(float power,uint32_t period,bool relay);
void board_off(void);
bool board_gate(void);
bool board_relay(void);
uint32_t board_gate_changed(void);
bool board_lease_failed(void);
bool board_watchdog_reset(void);
void board_watchdog(void);
void sensors_init(Controller *c);
void sensors_poll(Controller *c,uint32_t now);
void transport_init(void);
void transport_poll(Controller *c);
bool transport_idle(void);
bool eeprom_read(void *ctx,uint16_t address,uint8_t *data,size_t n);
bool eeprom_write(void *ctx,uint16_t address,const uint8_t *data,size_t n);
#endif
