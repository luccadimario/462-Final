#!/usr/bin/env python3
"""
Simple VPN Implementation
CS462 Computer Networks - VPN Project
"""

import os
import sys
import struct
import socket
import select
import fcntl
import platform
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.backends import default_backend
import argparse

# Constants for Linux
TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000
MTU = 1500

# Constants for macOS utun
CTLIOCGINFO = 0xc0644e03  # ioctl to get kernel control info
SYSPROTO_CONTROL = 2
AF_SYS_CONTROL = 2
PF_SYSTEM = 32
UTUN_CONTROL_NAME = b"com.apple.net.utun_control"

class VPNPacket:
    """
    VPN Packet Format (FIXED - Now includes unique IV per packet):
    [16 bytes: IV][4 bytes: sequence number][32 bytes: HMAC][N bytes: encrypted payload]

    Security improvements:
    - Unique IV generated for each packet (prevents CTR mode attacks)
    - HMAC covers IV + header + encrypted payload (prevents tampering)
    - Sequence numbers prevent replay attacks
    """
    IV_SIZE = 16
    HEADER_SIZE = 4
    HMAC_SIZE = 32

    def __init__(self, seq_num, payload):
        self.seq_num = seq_num
        self.payload = payload

    def pack(self, encryption_key, hmac_key):
        """Encrypt and pack the packet with a unique IV"""
        # Generate NEW IV for THIS packet (fixes CTR mode security)
        iv = os.urandom(16)

        # Create cipher with the new IV
        cipher = Cipher(
            algorithms.AES(encryption_key),
            modes.CTR(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()

        # Pad payload to multiple of 16 bytes (AES block size)
        padding_length = 16 - (len(self.payload) % 16)
        padded_payload = self.payload + bytes([padding_length] * padding_length)
        encrypted_payload = encryptor.update(padded_payload) + encryptor.finalize()

        # Create header
        header = struct.pack('!I', self.seq_num)

        # Calculate HMAC over IV + header + encrypted payload
        h = hmac.HMAC(hmac_key, hashes.SHA256(), backend=default_backend())
        h.update(iv + header + encrypted_payload)
        hmac_value = h.finalize()

        # Return: IV + header + HMAC + encrypted_payload
        return iv + header + hmac_value + encrypted_payload

    @staticmethod
    def unpack(data, encryption_key, hmac_key, expected_seq):
        """Unpack and decrypt the packet"""
        min_size = VPNPacket.IV_SIZE + VPNPacket.HEADER_SIZE + VPNPacket.HMAC_SIZE
        if len(data) < min_size:
            raise ValueError("Packet too short")

        # Extract components
        iv = data[:VPNPacket.IV_SIZE]
        header = data[VPNPacket.IV_SIZE:VPNPacket.IV_SIZE + VPNPacket.HEADER_SIZE]
        hmac_start = VPNPacket.IV_SIZE + VPNPacket.HEADER_SIZE
        received_hmac = data[hmac_start:hmac_start + VPNPacket.HMAC_SIZE]
        encrypted_payload = data[hmac_start + VPNPacket.HMAC_SIZE:]

        # Verify HMAC
        h = hmac.HMAC(hmac_key, hashes.SHA256(), backend=default_backend())
        h.update(iv + header + encrypted_payload)
        try:
            h.verify(received_hmac)
        except Exception:
            raise ValueError("HMAC verification failed - packet may be tampered")

        # Extract sequence number
        seq_num = struct.unpack('!I', header)[0]

        # Check for replay attacks
        if seq_num <= expected_seq:
            raise ValueError(f"Replay attack detected: received seq {seq_num}, expected > {expected_seq}")

        # Create cipher with extracted IV
        cipher = Cipher(
            algorithms.AES(encryption_key),
            modes.CTR(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded_payload = decryptor.update(encrypted_payload) + decryptor.finalize()

        # Remove padding
        padding_length = padded_payload[-1]
        payload = padded_payload[:-padding_length]

        return VPNPacket(seq_num, payload)


class VPN:
    def __init__(self, mode, local_ip, remote_ip, local_port, remote_port, key, tun_local, tun_remote):
        self.mode = mode  # 'server' or 'client'
        self.local_ip = local_ip
        self.remote_ip = remote_ip
        self.local_port = local_port
        self.remote_port = remote_port
        self.tun_local = tun_local
        self.tun_remote = tun_remote

        # Cryptographic setup
        self.key = key.encode() if isinstance(key, str) else key
        # Derive encryption and HMAC keys from master key
        self.encryption_key = self.key[:32]  # 256-bit key for AES
        self.hmac_key = self.key[32:64] if len(self.key) >= 64 else self.key[:32]

        # Sequence numbers for replay protection
        self.send_seq = 0
        self.recv_seq = 0

        # Platform detection
        self.platform = platform.system()
        self.tun_name = None  # Will be set by create_tun()

        # Create TUN interface
        self.tun = self.create_tun()

        # Create UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.local_ip, self.local_port))

        print(f"[+] VPN initialized in {mode} mode")
        print(f"[+] Listening on {self.local_ip}:{self.local_port}")
        print(f"[+] TUN interface: {self.tun_local} <-> {self.tun_remote}")
    
    def create_tun(self):
        """Create and configure TUN interface (cross-platform)"""
        try:
            if self.platform == 'Darwin':  # macOS
                return self._create_tun_macos()
            elif self.platform == 'Linux':
                return self._create_tun_linux()
            else:
                raise OSError(f"Unsupported platform: {self.platform}")
        except Exception as e:
            print(f"[-] Error creating TUN interface: {e}")
            print("[!] Make sure you run this with sudo/root privileges")
            sys.exit(1)

    def _create_tun_macos(self):
        """Create and configure utun interface on macOS (built-in, no drivers needed)"""
        # Try to create a utun interface by trying different unit numbers
        tun = None
        ctl_id = None
        unit_number = None

        # First, get the kernel control ID for utun
        temp_sock = socket.socket(PF_SYSTEM, socket.SOCK_DGRAM, SYSPROTO_CONTROL)
        ctl_info = struct.pack('I96s', 0, UTUN_CONTROL_NAME)
        ctl_info = fcntl.ioctl(temp_sock.fileno(), CTLIOCGINFO, ctl_info)
        ctl_id = struct.unpack('I96s', ctl_info)[0]
        temp_sock.close()

        # Try to connect to utun devices (unit numbers 1-16 correspond to utun0-utun15)
        for unit in range(1, 17):
            try:
                tun = socket.socket(PF_SYSTEM, socket.SOCK_DGRAM, SYSPROTO_CONTROL)
                # Python socket.connect() expects (id, unit) tuple for PF_SYSTEM
                # Unit N creates utun(N-1), so unit 1 = utun0, unit 2 = utun1, etc.
                tun.connect((ctl_id, unit))
                unit_number = unit
                self.tun_name = f'utun{unit - 1}'
                print(f"[+] Created utun interface: {self.tun_name}")
                break
            except OSError as e:
                if tun:
                    tun.close()
                tun = None
                continue

        if tun is None:
            raise OSError("Could not create utun interface (tried utun0-utun15)")

        # Get the file descriptor for use with os.read/write
        tun_fd = tun.fileno()

        # Configure interface using ifconfig
        # macOS utun format: ifconfig utunX <local_ip> <remote_ip> up
        cmd = f'ifconfig {self.tun_name} {self.tun_local} {self.tun_remote} up'
        result = os.system(cmd)
        if result != 0:
            raise OSError(f"Failed to configure interface with: {cmd}")

        # Add route to remote host through utun interface
        cmd = f'route add -host {self.tun_remote} -interface {self.tun_name}'
        result = os.system(cmd)
        if result != 0:
            print(f"[!] Warning: Failed to add route: {cmd}")

        print(f"[+] utun interface configured: {self.tun_name}")
        print(f"[+] Local: {self.tun_local}, Remote: {self.tun_remote}")

        # Return the file descriptor (not the socket object)
        # Store the socket object to prevent it from being garbage collected
        self._tun_socket = tun
        return tun_fd

    def _create_tun_linux(self):
        """Create and configure TUN interface on Linux"""
        tun = os.open("/dev/net/tun", os.O_RDWR)
        ifr = struct.pack('16sH', b'tun0', IFF_TUN | IFF_NO_PI)
        fcntl.ioctl(tun, TUNSETIFF, ifr)
        self.tun_name = 'tun0'

        # Configure interface
        os.system(f'ip addr add {self.tun_local}/24 dev tun0')
        os.system('ip link set dev tun0 up')

        # Add route to remote network through TUN
        os.system(f'ip route add {self.tun_remote}/32 dev tun0')

        print(f"[+] TUN interface created: tun0")
        return tun
    
    def run(self):
        """Main VPN loop"""
        print("[+] VPN running... Press Ctrl+C to stop")
        
        try:
            while True:
                # Use select to monitor both TUN and socket
                readable, _, _ = select.select([self.tun, self.sock], [], [])
                
                for fd in readable:
                    if fd == self.tun:
                        # Packet from TUN (local app) -> encrypt and send to remote
                        self.handle_tun_packet()
                    elif fd == self.sock:
                        # Packet from network -> decrypt and send to TUN
                        self.handle_network_packet()
        
        except KeyboardInterrupt:
            print("\n[+] Shutting down VPN...")
            self.cleanup()
    
    def handle_tun_packet(self):
        """Read packet from TUN, encrypt, and send over network"""
        try:
            # Read IP packet from TUN
            packet = os.read(self.tun, MTU)

            # macOS utun adds a 4-byte protocol header (AF_INET/AF_INET6)
            # We need to strip it before encrypting
            if self.platform == 'Darwin':
                if len(packet) < 4:
                    return
                # Skip the 4-byte protocol family header
                packet = packet[4:]

            # Create VPN packet
            self.send_seq += 1
            vpn_packet = VPNPacket(self.send_seq, packet)

            # Encrypt and pack (generates new IV for each packet)
            encrypted_data = vpn_packet.pack(self.encryption_key, self.hmac_key)

            # Send over UDP
            self.sock.sendto(encrypted_data, (self.remote_ip, self.remote_port))

            print(f"[→] Sent packet #{self.send_seq}, size: {len(packet)} bytes")

        except Exception as e:
            print(f"[-] Error handling TUN packet: {e}")
    
    def handle_network_packet(self):
        """Receive packet from network, decrypt, and write to TUN"""
        try:
            # Receive encrypted packet
            data, addr = self.sock.recvfrom(65535)

            # Unpack and decrypt (extracts IV from packet)
            vpn_packet = VPNPacket.unpack(data, self.encryption_key, self.hmac_key, self.recv_seq)
            self.recv_seq = vpn_packet.seq_num

            # macOS utun requires a 4-byte protocol family header
            # Determine protocol family from IP version (first 4 bits of first byte)
            if self.platform == 'Darwin':
                ip_version = (vpn_packet.payload[0] >> 4) if len(vpn_packet.payload) > 0 else 4
                if ip_version == 4:
                    protocol_family = struct.pack('!I', socket.AF_INET)  # 2 in network byte order
                elif ip_version == 6:
                    protocol_family = struct.pack('!I', socket.AF_INET6)  # 30 in network byte order
                else:
                    protocol_family = struct.pack('!I', socket.AF_INET)  # Default to IPv4

                # Prepend protocol family header
                packet_to_write = protocol_family + vpn_packet.payload
            else:
                packet_to_write = vpn_packet.payload

            # Write decrypted IP packet to TUN
            os.write(self.tun, packet_to_write)

            print(f"[←] Received packet #{vpn_packet.seq_num}, size: {len(vpn_packet.payload)} bytes")

        except ValueError as e:
            print(f"[!] Security error: {e}")
        except Exception as e:
            print(f"[-] Error handling network packet: {e}")
    
    def cleanup(self):
        """Clean up resources (cross-platform)"""
        if self.platform == 'Darwin':  # macOS
            # Close the utun socket
            if hasattr(self, '_tun_socket'):
                self._tun_socket.close()
            # Bring interface down and remove route
            os.system(f'ifconfig {self.tun_name} down')
            os.system(f'route delete -host {self.tun_remote}')
        else:  # Linux
            os.close(self.tun)
            os.system(f'ip link set dev {self.tun_name} down')

        self.sock.close()
        print("[+] Cleanup complete")


def main():
    parser = argparse.ArgumentParser(description='Simple VPN Implementation')
    parser.add_argument('mode', choices=['server', 'client'], help='Run as server or client')
    parser.add_argument('--local-ip', required=True, help='Local IP address to bind')
    parser.add_argument('--remote-ip', required=True, help='Remote IP address to connect')
    parser.add_argument('--local-port', type=int, required=True, help='Local UDP port')
    parser.add_argument('--remote-port', type=int, required=True, help='Remote UDP port')
    parser.add_argument('--key', required=True, help='Shared secret key (min 64 chars)')
    parser.add_argument('--tun-local', required=True, help='Local TUN IP (e.g., 10.0.0.1)')
    parser.add_argument('--tun-remote', required=True, help='Remote TUN IP (e.g., 10.0.0.2)')
    
    args = parser.parse_args()
    
    if len(args.key) < 64:
        print("[!] Key must be at least 64 characters for security")
        sys.exit(1)
    
    vpn = VPN(
        mode=args.mode,
        local_ip=args.local_ip,
        remote_ip=args.remote_ip,
        local_port=args.local_port,
        remote_port=args.remote_port,
        key=args.key,
        tun_local=args.tun_local,
        tun_remote=args.tun_remote
    )
    
    vpn.run()


if __name__ == '__main__':
    main()

