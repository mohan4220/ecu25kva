/* State machine and scheduling. Module state lives here, in statics. */
#include <string.h>
#include "ecu.h"

void ecu_init(ecu_io *io)
{
    memset(io->inj, 0, sizeof io->inj);
    io->meter_duty = 0;
    io->wdg = 0;
    io->can_n = 0;
    io->can_drops = 0;
    io->state = ECU_OFF;
    io->fault_n = io->synced = 0;
    io->rpm = io->fuel_mg = io->rail_bar = io->clt_c = io->oil_kpa = 0;
}

void ecu_crank_edge(ecu_io *io, uint32_t t_us) { (void)io; (void)t_us; }
void ecu_cam_edge(ecu_io *io, uint32_t t_us) { (void)io; (void)t_us; }
void ecu_tick_1ms(ecu_io *io, uint32_t t_us) { (void)io; (void)t_us; }
size_t ecu_io_size(void) { return sizeof(ecu_io); }
