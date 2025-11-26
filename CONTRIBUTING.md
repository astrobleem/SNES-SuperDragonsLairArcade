# Contributing to SNES Super Dragons Lair Arcade

Thank you for your interest in contributing to **SNES‑SuperDragonsLairArcade**! 🎉

## How to Get Started
1. **Fork the repository** on GitHub.
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/<your‑username>/SNES-SuperDragonsLairArcade.git
   cd SNES-SuperDragonsLairArcade
   ```
3. **Create a new branch** for your work:
   ```bash
   git checkout -b <feature-or‑bugfix‑name>
   ```
4. Make your changes, ensuring the existing test suite passes.
5. **Commit** with a clear message and **push** to your fork.
6. Open a **Pull Request** against the `main` branch.

## Code Style & Guidelines
- Follow the existing Python coding style (PEP 8). Use `black` and `flake8` for formatting and linting.
- Keep functions small and well‑documented. Add docstrings for public APIs.
- Update or add tests for any new functionality. The project uses `pytest` – run `pytest` locally before submitting.

## Reporting Issues
- Search existing issues before opening a new one.
- Provide a clear description, steps to reproduce, and any relevant logs or screenshots.

## Pull Request Checklist
- [ ] Runs on the latest Python 3 version.
- [ ] All existing tests pass (`pytest`).
- [ ] New code includes tests and documentation where appropriate.
- [ ] Follows the project's coding style.

## Adding New Scenes/Events (Space Ace & Dragon's Lair)
> [!TIP]
> Use the helper script to generate boilerplate code and avoid common errors:
> `python tools/create_event.py Event.my_new_scene`

When creating new scenes or events, follow these guidelines to avoid common build pitfalls:

### 1. Naming Conventions
*   **Keep Names Short:** The WLA-DX assembler has a symbol length limit. Try to keep class names and labels under 30 characters.
    *   **Bad:** `Event.falling_platform_long_fell_to_death`
    *   **Good:** `Event.fall_plat_long_die`
*   **Unique Labels:** Ensure local labels (like `_loop`, `_exit`) don't conflict. Use named local labels (e.g., `_my_loop`) instead of generic `+`/`-` for complex logic to avoid "Too large distance" branch errors.

### 2. File Structure
*   **Header (`.h`):**
    *   **Include Guards:** ALWAYS use include guards to prevent redefinition errors.
        ```assembly
        .ifndef MY_EVENT_H
        .define MY_EVENT_H
        ...
        .endif
        ```
    *   **Struct Definitions:** If you need a custom `vars` struct, define it in the **implementation file (`.65816`)**, NOT the header, unless it must be shared. If shared, give it a unique name (e.g., `my_event_vars`) to avoid conflicts with other files defining `vars`.
    *   **Object ID:** Define a unique `OBJID` for your class.

*   **Implementation (`.65816`):**
    *   **Include Header:** `.include "src/object/event/MyEvent.h"`
    *   **Struct Mapping:** Map `this` to your struct in the `.65816` file if it's private.
        ```assembly
        .struct my_event_vars
          timer dw
        .endst
        .enum zpLen
          this INSTANCEOF my_event_vars
        .ende
        .redefine CLASS.ZP_LENGTH zpLen + _sizeof_my_event_vars
        ```
    *   **Methods:** Implement `init`, `play`, `kill`.
    *   **Registration:** Use the `CLASS` macro at the end of the file.

### 3. Registration Checklist
To ensure your new event builds and runs:
1.  **`src/config/structs.inc`:** Add any new global struct members here (e.g., if you need a new field in `eventStruct`).
2.  **`src/object/script/script.h`:** If your object is referenced in a script (e.g., `NEW MyEvent.CLS.PTR`), you MUST define a label for it in the script or header.
    *   **Example:** `.def objMyEvent hashPtr.10` (ensure the slot is available/correct).
3.  **`src/config/macros.inc`:** If you add a new interface method (like `translate`), ensure the `CLASS` macro exports it.

### 4. Adding New Sprites
Sprites often share similar pitfalls with events but have specific requirements regarding inheritance and struct definitions.

*   **Inheritance:** Most sprites should implement `interface.dimension` and `interface.animation`.
    *   Ensure your `CLASS` macro exports necessary methods (e.g., `translate` if used).
*   **Struct Definitions (Critical):**
    *   **NEVER** define a generic `vars` struct in a sprite header (`.h`) if that header might be included by other files (like events).
    *   **Pattern:**
        *   **Header (`MySprite.h`):** Only define the `OBJID`.
        *   **Implementation (`MySprite.65816`):** Define the `vars` struct here.
        *   **Mapping:** Map `this` to your struct within the implementation file.
    *   **Why?** If `Event.my_scene` includes `MySprite.h` and `MyOtherSprite.h`, and both define `struct vars`, the assembler will error with "Redefinition".

### 5. Common Pitfalls
*   **"Unknown Label":** Check if you defined the object label in the script or `script.h`.
*   **"Redefinition Error":** Check for missing include guards or conflicting struct names (like `vars`) in headers.
*   **"Too Large Distance":** Replace long conditional branches (`beq target`) with `bne + / jmp target / +`.
*   **"Symbol Not Found (this.endFrame)":** Ensure you have mapped `this` to a struct that actually contains `endFrame` in the scope where you are using it.

Feel free to ask for clarification in the issue or PR comments. We appreciate your contributions and look forward to collaborating with you!
