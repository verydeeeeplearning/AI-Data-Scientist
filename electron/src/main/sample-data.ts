/**
 * P1-08 Phase 3: locate and load onboarding sample datasets.
 *
 * Resource layout (kept identical for dev and packaged builds, just rooted
 * differently):
 *   resources/sample-data/manifest.json
 *   resources/sample-data/<filename>.csv
 *
 * - dev: project tree, resolved from this file's path.
 * - packaged: copied via electron-builder `extraResources` to
 *   `process.resourcesPath/sample-data/`.
 */

import fs from 'fs/promises';
import path from 'path';
import { app } from 'electron';

interface SampleManifestEntry {
  filename: string;
  label: string;
  description: string;
  rows: number;
  columns: string[];
}

interface SampleManifest {
  version: number;
  samples: Record<string, SampleManifestEntry>;
}

export interface SamplePayload {
  useCaseId: string;
  filename: string;
  label: string;
  description: string;
  mimeType: string;
  data: string; // base64-encoded
}

let cachedManifest: SampleManifest | null = null;

function resolveSampleDataDir(): string {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'sample-data');
  }
  // In dev `__dirname` resolves to electron/dist/main; resources live one
  // level above the dist root next to package.json.
  return path.join(__dirname, '..', '..', 'resources', 'sample-data');
}

async function loadManifest(): Promise<SampleManifest> {
  if (cachedManifest) return cachedManifest;
  const manifestPath = path.join(resolveSampleDataDir(), 'manifest.json');
  const raw = await fs.readFile(manifestPath, 'utf-8');
  const parsed = JSON.parse(raw) as SampleManifest;
  if (!parsed || typeof parsed !== 'object' || !parsed.samples) {
    throw new Error(`Sample manifest at ${manifestPath} is malformed.`);
  }
  cachedManifest = parsed;
  return parsed;
}

/**
 * Return the sample dataset metadata + base64 content for the given use case.
 * Falls back to the `general` entry when the use case has no specific mapping.
 * Throws on missing files so the renderer can surface a real error.
 */
export async function loadSampleForUseCase(useCaseId: string): Promise<SamplePayload> {
  const manifest = await loadManifest();
  const entry =
    manifest.samples[useCaseId] ?? manifest.samples.general ?? null;
  if (!entry) {
    throw new Error(
      `No sample dataset registered for use case '${useCaseId}' and no 'general' fallback defined.`
    );
  }

  const filePath = path.join(resolveSampleDataDir(), entry.filename);
  const buffer = await fs.readFile(filePath);
  return {
    useCaseId: useCaseId in manifest.samples ? useCaseId : 'general',
    filename: entry.filename,
    label: entry.label,
    description: entry.description,
    mimeType: 'text/csv',
    data: buffer.toString('base64'),
  };
}

/** Test/diagnostic helper: clear the cached manifest. */
export function _resetSampleManifestCache(): void {
  cachedManifest = null;
}
