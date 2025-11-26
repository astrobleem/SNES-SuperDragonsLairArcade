#!/usr/bin/env python3
import os
import sys
import glob
import subprocess
import concurrent.futures
import time

def process_chapter(xml_file, video_file, out_folder, tools_dir):
    """
    Runs xmlsceneparser.py for a single XML file.
    """
    xml_path = os.path.abspath(xml_file)
    video_path = os.path.abspath(video_file)
    out_path = os.path.abspath(out_folder)
    parser_script = os.path.join(tools_dir, 'xmlsceneparser.py')
    
    cmd = [
        sys.executable, parser_script,
        '-infile', xml_path,
        '-outfolder', out_path,
        '-videofile', video_path,
        # We don't need convertedoutfolder/convertedframefolder as we patched the script
        # to output directly to chapterfolder
    ]
    
    try:
        # Capture output to avoid spamming console
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        return (True, xml_file)
    except subprocess.CalledProcessError as e:
        return (False, xml_file)

def main():
    if len(sys.argv) < 3:
        print("Usage: batch_process_video.py <events_dir> <video_file> [out_dir]")
        sys.exit(1)
        
    events_dir = sys.argv[1]
    video_file = sys.argv[2]
    out_dir = sys.argv[3] if len(sys.argv) > 3 else "data/chapters"
    
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    
    xml_files = glob.glob(os.path.join(events_dir, "*.xml"))
    print(f"Found {len(xml_files)} XML chapters to process.")
    
    start_time = time.time()
    
    # Use parallel processing
    # Adjust max_workers based on CPU cores. 
    # ffmpeg and superfamiconv are CPU intensive.
    max_workers = os.cpu_count() or 4
    print(f"Starting processing with {max_workers} workers...")
    
    completed = 0
    failed = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_xml = {executor.submit(process_chapter, xml, video_file, out_dir, tools_dir): xml for xml in xml_files}
        
        for future in concurrent.futures.as_completed(future_to_xml):
            success, xml = future.result()
            completed += 1
            if success:
                print(f"[{completed}/{len(xml_files)}] Processed: {os.path.basename(xml)}")
            else:
                print(f"[{completed}/{len(xml_files)}] FAILED: {os.path.basename(xml)}")
                failed.append(xml)
                
    duration = time.time() - start_time
    print(f"\nProcessing complete in {duration:.2f} seconds.")
    print(f"Successful: {len(xml_files) - len(failed)}")
    print(f"Failed: {len(failed)}")
    
    if failed:
        print("Failed chapters:")
        for f in failed:
            print(f"  {f}")
            
if __name__ == "__main__":
    main()
