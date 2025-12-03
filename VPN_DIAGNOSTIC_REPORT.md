# VPN Diagnostic Report
**CS462 Computer Networks - VPN Project**
**Date:** December 1, 2025
**Testing Environment:** macOS (client) ↔ Linux (server) via Tailscale

---

## 1. System Configuration

### macOS Client (Luccas-MacBook-Pro)
- **OS:** macOS 26.1 (Build 25B78)
- **Tailscale IP:** 100.105.100.121
- **VPN Tunnel IP:** 10.0.0.2
- **Interface:** utun8 (native macOS utun - no third-party drivers required)

### Linux Server (DeepSpace9)
- **OS:** Ubuntu Linux 6.8.0-87-generic (x86_64)
- **Kernel:** 6.8.0-87-generic #88-Ubuntu SMP PREEMPT_DYNAMIC
- **Tailscale IP:** 100.113.49.125
- **VPN Tunnel IP:** 10.0.0.1
- **Interface:** tun0

### VPN Configuration
- **Transport:** UDP over Tailscale mesh network
- **macOS Port:** 5555
- **Linux Port:** 5556
- **MTU:** 1500 bytes

---

## 2. VPN Interface Status

### macOS (utun8)
```
utun8: flags=8051<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1500
    inet 10.0.0.2 --> 10.0.0.1 netmask 0xff000000
```
**Status:** ✅ UP and RUNNING

### macOS Routing Table
```
Destination        Gateway            Flags               Netif
10.0.0.1           10.0.0.2           UH                  utun8
```
**Status:** ✅ Route configured correctly

### Linux (tun0)
```
tun0: <POINTOPOINT,MULTICAST,NOARP,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UNKNOWN
    link/none
    inet 10.0.0.1/24 scope global tun0
       valid_lft forever preferred_lft forever
    inet6 fe80::9836:572c:d1cb:a457/64 scope link stable-privacy
       valid_lft forever preferred_lft forever
```
**Status:** ✅ UP and RUNNING

### Linux Routing Table
```
10.0.0.0/24 dev tun0 proto kernel scope link src 10.0.0.1
10.0.0.2 dev tun0 scope link
```
**Status:** ✅ Route configured correctly

---

## 3. Connectivity Tests

### Ping Test: macOS → Linux
```
PING 10.0.0.1 (10.0.0.1): 56 data bytes
64 bytes from 10.0.0.1: icmp_seq=0 ttl=64 time=51.382 ms
64 bytes from 10.0.0.1: icmp_seq=1 ttl=64 time=56.308 ms
64 bytes from 10.0.0.1: icmp_seq=2 ttl=64 time=48.191 ms
64 bytes from 10.0.0.1: icmp_seq=3 ttl=64 time=44.478 ms
64 bytes from 10.0.0.1: icmp_seq=4 ttl=64 time=49.594 ms

--- 10.0.0.1 ping statistics ---
5 packets transmitted, 5 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 44.478/49.991/56.308/3.889 ms
```
**Result:** ✅ 100% packet delivery, avg latency ~50ms

### Ping Test: Linux → macOS
```
PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.
64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=78.4 ms
64 bytes from 10.0.0.2: icmp_seq=2 ttl=64 time=63.7 ms
64 bytes from 10.0.0.2: icmp_seq=3 ttl=64 time=50.3 ms
64 bytes from 10.0.0.2: icmp_seq=4 ttl=64 time=95.0 ms
64 bytes from 10.0.0.2: icmp_seq=5 ttl=64 time=51.5 ms

--- 10.0.0.2 ping statistics ---
5 packets transmitted, 5 received, 0% packet loss, time 4006ms
rtt min/avg/max/mdev = 50.329/67.782/94.961/16.956 ms
```
**Result:** ✅ 100% packet delivery, avg latency ~68ms
**Bidirectional Test:** ✅ Both directions working perfectly

### Extended Latency Test (20 packets)
```
20 packets transmitted, 20 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 42.864/57.427/101.086/15.234 ms
```
**Result:** ✅ 100% reliability, consistent performance

