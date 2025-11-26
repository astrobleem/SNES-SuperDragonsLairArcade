import os
import sys
import argparse

def create_event(event_name, base_dir=None):
    """
    Creates a new Event class for the Super Road Blaster engine.
    
    The Event System:
    -----------------
    Events are 65816 classes that handle game logic, cutscenes, and interactions.
    They are instantiated by the 'EVENT' macro in chapter scripts (generated from XML).
    
    Lifecycle:
    1. init: Called when the event is created. Arguments from the EVENT macro are passed on the stack.
             Use this to initialize variables and store event properties (startFrame, endFrame, etc.).
    2. play: Called every frame. Use this for active logic (checking input, timers, etc.).
             Call 'abstract.Event.checkResult' to handle standard start/end frame logic.
    3. kill: Called when the event is destroyed. Clean up resources here.
    
    Structure:
    - Header (.h): Defines the 'vars' struct (private variables), Zero Page mapping, and Class properties.
    - Source (.65816): Implements the 'init', 'play', and 'kill' methods using the METHOD macro, and exports the class using the CLASS macro.
    """
    
    # 1. Validation
    if len(event_name) > 29:
        print(f"Error: Event name '{event_name}' is too long ({len(event_name)} chars). Max is 29.")
        return False

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

    if os.path.exists(header_path) or os.path.exists(source_path):
        print(f"Info: Files for '{event_name}' already exist. Skipping.")
        return True

    # 2. Content Generation
    # Header Content
    header_content = f"""
.include "src/config/config.inc"

.struct vars
    ; Define your private variables here
    timer dw
    state dw
.endst

;zp-vars
.enum 0
  iterator INSTANCEOF iteratorStruct
  event INSTANCEOF eventStruct
  this INSTANCEOF vars
  zpLen ds 0
.ende

;object class static flags, default properties and zero page 
.define CLASS.FLAGS OBJECT.FLAGS.Present
.define CLASS.PROPERTIES OBJECT.PROPERTIES.isEvent
.define CLASS.ZP_LENGTH zpLen

.base BSL
.bank 0 slot 0
"""

    # Source Content
    source_content = f"""/**
* {event_name}
*/
.include "src/object/event/{event_name}.h"
.section "{event_name}"

  METHOD init
  rep #$31
  
  ; Arguments passed via EVENT macro are on the stack.
  ; Stack offset depends on how many args were pushed.
  ; OBJECT.CALL.ARG.1 corresponds to the first argument after the class pointer.
  
  ; Example: Initialize standard event properties
  lda OBJECT.CALL.ARG.1,s
  sta.b event.startFrame
  lda OBJECT.CALL.ARG.2,s
  sta.b event.endFrame
  
  ; Initialize private variables
  stz.b this.timer
  stz.b this.state
  
  rts

  METHOD play
  rep #$31
  
  ; Main logic loop
  ; Check if the event should trigger based on frame count
  jsr abstract.Event.checkResult
  
  ; Add your custom logic here
  ; lda.b this.timer
  ; inc a
  ; sta.b this.timer
  
  rts

  METHOD kill
  rep #$31
  lda #OBJR_kill
  sta 3,s
  rts

  CLASS {event_name}
.ends
"""

    # 3. Write Files
    try:
        with open(header_path, "w") as f:
            f.write(header_content.strip())
        
        with open(source_path, "w") as f:
            f.write(source_content.strip())
    except IOError as e:
        print(f"Error writing files: {e}")
        return False

    print(f"Successfully created:")
    print(f"  - {header_path}")
    print(f"  - {source_path}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a new event with boilerplate code.")
    parser.add_argument("name", help="Name of the event (e.g., Event.my_scene)")
    args = parser.parse_args()
    
    if create_event(args.name):
        print("\nNEXT STEPS:")
        print("1. Open src/config/ids.inc (or similar) and define a unique OBJID for your class:")
        print(f"   .def OBJID.{args.name} $XXXX")
        print(f"2. Open src/object/script/script.h and add:")
        print(f"   .def obj{args.name.split('.')[-1]} hashPtr.XX")
        print("3. Add your event to a chapter script using the EVENT macro.")
    else:
        sys.exit(1)
