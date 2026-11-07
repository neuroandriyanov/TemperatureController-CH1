#ifndef TC_STORAGE_H
#define TC_STORAGE_H
#include "core.h"
#define STORAGE_SLOT_SIZE 256u
#define STORAGE_BASE 0x0400u
typedef bool (*StorageRead)(void *,uint16_t,uint8_t *,size_t);
typedef bool (*StorageWrite)(void *,uint16_t,const uint8_t *,size_t);
typedef struct { void *context; StorageRead read; StorageWrite write; uint32_t sequence; int slot; } Storage;
bool storage_load(Storage *st,Config *c);
bool storage_save(Storage *st,const Config *c);
#endif
