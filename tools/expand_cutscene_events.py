
import re

input_file = 'src/object/event/Event.cutscene.65816'
output_file = 'src/object/event/Event.cutscene.65816'

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Expand cutscene event macros in Event.cutscene.65816.")
    parser.parse_args()

    with open(input_file, 'r') as f:
        content = f.read()

    # Define the expansion template
    template = """
    .section "Event.{name}"
      METHOD init
      rep #$31

      lda OBJECT.CALL.ARG.1,s
      sta.b event.startFrame
      lda OBJECT.CALL.ARG.2,s
      sta.b event.endFrame
      lda OBJECT.CALL.ARG.3,s
      sta.b event.result
      lda OBJECT.CALL.ARG.4,s
      sta.b event.resultTarget

      rts

      METHOD play
      rep #$31
      jsr abstract.Event.checkResult
      rts

      METHOD kill
      rep #$31
      lda #OBJR_kill
      sta 3,s
      rts

      CLASS Event.{name}
    .ends
    """

    # Regex to find macro calls
    # DEFINE_CUTSCENE_EVENT name
    pattern = re.compile(r'^DEFINE_CUTSCENE_EVENT\s+(\w+)', re.MULTILINE)

    def replace_macro(match):
        name = match.group(1)
        return template.format(name=name).strip()

    # Perform replacement
    new_content = pattern.sub(replace_macro, content)

    # Also remove the macro definition itself
    # It starts with .macro DEFINE_CUTSCENE_EVENT and ends with .endm
    macro_def_pattern = re.compile(r'\.macro DEFINE_CUTSCENE_EVENT.*?\.endm', re.DOTALL)
    new_content = macro_def_pattern.sub('; Macro manually expanded due to WLA-DX bug', new_content)

    with open(output_file, 'w') as f:
        f.write(new_content)

    print(f"Expanded macros in {output_file}")
