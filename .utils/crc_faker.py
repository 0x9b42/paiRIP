import zipfile
import os
import logging
from pathlib import Path
from typing import List, Dict
from struct import pack, unpack

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def crc_faker(org_file: str, mod_file: str, output_file: str) -> None:
    """
    Patch CRC-32 values of .dex files in mod_file to match those in org_file.

    Args:
        org_file (str): Path to the original APK.
        mod_file (str): Path to the modified APK.
        output_file (str): Path to save the patched APK.

    Raises:
        FileNotFoundError: If input files are missing.
        zipfile.BadZipFile: If input files are not valid ZIPs.
        ValueError: If no .dex files are found or patching fails.
    """
    org_path = Path(org_file).resolve()
    mod_path = Path(mod_file).resolve()
    output_path = Path(output_file).resolve()

    # Validate input files
    for path in [org_path, mod_path]:
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

    def get_apk_entries(file_path: str) -> Dict[str, Dict[str, int]]:
        """
        Extract metadata for .dex files in the APK.

        Returns:
            Dict[str, Dict[str, int]]: Mapping of filenames to CRC, offsets, and sizes.
        """
        entries = {}
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for info in zip_ref.infolist():
                    print(info)
                    if '.dex' in info.filename:
                        # Read raw ZIP entry to get header offsets
                        with open(file_path, 'rb') as f:
                            f.seek(info.header_offset)
                            local_header = f.read(30)  # Local file header is 30 bytes minimum
                            # Parse local header fields
                            crc_offset = info.header_offset + 14  # CRC is at offset 14 in local header
                            entries[info.filename] = {
                                'crc': info.CRC,
                                'local_header_offset': info.header_offset,
                                'crc_offset': crc_offset,
                                'compressed_size': info.compress_size,
                                'uncompressed_size': info.file_size,
                                'compression_method': info.compress_type,
                                'central_dir_offset': None  # To be determined
                            }
                # Find central directory offsets (simplified; assumes standard ZIP structure)
                with open(file_path, 'rb') as f:
                    f.seek(-22, os.SEEK_END)  # End of central directory record
                    eocd = f.read(22)
                    central_dir_start = unpack('<I', eocd[16:20])[0]
                    f.seek(central_dir_start)
                    for _ in range(len(zip_ref.infolist())):
                        central_header = f.read(46)  # Central directory header is 46 bytes minimum
                        filename_len = unpack('<H', central_header[28:30])[0]
                        extra_len = unpack('<H', central_header[30:32])[0]
                        comment_len = unpack('<H', central_header[32:34])[0]
                        filename = f.read(filename_len).decode('utf-8')
                        f.seek(extra_len + comment_len, os.SEEK_CUR)
                        if filename in entries:
                            entries[filename]['central_dir_offset'] = central_dir_start + 16  # CRC is at offset 16
                        central_dir_start = f.tell()
            return entries
        except Exception as e:
            logging.error(f"Error extracting entries from {file_path}: {e}")
            raise

    # Extract entries
    org_entries = get_apk_entries(org_path)
    mod_entries = get_apk_entries(mod_path)

    if not org_entries or not mod_entries:
        raise ValueError("No .dex files found in one or both APKs")

    # Compare and identify CRCs to patch
    crc_patches = []
    for filename in org_entries:
        if filename not in mod_entries:
            logging.warning(f"File {filename} not found in modified APK")
            continue
        org_crc = org_entries[filename]['crc']
        mod_crc = mod_entries[filename]['crc']
        if org_crc != mod_crc:
            crc_patches.append({
                'filename': filename,
                'original_crc': org_crc,
                'modified_crc': mod_crc,
                'local_crc_offset': mod_entries[filename]['crc_offset'],
                'central_crc_offset': mod_entries[filename]['central_dir_offset']
            })
            logging.info(f"Will patch CRC for {filename}: {hex(mod_crc)} -> {hex(org_crc)}")

    if not crc_patches:
        logging.info("No CRCs need patching")
        # Copy mod_file to output_file
        with open(mod_path, 'rb') as src, open(output_path, 'wb') as dst:
            dst.write(src.read())
        return

    # Patch CRCs
    try:
        with open(mod_path, 'rb') as f:
            binary_content = bytearray(f.read())

        for patch in crc_patches:
            original_crc_bytes = pack('<I', patch['original_crc'])
            # Patch local file header
            binary_content[patch['local_crc_offset']:patch['local_crc_offset']+4] = original_crc_bytes
            # Patch central directory
            if patch['central_crc_offset'] is not None:
                binary_content[patch['central_crc_offset']:patch['central_crc_offset']+4] = original_crc_bytes
            logging.debug(f"Patched CRC for {patch['filename']} at offsets {patch['local_crc_offset']} and {patch['central_crc_offset']}")

        # Write patched APK
        with open(output_path, 'wb') as patched:
            patched.write(binary_content)
        logging.info(f"Patched APK saved to {output_path}")

        # Verify patched APK
        #with zipfile.ZipFile(output_path, 'r') as zip_ref:
        #    if zip_ref.testzip() is not None:
        #        raise ValueError("Patched APK is corrupted")
        #    patched_entries = get_apk_entries(output_path)
        #    for patch in crc_patches:
        #        filename = patch['filename']
        #        if patched_entries[filename]['crc'] != patch['original_crc']:
        #            raise ValueError(f"CRC patch failed for {filename}: {hex(patched_entries[filename]['crc'])} != {hex(patch['original_crc'])}")
        #logging.info("Patched APK verified successfully")
    except Exception as e:
        logging.error(f"Error patching CRCs: {e}")
        raise

crc_faker('a.apk', 'b.apk', 'out.apk')
