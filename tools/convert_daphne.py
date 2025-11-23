#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess

def parse_framefile(framefile_path):
    """
    Parses the Daphne framefile to get the list of video files.
    Returns a list of absolute paths to the video files.
    """
    video_files = []
    base_dir = os.path.dirname(os.path.abspath(framefile_path))
    
    with open(framefile_path, 'r') as f:
        lines = f.readlines()
    
    # The first line is usually the relative path to the content
    content_root_rel = lines[0].strip()
    content_root = os.path.normpath(os.path.join(base_dir, content_root_rel))
    
    print(f"Content root determined as: {content_root}")
    
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        
        # Format is usually: FrameNumber  Filename
        parts = line.split(None, 1) # Split on first whitespace
        if len(parts) >= 2:
            filename = parts[1]
            full_path = os.path.join(content_root, filename)
            video_files.append(full_path)
            
    return video_files

def create_concat_files(video_files, temp_dir="."):
    """
    Creates temporary concat files for ffmpeg.
    Returns paths to video_list.txt and audio_list.txt
    """
    video_list_path = os.path.join(temp_dir, "temp_video_list.txt")
    audio_list_path = os.path.join(temp_dir, "temp_audio_list.txt")
    
    with open(video_list_path, 'w') as fv, open(audio_list_path, 'w') as fa:
        for v_file in video_files:
            # Check if files exist
            if not os.path.exists(v_file):
                print(f"Warning: Video file not found: {v_file}")
                continue
                
            # Assume audio file is same name but .ogg
            # Daphne files are often .m2v, audio is .ogg
            # Sometimes filenames in framefile are just the m2v
            
            base_name = os.path.splitext(v_file)[0]
            # Try common extensions
            a_file = base_name + ".ogg"
            
            if not os.path.exists(a_file):
                 print(f"Warning: Audio file not found: {a_file}")
                 # If audio is missing, we might de-sync if we skip. 
                 # But for now, let's assume pairs exist or warn.
                 continue

            # Escape paths for ffmpeg concat demuxer
            # Windows paths need backslashes escaped or forward slashes
            safe_v = v_file.replace('\\', '/')
            safe_a = a_file.replace('\\', '/')
            
            fv.write(f"file '{safe_v}'\n")
            fa.write(f"file '{safe_a}'\n")
            
    return video_list_path, audio_list_path

def main():
    parser = argparse.ArgumentParser(description="Convert Daphne Laserdisc files to MP4.")
    parser.add_argument("--framefile", required=True, help="Path to the Daphne framefile (e.g., dlcdrom.TXT)")
    parser.add_argument("--output", required=True, help="Path to the output MP4 file")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="Path to ffmpeg executable")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose ffmpeg output")
    parser.add_argument("--logfile", default=None, help="Path to log file for ffmpeg output")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.framefile):
        print(f"Error: Framefile not found: {args.framefile}")
        sys.exit(1)
        
    print(f"Parsing framefile: {args.framefile}")
    video_files = parse_framefile(args.framefile)
    
    if not video_files:
        print("Error: No video files found in framefile.")
        sys.exit(1)
        
    print(f"Found {len(video_files)} segments.")
    
    # Create temp list files
    v_list, a_list = create_concat_files(video_files)
    
    # Ensure output directory exists
    out_dir = os.path.dirname(os.path.abspath(args.output))
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    # Construct ffmpeg command
    # -f concat -safe 0 -i v_list -f concat -safe 0 -i a_list ...
    cmd = [
        args.ffmpeg,
        "-y", # Overwrite output
        "-f", "concat", "-safe", "0", "-i", v_list,
        "-f", "concat", "-safe", "0", "-i", a_list,
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", # High quality video
        "-c:a", "aac", "-b:a", "192k", # Good quality audio
        "-map", "0:v", "-map", "1:a", # Map video from first input, audio from second
        args.output
    ]
    
    print("Running ffmpeg...")
    if not args.quiet:
        print(" ".join(cmd))
    
    # Setup output redirection for quiet mode
    stdout_dest = subprocess.DEVNULL if args.quiet else None
    stderr_dest = subprocess.DEVNULL if args.quiet else None
    
    # If logfile specified, redirect to file instead
    log_handle = None
    if args.logfile:
        log_handle = open(args.logfile, 'w')
        stdout_dest = log_handle
        stderr_dest = log_handle
        if args.quiet:
            print(f"Logging ffmpeg output to: {args.logfile}")
    
    try:
        subprocess.check_call(cmd, stdout=stdout_dest, stderr=stderr_dest)
        print(f"Successfully created: {args.output}")
    except subprocess.CalledProcessError as e:
        print(f"Error running ffmpeg: {e}")
        if log_handle:
            print(f"Check log file for details: {args.logfile}")
        sys.exit(1)
    finally:
        # Cleanup log handle
        if log_handle:
            log_handle.close()
        # Cleanup temp files
        if os.path.exists(v_list):
            os.remove(v_list)
        if os.path.exists(a_list):
            os.remove(a_list)

if __name__ == "__main__":
    main()
