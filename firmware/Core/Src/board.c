/* Peripheral setup adapted from src/ssr_cpu_v1/Core/Src/main.c (ST CubeMX).
 * Original generated portions: Copyright (c) 2023 STMicroelectronics.
 * Original notice: licensed under component LICENSE, otherwise provided AS-IS.
 * New application code has no redistribution license assigned yet. */
#include "board.h"
#include <math.h>

ADC_HandleTypeDef hadc;
DMA_HandleTypeDef hdma_adc,hdma_capture;
TIM_HandleTypeDef htim1,htim3,htim14;
SPI_HandleTypeDef hspi1;
I2C_HandleTypeDef hi2c2;
IWDG_HandleTypeDef hiwdg;
UART_HandleTypeDef huart1,huart2;
static volatile uint32_t lease_at,gate_changed,cycle_at;
static volatile uint16_t requested_power;
static volatile uint32_t period_ms=2000;
static volatile bool gate_state,relay_state,lease_failed,initialized;
static bool watchdog_reset;
#define CHECK(x) do { if((x)!=HAL_OK) Error_Handler(); } while(0)
static void pin(GPIO_TypeDef *port,uint32_t pins,uint32_t mode,uint32_t pull,uint32_t af) {
    GPIO_InitTypeDef g={0};g.Pin=pins;g.Mode=mode;g.Pull=pull;
    g.Speed=GPIO_SPEED_FREQ_HIGH;g.Alternate=af;HAL_GPIO_Init(port,&g);
}
static void clock_setup(void) {
    RCC_OscInitTypeDef o={0};RCC_ClkInitTypeDef c={0};RCC_PeriphCLKInitTypeDef p={0};
    o.OscillatorType=RCC_OSCILLATORTYPE_HSI14|RCC_OSCILLATORTYPE_LSI|RCC_OSCILLATORTYPE_HSE;
    o.HSEState=RCC_HSE_BYPASS;o.HSI14State=RCC_HSI14_ON;o.HSI14CalibrationValue=16;
    o.LSIState=RCC_LSI_ON;o.PLL.PLLState=RCC_PLL_ON;o.PLL.PLLSource=RCC_PLLSOURCE_HSE;
    o.PLL.PLLMUL=RCC_PLL_MUL12;o.PLL.PREDIV=RCC_PREDIV_DIV2;CHECK(HAL_RCC_OscConfig(&o));
    c.ClockType=RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK|RCC_CLOCKTYPE_PCLK1;
    c.SYSCLKSource=RCC_SYSCLKSOURCE_PLLCLK;c.AHBCLKDivider=RCC_SYSCLK_DIV1;c.APB1CLKDivider=RCC_HCLK_DIV1;
    CHECK(HAL_RCC_ClockConfig(&c,FLASH_LATENCY_1));
    p.PeriphClockSelection=RCC_PERIPHCLK_USART1;p.Usart1ClockSelection=RCC_USART1CLKSOURCE_PCLK1;
    CHECK(HAL_RCCEx_PeriphCLKConfig(&p));
}
static void uart_init(UART_HandleTypeDef *u,USART_TypeDef *instance) {
    u->Instance=instance;u->Init.BaudRate=38400;u->Init.WordLength=UART_WORDLENGTH_9B;
    u->Init.StopBits=UART_STOPBITS_1;u->Init.Parity=UART_PARITY_EVEN;
    u->Init.Mode=UART_MODE_TX_RX;u->Init.HwFlowCtl=UART_HWCONTROL_NONE;
    u->Init.OverSampling=UART_OVERSAMPLING_16;u->Init.OneBitSampling=UART_ONE_BIT_SAMPLE_DISABLE;
    u->AdvancedInit.AdvFeatureInit=UART_ADVFEATURE_NO_INIT;CHECK(HAL_UART_Init(u));
}
void board_init(void) {
    watchdog_reset=(RCC->CSR&(RCC_CSR_IWDGRSTF|RCC_CSR_WWDGRSTF))!=0;
    __HAL_RCC_CLEAR_RESET_FLAGS();
    HAL_Init();
    __HAL_RCC_GPIOA_CLK_ENABLE();__HAL_RCC_GPIOB_CLK_ENABLE();__HAL_RCC_GPIOC_CLK_ENABLE();
    GPIOA->BSRR=(uint32_t)GPIO_PIN_3<<16;GPIOB->BSRR=(uint32_t)GPIO_PIN_15<<16;
    pin(GPIOA,GPIO_PIN_3,GPIO_MODE_OUTPUT_PP,GPIO_NOPULL,0);
    pin(GPIOB,GPIO_PIN_15,GPIO_MODE_OUTPUT_PP,GPIO_NOPULL,0);
    clock_setup();
    __HAL_RCC_DMA1_CLK_ENABLE();__HAL_RCC_ADC1_CLK_ENABLE();__HAL_RCC_SPI1_CLK_ENABLE();
    __HAL_RCC_I2C2_CLK_ENABLE();__HAL_RCC_TIM1_CLK_ENABLE();__HAL_RCC_TIM3_CLK_ENABLE();
    __HAL_RCC_TIM14_CLK_ENABLE();__HAL_RCC_USART1_CLK_ENABLE();__HAL_RCC_USART2_CLK_ENABLE();
    __HAL_RCC_SYSCFG_CLK_ENABLE();__HAL_RCC_PWR_CLK_ENABLE();
    HAL_GPIO_WritePin(GPIOA,GPIO_PIN_4,GPIO_PIN_SET);
    pin(GPIOA,GPIO_PIN_4,GPIO_MODE_OUTPUT_PP,GPIO_NOPULL,0);
    pin(GPIOC,GPIO_PIN_13,GPIO_MODE_OUTPUT_PP,GPIO_NOPULL,0);
    pin(GPIOB,GPIO_PIN_0|GPIO_PIN_1,GPIO_MODE_INPUT,GPIO_NOPULL,0);
    pin(GPIOB,0x23F8,GPIO_MODE_INPUT,GPIO_PULLUP,0);
    pin(GPIOA,GPIO_PIN_1,GPIO_MODE_ANALOG,GPIO_NOPULL,0);
    pin(GPIOA,GPIO_PIN_5|GPIO_PIN_6|GPIO_PIN_7,GPIO_MODE_AF_PP,GPIO_NOPULL,GPIO_AF0_SPI1);
    pin(GPIOA,GPIO_PIN_8,GPIO_MODE_AF_PP,GPIO_NOPULL,GPIO_AF2_TIM1);
    pin(GPIOA,GPIO_PIN_9|GPIO_PIN_10,GPIO_MODE_AF_PP,GPIO_NOPULL,GPIO_AF1_USART1);
    pin(GPIOA,GPIO_PIN_14|GPIO_PIN_15,GPIO_MODE_AF_PP,GPIO_NOPULL,GPIO_AF1_USART2);
    pin(GPIOB,GPIO_PIN_10|GPIO_PIN_11,GPIO_MODE_AF_OD,GPIO_NOPULL,GPIO_AF1_I2C2);

    hdma_adc.Instance=DMA1_Channel1;hdma_adc.Init.Direction=DMA_PERIPH_TO_MEMORY;
    hdma_adc.Init.PeriphInc=DMA_PINC_DISABLE;hdma_adc.Init.MemInc=DMA_MINC_ENABLE;
    hdma_adc.Init.PeriphDataAlignment=DMA_PDATAALIGN_HALFWORD;hdma_adc.Init.MemDataAlignment=DMA_MDATAALIGN_HALFWORD;
    hdma_adc.Init.Mode=DMA_CIRCULAR;hdma_adc.Init.Priority=DMA_PRIORITY_HIGH;CHECK(HAL_DMA_Init(&hdma_adc));
    __HAL_LINKDMA(&hadc,DMA_Handle,hdma_adc);
    hadc.Instance=ADC1;hadc.Init.ClockPrescaler=ADC_CLOCK_ASYNC_DIV1;hadc.Init.Resolution=ADC_RESOLUTION_12B;
    hadc.Init.DataAlign=ADC_DATAALIGN_RIGHT;hadc.Init.ScanConvMode=ADC_SCAN_DIRECTION_FORWARD;
    hadc.Init.EOCSelection=ADC_EOC_SINGLE_CONV;hadc.Init.ContinuousConvMode=DISABLE;
    hadc.Init.ExternalTrigConv=ADC_EXTERNALTRIGCONV_T3_TRGO;hadc.Init.ExternalTrigConvEdge=ADC_EXTERNALTRIGCONVEDGE_RISING;
    hadc.Init.DMAContinuousRequests=ENABLE;hadc.Init.Overrun=ADC_OVR_DATA_OVERWRITTEN;CHECK(HAL_ADC_Init(&hadc));
    ADC_ChannelConfTypeDef ac={0};ac.Channel=ADC_CHANNEL_1;ac.Rank=ADC_RANK_CHANNEL_NUMBER;
    ac.SamplingTime=ADC_SAMPLETIME_41CYCLES_5;CHECK(HAL_ADC_ConfigChannel(&hadc,&ac));
    CHECK(HAL_ADCEx_Calibration_Start(&hadc));

    htim3.Instance=TIM3;htim3.Init.Prescaler=47;htim3.Init.CounterMode=TIM_COUNTERMODE_UP;
    htim3.Init.Period=199;htim3.Init.ClockDivision=TIM_CLOCKDIVISION_DIV1;CHECK(HAL_TIM_Base_Init(&htim3));
    TIM_MasterConfigTypeDef tm={0};tm.MasterOutputTrigger=TIM_TRGO_UPDATE;
    tm.MasterSlaveMode=TIM_MASTERSLAVEMODE_DISABLE;CHECK(HAL_TIMEx_MasterConfigSynchronization(&htim3,&tm));
    htim14.Instance=TIM14;htim14.Init.Prescaler=47;htim14.Init.Period=65535;
    htim14.Init.CounterMode=TIM_COUNTERMODE_UP;CHECK(HAL_TIM_Base_Init(&htim14));CHECK(HAL_TIM_Base_Start(&htim14));

    hdma_capture.Instance=DMA1_Channel2;hdma_capture.Init.Direction=DMA_PERIPH_TO_MEMORY;
    hdma_capture.Init.PeriphInc=DMA_PINC_DISABLE;hdma_capture.Init.MemInc=DMA_MINC_ENABLE;
    hdma_capture.Init.PeriphDataAlignment=DMA_PDATAALIGN_HALFWORD;hdma_capture.Init.MemDataAlignment=DMA_MDATAALIGN_HALFWORD;
    hdma_capture.Init.Mode=DMA_NORMAL;hdma_capture.Init.Priority=DMA_PRIORITY_LOW;CHECK(HAL_DMA_Init(&hdma_capture));
    __HAL_LINKDMA(&htim1,hdma[TIM_DMA_ID_CC1],hdma_capture);
    htim1.Instance=TIM1;htim1.Init.Prescaler=0;htim1.Init.Period=65535;
    htim1.Init.CounterMode=TIM_COUNTERMODE_UP;htim1.Init.ClockDivision=TIM_CLOCKDIVISION_DIV1;
    CHECK(HAL_TIM_IC_Init(&htim1));
    TIM_SlaveConfigTypeDef slave={0};slave.SlaveMode=TIM_SLAVEMODE_RESET;slave.InputTrigger=TIM_TS_TI1FP1;
    slave.TriggerPolarity=TIM_INPUTCHANNELPOLARITY_RISING;CHECK(HAL_TIM_SlaveConfigSynchro(&htim1,&slave));
    TIM_IC_InitTypeDef ic={0};ic.ICPolarity=TIM_INPUTCHANNELPOLARITY_RISING;
    ic.ICSelection=TIM_ICSELECTION_DIRECTTI;ic.ICPrescaler=TIM_ICPSC_DIV1;ic.ICFilter=4;
    CHECK(HAL_TIM_IC_ConfigChannel(&htim1,&ic,TIM_CHANNEL_1));

    hspi1.Instance=SPI1;hspi1.Init.Mode=SPI_MODE_MASTER;hspi1.Init.Direction=SPI_DIRECTION_2LINES;
    hspi1.Init.DataSize=SPI_DATASIZE_8BIT;hspi1.Init.CLKPolarity=SPI_POLARITY_HIGH;hspi1.Init.CLKPhase=SPI_PHASE_2EDGE;
    hspi1.Init.NSS=SPI_NSS_SOFT;hspi1.Init.BaudRatePrescaler=SPI_BAUDRATEPRESCALER_16;
    hspi1.Init.FirstBit=SPI_FIRSTBIT_MSB;hspi1.Init.TIMode=SPI_TIMODE_DISABLE;
    hspi1.Init.CRCCalculation=SPI_CRCCALCULATION_DISABLE;hspi1.Init.CRCPolynomial=7;
    hspi1.Init.CRCLength=SPI_CRC_LENGTH_DATASIZE;hspi1.Init.NSSPMode=SPI_NSS_PULSE_DISABLE;CHECK(HAL_SPI_Init(&hspi1));
    hi2c2.Instance=I2C2;hi2c2.Init.Timing=0x20303E5D;hi2c2.Init.AddressingMode=I2C_ADDRESSINGMODE_7BIT;
    hi2c2.Init.DualAddressMode=I2C_DUALADDRESS_DISABLE;hi2c2.Init.OwnAddress2Masks=I2C_OA2_NOMASK;
    hi2c2.Init.GeneralCallMode=I2C_GENERALCALL_DISABLE;hi2c2.Init.NoStretchMode=I2C_NOSTRETCH_DISABLE;
    CHECK(HAL_I2C_Init(&hi2c2));CHECK(HAL_I2CEx_ConfigAnalogFilter(&hi2c2,I2C_ANALOGFILTER_ENABLE));
    uart_init(&huart1,USART1);uart_init(&huart2,USART2);
    HAL_NVIC_SetPriority(DMA1_Channel1_IRQn,1,0);HAL_NVIC_EnableIRQ(DMA1_Channel1_IRQn);
    HAL_NVIC_SetPriority(DMA1_Channel2_3_IRQn,1,0);HAL_NVIC_EnableIRQ(DMA1_Channel2_3_IRQn);
    HAL_NVIC_SetPriority(USART1_IRQn,0,0);HAL_NVIC_EnableIRQ(USART1_IRQn);
    HAL_NVIC_SetPriority(USART2_IRQn,0,0);HAL_NVIC_EnableIRQ(USART2_IRQn);
    hiwdg.Instance=IWDG;hiwdg.Init.Prescaler=IWDG_PRESCALER_32;hiwdg.Init.Window=4095;hiwdg.Init.Reload=3750;
    CHECK(HAL_IWDG_Init(&hiwdg));initialized=true;
}
uint32_t board_us(void) {
    static uint16_t previous;static uint32_t high;
    uint32_t mask=__get_PRIMASK();__disable_irq();
    uint16_t low=(uint16_t)TIM14->CNT;
    if(low<previous) high+=65536;
    previous=low;
    uint32_t result=high+low;__set_PRIMASK(mask);return result;
}
void board_off(void) {
    uint32_t mask=__get_PRIMASK();__disable_irq();
    requested_power=0;relay_state=false;
    GPIOA->BSRR=(uint32_t)GPIO_PIN_3<<16;GPIOB->BSRR=(uint32_t)GPIO_PIN_15<<16;
    if(gate_state) gate_changed=HAL_GetTick();
    gate_state=false;
    __set_PRIMASK(mask);
}
void board_output(float power,uint32_t period,bool relay) {
    uint32_t mask=__get_PRIMASK();__disable_irq();
    if(!isfinite(power)) { power=0;relay=false; }
    if(power<=0) {
        requested_power=0;
        GPIOA->BSRR=(uint32_t)GPIO_PIN_3<<16;
        if(gate_state) gate_changed=HAL_GetTick();
        gate_state=false;
    }
    else {
        if(!requested_power) cycle_at=HAL_GetTick();
        requested_power=(uint16_t)fminf(10000,power*100);
    }
    period_ms=period;lease_at=HAL_GetTick();
    if(relay_state!=relay) {
        relay_state=relay;HAL_GPIO_WritePin(GPIOB,GPIO_PIN_15,relay?GPIO_PIN_SET:GPIO_PIN_RESET);
    }
    __set_PRIMASK(mask);
}
void board_tick(void) {
    if(!initialized) return;
    (void)board_us(); /* Extend TIM14 every ms, including long main-loop I/O. */
    uint32_t now=HAL_GetTick();
    if((uint32_t)(now-lease_at)>50 && (requested_power || relay_state)) {
        lease_failed=true;board_off();
    }
    uint32_t elapsed=now-cycle_at;
    if(elapsed>=period_ms) { cycle_at=now;elapsed=0; }
    bool on=requested_power && elapsed<burst_on_time_ms(period_ms,requested_power);
    if(on!=gate_state) {
        gate_state=on;gate_changed=now;HAL_GPIO_WritePin(GPIOA,GPIO_PIN_3,on?GPIO_PIN_SET:GPIO_PIN_RESET);
    }
}
bool board_gate(void) { return gate_state; }
bool board_relay(void) { return relay_state; }
uint32_t board_gate_changed(void) { return gate_changed; }
bool board_lease_failed(void) { bool v=lease_failed;lease_failed=false;return v; }
bool board_watchdog_reset(void) { return watchdog_reset; }
void board_watchdog(void) {
    HAL_IWDG_Refresh(&hiwdg);
    HAL_GPIO_WritePin(GPIOC,GPIO_PIN_13,GPIO_PIN_SET);
    HAL_GPIO_WritePin(GPIOC,GPIO_PIN_13,GPIO_PIN_RESET);
}
void Error_Handler(void) { board_off();__disable_irq();for(;;) {} }
