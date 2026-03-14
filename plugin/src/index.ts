import { resolve } from "node:path";
import { setWorkerUrl } from "./utils/workerClient.js";
import { setWorkspaceRoot } from "./utils/pathValidator.js";
import { initLogger, log } from "./utils/logger.js";
import { formDetectFieldsTool } from "./tools/formDetectFields.js";
import { formExtractProfileTool } from "./tools/formExtractProfile.js";
import { formFillPdfTool } from "./tools/formFillPdf.js";
import { formSaveOutputTool } from "./tools/formSaveOutput.js";
import { formTranscribeAudioTool } from "./tools/formTranscribeAudio.js";

interface PluginApi {
  id: string;
  name: string;
  pluginConfig?: Record<string, unknown>;
  logger: { info: (msg: string) => void; warn: (msg: string) => void };
  registerTool: (tool: unknown, opts?: { name?: string; optional?: boolean }) => void;
  resolvePath: (input: string) => string;
}

const DEFAULT_WORKSPACE = resolve(
  import.meta.dirname ?? ".",
  "..",
  "..",
  "workspace",
);

export default function register(api: PluginApi): void {
  const cfg = (api.pluginConfig ?? {}) as Record<string, string>;

  const workerUrl = cfg.workerUrl || "http://127.0.0.1:8100";
  const workspacePath = cfg.workspacePath
    ? resolve(cfg.workspacePath)
    : DEFAULT_WORKSPACE;

  setWorkerUrl(workerUrl);
  setWorkspaceRoot(workspacePath);
  initLogger(workspacePath);

  api.logger.info(
    `ClawShield plugin loaded — worker=${workerUrl}  workspace=${workspacePath}`,
  );
  log({
    event: "intent_parsed",
    details: { message: "ClawShield plugin initialized", workerUrl, workspacePath },
  });

  api.registerTool(formDetectFieldsTool, { name: "form_detect_fields" });
  api.registerTool(formExtractProfileTool, { name: "form_extract_profile_data" });
  api.registerTool(formFillPdfTool, { name: "form_fill_pdf" });
  api.registerTool(formSaveOutputTool, { name: "form_save_output" });
  api.registerTool(formTranscribeAudioTool, {
    name: "form_transcribe_audio",
    optional: true,
  });
}
