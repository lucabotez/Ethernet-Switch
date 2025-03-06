Copyright @lucabotez

# Ethernet Switch

## Overview
**Ethernet Switch** is a Python-based implementation of a **layer 2 switch** with support for **Spanning Tree Protocol and VLANs**. This project simulates a software-controlled switch that dynamically learns MAC addresses, forwards frames, handles VLAN tagging, and prevents network loops using STP.

## Features
- **MAC Address Learning**: Stores source MAC addresses and associates them with ports.
- **Frame Forwarding**: Directs packets based on the MAC address table.
- **Broadcast Handling**: Sends frames to all ports when a destination MAC is unknown.
- **VLAN Support**: Tags and processes VLAN traffic with 802.1Q headers.
- **Spanning Tree Protocol (STP)**: Prevents network loops using BPDU handling.
- **BPDU Packet Processing**: Manages BPDU messages to determine the root bridge and port states.
- **Port Blocking & Listening**: Implements port states to ensure a loop-free topology.

## Implementation Details
### **1. MAC Address Learning & Forwarding**
- Maintains a **MAC table** mapping addresses to ports.
- When a frame arrives:
  - If the destination MAC is known, forwards the frame to the correct port.
  - If unknown, broadcasts the frame to all other ports.
- Ensures efficient unicast forwarding while minimizing unnecessary traffic.

### **2. VLAN Support**
- Parses **VLAN tags (802.1Q)** to determine VLAN membership.
- Assigns VLANs based on port configuration (`access` or `trunk`).
- Ensures frames are forwarded only to ports within the same VLAN.

### **3. Spanning Tree Protocol (STP) Implementation**
- Prevents loops by designating:
  - **Root Bridge**: Switch with the lowest bridge ID.
  - **Root Port**: Port with the lowest cost to the root bridge.
  - **Designated Ports**: Forwarding ports on non-root switches.
- Listens for **BPDU packets** and adjusts port states dynamically.
- Sends **BPDU messages** periodically to maintain network topology.

## Notes
- The switch dynamically learns MAC addresses and updates its table.
- VLAN traffic is handled based on **802.1Q tagging**.
- STP dynamically blocks ports to prevent loops.
- BPDU packets are **sent every second** to manage STP roles.
