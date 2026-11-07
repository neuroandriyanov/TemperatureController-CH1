#ifdef LCD_CAPTURE
#include <Arduino.h>
#include <driver/periph_ctrl.h>
#include <driver/pcnt.h>
#include <esp_private/gdma.h>
#include <esp_rom_gpio.h>
#include <rom/lldesc.h>
#include <soc/gpio_sig_map.h>
#include <soc/lcd_cam_struct.h>
#include <soc/gdma_struct.h>
#include <freertos/message_buffer.h>
#include "display_link.h"

#pragma GCC optimize ("O3")

void setupKeypad();
void pollKeypad(int (*)(), void (*)(const uint8_t *, size_t));

namespace {
constexpr int blockSize = 2048;
constexpr int blockCount = 88;
constexpr int baud = 4000000;
DMA_ATTR uint8_t samples[blockCount][blockSize];
DMA_ATTR lldesc_t descriptors[blockCount];
gdma_channel_handle_t dma;
MessageBufferHandle_t serialPackets;
int dmaIndex;
uint32_t sequence = 0;
uint8_t dataBytes[blockSize / 8 + 1];
uint8_t modes[sizeof(dataBytes)];
uint8_t packet[10 + 2 * sizeof(dataBytes)];
int bitCount = 0;
uint8_t byteValue = 0;
int lastMode = -1;
bool aligned = false;

void waitForDisplayClock() {
    int16_t initial = 0;
    pcnt_get_counter_value(PCNT_UNIT_0, &initial);
    const uint32_t started = micros();
    do {
        int16_t current = 0;
        pcnt_get_counter_value(PCNT_UNIT_0, &current);
        if ((current - initial + 30001) % 30001 >= 8) {
            return;
        }
        delayMicroseconds(20);
    } while (micros() - started < 50000);
}

void startDma() {
    LCD_CAM.cam_ctrl1.cam_start = 0;
    LCD_CAM.cam_ctrl1.cam_reset = 1;
    LCD_CAM.cam_ctrl1.cam_reset = 0;
    LCD_CAM.cam_ctrl1.cam_afifo_reset = 1;
    LCD_CAM.cam_ctrl1.cam_afifo_reset = 0;
    LCD_CAM.cam_ctrl1.cam_rec_data_bytelen = blockSize - 1;
    auto &channel = GDMA.channel[dmaIndex].in;
    ESP_ERROR_CHECK(gdma_reset(dma));
    channel.int_clr.val = ~0u;
    channel.conf0.indscr_burst_en = 1;
    channel.conf0.in_data_burst_en = 1;
    channel.peri_sel.sel = SOC_GDMA_TRIG_PERIPH_CAM0;
    for (auto &descriptor : descriptors) {
        descriptor.length = 0;
        descriptor.owner = 1;
    }
    ESP_ERROR_CHECK(gdma_start(dma, reinterpret_cast<intptr_t>(descriptors)));
    LCD_CAM.cam_ctrl.cam_update = 1;
    LCD_CAM.cam_ctrl1.cam_start = 1;
    LCD_CAM.cam_ctrl.cam_update = 1;
    // Open the line gate after a virtual frame pulse.
    esp_rom_gpio_connect_in_signal(GPIO_MATRIX_CONST_ZERO_INPUT, CAM_H_ENABLE_IDX, false);
    esp_rom_gpio_connect_in_signal(GPIO_MATRIX_CONST_ZERO_INPUT, CAM_H_SYNC_IDX, false);
    esp_rom_gpio_connect_in_signal(GPIO_MATRIX_CONST_ONE_INPUT, CAM_V_SYNC_IDX, false);
    waitForDisplayClock();
    esp_rom_gpio_connect_in_signal(GPIO_MATRIX_CONST_ZERO_INPUT, CAM_V_SYNC_IDX, false);
    waitForDisplayClock();
    esp_rom_gpio_connect_in_signal(GPIO_MATRIX_CONST_ONE_INPUT, CAM_H_SYNC_IDX, false);
    esp_rom_gpio_connect_in_signal(GPIO_MATRIX_CONST_ONE_INPUT, CAM_H_ENABLE_IDX, false);
}

void configureCapture() {
    for (int pin : {9, 11, 12}) {
        pinMode(pin, INPUT);
    }
    pcnt_config_t clockCounter = {};
    clockCounter.pulse_gpio_num = 12;
    clockCounter.ctrl_gpio_num = PCNT_PIN_NOT_USED;
    clockCounter.pos_mode = PCNT_COUNT_INC;
    clockCounter.counter_h_lim = 30001;
    clockCounter.counter_l_lim = -1;
    ESP_ERROR_CHECK(pcnt_unit_config(&clockCounter));
    ESP_ERROR_CHECK(pcnt_filter_disable(PCNT_UNIT_0));
    ESP_ERROR_CHECK(pcnt_counter_clear(PCNT_UNIT_0));
    ESP_ERROR_CHECK(pcnt_counter_resume(PCNT_UNIT_0));
    periph_module_enable(PERIPH_LCD_CAM_MODULE);
    periph_module_reset(PERIPH_LCD_CAM_MODULE);
    LCD_CAM.lcd_clock.clk_en = 1;
    esp_rom_gpio_connect_in_signal(12, CAM_PCLK_IDX, false);
    esp_rom_gpio_connect_in_signal(11, CAM_DATA_IN0_IDX, false);
    esp_rom_gpio_connect_in_signal(9, CAM_DATA_IN1_IDX, false);
    for (int index = 2; index < 8; ++index) {
        esp_rom_gpio_connect_in_signal(GPIO_MATRIX_CONST_ZERO_INPUT, CAM_DATA_IN0_IDX + index, false);
    }
    esp_rom_gpio_connect_in_signal(GPIO_MATRIX_CONST_ZERO_INPUT, CAM_H_ENABLE_IDX, false);
    esp_rom_gpio_connect_in_signal(GPIO_MATRIX_CONST_ZERO_INPUT, CAM_H_SYNC_IDX, false);
    esp_rom_gpio_connect_in_signal(GPIO_MATRIX_CONST_ZERO_INPUT, CAM_V_SYNC_IDX, false);

    gdma_channel_alloc_config_t config = {};
    config.direction = GDMA_CHANNEL_DIRECTION_RX;
    ESP_ERROR_CHECK(gdma_new_channel(&config, &dma));
    ESP_ERROR_CHECK(gdma_get_channel_id(dma, &dmaIndex));
    ESP_ERROR_CHECK(gdma_connect(dma, GDMA_MAKE_TRIGGER(GDMA_TRIG_PERIPH_CAM, 0)));
    gdma_strategy_config_t strategy = {};
    strategy.owner_check = true;
    ESP_ERROR_CHECK(gdma_apply_strategy(dma, &strategy));
    for (int index = 0; index < blockCount; ++index) {
        auto &descriptor = descriptors[index];
        descriptor.size = blockSize;
        descriptor.owner = 1;
        descriptor.buf = samples[index];
        descriptor.qe.stqe_next = &descriptors[(index + 1) % blockCount];
    }

    LCD_CAM.cam_ctrl.val = 0;
    LCD_CAM.cam_ctrl.cam_clk_sel = 3;
    LCD_CAM.cam_ctrl.cam_clkm_div_num = 1;
    LCD_CAM.cam_ctrl.cam_vsync_filter_thres = 4;
    LCD_CAM.cam_ctrl1.val = 0;
    LCD_CAM.cam_rgb_yuv.val = 0;
    startDma();
}

bool repeatsPair(int start, int count) {
    return start + 5 < count && modes[start + 1] == modes[start]
        && modes[start + 2] == modes[start] && modes[start + 3] == modes[start]
        && modes[start + 4] == modes[start] && modes[start + 5] == modes[start]
        && dataBytes[start] != dataBytes[start + 1]
        && dataBytes[start] == dataBytes[start + 2] && dataBytes[start] == dataBytes[start + 4]
        && dataBytes[start + 1] == dataBytes[start + 3] && dataBytes[start + 1] == dataBytes[start + 5];
}

void sendBytes(int count) {
    if (!count) {
        return;
    }
    int output = 10;
    for (int start = 0; start < count;) {
        const uint8_t mode = modes[start] << 7;
        int end = start + 1;
        while (end < count && end - start < 64 && modes[end] == modes[start]
               && dataBytes[end] == dataBytes[start]) {
            ++end;
        }
        if (end - start >= 3) {
            packet[output++] = mode | 0x40 | (end - start - 1);
            packet[output++] = dataBytes[start];
        } else if (repeatsPair(start, count)) {
            end = start + 6;
            while (end + 1 < count && end - start < 256 && modes[end] == modes[start]
                   && modes[end + 1] == modes[start] && dataBytes[end] == dataBytes[start]
                   && dataBytes[end + 1] == dataBytes[start + 1]) {
                end += 2;
            }
            packet[output++] = mode | 0x3F;
            packet[output++] = (end - start) / 2;
            packet[output++] = dataBytes[start];
            packet[output++] = dataBytes[start + 1];
        } else {
            while (end < count && end - start < 63 && modes[end] == modes[start]) {
                if (repeatsPair(end, count)) {
                    break;
                }
                if (end + 2 < count && modes[end + 2] == modes[start]
                    && modes[end + 1] == modes[start] && dataBytes[end] == dataBytes[end + 1]
                    && dataBytes[end] == dataBytes[end + 2]) {
                    break;
                }
                ++end;
            }
            packet[output++] = mode | (end - start - 1);
            memcpy(packet + output, dataBytes + start, end - start);
            output += end - start;
        }
        start = end;
    }
    memcpy(packet, "LB03", 4);
    memcpy(packet + 4, &sequence, 4);
    const uint16_t payloadSize = output - 10;
    memcpy(packet + 8, &payloadSize, 2);
    ++sequence;
    // Never hold up DMA to wait for the serial link. A sequence gap marks a drop.
    xMessageBufferSend(serialPackets, packet, output, 0);
}

void serialWriter(void *) {
    uint8_t outgoing[sizeof(packet)];
    while (true) {
        serviceDisplayLink();
        pollKeypad(readDisplayCommand, writeDisplayData);
        const size_t size = xMessageBufferReceive(serialPackets, outgoing, sizeof(outgoing), 0);
        if (size) {
            writeDisplayData(outgoing, size);
        } else {
            delay(1);
        }
    }
}

int decodeBlock(const uint8_t *input, int size) {
    int count = 0;
    int index = 0;
    while (index < size) {
        if (aligned && bitCount == 0 && index + 8 <= size) {
            uint32_t first;
            uint32_t second;
            memcpy(&first, input + index, sizeof(first));
            memcpy(&second, input + index + 4, sizeof(second));
            const uint32_t modeBits = lastMode ? 0x02020202u : 0;
            if ((((first ^ modeBits) | (second ^ modeBits)) & 0x02020202u) == 0) {
                // Gather the least significant bit of each sample, MSB first.
                const auto upper = ((first & 0x01010101u) * 0x08040201u) >> 24;
                const auto lower = ((second & 0x01010101u) * 0x08040201u) >> 24;
                dataBytes[count] = (upper << 4) | (lower & 15);
                modes[count++] = lastMode;
                index += 8;
                continue;
            }
        }
        const int mode = (input[index] >> 1) & 1;
        if (mode != lastMode) {
            if (lastMode >= 0) {
                aligned = true;
            }
            lastMode = mode;
            bitCount = 0;
        }
        byteValue = (byteValue << 1) | (input[index] & 1);
        if (++bitCount == 8) {
            if (aligned) {
                dataBytes[count] = byteValue;
                modes[count++] = mode;
            }
            bitCount = 0;
        }
        ++index;
    }
    return count;
}
}

