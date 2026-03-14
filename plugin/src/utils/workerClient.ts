let workerUrl = "http://127.0.0.1:8100";

export function setWorkerUrl(url: string): void {
  workerUrl = url.replace(/\/+$/, "");
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${workerUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Worker ${path} failed (${res.status}): ${detail}`);
  }
  return res.json() as Promise<T>;
}

export interface DetectedField {
  label: string;
  box_2d?: number[];
  type?: string;
  page?: number;
}

export interface ProfileResult {
  values: Record<string, string>;
  confidence: Record<string, number>;
  missing_fields: string[];
}

export interface FillResult {
  staged_path: string;
}

export interface TranscribeResult {
  text: string;
}

export function detectFields(pdfPath: string): Promise<{ fields: DetectedField[] }> {
  return post("/detect-fields", { pdf_path: pdfPath });
}

export function extractProfile(
  profilePaths: string[],
  fieldSchema: DetectedField[],
): Promise<ProfileResult> {
  return post("/extract-profile", {
    profile_paths: profilePaths,
    field_schema: fieldSchema,
  });
}

export function fillPdf(
  pdfPath: string,
  fieldValues: Record<string, unknown>[],
): Promise<FillResult> {
  return post("/fill-pdf", { pdf_path: pdfPath, field_values: fieldValues });
}

export function transcribeAudio(
  audioPath: string,
  language = "en-IN",
): Promise<TranscribeResult> {
  return post("/transcribe", { audio_path: audioPath, language });
}