---

## 4. Security Configuration

### Encryption Architecture
```
VPN Packet Format:
[16 bytes: IV][4 bytes: sequence number][32 bytes: HMAC][N bytes: encrypted payload]
```

### Security Features
1. **Encryption:** AES-256-CTR with unique IV per packet
2. **Authentication:** HMAC-SHA256 (prevents tampering)
3. **Replay Protection:** Sequence numbers prevent replay attacks
4. **Key Derivation:**
   - Master key: 64+ characters
   - Encryption key: First 32 bytes (256-bit AES)
   - HMAC key: Next 32 bytes (256-bit HMAC)

### Security Improvements Over Basic VPN
- ✅ Unique IV generation for each packet (prevents CTR mode attacks)
- ✅ HMAC covers IV + header + encrypted payload (integrity protection)
- ✅ Sequence numbers prevent replay attacks
- ✅ Separate keys for encryption and authentication

---

## 5. Performance Metrics

### Latency Statistics
- **Minimum RTT:** 42.864 ms
- **Average RTT:** 57.427 ms
- **Maximum RTT:** 101.086 ms
- **Standard Deviation:** 15.234 ms
- **Packet Loss:** 0.0%

### Packet Overhead Analysis
- **Original IP packet:** Variable (e.g., 84 bytes for ping)
- **VPN overhead:** 52 bytes (16 IV + 4 seq + 32 HMAC)
- **Total encrypted packet:** Original + 52 bytes
- **Overhead percentage:** ~62% for small packets, decreases with larger payloads

### Performance Observations
- Latency is primarily due to Tailscale transport (VPN adds minimal overhead)
- Encryption/decryption is fast (software-based AES)
- Zero packet loss demonstrates reliable UDP transport over Tailscale

---

## 6. Platform-Specific Implementation

### macOS (Darwin)
- **TUN Interface:** Native utun (no third-party drivers needed)
- **Creation Method:** PF_SYSTEM socket with SYSPROTO_CONTROL
- **Configuration:** ifconfig + route commands
- **Packet Format:** 4-byte protocol family header (AF_INET/AF_INET6)
  - Header stripped on read, added on write

### Linux
- **TUN Interface:** /dev/net/tun
- **Creation Method:** ioctl with TUNSETIFF
- **Configuration:** ip addr + ip route commands
- **Packet Format:** Raw IP packets (no header)

### Cross-Platform Compatibility
✅ Transparent packet handling - header differences managed automatically
✅ Same encryption/decryption on both platforms
✅ UDP socket communication platform-agnostic

---

## 7. Network Architecture

```
┌─────────────────────┐                    ┌─────────────────────┐
│   macOS Client      │                    │   Linux Server      │
│  (10.0.0.2)         │                    │  (10.0.0.1)         │
│                     │                    │                     │
│  Application        │                    │  Application        │
│       ↓             │                    │       ↑             │
│  utun8 (VPN)        │                    │  tun0 (VPN)         │
│       ↓             │                    │       ↑             │
│  Encrypt + HMAC     │                    │  Decrypt + Verify   │
│       ↓             │                    │       ↑             │
│  UDP Socket:5555    │    Tailscale       │  UDP Socket:5556    │
│       ↓             │ ←─────────────────→│       ↑             │
│  utun7 (Tailscale)  │   100.113.49.125   │  Tailscale          │
│  100.105.100.121    │                    │                     │
└─────────────────────┘                    └─────────────────────┘
```

---

## 8. Diagnostic Commands Reference

### macOS Client Commands
```bash
# Check VPN interface
ifconfig utun8

# Check routing
netstat -rn | grep 10.0.0

# Test connectivity
ping 10.0.0.1

# Monitor VPN traffic
sudo tcpdump -i utun8 -n

# Monitor encrypted UDP traffic
sudo tcpdump -i any udp port 5555 -n
```

