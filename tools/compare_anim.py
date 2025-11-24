import struct
import sys

def parse_header(f):
    magic = f.read(2)
    max_tile = struct.unpack('<H', f.read(2))[0]
    max_pal = struct.unpack('<H', f.read(2))[0]
    frames = struct.unpack('<H', f.read(2))[0]
    bpp = ord(f.read(1))
    return {'magic': magic, 'max_tile': max_tile, 'max_pal': max_pal, 'frames': frames, 'bpp': bpp}

def compare(file1, file2):
    print(f"Comparing {file1} vs {file2}")
    with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
        h1 = parse_header(f1)
        h2 = parse_header(f2)
        
        print("Header 1:", h1)
        print("Header 2:", h2)
        
        if h1['frames'] != h2['frames']:
            print("Frame count mismatch!")
            return

        # Read pointers
        # Pointer list starts at 9
        # Length = frames * 2
        f1.seek(9)
        f2.seek(9)
        
        p1 = [struct.unpack('<H', f1.read(2))[0] for _ in range(h1['frames'])]
        p2 = [struct.unpack('<H', f2.read(2))[0] for _ in range(h2['frames'])]
        
        print("Pointers 1:", p1)
        print("Pointers 2:", p2)
        
        # Compare frame headers
        for i in range(h1['frames']):
            print(f"--- Frame {i} ---")
            f1.seek(p1[i])
            f2.seek(p2[i])
            
            fh1 = struct.unpack('<HHH', f1.read(6))
            fh2 = struct.unpack('<HHH', f2.read(6))
            
            print(f"Frame {i} Header 1 (Tiles, Map, Pal): {fh1}")
            print(f"Frame {i} Header 2 (Tiles, Map, Pal): {fh2}")
            
            # We expect sizes to be potentially different due to optimization, 
            # but Map size should be roughly similar (or exactly same if same number of tiles).
            # If map size is different, it means different number of non-empty tiles were detected.

if __name__ == "__main__":
    compare(sys.argv[1], sys.argv[2])
