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
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.backends import default_backend
import argparse

# Constants
TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000
MTU = 1500

class VPNPacket:
    """
    VPN Packet Format:
    [4 bytes: sequence number][32 bytes: HMAC][N bytes: encrypted payload]
    """
    HEADER_SIZE = 4
    HMAC_SIZE = 32
    
    def __init__(self, seq_num, payload):
        self.seq_num = seq_num
        self.payload = payload
    
    def pack(self, cipher, hmac_key):
        """Encrypt and pack the packet"""
        # Encrypt payload
        encryptor = cipher.encryptor()
        # Pad payload to multiple of 16 bytes (AES block size)
        padding_length = 16 - (len(self.payload) % 16)
        padded_payload = self.payload + bytes([padding_length] * padding_length)
        encrypted_payload = encryptor.update(padded_payload) + encryptor.finalize()
        
        # Create header
        header = struct.pack('!I', self.seq_num)
        
        # Calculate HMAC over header + encrypted payload
        h = hmac.HMAC(hmac_key, hashes.SHA256(), backend=default_backend())
        h.update(header + encrypted_payload)
        hmac_value = h.finalize()
        
        return header + hmac_value + encrypted_payload
    
    @staticmethod
    def unpack(data, cipher, hmac_key, expected_seq):
        """Unpack and decrypt the packet"""
        if len(data) < VPNPacket.HEADER_SIZE + VPNPacket.HMAC_SIZE:
            raise ValueError("Packet too short")
        
        # Extract components
        header = data[:VPNPacket.HEADER_SIZE]
        received_hmac = data[VPNPacket.HEADER_SIZE:VPNPacket.HEADER_SIZE + VPNPacket.HMAC_SIZE]
        encrypted_payload = data[VPNPacket.HEADER_SIZE + VPNPacket.HMAC_SIZE:]
        
        # Verify HMAC
        h = hmac.HMAC(hmac_key, hashes.SHA256(), backend=default_backend())
        h.update(header + encrypted_payload)
        try:
            h.verify(received_hmac)
        except Exception:
            raise ValueError("HMAC verification failed - packet may be tampered")
        
        # Extract sequence number
        seq_num = struct.unpack('!I', header)[0]
        
        # Check for replay attacks
        if seq_num <= expected_seq:
            raise ValueError(f"Replay attack detected: received seq {seq_num}, expected > {expected_seq}")
        
        # Decrypt payload
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
        
        # Initialize cipher (using CTR mode for stream encryption)
        self.iv = os.urandom(16)
        self.cipher = Cipher(
            algorithms.AES(self.encryption_key),
            modes.CTR(self.iv),
            backend=default_backend()
        )
        
        # Sequence numbers for replay protection
        self.send_seq = 0
        self.recv_seq = 0
        
        # Create TUN interface
        self.tun = self.create_tun()
        
        # Create UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.local_ip, self.local_port))
        
        print(f"[+] VPN initialized in {mode} mode")
        print(f"[+] Listening on {self.local_ip}:{self.local_port}")
        print(f"[+] TUN interface: {self.tun_local} <-> {self.tun_remote}")
    
    def create_tun(self):
        """Create and configure TUN interface"""
        try:
            tun = os.open("/dev/net/tun", os.O_RDWR)
            ifr = struct.pack('16sH', b'tun0', IFF_TUN | IFF_NO_PI)
            fcntl.ioctl(tun, TUNSETIFF, ifr)
            
            # Configure interface
            os.system(f'ip addr add {self.tun_local}/24 dev tun0')
            os.system('ip link set dev tun0 up')
            
            # Add route to remote network through TUN
            os.system(f'ip route add {self.tun_remote}/32 dev tun0')
            
            print(f"[+] TUN interface created: tun0")
            return tun
        except Exception as e:
            print(f"[-] Error creating TUN interface: {e}")
            print("[!] Make sure you run this with sudo/root privileges")
            sys.exit(1)
    
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
            
            # Create VPN packet
            self.send_seq += 1
            vpn_packet = VPNPacket(self.send_seq, packet)
            
            # Encrypt and pack
            encrypted_data = vpn_packet.pack(self.cipher, self.hmac_key)
            
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
            
            # Unpack and decrypt
            vpn_packet = VPNPacket.unpack(data, self.cipher, self.hmac_key, self.recv_seq)
            self.recv_seq = vpn_packet.seq_num
            
            # Write decrypted IP packet to TUN
            os.write(self.tun, vpn_packet.payload)
            
            print(f"[←] Received packet #{vpn_packet.seq_num}, size: {len(vpn_packet.payload)} bytes")
        
        except ValueError as e:
            print(f"[!] Security error: {e}")
        except Exception as e:
            print(f"[-] Error handling network packet: {e}")
    
    def cleanup(self):
        """Clean up resources"""
        os.close(self.tun)
        self.sock.close()
        os.system('ip link set dev tun0 down')
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

