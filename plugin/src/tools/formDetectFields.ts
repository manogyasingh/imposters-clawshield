import { Type } from "@sinclair/typebox";
import { validateInboxPath } from "../utils/pathValidator.js";
import { detectFields } from "../utils/workerClient.js";
import { log } from "../utils/logger.js";

export const formDetectFieldsTool = {
  name: "form_detect_fields",
  label: "Detect Form Fields",
  description:
    "Analyze a PDF form and detect all fillable fields with their bounding boxes. " +
    "The pdf_path must point to a file inside workspace/forms/inbox/.",
  parameters: Type.Object({
    pdf_path: Type.String({
      description: "Path to the PDF file (must be under workspace/forms/inbox/)",
    }),
  }),
  async execute(
    _toolCallId: string,
    params: { pdf_path: string },
  ) {
    const start = Date.now();
    let validated: string;
    try {
      validated = validateInboxPath(params.pdf_path);
    } catch (err: unknown) {
      const reason = (err as Error).message;
      log({
        event: "tool_blocked",
        tool: "form_detect_fields",
        args: { pdf_path: params.pdf_path },
        policy_decision: "blocked",
        block_reason: reason,
      });
      return {
        content: [{ type: "text" as const, text: `Blocked: ${reason}` }],
        isError: true,
      };
    }

    try {
      const result = await detectFields(validated);
      const durationMs = Date.now() - start;
      log({
        event: "tool_executed",
        tool: "form_detect_fields",
        args: { pdf_path: params.pdf_path },
        policy_decision: "allowed",
        result_summary: `detected ${result.fields.length} fields`,
        duration_ms: durationMs,
      });
      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify(result.fields, null, 2),
          },
        ],
        details: { field_count: result.fields.length, fields: result.fields },
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
