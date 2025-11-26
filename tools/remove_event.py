import os
import sys
import argparse

def remove_event(event_name, base_dir=None):
    """
    Removes an Event class (header and source files).
    """
    
    # Ensure directories exist
    if base_dir is None:
        base_dir = os.path.join("src", "object", "event")
    
    if not os.path.exists(base_dir):
        # Try to find the src directory relative to the current script if not found
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_script_dir)
        base_dir = os.path.join(project_root, "src", "object", "event")
        
        if not os.path.exists(base_dir):
            print(f"Error: Directory '{base_dir}' does not exist. Are you in the project root?")
            return False

    header_path = os.path.join(base_dir, f"{event_name}.h")
    source_path = os.path.join(base_dir, f"{event_name}.65816")

    files_removed = False

    if os.path.exists(header_path):
        try:
            os.remove(header_path)
            print(f"Removed: {header_path}")
            files_removed = True
        except OSError as e:
            print(f"Error removing {header_path}: {e}")

    if os.path.exists(source_path):
        try:
            os.remove(source_path)
            print(f"Removed: {source_path}")
            files_removed = True
        except OSError as e:
            print(f"Error removing {source_path}: {e}")

    if not files_removed:
        print(f"Warning: No files found for event '{event_name}' in {base_dir}")
        return False
        
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove an event class.")
    parser.add_argument("name", help="Name of the event to remove (e.g., Event.Test)")
    args = parser.parse_args()
    
    if remove_event(args.name):
        print("\nREMINDER:")
        print("1. Remove any references to this event in src/config/ids.inc")
        print("2. Remove any references to this event in src/object/script/script.h")
        print("3. Remove any usages of this event in your chapter scripts.")
    else:
        sys.exit(1)
