#pragma once
#include <Arduino.h>

void setupDisplayLink();
void serviceDisplayLink();
int readDisplayCommand();
void writeDisplayData(const uint8_t *data, size_t size);
