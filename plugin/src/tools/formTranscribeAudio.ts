import { Type } from "@sinclair/typebox";
import { resolve } from "node:path";
import { getWorkspaceRoot } from "../utils/pathValidator.js";
import { transcribeAudio } from "../utils/workerClient.js";
import { log } from "../utils/logger.js";

export const formTranscribeAudioTool = {
  name: "form_transcribe_audio",
  label: "Transcribe Audio",
  description:
    "Transcribe an audio file to text using Sarvam AI STT. " +
    "The audio_path must be within the workspace directory.",
  parameters: Type.Object({
    audio_path: Type.String({
      description: "Path to an audio file (WAV/MP3) within the workspace",
    }),
    language: Type.Optional(
      Type.String({
        description: "Language code (default: en-IN)",
        default: "en-IN",
      }),
    ),
  }),
  async execute(
    _toolCallId: string,
    params: { audio_path: string; language?: string },
  ) {
    const start = Date.now();
    const resolved = resolve(params.audio_path);
    const root = getWorkspaceRoot();

    if (!resolved.startsWith(root + "/") && resolved !== root) {
      const reason = `Path "${params.audio_path}" is outside the workspace`;
      log({
        event: "tool_blocked",
        tool: "form_transcribe_audio",
        args: { audio_path: params.audio_path },
        policy_decision: "blocked",
        block_reason: reason,
      });
      return {
        content: [{ type: "text" as const, text: `Blocked: ${reason}` }],
        isError: true,
      };
    }

    try {
      const result = await transcribeAudio(resolved, params.language ?? "en-IN");
      const durationMs = Date.now() - start;
      log({
        event: "tool_executed",
        tool: "form_transcribe_audio",
        args: { audio_path: params.audio_path, language: params.language },
        policy_decision: "allowed",
        result_summary: `transcribed ${result.text.length} chars`,
        duration_ms: durationMs,
      });
      return {
        content: [{ type: "text" as const, text: result.text }],
        details: { text: result.text },
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
