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

// Enable/disable radios at runtime (button, serial or BLE command).
void net_set_wifi(bool on);
void net_set_ble(bool on);
bool net_wifi_on();
bool net_ble_on();

// Register the handler for inbound commands ("measure", "wifi on", ...).
void net_on_command(NetCommandFn fn);

// Handle one command line (shared by serial/BLE/HTTP 'cmd').
void net_dispatch(const char *cmd);
