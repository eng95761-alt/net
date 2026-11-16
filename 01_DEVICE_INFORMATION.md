# 01 — DEVICE INFORMATION & HARDWARE AUDIT
**Device:** MikroTik RB4011iGS+  
**Audit Timestamp:** 2026-11-15T18:09:53  
**Status:** FULLY INSPECTED & VERIFIED

---

## 1. Hardware Specifications & Architecture

The MikroTik RB4011iGS+ is an enterprise-grade desktop router equipped with an Annapurna Labs Alpine AL21400 quad-core ARM Cortex-A15 processor. It features dual Realtek RTL8367 switch chips connected to the CPU via dedicated 2.5 Gbps SGMII links, plus an independent 10 Gbps SFP+ cage.

| Hardware Parameter | Detailed Specification | Operational State |
| :--- | :--- | :--- |
| **Model** | MikroTik RB4011iGS+ | RB4011iGS+ |
| **Hardware Revision** | Revision 2 (`r2`) | Validated |
| **Serial Number** | `HE608SMWF5A` | Validated |
| **Platform** | MikroTik RouterBOARD | Validated |
| **CPU Architecture** | `arm` (32-bit ARM Cortex-A15 AL21400) | Normal |
| **CPU Core Count** | 4 Physical Cores | Normal |
| **CPU Frequency** | **1400 MHz** (Manual setting) | **Warning: cpu not running at default frequency** |
| **CPU Load** | Average: 6% – 11% across all 4 cores | Normal / Low |
| **Total RAM** | 1024.0 MiB (1 GB DDR3) | Normal |
| **Free RAM** | 794.0 MiB (77.5% Free) | Healthy |
| **Total Storage (NAND)** | 512.0 MiB | Normal |
| **Free Storage Space** | 420.6 MiB (82.1% Free) | Healthy |
| **Bad Blocks** | **0.0%** | Healthy (No flash degradation) |
| **Total Sector Writes** | 1,286,470 sectors | Normal write wear |
| **Writes Since Reboot** | 23,263 sectors | Normal operational writes |

---

## 2. RouterBOARD & Firmware Audit

The RouterBOARD bootloader (RouterBOOT) manages low-level hardware initialization, PCI/switch bus arbitration, and kernel staging.

```
       routerboard: yes
             model: RB4011iGS+
          revision: r2
     serial-number: HE608SMWF5A
     firmware-type: al2
  minimum-firmware: 7.6
  current-firmware: 7.15.1
  upgrade-firmware: 7.25.1
```

### Critical Observation on Firmware:
- **Firmware Lag:** The currently executing RouterBOARD firmware is **7.15.1**, while the software image running on the system is **7.25.1**.
- **Risk Assessment:** Running a bootloader that is 10 minor versions behind the kernel can cause hardware offload quirks (specifically regarding the dual RTL8367 switch chips), improper thermal throttling behavior, or potential reboot stalls under high load.
- **CPU Frequency Warning:** The RouterBOARD settings report:
  `;;; Warning: cpu not running at default frequency`
  In `/system routerboard settings`, `cpu-frequency` has been manually pinned to `1400MHz`. While 1400MHz is stable, the RB4011 supports auto-frequency scaling (and up to 1900MHz under dynamic thermal overhead). Setting it to fixed frequency generates this diagnostic warning.

---

## 3. Operating System & Software Packages

The router runs RouterOS version 7 (ARM), which introduces the revised Linux 5.6.3+ kernel architecture, wireguard native support, and the updated User Manager v5 package.

```
Flags: X - DISABLED; A - AVAILABLE
 #   NAME         VERSION   BUILD-TIME           SIZE
 0   wireless     7.25.1    2026-11-02 12:39:53   1788.1 KiB
 1   user-manager 7.25.1    2026-11-02 12:39:53   332.1 KiB
 2   routeros     7.25.1    2026-11-02 12:39:53   11.7 MiB
```

### Software Evaluation:
- **Core OS:** `routeros-7.25.1.npk` is cleanly installed.
- **User Manager:** `user-manager-7.25.1.npk` is installed and actively serving local RADIUS requests for PPPoE subscribers.
- **Wireless Package:** The `wireless` package is installed; however, the RB4011iGS+ (non-WiFi version) has no onboard radio. The wireless package is only utilized for remote CAPsMAN management or is leftover from an all-packages installation bundle.
- **Extraneous Packages:** All other modular packages (`container`, `dude`, `iot`, `zerotier`, `rose-storage`, etc.) are available but uninstalled, keeping the NAND footprint minimal.

---

## 4. Hardware Health & Telemetry

MikroTik RB4011 features onboard voltage and thermal monitoring sensors.

```
Columns: NAME, VALUE, TYPE
#  NAME         VALUE  TYPE
0  voltage      25.1   V
1  temperature  36     C
```

### Health Analysis:
- **Input Voltage:** Measured at **25.1 V DC**. The RB4011 supports 12–57 V via DC jack or passive PoE on `ether1`. 25.1V indicates a standard 24V/2.5A switching power adapter operating within nominal calibration tolerance.
- **Board Temperature:** Measured at **36 °C**. Operating ambient temperature range is -40 °C to +70 °C. 36 °C is well below any thermal threshold, indicating excellent passive heat dissipation across the solid matte-black metal enclosure.

---

## 5. System Identity, Clock, and Licensing

### System Identity:
- **Configured Identity:** `Home`
- **Location in Export:** `/system identity set name=Home`
- **Audit Note:** The identity `Home` is a generic default. In an ISP/distribution environment serving multiple subscribers and linked to towers, a structured naming convention (e.g., `CORE-GW-RB4011-01`) is recommended to prevent administrative confusion during multi-device Winbox discovery.

### System Clock & NTP:
- **Timezone:** Configured to local timezone.
- **System Date/Time:** Monitored accurately during live audit.
- **NTP Client (`/system ntp client`):**
  ```
  enabled: no
  mode: unicast
  ```
  The NTP client is **disabled**. Time synchronization currently relies on dynamic peer NTP from the upstream DHCP client or MikroTik Cloud update-time. For cryptographic integrity (WireGuard handshakes, TLS certificates, User Manager session accounting), an independent, resilient NTP client configuration pointing to `pool.ntp.org` or regional time servers is strongly advised.

### Licensing Information:
- **Software ID:** `Q7PH-YJND`
- **License Level:** Level 5 (MikroTik RouterOS Controller License).
- **Entitlements:** Unlimited PPPoE server connections (within hardware RAM/CPU limits), full BGP/OSPF/RIP routing, and full User Manager subscriber support.

---

## 6. Watchdog & System Recovery Settings

```
          watch-address: none
        watchdog-timer: yes
 ping-start-after-boot: 5m
          ping-timeout: 1m
      automatic-supout: yes
      auto-send-supout: no
```

### Watchdog Analysis:
- **Hardware Watchdog:** The hardware timer is enabled (`watchdog-timer: yes`), guaranteeing automatic reboot if the kernel enters a hard lock or unrecoverable kernel panic.
- **Watch Address:** Currently set to `none`. There is no ICMP keepalive gateway monitored by the watchdog. While this prevents unexpected reboots during upstream ISP outages, Netwatch or a script is usually preferred over hardware watch-address rebooting.
- **Crash Dump Generation:** `automatic-supout: yes` ensures that if an unexpected reboot occurs, a diagnostic `autosupout.rif` file will be generated in flash storage for forensic examination.
