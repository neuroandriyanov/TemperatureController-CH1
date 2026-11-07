#ifdef LCD_CAPTURE
#include <Arduino.h>
#include <driver/gpio.h>
#include <soc/gpio_struct.h>
#include <xtensa/core-macros.h>

namespace {
constexpr gpio_num_t sda = GPIO_NUM_5;
constexpr gpio_num_t scl = GPIO_NUM_6;
constexpr uint32_t sdaMask = 1u << sda;
constexpr uint32_t sclMask = 1u << scl;
constexpr uint8_t readAddress = 0x49;
constexpr uint8_t codes[] = {
    0x6C, 0x64, 0x5C, 0x54, 0x6D, 0x65, 0x5D, 0x55,
    0x6E, 0x66, 0x5E, 0x56, 0, 0x67, 0x5F, 0x57
};

volatile uint32_t reads = 0;
volatile uint32_t clockEdges = 0;
volatile uint32_t starts = 0;
volatile uint8_t lastRead = 0;
uint8_t clocks = 0;
uint8_t address = 0;
uint8_t data = 0;
bool started = false;
uint32_t previousRise = 0;
#ifdef KEYPAD_EMULATE
volatile uint8_t reply = 0x2E;
uint8_t transactionReply = 0;
#endif

void IRAM_ATTR onClock(void *) {
    ++clockEdges;
    const uint32_t levels = GPIO.in;
    if (levels & sclMask) {
        const uint32_t now = XTHAL_GET_CCOUNT();
        const uint32_t gap = now - previousRise;
        previousRise = now;
        // The LB02A parks SCL low for about 30 ms between polls. Its first
        // rising edge prepares START and does not carry an address bit.
        if (gap > 240000) {
            ++starts;
            clocks = address = data = 0;
            started = true;
            return;
        }
        if (!started) {
            return;
        }
        ++clocks;
        if (clocks <= 8) {
            address = (address << 1) | bool(levels & sdaMask);
        } else if (address == readAddress && clocks >= 10 && clocks <= 17) {
            data = (data << 1) | bool(levels & sdaMask);
            if (clocks == 17) {
                lastRead = data;
                ++reads;
            }
        }
        if (clocks >= 18) {
            started = false;
        }
        return;
    }
#ifdef KEYPAD_EMULATE
    if (!started || address != readAddress || clocks < 8) {
        return;
    }
    if (clocks == 8) {
        transactionReply = reply;
        GPIO.out_w1tc = sdaMask;  // ACK
    } else if (clocks == 17 || (transactionReply & (1u << (16 - clocks)))) {
        GPIO.out_w1ts = sdaMask;  // release SDA
    } else {
        GPIO.out_w1tc = sdaMask;
    }
#endif
}

#ifdef KEYPAD_EMULATE
void IRAM_ATTR onGpioInterrupt(void *argument) {
    if (GPIO.status & sclMask) {
        GPIO.status_w1tc = sclMask;
        onClock(argument);
    }
}
#endif

void initializeBus(void *) {
    gpio_config_t config = {};
    config.pin_bit_mask = sdaMask | sclMask;
    config.mode = GPIO_MODE_INPUT;
    ESP_ERROR_CHECK(gpio_config(&config));
#ifdef KEYPAD_EMULATE
    ESP_ERROR_CHECK(gpio_set_level(sda, 1));
    ESP_ERROR_CHECK(gpio_set_direction(sda, GPIO_MODE_INPUT_OUTPUT_OD));
    // Provide a pull-up on the controller side of the isolated SDA line.
    ESP_ERROR_CHECK(gpio_pullup_en(sda));
#endif
#ifdef KEYPAD_EMULATE
    ESP_ERROR_CHECK(gpio_isr_register(onGpioInterrupt, nullptr, ESP_INTR_FLAG_IRAM | ESP_INTR_FLAG_LEVEL3, nullptr));
    ESP_ERROR_CHECK(gpio_set_intr_type(scl, GPIO_INTR_ANYEDGE));
    ESP_ERROR_CHECK(gpio_intr_enable(scl));
#else
    ESP_ERROR_CHECK(gpio_install_isr_service(ESP_INTR_FLAG_IRAM));
    ESP_ERROR_CHECK(gpio_set_intr_type(scl, GPIO_INTR_POSEDGE));
    ESP_ERROR_CHECK(gpio_isr_handler_add(scl, onClock, nullptr));
#endif
    vTaskDelete(nullptr);
}
}

void setupKeypad() {
    // Keep the keyboard's GPIO interrupts off the LCD DMA consumer core.
    const auto created = xTaskCreatePinnedToCore(initializeBus, "keypad-init", 3072, nullptr, 2, nullptr, 0);
    ESP_ERROR_CHECK(created == pdPASS ? ESP_OK : ESP_ERR_NO_MEM);
}

void pollKeypad(int (*readCommand)(), void (*writeReport)(const uint8_t *, size_t)) {
    static uint32_t lastReport = 0;
    const uint32_t now = millis();
#ifdef KEYPAD_EMULATE
    static uint32_t changedAt = 0;
    if ((reply & 0x40) && now - changedAt >= 180) {
        reply &= ~0x40;
        changedAt = now;
    }
#endif
    for (int budget = 8; budget > 0; --budget) {
        const int command = readCommand();
        if (command < 0) break;
        const int index = command - 0xA1;
#ifdef KEYPAD_EMULATE
        if (index >= 0 && index < int(sizeof(codes)) && codes[index]
            && !(reply & 0x40) && now - changedAt >= 100) {
            reply = codes[index];
            changedAt = now;
        }
#else
        (void)index;
#endif
    }
    if (now - lastReport >= 500) {
        lastReport = now;
#ifdef KEYPAD_EMULATE
        constexpr uint8_t mode = 1;
#else
        constexpr uint8_t mode = 0;
#endif
        const uint32_t count = reads;
        const uint32_t edges = clockEdges;
        const uint32_t transactions = starts;
        uint8_t report[19] = {'L', 'B', 'K', '2', mode, lastRead};
        memcpy(report + 6, &count, sizeof(count));
        memcpy(report + 10, &edges, sizeof(edges));
        memcpy(report + 14, &transactions, sizeof(transactions));
        report[18] = (gpio_get_level(scl) << 1) | gpio_get_level(sda);
        writeReport(report, sizeof(report));
    }
}
#endif
