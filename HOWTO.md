# VPN Setup and Usage Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Detailed Configuration](#detailed-configuration)
5. [Testing the VPN](#testing-the-vpn)
6. [Running Tests](#running-tests)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Usage](#advanced-usage)

---

## Prerequisites

### System Requirements
- **Operating System**: Linux (Ubuntu 20.04+ recommended)
- **Python**: Python 3.7 or later
- **Privileges**: Root/sudo access (required for TUN interface)
- **Network**: Two hosts with network connectivity

### Software Dependencies
- Python 3.7+
- `cryptography` library (for AES and HMAC)
- `iproute2` package (for `ip` command)
- TUN/TAP support in kernel

### Check Prerequisites

```bash
# Check Python version
python3 --version

# Check if TUN is available
ls -l /dev/net/tun

# Check if ip command is available
which ip
```

---

## Installation

### Step 1: Clone or Copy Files

```bash
cd /path/to/project
# Files needed:
# - vpn.py
# - test_vpn.py
# - test_security.py
# - test_performance.py
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
# Install cryptography library
pip install cryptography
```

### Step 4: Verify Installation

```bash
# Test import
python3 -c "from cryptography.hazmat.primitives.ciphers import Cipher; print('OK')"

# Check VPN script
python3 vpn.py --help
```

---

## Quick Start

This section provides a minimal working example to get the VPN running between two hosts.

### Scenario: Connect Host A and Host B

**Network Setup:**
- Host A: 192.168.1.10 (public IP)
- Host B: 192.168.1.20 (public IP)
- VPN Network: 10.0.0.0/24
- Host A VPN IP: 10.0.0.1
- Host B VPN IP: 10.0.0.2

### On Host A (Server)

```bash
# Activate virtual environment
source venv/bin/activate

# Generate a shared secret key (64+ characters)
# IMPORTANT: Use the same key on both hosts!
KEY="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@"

# Run VPN server
sudo venv/bin/python3 vpn.py server \
  --local-ip 192.168.1.10 \
  --remote-ip 192.168.1.20 \
  --local-port 5000 \
  --remote-port 5000 \
  --key "$KEY" \
  --tun-local 10.0.0.1 \
  --tun-remote 10.0.0.2
```

### On Host B (Client)

```bash
# Activate virtual environment
source venv/bin/activate

# Use the SAME key as Host A!
KEY="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@"

# Run VPN client
sudo venv/bin/python3 vpn.py client \
  --local-ip 192.168.1.20 \
  --remote-ip 192.168.1.10 \
  --local-port 5000 \
  --remote-port 5000 \
  --key "$KEY" \
  --tun-local 10.0.0.2 \
  --tun-remote 10.0.0.1
```

### Test the Connection

On Host A:
```bash
# Ping Host B through VPN
ping 10.0.0.2
```

On Host B:
```bash
# Ping Host A through VPN
ping 10.0.0.1
```

You should see encrypted packets being sent/received in the VPN output!

---

## Detailed Configuration

### Command-Line Arguments

```
python3 vpn.py {server|client} [OPTIONS]

Required Arguments:
  mode                   Run as 'server' or 'client'
  --local-ip IP          Local IP address to bind UDP socket
  --remote-ip IP         Remote peer IP address
  --local-port PORT      Local UDP port (e.g., 5000)
  --remote-port PORT     Remote UDP port (must match peer)
  --key KEY              Shared secret key (minimum 64 characters)
  --tun-local IP         Local TUN interface IP (e.g., 10.0.0.1)
  --tun-remote IP        Remote TUN interface IP (e.g., 10.0.0.2)
```

### Key Generation

The VPN requires a **64-character minimum** shared key for security.

**Generate a secure key:**

```bash
# Method 1: Using Python
python3 -c "import os; print(os.urandom(64).hex())"

# Method 2: Using OpenSSL
openssl rand -hex 32

# Method 3: Using /dev/urandom
head -c 64 /dev/urandom | base64
```

**Example output:**
```
a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6A7B8C9D0E1F2G3
```

### Firewall Configuration

Ensure UDP port is open on both hosts:

```bash
# Ubuntu/Debian with ufw
sudo ufw allow 5000/udp

# CentOS/RHEL with firewalld
sudo firewall-cmd --permanent --add-port=5000/udp
sudo firewall-cmd --reload

# Using iptables directly
sudo iptables -A INPUT -p udp --dport 5000 -j ACCEPT
```

---

## Testing the VPN

### Basic Connectivity Test

```bash
# From either host, ping the other through the VPN
ping -c 5 10.0.0.2

# Expected output:
# 64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=2.1 ms
# ...
```

### Verify Encryption

```bash
# On Host A, capture traffic on the physical interface
sudo tcpdump -i eth0 -n udp port 5000 -X

# On Host B, send ping through VPN
ping -c 1 10.0.0.1

# In tcpdump output, you should see encrypted data (random bytes)
# NOT the plaintext "ping" or ICMP packet
```

### Transfer Data Through VPN

```bash
# On Host A, start a simple HTTP server
python3 -m http.server 8000 --bind 10.0.0.1

# On Host B, download a file through the VPN
curl http://10.0.0.1:8000/
```

### Monitor VPN Traffic

```bash
# On TUN interface (see decrypted traffic)
sudo tcpdump -i tun0 -n

# On physical interface (see encrypted traffic)
sudo tcpdump -i eth0 -n udp port 5000
```

---

## Running Tests

### Basic Unit Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run basic VPN packet tests
python3 test_vpn.py

# Expected: All 4 tests pass
# - Encryption/Decryption
# - HMAC Tampering Detection
# - Replay Protection
# - Unique IV Per Packet
```

### Comprehensive Security Tests

```bash
# Run CIA (Confidentiality, Integrity, Availability) tests
python3 test_security.py

# Expected: All 7 tests pass
# - Encryption Strength
# - Semantic Security
# - HMAC Coverage
# - Wrong Key Detection
# - Bit-Flipping Resistance
# - Packet Reordering
# - Key Separation
```

### Performance Benchmarks

```bash
# Run performance tests
python3 test_performance.py

# Outputs:
# - Encryption/Decryption throughput
# - Packet overhead analysis
# - Latency statistics
# - Round-trip time
```

---

## Troubleshooting

### Issue: "Permission denied" when running VPN

**Cause**: TUN interface requires root privileges

**Solution**:
```bash
# Run with sudo and specify full path to Python in venv
sudo venv/bin/python3 vpn.py ...

# OR: Give Python CAP_NET_ADMIN capability (less secure)
sudo setcap cap_net_admin+ep venv/bin/python3
```

### Issue: "No such file or directory: /dev/net/tun"

**Cause**: TUN/TAP module not loaded

**Solution**:
```bash
# Load TUN module
sudo modprobe tun

# Verify
ls -l /dev/net/tun

# Make persistent across reboots
echo "tun" | sudo tee -a /etc/modules
```

### Issue: "Key must be at least 64 characters"

**Cause**: Provided key is too short

**Solution**:
```bash
# Generate a proper 64+ character key
KEY=$(python3 -c "import os; print(os.urandom(64).hex())")
echo "Use this key on both hosts: $KEY"
```

### Issue: Packets not reaching the other host

**Checklist**:

1. **Verify both hosts are running VPN**
   ```bash
   # Check if VPN process is running
   ps aux | grep vpn.py
   ```

2. **Check TUN interface is up**
   ```bash
   ip addr show tun0
   # Should show UP and configured IP
   ```

3. **Verify UDP connectivity**
   ```bash
   # On Host B, test if Host A:5000 is reachable
   nc -u -v 192.168.1.10 5000
   ```

4. **Check firewall rules**
   ```bash
   sudo iptables -L -n | grep 5000
   ```

5. **Verify same key on both hosts**
   ```bash
   # Keys must be EXACTLY the same
   ```

### Issue: "HMAC verification failed"

**Cause**: Different keys on client and server, or corrupted packet

**Solution**:
```bash
# Verify you're using the EXACT same key on both hosts
# Even one character difference will cause HMAC failure
```

### Issue: High CPU usage

**Cause**: Encryption/decryption is CPU-intensive

**Solutions**:
- Use hardware with AES-NI support
- Reduce traffic volume
- Profile with `top` or `htop` to confirm it's the VPN process

---

## Advanced Usage

### Running VPN as a Background Service

Create a systemd service file:

```bash
# Create /etc/systemd/system/vpn.service
sudo nano /etc/systemd/system/vpn.service
```

Content:
```ini
[Unit]
Description=Custom VPN Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/vpn
ExecStart=/path/to/venv/bin/python3 /path/to/vpn.py server \
  --local-ip 192.168.1.10 \
  --remote-ip 192.168.1.20 \
  --local-port 5000 \
  --remote-port 5000 \
  --key "YOUR_64_CHAR_KEY_HERE" \
  --tun-local 10.0.0.1 \
  --tun-remote 10.0.0.2
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable vpn
sudo systemctl start vpn
sudo systemctl status vpn
```

### Custom Routing

Route specific subnets through the VPN:

```bash
# Route 192.168.100.0/24 through VPN
sudo ip route add 192.168.100.0/24 via 10.0.0.2 dev tun0

# Make Host B the gateway for that subnet
# On Host B, enable IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -t nat -A POSTROUTING -s 10.0.0.0/24 -j MASQUERADE
```

### Using VPN with SSH

```bash
# SSH through the VPN tunnel
ssh user@10.0.0.2

# This traffic is now double-encrypted:
# 1. SSH encryption
# 2. VPN encryption (redundant but works)
```

### NAT Traversal

If hosts are behind NAT, you may need to:

1. **Port forward** UDP 5000 on both routers
2. **Use public IPs** in --local-ip and --remote-ip
3. **Keep-alive packets** (not implemented, would need modification)

---

## Example: Three-Host Setup

Connect three hosts in a star topology:

**Topology**: Host A ←→ Host B (hub) ←→ Host C

**Host B runs two VPN instances**:

Instance 1 (to Host A):
```bash
sudo venv/bin/python3 vpn.py server \
  --local-ip 192.168.1.20 \
  --remote-ip 192.168.1.10 \
  --local-port 5000 \
  --remote-port 5000 \
  --key "$KEY_AB" \
  --tun-local 10.0.1.1 \
  --tun-remote 10.0.1.2
```

Instance 2 (to Host C):
```bash
sudo venv/bin/python3 vpn.py server \
  --local-ip 192.168.1.20 \
  --remote-ip 192.168.1.30 \
  --local-port 5001 \
  --remote-port 5001 \
  --key "$KEY_BC" \
  --tun-local 10.0.2.1 \
  --tun-remote 10.0.2.2
```

Then enable routing on Host B to forward between tun0 and tun1.

---

## Performance Tuning

### Optimize for Throughput

```bash
# Increase UDP buffer sizes
sudo sysctl -w net.core.rmem_max=26214400
sudo sysctl -w net.core.wmem_max=26214400
sudo sysctl -w net.core.rmem_default=26214400
sudo sysctl -w net.core.wmem_default=26214400
```

### Optimize for Latency

```bash
# Reduce interrupt coalescing
sudo ethtool -C eth0 rx-usecs 0 tx-usecs 0

# Use real-time scheduling (advanced, requires privileges)
sudo chrt -f 99 venv/bin/python3 vpn.py ...
```

---

## Security Best Practices

1. **Key Management**:
   - Never share keys over unencrypted channels
   - Use a secure key exchange mechanism out-of-band
   - Rotate keys periodically

2. **Access Control**:
   - Restrict VPN script to root only
   - Use firewall rules to limit VPN access
   - Monitor VPN logs for suspicious activity

3. **Network Isolation**:
   - Use VPN on isolated network segment
   - Don't expose VPN port to public internet without firewall

4. **Monitoring**:
   - Log all VPN connections
   - Monitor for unusual traffic patterns
   - Set up alerts for failed authentication attempts

---

## Additional Resources

- **Architecture Documentation**: See `ARCHITECTURE.md` for detailed system design
- **Test Results**: See `TEST_RESULTS.md` for comprehensive testing analysis
- **Source Code**: See `vpn.py` with inline comments
- **Performance Data**: Run `test_performance.py` for benchmarks

---

## Getting Help

If you encounter issues:

1. Check this guide's Troubleshooting section
2. Review error messages carefully
3. Verify all prerequisites are met
4. Test with simplified configuration first
5. Check system logs: `sudo journalctl -xe`
