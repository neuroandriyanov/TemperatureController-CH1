#ifndef TC_MODBUS_H
#define TC_MODBUS_H
#include "core.h"
#define RTU_MAX 256u
uint16_t modbus_crc(const uint8_t *p,size_t n);
typedef struct { uint32_t valid, crc_errors, malformed, exceptions, framing_errors; } ModbusStats;
size_t modbus_process(Controller *s,const uint8_t *request,size_t n,uint8_t response[RTU_MAX],
                      uint32_t now,bool gate,bool relay,ModbusStats *stats);
typedef struct {
 uint8_t bytes[RTU_MAX]; uint16_t length; uint32_t last_us, errors;
 bool started, discard, ready;
} RtuFramer;
void rtu_byte(RtuFramer *f,uint8_t b,uint32_t us);
void rtu_poll(RtuFramer *f,uint32_t us);
void rtu_release(RtuFramer *f);
void rtu_error(RtuFramer *f,uint32_t us);
#endif
