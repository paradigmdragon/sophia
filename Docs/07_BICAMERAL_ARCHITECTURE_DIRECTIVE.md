# Bicameral Architecture Directive: Sophia v0.1

## 1. Core Architecture: The Bicameral Mind
This directive defines the "Bicameral Mind" (Left/Right Brain) architecture as the core cognitive model for Sophia.

| Component | **Left Brain (Local)** | **Right Brain (Server)** |
| :--- | :--- | :--- |
| **Domain** | User's World (Subjectivity) | Epidora Reality (Objectivity) |
| **Language** | User's specific language & context | Structural patterns & logic |
| **Role** | Translation, Expression, Rendering | Detection, Validation, Knowledge |
| **Constraint** | Never speaks unless consistent with User Context | Never sees raw content, only structure |

## 2. Interaction Model: Gap & Question
- **Gap Detection:** The Right Brain detects a structural pattern (e.g., circular logic) but realizes the Left Brain has no corresponding term for it.
- **Question Generation:** Instead of stating the fact ("This is circular logic"), Sophia generates a question ("How would you describe this repeating pattern?").
- **Growth (Sync):** When the user provides a term (e.g., "Loop"), the Left and Right brains sync, and Sophia gains the ability to speak about this concept using the user's language.

## 3. Implementation Guidelines
- **Local Module (Left):**
    - Manages `memory_manifest.json`.
    - Runs the LLM for persona and context generation.
    - **Sole Output Source:** All user-facing communication MUST originate here.
- **Logic Module (Right):**
    - Runs `Epidora Engine` (6 Coordinates).
    - Manages Knowledge Graph (Structure only).
    - **Signal Only:** Outputs structural signals, never raw text.

## 4. Final Checklist
- [x] `Docs/Sophia.md`: Updated to define the Bicameral Mind.
- [x] `Docs/SonE.md`: Updated to include Bicameral Integration.
- [x] `Docs/Epidora.md`: Confirmed as the logic engine for the Right Brain.
- [ ] **Implementation:** Proceed with code implementation adhering to this strict separation.
