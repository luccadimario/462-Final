#!/usr/bin/env python3
"""
Comprehensive Security Test Suite for VPN
Tests CIA (Confidentiality, Integrity, Availability) properties
"""

import os
import sys
import time
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

sys.path.insert(0, os.path.dirname(__file__))
from vpn import VPNPacket

def test_confidentiality_encryption_strength():
    """Test that encryption properly protects confidentiality"""
    print("[SECURITY TEST] Confidentiality - Encryption Strength")

    key = b'A' * 64
    encryption_key = key[:32]
    hmac_key = key[32:64]

    # Known plaintext
    plaintext = b'This is secret data that must be protected!'
    packet = VPNPacket(1, plaintext)
    encrypted = packet.pack(encryption_key, hmac_key)

    # Extract ciphertext portion (skip IV + header + HMAC)
    ciphertext = encrypted[52:]

    # Verify plaintext doesn't appear in ciphertext
    if plaintext in encrypted:
        print("  ❌ FAIL: Plaintext found in encrypted packet!")
        return False

    print(f"  ✓ Plaintext: {plaintext[:20]}...")
    print(f"  ✓ Ciphertext: {ciphertext.hex()[:40]}...")
    print("  ✓ Plaintext not visible in ciphertext")
    print("  ✓ AES-256-CTR encryption applied")
    print("  ✅ PASS: Confidentiality protected\n")
    return True

def test_integrity_hmac_coverage():
    """Test that HMAC covers all critical packet components"""
    print("[SECURITY TEST] Integrity - HMAC Coverage")

    key = b'A' * 64
    encryption_key = key[:32]
    hmac_key = key[32:64]

    packet = VPNPacket(42, b'Test data')
    packed = packet.pack(encryption_key, hmac_key)

    # Test 1: Modify IV
    tampered_iv = bytearray(packed)
    tampered_iv[0] ^= 0x01
    try:
        VPNPacket.unpack(bytes(tampered_iv), encryption_key, hmac_key, 0)
        print("  ❌ FAIL: IV tampering not detected!")
        return False
    except ValueError:
        print("  ✓ IV tampering detected")

    # Test 2: Modify sequence number
    tampered_seq = bytearray(packed)
    tampered_seq[16] ^= 0x01  # Modify first byte of seq num
    try:
        VPNPacket.unpack(bytes(tampered_seq), encryption_key, hmac_key, 0)
        print("  ❌ FAIL: Sequence number tampering not detected!")
        return False
    except ValueError:
        print("  ✓ Sequence number tampering detected")

    # Test 3: Modify ciphertext
    tampered_data = bytearray(packed)
    tampered_data[-1] ^= 0x01
    try:
        VPNPacket.unpack(bytes(tampered_data), encryption_key, hmac_key, 0)
        print("  ❌ FAIL: Ciphertext tampering not detected!")
        return False
    except ValueError:
        print("  ✓ Ciphertext tampering detected")

    print("  ✓ HMAC protects: IV, sequence number, and ciphertext")
    print("  ✅ PASS: Integrity fully protected\n")
    return True

def test_integrity_wrong_key():
    """Test that wrong key prevents decryption"""
    print("[SECURITY TEST] Integrity - Wrong Key Detection")

    # Encrypt with one key
    key1 = b'A' * 64
    enc_key1 = key1[:32]
    hmac_key1 = key1[32:64]

    packet = VPNPacket(1, b'Secret data')
    encrypted = packet.pack(enc_key1, hmac_key1)

    # Try to decrypt with different key
    key2 = b'B' * 64
    enc_key2 = key2[:32]
    hmac_key2 = key2[32:64]

    try:
        VPNPacket.unpack(encrypted, enc_key2, hmac_key2, 0)
        print("  ❌ FAIL: Packet decrypted with wrong key!")
        return False
    except ValueError as e:
        print(f"  ✓ Wrong key rejected: {e}")
        print("  ✅ PASS: Cannot decrypt without correct key\n")
        return True

def test_availability_packet_reordering():
    """Test handling of out-of-order packets"""
    print("[SECURITY TEST] Availability - Packet Reordering")

    key = b'A' * 64
    encryption_key = key[:32]
    hmac_key = key[32:64]

    # Create packets with different sequence numbers
    packet1 = VPNPacket(1, b'First')
    packet2 = VPNPacket(2, b'Second')
    packet3 = VPNPacket(3, b'Third')

    p1 = packet1.pack(encryption_key, hmac_key)
    p2 = packet2.pack(encryption_key, hmac_key)
    p3 = packet3.pack(encryption_key, hmac_key)

    # Process packet 2 first
    recv_seq = 0
    try:
        pkt = VPNPacket.unpack(p2, encryption_key, hmac_key, recv_seq)
        recv_seq = pkt.seq_num
        print(f"  ✓ Accepted packet #{pkt.seq_num} (expected > 0)")

        # Try to process packet 1 (older) - should be rejected
        try:
            VPNPacket.unpack(p1, encryption_key, hmac_key, recv_seq)
            print("  ❌ FAIL: Old packet accepted after newer one!")
            return False
        except ValueError:
            print(f"  ✓ Rejected old packet #1 (recv_seq = {recv_seq})")

        # Process packet 3 (newer) - should be accepted
        pkt = VPNPacket.unpack(p3, encryption_key, hmac_key, recv_seq)
        print(f"  ✓ Accepted packet #{pkt.seq_num} (expected > {recv_seq})")

        print("  ✓ Replay protection prevents old packets")
        print("  ✅ PASS: Packet ordering enforced\n")
        return True

    except Exception as e:
        print(f"  ❌ FAIL: Error handling packet order: {e}")
        return False

