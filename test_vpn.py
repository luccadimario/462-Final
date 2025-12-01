#!/usr/bin/env python3
"""
VPN Test Suite
Tests for vpn.py implementation
"""

import os
import sys
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# Import VPN components
sys.path.insert(0, os.path.dirname(__file__))
from vpn import VPNPacket

def test_packet_encryption_decryption():
    """Test basic packet encryption and decryption"""
    print("[TEST] Packet Encryption/Decryption")

    # Setup keys
    key = b'A' * 64
    encryption_key = key[:32]
    hmac_key = key[32:64]

    # Create and pack a packet
    seq_num = 1
    payload = b'Hello, this is a test packet!'
    packet = VPNPacket(seq_num, payload)

    packed = packet.pack(encryption_key, hmac_key)
    print(f"  ✓ Original payload: {payload}")
    print(f"  ✓ Packed size: {len(packed)} bytes (includes unique IV)")

    # Unpack the packet (IV is extracted automatically)
    unpacked = VPNPacket.unpack(packed, encryption_key, hmac_key, 0)
    print(f"  ✓ Decrypted payload: {unpacked.payload}")
    print(f"  ✓ Sequence number: {unpacked.seq_num}")

    # Verify
    assert unpacked.payload == payload, "Payload mismatch!"
    assert unpacked.seq_num == seq_num, "Sequence number mismatch!"
    print("  ✅ PASS: Encryption/Decryption works\n")
    return True

def test_hmac_tampering():
    """Test HMAC detects tampering"""
    print("[TEST] HMAC Tampering Detection")

    # Setup keys
    key = b'A' * 64
    encryption_key = key[:32]
    hmac_key = key[32:64]

    # Create packet
    packet = VPNPacket(1, b'Test data')
    packed = packet.pack(encryption_key, hmac_key)

    # Tamper with the data
    tampered = bytearray(packed)
    tampered[-1] ^= 0xFF  # Flip last byte

    # Try to unpack tampered packet
    try:
        VPNPacket.unpack(bytes(tampered), encryption_key, hmac_key, 0)
        print("  ❌ FAIL: Tampered packet was accepted!")
        return False
    except ValueError as e:
        print(f"  ✓ Tampering detected: {e}")
        print("  ✅ PASS: HMAC detects tampering\n")
        return True

def test_replay_protection():
    """Test replay attack protection"""
    print("[TEST] Replay Attack Protection")

    # Setup
    key = b'A' * 64
    encryption_key = key[:32]
    hmac_key = key[32:64]

    # Create packet with seq 5
    packet = VPNPacket(5, b'Test')
    packed = packet.pack(encryption_key, hmac_key)

    # Try to accept packet with seq 5 when we expect > 10
    try:
        VPNPacket.unpack(packed, encryption_key, hmac_key, 10)
        print("  ❌ FAIL: Replayed packet was accepted!")
        return False
    except ValueError as e:
        print(f"  ✓ Replay detected: {e}")
        print("  ✅ PASS: Replay protection works\n")
        return True

def test_iv_reuse_vulnerability():
    """Verify that unique IVs are used for each packet"""
    print("[TEST] Unique IV Per Packet Check")

    key = b'A' * 64
    encryption_key = key[:32]
    hmac_key = key[32:64]

    msg1 = b'Secret message A' + b'\x00' * 16  # Pad to 32 bytes
    msg2 = b'Secret message B' + b'\x00' * 16

    packet1 = VPNPacket(1, msg1)
    packet2 = VPNPacket(2, msg2)

    # Each pack() should generate a unique IV
    packed1 = packet1.pack(encryption_key, hmac_key)
    packed2 = packet2.pack(encryption_key, hmac_key)

    # Extract IVs from packets (first 16 bytes)
    iv1 = packed1[:16]
    iv2 = packed2[:16]

    print(f"  ✓ Packet 1 IV: {iv1.hex()[:32]}...")
    print(f"  ✓ Packet 2 IV: {iv2.hex()[:32]}...")

    # Verify IVs are different
    if iv1 == iv2:
        print("  ❌ CRITICAL: Same IV used for both packets!")
        print("  ❌ This violates CTR mode security!")
        return False

    print("  ✓ IVs are unique - CTR mode is secure")

    # Verify that ciphertext XOR does NOT reveal plaintext XOR
    # Extract encrypted portions (skip IV + header + HMAC = 16+4+32 = 52 bytes)
    enc1 = packed1[52:52+32]
    enc2 = packed2[52:52+32]

    xor_result = bytes(a ^ b for a, b in zip(enc1, enc2))
    expected = bytes(a ^ b for a, b in zip(msg1, msg2))

    if xor_result[:16] == expected[:16]:
        print("  ❌ FAIL: Ciphertext XOR still reveals plaintext XOR")
        return False

    print("  ✓ Semantic security maintained")
    print("  ✅ PASS: Unique IV per packet - VULNERABILITY FIXED!\n")
    return True

def main():
    print("="*60)
    print("VPN Security Test Suite")
    print("="*60 + "\n")

    results = []

    # Run tests
    results.append(("Encryption/Decryption", test_packet_encryption_decryption()))
    results.append(("HMAC Tampering Detection", test_hmac_tampering()))
    results.append(("Replay Protection", test_replay_protection()))
    results.append(("IV Reuse Check", test_iv_reuse_vulnerability()))

    # Summary
    print("="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed < total:
        print("\n⚠️  CRITICAL ISSUES FOUND - See failed tests above")
        return 1
    else:
        print("\n✅ All tests passed")
        return 0

if __name__ == '__main__':
    sys.exit(main())
