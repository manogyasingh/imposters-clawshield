REMEMBER TO UPDATE THIS WITH THE PROGRESS AS YOU BUILD.

# ClawShield Implementation Plan

## Goal

Adapt the existing PDF form-filling assistant into an OpenClaw + ArmorIQ submission that satisfies the hackathon requirements:

- autonomous multi-step execution
- clear separation between reasoning and execution
- policy-based runtime enforcement
- visible allow/block outcomes
- traceable decision logs

## 0. Standardize Inference on OpenRouter ✅

- ~~Move all LLM inference to OpenRouter.~~
- ~~Read `OPENROUTER_MODEL` and `OPENROUTER_API_KEY` from `.env`.~~
- ~~Treat these as the single default inference configuration for:~~
  - ~~form field detection~~
  - ~~voice transcript cleanup~~
  - ~~any planning or extraction prompts that require an LLM~~
- ~~Remove UI-level provider switching from the old Streamlit flow.~~
- ~~Expose model selection through environment configuration, not hardcoded UI controls.~~

**Done.** Added `utils/config.py` as the centralized config loader. All LLM calls in `llm_helper.py` and `sarvam_helper.py` now default to env config. Sidebar LLM controls removed from `app.py`. Added `OPENROUTER_VISION_MODEL` env var for vision-specific tasks.

## 1. Reframe the Product for This Hackathon

- Position the project as `ClawShield`, an intent-aware form automation agent.
- The core story is not "AI fills forms" but "an autonomous agent fills forms only within explicit, enforced user intent boundaries."
- The old project provides the domain workflow; the new project must provide the enforcement architecture.

## 2. Target Stack

- Use OpenClaw as the agent runtime.
- Use ArmorIQ / ArmorClaw as the intent verification and policy enforcement layer.
- Use Node.js 20+, TypeScript, and `pnpm` for the main application.
- Keep the current Python PDF processing logic only as a narrow worker or helper layer if that is faster than porting it.
- Use `.env` for runtime secrets and model configuration.

## 3. Reuse Strategy from the Existing Codebase

### Reuse directly

- PDF-to-image conversion and PDF overlay logic from `utils/pdf_processor.py`
- Form field detection prompt and JSON normalization from `utils/llm_helper.py`
- Optional voice flow from `utils/sarvam_helper.py`

### Do not reuse as-is

- The Streamlit app shell in `app.py`
- Direct temp-file based execution without scoped policies
- Free-form tool invocation without intent validation

## 4. New Architecture

Build the system in four layers:

1. `OpenClaw Agent Layer`
   - accepts the user request
   - produces a structured execution plan
   - delegates work to scoped tools

2. `Intent + Policy Layer`
   - validates the user request into a structured intent object
   - checks each proposed action against enforceable policy
   - blocks out-of-scope actions deterministically

3. `Execution Tools Layer`
   - `form_detect_fields`
   - `form_extract_profile_data`
   - `form_fill_pdf`
   - `form_save_output`
   - optional `form_transcribe_audio`

4. `Worker Layer`
   - Python utilities for PDF/image manipulation and any existing voice helpers
   - isolated behind tool interfaces

## 5. Intent Model

Define a structured intent object instead of relying on prompt text alone.

Suggested shape:

```json
{
  "goal": "fill_form",
  "input_document": "workspace/forms/inbox/scholarship.pdf",
  "data_sources": [
    "workspace/data/profile/student_profile.json"
  ],
  "requested_actions": [
    "analyze_form",
    "extract_profile_data",
    "fill_pdf",
    "save_output"
  ],
  "output_destination": "workspace/forms/outbox/",
  "forbidden_actions": [
    "email",
    "upload",
    "read_sensitive_dirs",
    "write_outside_outbox"
  ]
}
```

This should be generated, stored, and referenced during runtime enforcement.

## 6. Policy Model

Policies must be explicit and enforceable, not hardcoded ad hoc checks.

Initial policy set:

- allow reading only from `workspace/forms/inbox`
- allow reading profile data only from `workspace/data/profile`
- allow writing only to `workspace/forms/outbox`
- deny writes outside the approved output directory
- deny overwriting existing files unless explicitly requested in intent
- deny non-PDF output generation
- deny email, upload, share, or publish actions
- deny access to hidden directories and sensitive user paths
- optionally deny network actions except approved OpenRouter inference calls

## 7. Tool Design

Implement a narrow tool surface so each action can be verified independently.

Suggested tools:

- `form_detect_fields(pdf_path)`
  - converts PDF pages to images
  - calls OpenRouter vision model
  - returns normalized field schema

- `form_extract_profile_data(profile_paths, field_schema)`
  - maps available profile data to requested fields
  - returns candidate values plus confidence and missing fields

- `form_fill_pdf(pdf_path, field_values)`
  - writes values into detected bounding boxes
  - produces a staged output artifact

- `form_save_output(staged_file, destination_path)`
  - saves only inside approved output directory

- `form_transcribe_audio(audio_path)`
  - optional voice input path
  - only if voice remains part of the demo

## 8. Separation of Reasoning and Execution

Keep the architecture visibly split:

- reasoning decides what should happen
- enforcement checks whether it may happen
- execution performs the action only after approval

Do not let the LLM call file operations directly. All side effects must pass through policy-checked tools.

## 9. Logging and Traceability

Add structured logs for every step:

- raw user request
- normalized intent object
- proposed plan
- policy decision per tool call
- allowed execution result
- blocked execution result
- final artifact path

Use these logs both for debugging and for the demo video.

## 10. Demo Design

The demo should show one clear success path and one clear blocked path.

### Allowed path

- User asks the agent to fill an approved PDF from approved profile data.
- Agent plans the task.
- ArmorIQ validates the actions.
- Tools execute.
- Filled PDF is saved in the approved outbox.

### Blocked path

Use one of these:

- user asks to save the result outside the approved directory
- user asks the agent to email/upload the filled form
- user asks the agent to read unrelated sensitive files to find missing data

The system must visibly block the step and explain why.

## 11. Delegation Bonus

If time permits, split the flow into bounded sub-agents:

- `Field Extraction Agent`
  - can only inspect the input PDF and return field schema

- `Fill Agent`
  - can only populate approved fields and write to staged output

- `Delivery Agent`
  - can only save into the approved outbox

Any attempt by a delegated agent to exceed scope should be blocked.

## 12. Build Order

1. Set up the OpenClaw + ArmorIQ project skeleton in TypeScript.
2. Add `.env` loading and standardize all inference on OpenRouter.
3. Port or wrap the Python utilities behind narrow execution tools.
4. Implement the structured intent schema.
5. Implement the policy model and runtime enforcement hooks.
6. Add logging and trace visualization.
7. Build the happy path demo flow.
8. Add at least one deterministic blocked scenario.
9. Add delegation only if the base flow is already stable.
10. Prepare the final docs, diagram, and demo video.

## 13. Deliverables to Prepare

- source repository
- architecture diagram
- short document covering:
  - intent model
  - policy model
  - enforcement mechanism
- three-minute demo video with:
  - system overview
  - one allowed action
  - one blocked action
  - explanation of why the block occurred

## 14. Success Criteria

The project is ready for submission when all of the following are true:

- OpenClaw is the runtime entry point
- ArmorIQ validates or blocks each meaningful tool action
- the form-filling workflow executes end to end
- the output is saved only within approved scope
- at least one realistic violation is blocked deterministically
- logs clearly explain both outcomes
- inference configuration comes from `.env` via `OPENROUTER_MODEL` and `OPENROUTER_API_KEY`
