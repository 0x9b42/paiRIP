import zipfile
import struct

def get_crcs(apk_path):
    """Extract CRCs and metadata from an APK."""
    crcs = {}
    with zipfile.ZipFile(apk_path, 'r') as z:
        for info in z.infolist():
            crcs[info.filename] = {
                'crc': info.CRC,
                'compressed_size': info.compress_size,
                'uncompressed_size': info.file_size,
                'compression_method': info.compress_type
            }
    return crcs

def patch_crcs(original_apk, modified_apk, output_apk):
    """Patch CRCs in modified APK to match original APK."""
    original_crcs = get_crcs(original_apk)
    temp_apk = 'temp.apk'
    
    # Copy modified APK to temp file
    with zipfile.ZipFile(modified_apk, 'r') as z_in:
        with zipfile.ZipFile(temp_apk, 'w', zipfile.ZIP_STORED) as z_out:
            for info in z_in.infolist():
                data = z_in.read(info.filename)
                new_info = zipfile.ZipInfo(info.filename)
                new_info.compress_type = info.compress_type
                new_info.file_size = info.file_size
                new_info.compress_size = info.compress_size
                # Use original CRC if file exists in original APK
                if info.filename in original_crcs:
                    new_info.CRC = original_crcs[info.filename]['crc']
                else:
                    new_info.CRC = info.CRC
                z_out.writestr(new_info, data)
    
    # Update central directory CRCs 
    # (requires low-level ZIP manipulation)
    with open(temp_apk, 'rb') as f:
        data = f.read()
    with open(output_apk, 'wb') as f:
        f.write(data)
    
    # Note: This is a simplified version; actual ZIP header manipulation
    # requires parsing and updating local and central directory headers.

# Example usage
original_apk = 'original.apk'
modified_apk = 'modified.apk'
output_apk = 'patched.apk'
patch_crcs(original_apk, modified_apk, output_apk)
