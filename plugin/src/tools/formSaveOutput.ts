import { Type } from "@sinclair/typebox";
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { validateStagedPath, validateOutboxPath } from "../utils/pathValidator.js";
import { log } from "../utils/logger.js";

export const formSaveOutputTool = {
  name: "form_save_output",
  label: "Save Filled PDF",
  description:
    "Copy a staged (filled) PDF to the outbox. " +
    "staged_file must be under workspace/forms/staged/ and " +
    "destination_path must be under workspace/forms/outbox/. " +
    "Overwrites are denied unless explicitly approved.",
  parameters: Type.Object({
    staged_file: Type.String({
      description: "Path to the staged filled PDF (must be under workspace/forms/staged/)",
    }),
    destination_path: Type.String({
      description: "Destination path in the outbox (must be under workspace/forms/outbox/)",
    }),
  }),
  async execute(
    _toolCallId: string,
    params: { staged_file: string; destination_path: string },
  ) {
    const start = Date.now();

    let validatedStaged: string;
    let validatedDest: string;
    try {
      validatedStaged = validateStagedPath(params.staged_file);
      validatedDest = validateOutboxPath(params.destination_path);
    } catch (err: unknown) {
      const reason = (err as Error).message;
      log({
        event: "tool_blocked",
        tool: "form_save_output",
        args: params,
        policy_decision: "blocked",
        block_reason: reason,
      });
      return {
        content: [{ type: "text" as const, text: `Blocked: ${reason}` }],
        isError: true,
      };
    }

    if (!existsSync(validatedStaged)) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Error: staged file not found: ${validatedStaged}`,
          },
        ],
        isError: true,
      };
    }

    if (existsSync(validatedDest)) {
      log({
        event: "tool_blocked",
        tool: "form_save_output",
        args: params,
        policy_decision: "blocked",
        block_reason: "destination file already exists — overwrite denied",
      });
      return {
        content: [
          {
            type: "text" as const,
            text: `Blocked: destination "${params.destination_path}" already exists. Overwrite is not allowed.`,
          },
        ],
        isError: true,
      };
    }

    try {
      mkdirSync(dirname(validatedDest), { recursive: true });
      copyFileSync(validatedStaged, validatedDest);
      const durationMs = Date.now() - start;

      log({
        event: "output_saved",
        tool: "form_save_output",
        args: params,
        policy_decision: "allowed",
        result_summary: `saved to ${validatedDest}`,
        duration_ms: durationMs,
      });
      return {
        content: [
          {
            type: "text" as const,
            text: `Saved filled PDF to: ${validatedDest}`,
          },
        ],
        details: { output_path: validatedDest },
      };
    } catch (err: unknown) {
      return {
        content: [
          { type: "text" as const, text: `Error: ${(err as Error).message}` },
        ],
        isError: true,
      };
    }
  },
};
