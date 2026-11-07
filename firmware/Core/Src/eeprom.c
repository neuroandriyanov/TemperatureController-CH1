#include "board.h"
bool eeprom_read(void *ctx,uint16_t a,uint8_t *d,size_t n) {
    (void)ctx;
    return n<=65535 && HAL_I2C_Mem_Read(&hi2c2,0xA0,a,I2C_MEMADD_SIZE_16BIT,d,(uint16_t)n,25)==HAL_OK;
}
bool eeprom_write(void *ctx,uint16_t a,const uint8_t *d,size_t n) {
    (void)ctx;
    while(n) {
        size_t part=128u-(a%128u);if(part>n) part=n;
        if(HAL_I2C_Mem_Write(&hi2c2,0xA0,a,I2C_MEMADD_SIZE_16BIT,(uint8_t *)d,(uint16_t)part,25)!=HAL_OK) return false;
        bool ready=false;uint32_t start=HAL_GetTick();
        do {
            if(HAL_I2C_IsDeviceReady(&hi2c2,0xA0,1,2)==HAL_OK) { ready=true;break; }
        } while((uint32_t)(HAL_GetTick()-start)<12);
        if(!ready) return false;
        a+=(uint16_t)part;d+=part;n-=part;
    }
    return true;
}
