#include "board.h"
void NMI_Handler(void) { Error_Handler(); }
void HardFault_Handler(void) { Error_Handler(); }
void SVC_Handler(void) {}
void PendSV_Handler(void) {}
void SysTick_Handler(void) { HAL_IncTick();board_tick(); }
void DMA1_Channel1_IRQHandler(void) { HAL_DMA_IRQHandler(&hdma_adc); }
void DMA1_Channel2_3_IRQHandler(void) { HAL_DMA_IRQHandler(&hdma_capture); }
void USART1_IRQHandler(void) { HAL_UART_IRQHandler(&huart1); }
void USART2_IRQHandler(void) { HAL_UART_IRQHandler(&huart2); }
