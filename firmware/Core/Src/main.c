#include "board.h"
#include "storage.h"
static Controller controller;
static Storage storage={0,eeprom_read,eeprom_write,0,-1};
int main(void) {
    board_init();controller_init(&controller);
    if(storage_load(&storage,&controller.config)) {
        controller.saved_sequence=storage.sequence;controller.storage_status=0;
    } else { controller.storage_status=3;controller.dirty=true; }
    controller_powerup(&controller,HAL_GetTick());
    if(board_watchdog_reset()) { controller.latched|=F_LOOP;controller_stop(&controller); }
    sensors_init(&controller);transport_init();
    for(;;) {
        uint32_t now=HAL_GetTick();
        bool rotary_initialized=controller.rotary.initialized;
        if(rotary_update(&controller.rotary,rotary_decode((uint16_t)GPIOB->IDR),now) && rotary_initialized) {
            controller_stop(&controller);board_off();
        }
        if(board_lease_failed()) { controller.latched|=F_LOOP;controller_stop(&controller);board_off(); }
        sensors_poll(&controller,now);
        controller_update(&controller,HAL_GetTick(),board_gate(),board_gate_changed());
        controller_boot_update(&controller,HAL_GetTick());
        if(!controller.mode) board_output(0,config_burst_period_ms(&controller.config),controller_relay(&controller));
        transport_poll(&controller);
        /* Apply protection again after protocol writes, before energizing output. */
        controller_update(&controller,HAL_GetTick(),board_gate(),board_gate_changed());
        if(controller.save_requested && transport_idle()) {
            board_off();
            bool ok=storage_save(&storage,&controller.config);
            controller.storage_status=ok?2:4;controller.save_requested=false;
            if(ok) { controller.dirty=false;controller.saved_sequence=storage.sequence; }
            else {
                controller.latched|=F_STORAGE;controller_stop(&controller);
                controller.save_requested=false;controller.storage_status=4;
            }
        }
        board_output(controller.output,config_burst_period_ms(&controller.config),controller_relay(&controller));
        board_watchdog();
    }
}
