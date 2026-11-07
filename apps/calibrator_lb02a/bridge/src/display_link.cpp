#ifdef LCD_CAPTURE
#include "display_link.h"
#include <Preferences.h>
#include <WiFi.h>
#include <esp_system.h>
#include <lwip/sockets.h>

namespace {
WiFiServer server(8769, 1);
WiFiClient client;
char ssid[13];
char password[13];
bool apReady = false;
bool networkActive = false;
}

void setupDisplayLink() {
    Preferences preferences;
    if (!preferences.begin("lb02a-wifi")) return;
    String saved = preferences.getString("password");
    if (saved.length() != 12) {
        snprintf(password, sizeof(password), "%08lx%04lx",
                 static_cast<unsigned long>(esp_random()),
                 static_cast<unsigned long>(esp_random() & 0xFFFF));
        if (preferences.putString("password", password) != 12) return;
    } else {
        saved.toCharArray(password, sizeof(password));
    }
    snprintf(ssid, sizeof(ssid), "LB02A-%06lX",
             static_cast<unsigned long>(ESP.getEfuseMac() >> 24));
    apReady = WiFi.softAP(ssid, password, 1, false, 1);
    if (apReady) server.begin();
}

void serviceDisplayLink() {
    if (!apReady) return;
    if (networkActive && !client.connected()) {
        client.stop();
        networkActive = false;
    }
    if (!networkActive) {
        client = server.available();
        if (client) {
            client.setNoDelay(true);
            networkActive = true;
        }
    }
    static uint32_t lastReport = 0;
    if (!networkActive && millis() - lastReport >= 2000 && Serial.availableForWrite() >= 28) {
        lastReport = millis();
        uint8_t report[28] = {'L', 'B', 'W', '1'};
        memcpy(report + 4, ssid, 12);
        memcpy(report + 16, password, 12);
        Serial.write(report, sizeof(report));
    }
}

int readDisplayCommand() {
    if (!networkActive) return Serial.read();
    while (Serial.available()) Serial.read();
    return client.read();
}

void writeDisplayData(const uint8_t *data, size_t size) {
    if (!networkActive) {
        Serial.write(data, size);
        return;
    }
    const uint32_t started = millis();
    while (size) {
        const int written = send(client.fd(), data, size, MSG_DONTWAIT);
        if (written > 0) {
            data += written;
            size -= written;
        } else if (written < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)
                   && millis() - started < 80) {
            delay(1);
        } else {
            // Drop the connection on sustained backpressure. A partial packet
            // must never be followed by a new packet on the same TCP stream.
            client.stop();
            networkActive = false;
            return;
        }
    }
}
#endif
