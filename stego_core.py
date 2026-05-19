"""
StegoVault Pro - Unified Core Engine
Handles AES-256-GCM encryption and LSB Steganography.
"""

import os
import io
import struct
import hashlib
import hmac as _hmac
import zipfile
from pathlib import Path
from PIL import Image

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ── Configuration ─────────────────────────────────────────────────────────────
_ITERATIONS = 600_000
_SALT_LEN   = 16
_NONCE_LEN  = 12

_K1 = bytes([0x4e, 0x1a, 0x7c, 0x23, 0x88, 0x5f, 0x3d, 0x92, 0x61, 0xb4, 0x0e, 0x77, 0x96, 0x2a, 0xd5, 0x48, 0x13, 0xf6, 0x84, 0xcc, 0x3b, 0x5e, 0xa7, 0x19, 0xd2, 0x60, 0x4f, 0x8b, 0xe3, 0x27, 0x9c, 0x55])
_K2 = bytes([0x1b, 0x6e, 0x2d, 0x70, 0xf4, 0x0a, 0x53, 0xc8, 0x37, 0xe5, 0x4c, 0x28, 0xca, 0x7f, 0x91, 0x16, 0x4a, 0xbd, 0xd7, 0x83, 0x6c, 0x0e, 0xf2, 0x5a, 0x8e, 0x35, 0x19, 0xc6, 0xb1, 0x72, 0xe0, 0x09])
_SECRET = bytes(a ^ b for a, b in zip(_K1, _K2))

_MAGIC    = hashlib.sha256(_SECRET + b'\x00').digest()[:16]
_HMAC_KEY = hashlib.sha256(_SECRET + b'\x01').digest()

_HEADER_SIZE = 16 + 32 + 4  # Magic + HMAC + Len

# ── Crypto ──────────────────────────────────────────────────────────────────

def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt,
        iterations=_ITERATIONS, backend=default_backend()
    )
    return kdf.derive(password.encode("utf-8"))

def encrypt_payload(password: str, filename: str, data: bytes) -> bytes:
    salt = os.urandom(_SALT_LEN)
    nonce = os.urandom(_NONCE_LEN)
    key = _derive_key(password, salt)
    
    # Format: [fname_len:2B][fname][data]
    fname_bytes = filename.encode("utf-8")
    plaintext = struct.pack("<H", len(fname_bytes)) + fname_bytes + data
    
    aes = AESGCM(key)
    ciphertext = aes.encrypt(nonce, plaintext, None)
    
    # Inner payload: [salt][nonce][ciphertext]
    inner = salt + nonce + ciphertext
    payload_len = struct.pack("<I", len(inner))
    
    # HMAC signed meta: [MAGIC][LEN][INNER]
    mac = _hmac.new(_HMAC_KEY, _MAGIC + payload_len + inner, digestmod="sha256").digest()
    
    return _MAGIC + mac + payload_len + inner

def decrypt_payload(password: str, raw_payload: bytes) -> tuple[str, bytes]:
    if len(raw_payload) < _HEADER_SIZE:
        raise ValueError("Invalid payload: too short.")
    
    magic = raw_payload[:16]
    hmac_val = raw_payload[16:48]
    len_bytes = raw_payload[48:52]
    p_len = struct.unpack("<I", len_bytes)[0]
    inner = raw_payload[52:52+p_len]
    
    if magic != _MAGIC:
        raise ValueError("Not a StegoVault payload.")
    
    expected_mac = _hmac.new(_HMAC_KEY, _MAGIC + len_bytes + inner, digestmod="sha256").digest()
    if not _hmac.compare_digest(hmac_val, expected_mac):
        raise ValueError("Security check failed: HMAC mismatch.")
    
    salt = inner[:_SALT_LEN]
    nonce = inner[_SALT_LEN:_SALT_LEN+_NONCE_LEN]
    ciphertext = inner[_SALT_LEN+_NONCE_LEN:]
    
    key = _derive_key(password, salt)
    aes = AESGCM(key)
    try:
        plaintext = aes.decrypt(nonce, ciphertext, None)
    except:
        raise ValueError("Decryption failed. Wrong password?")
    
    fname_len = struct.unpack("<H", plaintext[:2])[0]
    filename = plaintext[2:2+fname_len].decode("utf-8")
    data = plaintext[2+fname_len:]
    return filename, data

# ── Stego ──────────────────────────────────────────────────────────────────

def get_capacity(image_path: str) -> int:
    with Image.open(image_path) as img:
        return (img.size[0] * img.size[1] * 3) // 8

def encode_to_image(carrier_path: str, payload: bytes, output_path: str):
    img = Image.open(carrier_path).convert("RGB")
    pixels = list(img.getdata())
    
    if len(payload) > (len(pixels) * 3) // 8:
        raise ValueError(f"Image too small. Needs {(len(payload)*8)//3} pixels.")
    
    # Flatten pixels to R,G,B,R,G,B...
    flat = []
    for p in pixels: flat.extend(p)
    
    # Modify LSBs
    for i, byte in enumerate(payload):
        for bit in range(8):
            idx = i * 8 + bit
            val = (byte >> (7 - bit)) & 1
            flat[idx] = (flat[idx] & ~1) | val
            
    # Reconstruct
    new_pixels = []
    for i in range(0, len(flat), 3):
        new_pixels.append(tuple(flat[i:i+3]))
        
    out = Image.new("RGB", img.size)
    out.putdata(new_pixels)
    out.save(output_path, "PNG")

def decode_from_image(image_path: str) -> bytes:
    img = Image.open(image_path).convert("RGB")
    pixels = list(img.getdata())
    
    flat = []
    for p in pixels: flat.extend(p)
    
    # Read Header first to find length
    def read_bytes(offset_bytes, count):
        res = bytearray()
        for i in range(count):
            byte = 0
            base = (offset_bytes + i) * 8
            for bit in range(8):
                byte = (byte << 1) | (flat[base + bit] & 1)
            res.append(byte)
        return bytes(res)
    
    magic = read_bytes(0, 16)
    if magic != _MAGIC:
        raise ValueError("StegoVault signature not found.")
    
    len_bytes = read_bytes(48, 4)
    p_len = struct.unpack("<I", len_bytes)[0]
    
    full_payload = read_bytes(0, _HEADER_SIZE + p_len)
    return full_payload

# ── Utils ──────────────────────────────────────────────────────────────────

def create_payload_bundle(text_content: str, file_list: list[str]) -> tuple[str, bytes]:
    """Combines text and multiple files into a single ZIP bundle."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        if text_content.strip():
            zf.writestr("NOTE.txt", text_content.strip())
        for f in file_list:
            if os.path.exists(f):
                zf.write(f, Path(f).name)
    
    # We return the name 'bundle.zip' as the virtual filename for encryption
    return "bundle.zip", buf.getvalue()

def zip_files(file_list: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in file_list:
            if os.path.exists(f):
                zf.write(f, Path(f).name)
    return buf.getvalue()
