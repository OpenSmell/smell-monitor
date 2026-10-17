// cycle.h - three-phase measurement state machine (blueprint 7.1).
#pragma once

#include <stdint.h>

void cycle_begin();
void cycle_loop();
void cycle_request();      // ask for one cycle (button / command)
bool cycle_busy();
uint8_t cycle_phase();