void setup() {
    Serial.setTxBufferSize(8192);
    Serial.begin(baud);
    serialPackets = xMessageBufferCreate(49152);
    ESP_ERROR_CHECK(serialPackets ? ESP_OK : ESP_ERR_NO_MEM);
    setupDisplayLink();
    const auto created = xTaskCreatePinnedToCore(serialWriter, "lcd-serial", 6144, nullptr, 2, nullptr, 0);
    ESP_ERROR_CHECK(created == pdPASS ? ESP_OK : ESP_ERR_NO_MEM);
    configureCapture();
    setupKeypad();
}

void loop() {
    static int index = 0;
    static uint32_t lastBlock = 0;
    static uint32_t lastClockCheck = 0;
    static int16_t previousClock = 0;
    const uint32_t now = millis();
    const auto &interrupts = GDMA.channel[dmaIndex].in.int_raw;
    auto &descriptor = *static_cast<volatile lldesc_t *>(&descriptors[index]);
    bool stalled = false;
    if (now - lastClockCheck >= 250) {
        int16_t clockEdges = 0;
        pcnt_get_counter_value(PCNT_UNIT_0, &clockEdges);
        const int delta = (clockEdges - previousClock + 30001) % 30001;
        stalled = now - lastBlock >= 250 && delta >= 2 * blockSize;
        previousClock = clockEdges;
        lastClockCheck = now;
    }
    // Preserve already captured samples before restarting a stopped DMA ring.
    if (descriptor.owner && (stalled || interrupts.in_dscr_err || interrupts.in_dscr_empty)) {
        const char *reason = stalled ? "CAM restart: clock without blocks\n" : "CAM restart: DMA\n";
        xMessageBufferSend(serialPackets, reason, strlen(reason), 0);
        gdma_stop(dma);
        ++sequence;
        index = bitCount = 0;
        lastMode = -1;
        aligned = false;
        startDma();
        lastBlock = millis();
        return;
    }
    if (descriptor.owner) {
        delay(1);
        return;
    }
    if (xMessageBufferSpacesAvailable(serialPackets) < sizeof(packet) + sizeof(size_t)) {
        delay(1);
        return;
    }
    const int count = decodeBlock(samples[index], descriptor.length);
    lastBlock = millis();
    descriptor.length = 0;
    descriptor.owner = 1;
    index = (index + 1) % blockCount;
    sendBytes(count);
}
#endif
