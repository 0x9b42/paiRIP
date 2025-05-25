import struct
import shutil
import zipfile
import logging
import argparse
from datetime import datetime

# Configure logging
def setup_logger():
    logger = logging.getLogger('crc_faker')
    logger.setLevel(logging.DEBUG)
    
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    ch.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(ch)
    
    return logger

logger = setup_logger()

def find_eocd(data):
    """Locate the End of Central Directory (EOCD) signature."""
    logger.debug("Searching for EOCD signature...")
    signature = b'\x50\x4b\x05\x06'
    max_comment_length = 65535
    search_start = max(0, len(data) - max_comment_length - 22)
    eocd_pos = data.rfind(signature, search_start)
    if eocd_pos == -1:
        logger.error("EOCD record not found!")
        raise ValueError("EOCD record not found")
    logger.debug(f"Found EOCD at position 0x{eocd_pos:X}")
    return eocd_pos

def parse_eocd(data, eocd_pos):
    """Parse EOCD fields and return central directory offset."""
    logger.debug("Parsing EOCD structure...")
    if data[eocd_pos:eocd_pos+4] != b'\x50\x4b\x05\x06':
        logger.error("Invalid EOCD signature!")
        raise ValueError("Invalid EOCD signature")
    
    fields = struct.unpack('<HHHHIIH', data[eocd_pos+4:eocd_pos+22])
    result = {
        'cd_offset': fields[5],  # Central directory start offset
        'comment_length': fields[6]
    }
    logger.debug(f"Central Directory starts at 0x{result['cd_offset']:X}")
    logger.debug(f"Comment length: {result['comment_length']} bytes")
    return result

def parse_central_directory(data, cd_offset):
    """Parse central directory entries."""
    logger.info("Parsing Central Directory entries...")
    entries = []
    pos = cd_offset
    entry_count = 0
    
    while pos < len(data) - 4:
        if data[pos:pos+4] != b'\x50\x4b\x01\x02':
            logger.debug("Reached end of Central Directory")
            break
        
        fixed_fields = struct.unpack('<HHHHHHIIIHHHHHII', data[pos+4:pos+46])
        filename_len = fixed_fields[9]
        extra_len = fixed_fields[10]
        comment_len = fixed_fields[11]
        
        filename = data[pos+46:pos+46+filename_len].decode('utf-8')
        logger.debug(f"Found entry: {filename} at 0x{pos:X}")
        
        entries.append({
            'filename': filename,
            'crc': fixed_fields[6],
            'compress_size': fixed_fields[7],
            'file_size': fixed_fields[8],
            'compression_method': fixed_fields[3],
            'local_header_offset': fixed_fields[15],
            'entry_offset': pos,
            'entry_size': 46 + filename_len + extra_len + comment_len
        })
        
        pos += 46 + filename_len + extra_len + comment_len
        entry_count += 1
    
    logger.info(f"Found {entry_count} Central Directory entries")
    return entries

def get_original_metadata(original_zip):
    """Extract metadata from original ZIP."""
    logger.info(f"Extracting metadata from original file: {original_zip}")
    metadata = {}
    
    try:
        with zipfile.ZipFile(original_zip, 'r') as zf:
            for info in zf.infolist():
                logger.debug(f"Processing original entry: {info.filename}")
                metadata[info.filename] = {
                    'crc': info.CRC,
                    'compress_size': info.compress_size,
                    'file_size': info.file_size,
                    'compression_method': info.compress_type,
                }
        logger.info(f"Extracted metadata for {len(metadata)} entries")
    except Exception as e:
        logger.error(f"Failed to read original ZIP: {str(e)}")
        raise
    
    return metadata

def fake_crc(modified_path, original_path, output_path):
    logger.info(f"Starting CRC faking process")
    logger.info(f"Modified file: {modified_path}")
    logger.info(f"Original file: {original_path}")
    logger.info(f"Output file: {output_path}")
    
    try:
        # Create working copy
        logger.debug(f"Creating working copy: {modified_path} -> {output_path}")
        shutil.copyfile(modified_path, output_path)
        
        # Read original metadata
        original_metadata = get_original_metadata(original_path)
        
        # Process output file
        logger.debug("Reading output file data")
        with open(output_path, 'r+b') as f:
            data = bytearray(f.read())
        
        # Find and parse EOCD
        eocd_pos = find_eocd(data)
        eocd = parse_eocd(data, eocd_pos)
        
        # Parse central directory
        cd_entries = parse_central_directory(data, eocd['cd_offset'])
        
        # Update headers
        logger.info("Starting header updates")
        updated_entries = 0
        skipped_entries = 0
        
        for entry in cd_entries:
            filename = entry['filename']
            orig_data = original_metadata.get(filename)
            
            if not orig_data:
                logger.warning(f"No original metadata for: {filename} - skipping")
                skipped_entries += 1
                continue
            
            logger.debug(f"Processing: {filename}")
            
            # Local header updates
            lh_offset = entry['local_header_offset']
            if lh_offset + 22 > len(data):
                logger.error(f"Invalid local header offset 0x{lh_offset:X} for {filename}")
                continue
            
            # Pack new values
            logger.debug(f"Updating local header at 0x{lh_offset:X}")
            struct.pack_into('<III', data, lh_offset + 14,
                            orig_data['crc'],
                            orig_data['compress_size'],
                            orig_data['file_size'])
            
            struct.pack_into('<H', data, lh_offset + 8,
                            orig_data['compression_method'])
            
            # Central directory updates
            cd_offset = entry['entry_offset']
            logger.debug(f"Updating central directory entry at 0x{cd_offset:X}")
            struct.pack_into('<III', data, cd_offset + 16,
                            orig_data['crc'],
                            orig_data['compress_size'],
                            orig_data['file_size'])
            
            struct.pack_into('<H', data, cd_offset + 10,
                            orig_data['compression_method'])
            
            updated_entries += 1
        
        # Write modified data back
        logger.debug("Writing modified data to output file")
        with open(output_path, 'wb') as f:
            f.write(data)
        
        logger.info(f"Process complete. Updated {updated_entries} entries, skipped {skipped_entries}")
    
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fake CRC values in modified ZIP/APK to match original')
    parser.add_argument('modified', help='Path to modified file')
    parser.add_argument('original', help='Path to original file')
    parser.add_argument('output', help='Path for output file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    try:
        fake_crc(args.modified, args.original, args.output)
        logger.info(f"Successfully created faked file: {args.output}")
    except Exception as e:
        logger.error(f"Failed to create faked file: {str(e)}")
        exit(1)
