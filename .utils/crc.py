import sys
import struct
import time


def read_all_headers(zip_bytes):
    i = 0
    entries = []
    while i < len(zip_bytes):
        sig = zip_bytes[i : i + 4]
        if sig == b"\x50\x4b\x03\x04":  # Local File Header
            name_len = struct.unpack("<H", zip_bytes[i + 26 : i + 28])[0]
            extra_len = struct.unpack("<H", zip_bytes[i + 28 : i + 30])[0]
            name = zip_bytes[i + 30 : i + 30 + name_len].decode(
                "utf-8", errors="ignore"
            )
            crc_offset = i + 14
            entries.append(
                {"type": "lfh", "offset": i, "crc_offset": crc_offset, "filename": name}
            )
            i += 30 + name_len + extra_len
        elif sig == b"\x50\x4b\x01\x02":  # Central Directory Header
            name_len = struct.unpack("<H", zip_bytes[i + 28 : i + 30])[0]
            extra_len = struct.unpack("<H", zip_bytes[i + 30 : i + 32])[0]
            comment_len = struct.unpack("<H", zip_bytes[i + 32 : i + 34])[0]
            name = zip_bytes[i + 46 : i + 46 + name_len].decode(
                "utf-8", errors="ignore"
            )
            crc_offset = i + 16
            entries.append(
                {"type": "cdh", "offset": i, "crc_offset": crc_offset, "filename": name}
            )
            i += 46 + name_len + extra_len + comment_len
        elif sig == b"\x50\x4b\x05\x06":  # EOCD
            break
        else:
            i += 1
    return entries


def fake_crc(mod_path, ori_path, out_path):
    start_time = time.time()
    print(f"[+] Reading input files...")

    with open(mod_path, "rb") as f:
        mod_data = bytearray(f.read())
    with open(ori_path, "rb") as f:
        ori_data = bytearray(f.read())

    print(f"[+] Scanning headers...")

    t1 = time.time()
    mod_headers = read_all_headers(mod_data)
    ori_headers = read_all_headers(ori_data)
    print(
        f"[i] Parsed {len(mod_headers)} mod headers and {len(ori_headers)} ori headers in {time.time() - t1:.2f}s"
    )

    ori_crc_map = {}
    for h in ori_headers:
        if h["type"] in ("lfh", "cdh"):
            ori_crc_map.setdefault(h["filename"], {})[h["type"]] = ori_data[
                h["crc_offset"] : h["crc_offset"] + 4
            ]

    patched_count = 0
    skipped = 0

    print(f"[+] Patching CRCs...")

    for h in mod_headers:
        filename = h["filename"]
        if filename in ori_crc_map and h["type"] in ori_crc_map[filename]:
            crc_bytes = ori_crc_map[filename][h["type"]]
            mod_data[h["crc_offset"] : h["crc_offset"] + 4] = crc_bytes
            print(f"  [✓] Patched {h['type'].upper()} for {filename}")
            patched_count += 1
        else:
            print(
                f"  [×] Skipped {h['type'].upper()} for {filename} (not found in original)"
            )
            skipped += 1

    with open(out_path, "wb") as f:
        f.write(mod_data)

    print(f"\n[✓] Done. Patched: {patched_count}, Skipped: {skipped}")
    print(f"[⏱️] Total time: {time.time() - start_time:.2f}s")
    print(f"[→] Output written to: {out_path}")


# CLI usage
if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python fake_crc.py mod.apk ori.apk mod_crc_faked.apk")
        sys.exit(1)
    fake_crc(sys.argv[1], sys.argv[2], sys.argv[3])
