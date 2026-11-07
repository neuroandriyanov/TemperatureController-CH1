#ifndef TC_CORE_H
#define TC_CORE_H
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
enum {
#define X(n,d,l,h) C_##n,
#include "config.def"
#undef X
    CONFIG_COUNT
};
typedef struct { uint16_t v[CONFIG_COUNT]; } Config;
void config_defaults(Config *c);
int32_t config_value(const Config *c, unsigned i);
bool config_valid(const Config *c);
uint32_t config_burst_period_ms(const Config *c);
uint32_t burst_on_time_ms(uint32_t period, uint16_t power);

typedef struct { float integral, derivative, last_pv; bool initialized; } Pid;
float pid_step(Pid *p, float sp, float pv, float dt, float kp, float ki,
               float kd, float tau, float maximum);
void pid_reset(Pid *p);

typedef struct { uint64_t sum, squares; uint32_t n; uint16_t min, max; } Moments;
void moments_reset(Moments *m);
void moments_add(Moments *m, const volatile uint16_t *v, unsigned n);
float moments_rms(const Moments *m);
float current_ma(float raw_rms, const Config *c);
bool external_capture_frequency(const uint16_t *periods, unsigned count, float *hz);
bool external_convert(float hz, const Config *c, float *mv, float *ua, float *temp);
float max_tc_decode(const uint8_t data[3]);
float max_cj_decode(const uint8_t data[2]);
bool max_cj_encode(float celsius, uint8_t data[2]);
bool max_cj_usable(uint16_t tc_type,float celsius);
uint8_t rotary_decode(uint16_t gpio_b);
typedef struct { uint8_t raw, address; uint32_t since; bool initialized, stable; } Rotary;
bool rotary_update(Rotary *r, uint8_t raw, uint32_t now);

enum { MODE_STOP, MODE_AUTO, MODE_MANUAL, MODE_CURRENT_TEST };
enum { RELAY_OFF, RELAY_TOLERANCE, RELAY_SOAK, RELAY_ERROR, RELAY_OVERCURRENT,
       RELAY_HEATER, RELAY_DEVICE };
enum {
 F_TC=1u<<0, F_TC_STALE=1u<<1, F_CURRENT=1u<<2, F_CURRENT_STALE=1u<<3,
 F_EXTERNAL=1u<<4, F_EXTERNAL_STALE=1u<<5, F_TEMPERATURE=1u<<6,
 F_OVERCURRENT=1u<<7, F_STUCK_OUTPUT=1u<<8, F_OPEN_HEATER=1u<<9,
 F_COMMUNICATION=1u<<10, F_ADDRESS=1u<<11, F_LOOP=1u<<12,
 F_CALIBRATION=1u<<13, F_STORAGE=1u<<14
};
typedef struct {
 float pv, cj, external_c, external_mv, external_ua, current_ma, adc_mean, adc_rms;
 uint32_t tc_at, current_at, ext_at, ext_hz, adc_overruns;
 uint16_t adc_min, adc_max, max_status;
 bool tc_valid, current_valid, ext_valid;
} Measurements;
typedef struct {
 Config config; Measurements m; Pid pid; Rotary rotary;
 uint32_t active, latched, last_contact, pid_at, over_since, off_since, open_since;
 uint32_t sample_id, config_revision, saved_sequence;
 float working_sp, output;
 uint16_t mode, manual, storage_status;
 bool dirty, over_timing, off_timing, open_timing, save_requested;
 uint32_t soak_since,boot_since,open_elapsed,current_test_since;
 uint16_t boot_status;
 bool soak_started,soak_ready,contact_seen;
} Controller;
void controller_init(Controller *s);
void controller_stop(Controller *s);
void controller_powerup(Controller *s,uint32_t now);
void controller_boot_update(Controller *s,uint32_t now);
bool controller_relay(const Controller *s);
void controller_update(Controller *s, uint32_t now, bool gate, uint32_t gate_changed);
uint8_t controller_mode(Controller *s, uint16_t mode, uint32_t now);
uint8_t controller_write(Controller *s, uint16_t addr, uint16_t n, const uint16_t *v,
                         bool broadcast, uint32_t now);
uint8_t controller_read(const Controller *s, bool input, uint16_t addr, uint16_t n,
                       uint16_t *v, uint32_t now, bool gate, bool relay);
#define INPUT_COUNT 64u
#define REG_MODE 0x0100u
#define REG_MANUAL 0x0101u
#define REG_SAVE 0x0102u
#define REG_CLEAR 0x0103u
#define REG_CURRENT_TEST 0x0104u
#define REG_WORKING_SETTINGS 0x0105u /* FC16: setpoint, tolerance below, above; autosave. */
#define CURRENT_TEST_KEY 0xCA10u
#define CURRENT_TEST_MS 10000u
#define CURRENT_TEST_LINK_MS 1000u
#define CURRENT_TEST_MAX_RMS 400.0f
#define CURRENT_TEST_MAX_C 65.0f
#define SAVE_KEY 0xA55Au
#define CLEAR_KEY 0xC1EAu
#endif
