#ifndef LCD_CAPTURE
#include <Arduino.h>
#include <driver/pcnt.h>

constexpr int pins[] = {12, 11, 9};
constexpr const char *names[] = {"SCLK", "MOSI", "DC"};
constexpr int signalCount = sizeof(pins) / sizeof(pins[0]);
constexpr int16_t counterLimit = 30000;
portMUX_TYPE counterLock = portMUX_INITIALIZER_UNLOCKED;
uint32_t wraps[signalCount] = {};

void IRAM_ATTR countWrap(void *argument) {
    const auto index = reinterpret_cast<uintptr_t>(argument);
    portENTER_CRITICAL_ISR(&counterLock);
    ++wraps[index];
    portEXIT_CRITICAL_ISR(&counterLock);
}

uint64_t readEdges(int index) {
    const auto unit = static_cast<pcnt_unit_t>(index);
    int16_t count = 0;
    portENTER_CRITICAL(&counterLock);
    const auto completed = wraps[index];
    pcnt_get_counter_value(unit, &count);
    portEXIT_CRITICAL(&counterLock);
    return uint64_t(completed) * counterLimit + count;
}

void setup() {
    Serial.begin(115200);
    for (int index = 0; index < signalCount; ++index) {
        pinMode(pins[index], INPUT);
        const auto unit = static_cast<pcnt_unit_t>(index);
        pcnt_config_t config = {};
        config.pulse_gpio_num = pins[index];
        config.ctrl_gpio_num = PCNT_PIN_NOT_USED;
        config.lctrl_mode = PCNT_MODE_KEEP;
        config.hctrl_mode = PCNT_MODE_KEEP;
        config.pos_mode = PCNT_COUNT_INC;
        config.neg_mode = PCNT_COUNT_DIS;
        config.counter_h_lim = counterLimit;
        config.counter_l_lim = -1;
        config.unit = unit;
        config.channel = PCNT_CHANNEL_0;
        ESP_ERROR_CHECK(pcnt_unit_config(&config));
        ESP_ERROR_CHECK(pcnt_counter_pause(unit));
        ESP_ERROR_CHECK(pcnt_filter_disable(unit));
        ESP_ERROR_CHECK(pcnt_event_enable(unit, PCNT_EVT_H_LIM));
    }
    ESP_ERROR_CHECK(pcnt_isr_service_install(0));
    for (int index = 0; index < signalCount; ++index) {
        const auto unit = static_cast<pcnt_unit_t>(index);
        ESP_ERROR_CHECK(pcnt_isr_handler_add(unit, countWrap, reinterpret_cast<void *>(index)));
        ESP_ERROR_CHECK(pcnt_counter_clear(unit));
        ESP_ERROR_CHECK(pcnt_counter_resume(unit));
    }
    Serial.println("LB02A display probe ready");
}

void loop() {
    delay(1000);
    for (int index = 0; index < signalCount; ++index) {
        Serial.printf("%s GPIO%d level=%d rising_total=%llu  ", names[index],
                      pins[index], digitalRead(pins[index]), readEdges(index));
    }
    Serial.println();
}
#endif
