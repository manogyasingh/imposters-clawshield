import { resolve, normalize } from "node:path";
import { statSync } from "node:fs";

let workspaceRoot = "";

export function setWorkspaceRoot(path: string): void {
  workspaceRoot = resolve(path);
}

export function getWorkspaceRoot(): string {
  return workspaceRoot;
}

function ensureUnder(filePath: string, ...allowedDirs: string[]): string {
  const resolved = resolve(filePath);
  const normalizedResolved = normalize(resolved);

  for (const dir of allowedDirs) {
    const resolvedDir = normalize(resolve(dir));
    if (
      normalizedResolved === resolvedDir ||
      normalizedResolved.startsWith(resolvedDir + "/")
    ) {
      return resolved;
    }
  }

  throw new Error(
    `Path "${filePath}" is outside allowed directories: ${allowedDirs.join(", ")}`,
  );
}

function ensureExistingFile(filePath: string): string {
  let stat;
  try {
    stat = statSync(filePath);
  } catch {
    throw new Error(`Path "${filePath}" does not exist`);
  }
  if (!stat.isFile()) {
    throw new Error(`Path "${filePath}" is not a file`);
  }
  return filePath;
}

export function validateInboxPath(filePath: string): string {
  return ensureExistingFile(ensureUnder(
    filePath,
    resolve(workspaceRoot, "forms", "inbox"),
  ));
}

export function validateProfilePath(filePath: string): string {
  return ensureExistingFile(ensureUnder(
    filePath,
    resolve(workspaceRoot, "data", "profile"),
  ));
}

export function validateStagedPath(filePath: string): string {
  return ensureUnder(
    filePath,
    resolve(workspaceRoot, "forms", "staged"),
  );
}

export function validateOutboxPath(filePath: string): string {
  return ensureUnder(
    filePath,
    resolve(workspaceRoot, "forms", "outbox"),
  );
}
