import { Type } from "@sinclair/typebox";
import { validateInboxPath } from "../utils/pathValidator.js";
import { fillPdf } from "../utils/workerClient.js";
import { log } from "../utils/logger.js";

export const formFillPdfTool = {
  name: "form_fill_pdf",
  label: "Fill PDF Form",
  description:
    "Overlay field values onto a PDF form. The pdf_path must be under workspace/forms/inbox/. " +
    "The filled PDF is saved to workspace/forms/staged/ and the staged path is returned.",
  parameters: Type.Object({
    pdf_path: Type.String({
      description: "Path to the original PDF (must be under workspace/forms/inbox/)",
    }),
    field_values: Type.Array(
      Type.Object({
        label: Type.String({ description: "Field label" }),
        value: Type.String({ description: "Value to fill" }),
        box_2d: Type.Array(Type.Number(), { minItems: 4, maxItems: 4 }),
        page: Type.Number({ description: "0-indexed page number" }),
      }),
    ),
  }),
  async execute(
    _toolCallId: string,
    params: {
      pdf_path: string;
      field_values: Array<{ label: string; value: string; box_2d: number[]; page: number }>;
    },
  ) {
    const start = Date.now();
    let validated: string;
    try {
      validated = validateInboxPath(params.pdf_path);
    } catch (err: unknown) {
      const reason = (err as Error).message;
      log({
        event: "tool_blocked",
        tool: "form_fill_pdf",
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
      const result = await fillPdf(validated, params.field_values);
      const durationMs = Date.now() - start;
      log({
        event: "tool_executed",
        tool: "form_fill_pdf",
        args: { pdf_path: params.pdf_path, field_count: params.field_values.length },
        policy_decision: "allowed",
        result_summary: `filled ${params.field_values.length} fields, staged at ${result.staged_path}`,
        duration_ms: durationMs,
      });
      return {
        content: [
          {
            type: "text" as const,
            text: `PDF filled successfully. Staged at: ${result.staged_path}`,
          },
        ],
        details: { staged_path: result.staged_path },
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
