import struct
from zipfile import ZipFile

def find_eocd(data):
    # End of Central Directory signature: 0x06054b50
    return data.rfind(b'\x50\x4b\x05\x06')

def read_central_dir_offset(data, eocd_pos):
    # Central directory offset is at EOCD+16 (4 bytes)
    return struct.unpack('<I', data[eocd_pos+16:eocd_pos+20])[0]

def crc_faker(mod_apk, ori_apk, out_apk):
    # 1. Get original CRCs from pristine APK
    with ZipFile(ori_apk, 'r') as zf:
        original_crcs = {info.filename: info.CRC for info in zf.infolist()}

    # 2. Load modified APK into memory
    with open(mod_apk, 'rb') as f:
        data = bytearray(f.read())

    # 3. Patch LOCAL FILE HEADERS
    with ZipFile(mod_apk, 'r') as zf:
        for info in zf.infolist():
            if info.filename not in original_crcs:
                continue

            # Local header CRC position: header_offset + 14
            crc_pos = info.header_offset + 14
            if crc_pos + 4 > len(data):
                continue  # Skip invalid entries

            # Write original CRC (little-endian)
            data[crc_pos:crc_pos+4] = struct.pack(
                '<I', 
                original_crcs[info.filename]
            )

    # 4. Patch CENTRAL DIRECTORY ENTRIES
    eocd_pos = find_eocd(data)
    if eocd_pos == -1:
        raise ValueError("Invalid ZIP/EOCD marker not found")

    central_dir_start = read_central_dir_offset(data, eocd_pos)
    pos = central_dir_start

    while pos < len(data) - 4:
        # Central directory entry signature: 0x02014b50
        if data[pos:pos+4] != b'\x50\x4b\x01\x02':
            break

        # Filename length (2 bytes at offset 28)
        name_len = struct.unpack('<H', data[pos+28:pos+30])[0]
        # Extra field length (2 bytes at offset 30)
        extra_len = struct.unpack('<H', data[pos+30:pos+32])[0]
        # File comment length (2 bytes at offset 32)
        comment_len = struct.unpack('<H', data[pos+32:pos+34])[0]

        # Extract filename
        name_start = pos + 46
        name_end = name_start + name_len
        filename = data[name_start:name_end].decode('utf-8')

        # Patch CRC if file exists in original
        if filename in original_crcs:
            # CRC position: pos + 16
            data[pos+16:pos+20] = struct.pack(
                '<I', 
                original_crcs[filename]
            )

        # Move to next entry
        entry_size = 46 + name_len + extra_len + comment_len
        pos += entry_size

    # 5. Write patched APK
    with open(out_apk, 'wb') as f:
        f.write(data)

    print(f"CRCs faked in {out_apk}. Now re-sign the APK!")
