// net.h - transports: USB serial (always), Wi-Fi (MQTT + HTTP), BLE (GATT).
#pragma once

#include <stddef.h>

typedef void (*NetCommandFn)(const char *cmd);

// Start serial command handling and load saved credentials.  Wi-Fi and BLE
// stay OFF until enabled (keeps idle power low - blueprint 7.5).
void net_begin();
void net_loop();

// Fan a JSON record out to every enabled transport (serial / MQTT / BLE).
void net_publish(const char *json);

// ISO-8601 UTC wall clock ("YYYY-MM-DDTHH:MM:SSZ"). Returns 0 when SNTP has
// never synced (no Wi-Fi, DNS failure, etc.); never blocks or retries inline.
size_t net_wall_clock(char *buf, size_t n);

// Enable/disable radios at runtime (button, serial or BLE command).
void net_set_wifi(bool on);
void net_set_ble(bool on);
bool net_wifi_on();
bool net_ble_on();

// Force the password-protected setup AP even when STA credentials are stored
// (MENU long press), and wipe all persisted settings then reboot (factory
// reset, only after an on-screen confirmation).
void net_enter_ap();
void net_factory_reset();

// Register the handler for inbound commands ("measure", "wifi on", ...).
void net_on_command(NetCommandFn fn);

// Handle one command line (shared by serial/BLE/HTTP 'cmd').
void net_dispatch(const char *cmd);
