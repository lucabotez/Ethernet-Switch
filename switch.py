# Copyright @lucabotez

#!/usr/bin/python3
import sys, struct, wrapper, threading, time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

# globally declared variables, in order to reduce the parameters
# passed to the functions
# mac_table = dictionary used to store all the MAC addresses linked to each port
# vlan_table = dictionary used to store all the vlan IDs linked to each port
# port_states = dictionart used to store the current state (0 - blocked,
#  1 - listening) of each port
own_bridge_id = root_bridge_id = root_path_cost = root_port = None
mac_table, port_states, vlan_table = {}, {}, {}
interfaces = []

# multicast MAC address used in STP
BPDU_MULTICAST_MAC = b'\x01\x80\xC2\x00\x00\x00'

def parse_ethernet_header(data):
    # Unpack the header fields from the byte array
    #dest_mac, src_mac, ethertype = struct.unpack('!6s6sH', data[:14])
    dest_mac = data[0:6]
    src_mac = data[6:12]
    
    # Extract ethertype. Under 802.1Q, this may be the bytes from the VLAN TAG
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # Check for VLAN tag (0x8100 in network byte order is b'\x81\x00')
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF  # extract the 12-bit VLAN ID
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

# function used to create BPDU packet, by packing the data in the right format
def create_bpdu_packet(bpdu_own_bridge_id, bpdu_root_path_cost,
                       bpdu_root_bridge_id):
    sender_mac = get_switch_mac()
    dest_mac = BPDU_MULTICAST_MAC

    return struct.pack("!6s6sIII", dest_mac, sender_mac, bpdu_own_bridge_id,
                        bpdu_root_path_cost, bpdu_root_bridge_id)

# function used to send BPDU packets to all trunk ports every second
# from the root port
def send_bpdu_every_sec():
    global own_bridge_id, interfaces, vlan_table

    while True:
        for i in interfaces:
            if vlan_table[get_interface_name(i)] == 'T':
                bpdu_packet = create_bpdu_packet(own_bridge_id, 0, own_bridge_id)
                send_to_link(i, len(bpdu_packet), bpdu_packet)

        time.sleep(1)

# function used to check if an address is unicast, by verifying the first bit
def is_unicast(address):
    return (address[0] & 0x01) == 0

# function used to extract the priority number and vlan ID for each port
def parse_config(switch_id):
    global vlan_table

    with open("configs/switch" + switch_id + ".cfg", "r") as config_file:
        # reading and parsing only the priority 
        priority = int(config_file.readline().strip())

        # reading and parsing the rest of information
        for line in config_file:
            name, vlan_id = line.strip().split()
            if vlan_id != 'T':
                vlan_table[name] = int(vlan_id)
            else:
                vlan_table[name] = vlan_id
            
    return priority

# function used to send a package to all other ports
def broadcast_package(interface, vlan_id, length, data):
    global vlan_table, interfaces

    for i in interfaces:
        dest_vlan_id = vlan_table[get_interface_name(i)]

        if i != interface:
            if dest_vlan_id == 'T' and port_states[get_interface_name(i)] != 0:
                # adding the vlan tag to the packet and modifying the length
                # accordingly
                data = data[0:12] + create_vlan_tag(vlan_id) + data[12:]
                length += 4

                send_to_link(i, length, data)
            elif dest_vlan_id == vlan_id:
                send_to_link(i, length, data)

# function used to handle the package forwarding logic by following the
# pseudocode provided and checking the vlan IDs for each port
def direct_package(data, length, dest_mac, vlan_id, interface):
    global vlan_table, interfaces

    if is_unicast(dest_mac):
        if dest_mac in mac_table:
            dest_vlan_id = vlan_table[get_interface_name(mac_table[dest_mac])]

            if dest_vlan_id == 'T' \
                and port_states[get_interface_name(mac_table[dest_mac])] != 0:
                data = data[0:12] + create_vlan_tag(vlan_id) + data[12:]
                length += 4

                send_to_link(mac_table[dest_mac], length, data)
            elif dest_vlan_id == vlan_id:
                send_to_link(mac_table[dest_mac], length, data)
        else:
            broadcast_package(interface, vlan_id, length, data)
    else:
        broadcast_package(interface, vlan_id, length, data)