### Linux Server Commands
```bash
# Check VPN interface
ip addr show tun0

# Check routing
ip route | grep 10.0.0

# Test connectivity
ping 10.0.0.2

# Monitor VPN traffic
sudo tcpdump -i tun0 -n

# Monitor encrypted UDP traffic
sudo tcpdump -i any udp port 5556 -n
```

---

## 9. VPN Operation Log Sample

### macOS Client Output
```
[+] Created utun interface: utun8
[+] utun interface configured: utun8
[+] Local: 10.0.0.2, Remote: 10.0.0.1
[+] VPN initialized in client mode
[+] Listening on 0.0.0.0:5555
[+] TUN interface: 10.0.0.2 <-> 10.0.0.1
[+] VPN running... Press Ctrl+C to stop

[→] Sent packet #1, size: 84 bytes
[←] Received packet #1, size: 84 bytes
[→] Sent packet #2, size: 84 bytes
[←] Received packet #2, size: 84 bytes
```

### Linux Server Output
```
[+] TUN interface created: tun0
[+] VPN initialized in server mode
[+] Listening on 0.0.0.0:5556
[+] TUN interface: 10.0.0.1 <-> 10.0.0.2
[+] VPN running... Press Ctrl+C to stop

[←] Received packet #1, size: 84 bytes
[→] Sent packet #1, size: 84 bytes
[←] Received packet #2, size: 84 bytes
[→] Sent packet #2, size: 84 bytes
```

---

## 10. Troubleshooting Notes

### Issues Encountered During Setup
1. **Tunnelblick Dependency (Resolved)**
   - Initial implementation used /dev/tun* which requires Tunnelblick
   - **Solution:** Switched to native macOS utun interface via PF_SYSTEM socket

2. **Asymmetric Connectivity (Resolved)**
   - macOS → Linux failed while Linux → macOS worked
   - **Root Cause:** Typo in remote IP (100.133.49.125 vs 100.113.49.125)
   - **Solution:** Corrected IP address in client command

3. **Socket Binding Issue (Resolved)**
   - Initial attempt to bind to specific Tailscale IP failed
   - **Solution:** Bind to 0.0.0.0 (all interfaces) instead

### Common Issues & Solutions
- **"Cannot assign requested address"**: Use `--local-ip 0.0.0.0`
- **Packets not arriving**: Verify remote IP is correct
- **"Could not open TUN device"**: Ensure sudo/root privileges
- **HMAC verification failed**: Check encryption keys match on both sides

---

## 11. Conclusions

### Successful Implementation ✅
- Cross-platform VPN successfully established between macOS and Linux
- Native OS support (no third-party drivers on macOS)
- Secure encryption with AES-256-CTR + HMAC-SHA256
- Reliable bidirectional communication over Tailscale transport
- Zero packet loss in testing
- Acceptable latency for VPN over internet (~50ms avg)

### Technical Achievements
1. ✅ Cross-platform TUN interface abstraction
2. ✅ Secure packet format with unique IVs
3. ✅ HMAC authentication for integrity
4. ✅ Replay attack protection
5. ✅ Transparent protocol family header handling (macOS utun)

### Performance Characteristics
- **Packet Loss:** 0% (perfect reliability)
- **Latency:** ~50ms average (acceptable for Tailscale transport)
- **Overhead:** 52 bytes per packet (reasonable for security features)
- **Throughput:** Limited by Tailscale, not VPN implementation

---

## 12. Future Enhancements

### Potential Improvements
- [ ] Perfect Forward Secrecy (PFS) with key rotation
- [ ] Diffie-Hellman key exchange instead of pre-shared keys
- [ ] Connection state management with keepalive
- [ ] MTU discovery and path MTU optimization
- [ ] Multi-client support with client routing table
- [ ] Performance optimizations (zero-copy, batch processing)
- [ ] IPv6 support
- [ ] Compression for large payloads

### Security Enhancements
- [ ] Certificate-based authentication
- [ ] Perfect forward secrecy
- [ ] Anti-fingerprinting techniques
- [ ] Traffic obfuscation

---

**End of Diagnostic Report**
