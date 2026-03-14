import { Type } from "@sinclair/typebox";
import { validateProfilePath } from "../utils/pathValidator.js";
import { extractProfile } from "../utils/workerClient.js";
import { log } from "../utils/logger.js";

export const formExtractProfileTool = {
  name: "form_extract_profile_data",
  label: "Extract Profile Data",
  description:
    "Read user profile JSON files and match their fields to a form's detected field schema. " +
    "All profile_paths must point to files under workspace/data/profile/.",
  parameters: Type.Object({
    profile_paths: Type.Array(
      Type.String({
        description: "Paths to profile JSON files (must be under workspace/data/profile/)",
      }),
      { minItems: 1 },
    ),
    field_schema: Type.Array(
      Type.Object({
        label: Type.String(),
        box_2d: Type.Optional(Type.Array(Type.Number())),
        type: Type.Optional(Type.String()),
        page: Type.Optional(Type.Number()),
      }),
    ),
  }),
  async execute(
    _toolCallId: string,
    params: {
      profile_paths: string[];
      field_schema: Array<{ label: string; box_2d?: number[]; type?: string; page?: number }>;
    },
  ) {
    const start = Date.now();

    const validatedPaths: string[] = [];
    for (const p of params.profile_paths) {
      try {
        validatedPaths.push(validateProfilePath(p));
      } catch (err: unknown) {
        const reason = (err as Error).message;
        log({
          event: "tool_blocked",
          tool: "form_extract_profile_data",
          args: { profile_paths: params.profile_paths },
          policy_decision: "blocked",
          block_reason: reason,
        });
        return {
          content: [{ type: "text" as const, text: `Blocked: ${reason}` }],
          isError: true,
        };
      }
    }

    try {
      const result = await extractProfile(validatedPaths, params.field_schema);
      const durationMs = Date.now() - start;
      const matchedCount = Object.keys(result.values).length;
      log({
        event: "tool_executed",
        tool: "form_extract_profile_data",
        args: { profile_paths: params.profile_paths },
        policy_decision: "allowed",
        result_summary: `matched ${matchedCount} fields, ${result.missing_fields.length} missing`,
        duration_ms: durationMs,
      });
      return {
        content: [
          { type: "text" as const, text: JSON.stringify(result, null, 2) },
        ],
        details: result,
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