# function used to handle the BPDU package forwarding logic by following the
# pseudocode provided and checking the vlan IDs for each port
def handle_bpdu(bpdu_own_bridge_id, bpdu_root_path_cost, 
                bpdu_root_bridge_id, interface):
    global own_bridge_id, root_bridge_id, root_path_cost, root_port
    global interfaces, vlan_table

    if bpdu_root_bridge_id < root_bridge_id:
        root_path_cost = bpdu_root_path_cost + 10 
        root_port = interface

        if own_bridge_id == root_bridge_id:
            for i in interfaces:
                if vlan_table[get_interface_name(i)] == 'T' and i != root_port:
                    port_states[get_interface_name(i)] = 0

        root_bridge_id = bpdu_root_bridge_id
 
        if port_states[get_interface_name(root_port)] == 0:
            port_states[get_interface_name(root_port)] = 1

        for i in interfaces:
            if vlan_table[get_interface_name(i)] == 'T' \
                and port_states[get_interface_name(i)] != 0 \
                and i != interface:

                bpdu_packet = create_bpdu_packet(own_bridge_id, 
                                                 root_path_cost, 
                                                 root_bridge_id)
                send_to_link(i, len(bpdu_packet), bpdu_packet)

    elif bpdu_root_bridge_id == root_bridge_id:
        if interface == root_port and bpdu_root_path_cost + 10 < root_path_cost:
            root_path_cost = bpdu_root_path_cost + 10
        elif interface != root_port:
            if bpdu_root_path_cost > root_path_cost:
                if port_states[get_interface_name(interface)] == 0:
                    port_states[get_interface_name(interface)] == 1

    elif bpdu_own_bridge_id == own_bridge_id:
        port_states[get_interface_name(interface)] == 0

    else:
        return

    if own_bridge_id == root_bridge_id:
        for i in interfaces:
            port_states[get_interface_name(i)] = 1

def main():
    global own_bridge_id, root_bridge_id, root_path_cost, root_port
    global vlan_table, interfaces

    switch_id = sys.argv[1]

    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(0, num_interfaces)

    priority = parse_config(switch_id)

    # initialize steps for STP
    for i in interfaces:
        if vlan_table[get_interface_name(i)] == 'T':
            port_states[get_interface_name(i)] = 0 # blocked port
        else:
            port_states[get_interface_name(i)] = 1 # opened port

    own_bridge_id = priority
    root_bridge_id = own_bridge_id
    root_path_cost = 0

    if own_bridge_id == root_bridge_id:
        for i in interfaces:
            port_states[get_interface_name(i)] = 1

    # Create and start a new thread that deals with sending BDPU
    if own_bridge_id == root_bridge_id:
        t = threading.Thread(target=send_bpdu_every_sec)
        t.start()

    while True:
        interface, data, length = recv_from_any_link()
        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)

        # checking if the packet received is a BPDU packet or not
        if dest_mac == BPDU_MULTICAST_MAC:
            # parsing the required information from the packet
            unpacked_data = struct.unpack("!6s6sIII", data)
            dest_mac, src_mac, bpdu_own_bridge_id = unpacked_data[0:3]
            bpdu_root_path_cost, bpdu_root_bridge_id = unpacked_data[3:]

            handle_bpdu(bpdu_own_bridge_id, bpdu_root_path_cost,
                        bpdu_root_bridge_id, interface)
        else:
            # if no vlan ID is assigned, assign it
            # else remove the current vlan header in order to create
            # and add a new one or send the packet without it on
            # trunk ports
            if vlan_id == -1:
                vlan_id = vlan_table[get_interface_name(interface)]
            else:
                data = data[0:12] + data[16:]
                length -= 4

            if src_mac not in mac_table:
                mac_table[src_mac] = interface
            
            direct_package(data, length, dest_mac, vlan_id, interface)

if __name__ == "__main__":
    main()