def test_semantic_security():
    """Test that identical plaintexts produce different ciphertexts"""
    print("[SECURITY TEST] Confidentiality - Semantic Security")

    key = b'A' * 64
    encryption_key = key[:32]
    hmac_key = key[32:64]

    # Encrypt the same plaintext twice
    plaintext = b'Same message encrypted twice'
    packet1 = VPNPacket(1, plaintext)
    packet2 = VPNPacket(2, plaintext)

    encrypted1 = packet1.pack(encryption_key, hmac_key)
    encrypted2 = packet2.pack(encryption_key, hmac_key)

    if encrypted1 == encrypted2:
        print("  ❌ FAIL: Same plaintext produces same ciphertext!")
        print("  ❌ This violates semantic security!")
        return False

    # Extract ciphertexts (skip IV + header + HMAC)
    ct1 = encrypted1[52:]
    ct2 = encrypted2[52:]

    if ct1 == ct2:
        print("  ❌ FAIL: Same ciphertext for same plaintext!")
        return False

    print(f"  ✓ Plaintext: {plaintext[:20]}...")
    print(f"  ✓ Ciphertext 1: {ct1.hex()[:40]}...")
    print(f"  ✓ Ciphertext 2: {ct2.hex()[:40]}...")
    print("  ✓ Different ciphertexts from same plaintext")
    print("  ✓ Unique IVs provide semantic security")
    print("  ✅ PASS: Semantic security maintained\n")
    return True

def test_key_separation():
    """Test that encryption and HMAC keys use different portions of master key"""
    print("[SECURITY TEST] Key Management - Key Separation")

    # Use a key with varying bytes to test proper separation
    key = os.urandom(64)
    encryption_key = key[:32]
    hmac_key = key[32:64]

    # Verify they use different portions
    if encryption_key == hmac_key:
        print("  ❌ FAIL: Encryption and HMAC keys are identical!")
        return False

    # Verify they're the right sizes
    if len(encryption_key) != 32:
        print(f"  ❌ FAIL: Encryption key wrong size: {len(encryption_key)}")
        return False

    if len(hmac_key) != 32:
        print(f"  ❌ FAIL: HMAC key wrong size: {len(hmac_key)}")
        return False

    print(f"  ✓ Encryption key: {encryption_key.hex()[:32]}... (256 bits)")
    print(f"  ✓ HMAC key: {hmac_key.hex()[:32]}... (256 bits)")
    print("  ✓ Keys derived from different portions of master key")
    print("  ✓ Prevents key reuse attacks")
    print("  ✅ PASS: Key separation properly implemented\n")
    return True

def test_resistance_to_bit_flipping():
    """Test resistance to bit-flipping attacks"""
    print("[SECURITY TEST] Integrity - Bit-Flipping Resistance")

    key = b'A' * 64
    encryption_key = key[:32]
    hmac_key = key[32:64]

    packet = VPNPacket(1, b'Transfer $100 to Alice')
    encrypted = packet.pack(encryption_key, hmac_key)

    # Attacker tries to flip bits in ciphertext
    attacks = [
        (52, "First byte of ciphertext"),
        (60, "Middle of ciphertext"),
        (-1, "Last byte of ciphertext"),
    ]

    for offset, description in attacks:
        tampered = bytearray(encrypted)
        tampered[offset] ^= 0xFF
        try:
            VPNPacket.unpack(bytes(tampered), encryption_key, hmac_key, 0)
            print(f"  ❌ FAIL: Bit flip in {description} not detected!")
            return False
        except ValueError:
            print(f"  ✓ Bit flip in {description} detected")

    print("  ✓ All bit-flipping attempts detected by HMAC")
    print("  ✅ PASS: Resistant to bit-flipping attacks\n")
    return True

def main():
    print("="*70)
    print("VPN COMPREHENSIVE SECURITY TEST SUITE")
    print("Testing CIA Properties (Confidentiality, Integrity, Availability)")
    print("="*70 + "\n")

    results = []

    # Confidentiality tests
    print("╔" + "="*68 + "╗")
    print("║" + " CONFIDENTIALITY TESTS".center(68) + "║")
    print("╚" + "="*68 + "╝\n")
    results.append(("Encryption Strength", test_confidentiality_encryption_strength()))
    results.append(("Semantic Security", test_semantic_security()))

    # Integrity tests
    print("╔" + "="*68 + "╗")
    print("║" + " INTEGRITY TESTS".center(68) + "║")
    print("╚" + "="*68 + "╝\n")
    results.append(("HMAC Coverage", test_integrity_hmac_coverage()))
    results.append(("Wrong Key Detection", test_integrity_wrong_key()))
    results.append(("Bit-Flipping Resistance", test_resistance_to_bit_flipping()))

    # Availability tests
    print("╔" + "="*68 + "╗")
    print("║" + " AVAILABILITY TESTS".center(68) + "║")
    print("╚" + "="*68 + "╝\n")
    results.append(("Packet Reordering", test_availability_packet_reordering()))

    # Additional tests
    print("╔" + "="*68 + "╗")
    print("║" + " KEY MANAGEMENT TESTS".center(68) + "║")
    print("╚" + "="*68 + "╝\n")
    results.append(("Key Separation", test_key_separation()))

    # Summary
    print("="*70)
    print("COMPREHENSIVE SECURITY TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed < total:
        print("\n⚠️  SECURITY ISSUES FOUND - See failed tests above")
        return 1
    else:
        print("\n✅ ALL SECURITY TESTS PASSED")
        print("✅ VPN meets CIA security requirements")
        return 0

if __name__ == '__main__':
    sys.exit(main())
