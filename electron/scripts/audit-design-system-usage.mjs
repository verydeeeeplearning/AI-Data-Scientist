#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '..');

const WAVE4_LIVE_SURFACE_TARGETS = [
  'src/renderer/components/mission/MissionHeader.tsx',
  'src/renderer/components/runtime/BranchRunDialog.tsx',
  'src/renderer/components/runtime/GatewayStatusPanel.tsx',
  'src/renderer/components/runtime/LineagePanel.tsx',
  'src/renderer/components/runtime/PlanTreePanel.tsx',
  'src/renderer/components/runtime/PolicyPanel.tsx',
  'src/renderer/components/runtime/ReasoningTracePanel.tsx',
  'src/renderer/components/runtime/RecurringGoalsPanel.tsx',
  'src/renderer/components/runtime/RunDetailDrawer.tsx',
  'src/renderer/components/runtime/RunDiffPanel.tsx',
  'src/renderer/components/runtime/RunsCompareBoard.tsx',
  'src/renderer/components/runtime/StandingOrdersPanel.tsx',
  'src/renderer/components/sidebar/FileExplorer.tsx',
  'src/renderer/components/sidebar/FilePreviewModal.tsx',
  'src/renderer/components/sidebar/FileUpload.tsx',
  'src/renderer/components/sidebar/ModeSelector.tsx',
  'src/renderer/components/sidebar/ModelSelector.tsx',
  'src/renderer/components/sidebar/PlotGallery.tsx',
  'src/renderer/components/sidebar/ProjectPanel.tsx',
  'src/renderer/components/sidebar/UsageMeter.tsx',
  'src/renderer/components/workflow/ApprovalPanel.tsx',
  'src/renderer/components/workspace/AudienceViewSwitcher.tsx',
  'src/renderer/components/workspace/EvidenceWorkspace.tsx',
  'src/renderer/components/workspace/SchemaPreviewCard.tsx',
  'src/renderer/components/workspace/SuggestedActions.tsx',
  'src/renderer/components/workspace/UploadErrorState.tsx',
  'src/renderer/components/workspace/WorkspaceContextRail.tsx',
  'src/renderer/components/workspace/WorkspaceEmptyState.tsx',
  'src/renderer/components/workspace/WorkspaceOverviewRail.tsx',
  'src/renderer/components/workspace/WorkspaceTabContent.tsx',
];

const LEGACY_MIGRATION_TARGETS = [
  ...WAVE4_LIVE_SURFACE_TARGETS,
  'src/renderer/components/admin/ApprovalGrantsPanel.tsx',
  'src/renderer/components/cards/ResultCard.tsx',
  'src/renderer/components/mission/ConnectionTooltip.tsx',
  'src/renderer/components/runtime/CertificationBoard.tsx',
  'src/renderer/components/runtime/RegressionBoard.tsx',
  'src/renderer/components/sandbox/SandboxApprovalModal.tsx',
  'src/renderer/components/sandbox/SandboxViolationToast.tsx',
  'src/renderer/components/sidebar/SidebarItem.tsx',
  'src/renderer/components/trust/TrustStrip.tsx',
  'src/renderer/components/workflow/DecisionOsReviewPrimitives.tsx',
];

function walk(dir, predicate, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const next = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(next, predicate, out);
    } else if (predicate(next)) {
      out.push(next);
    }
  }
  return out;
}

function read(relativePath) {
  return fs.readFileSync(path.join(repoRoot, relativePath), 'utf8');
}

function fileExists(relativePath) {
  return fs.existsSync(path.join(repoRoot, relativePath));
}

function usesDesignSystem(relativePath) {
  if (!fileExists(relativePath)) {
    return false;
  }
  const content = read(relativePath);
  return /from ['"][^'"]*design-system\/(primitives|composites)['"]/.test(content);
}

function countStoryExports() {
  const storyFiles = walk(
    path.join(repoRoot, 'src', 'renderer', 'design-system'),
    (filePath) => /\.stories\.(ts|tsx)$/.test(filePath),
  );
  let exportCount = 0;
  for (const storyFile of storyFiles) {
    const content = fs.readFileSync(storyFile, 'utf8');
    exportCount += [...content.matchAll(/^export const (\w+)/gm)].length;
  }
  return {
    files: storyFiles.length,
    exports: exportCount,
    threshold: 50,
    passed: exportCount >= 50,
  };
}

function auditTargetSet(name, threshold, targets) {
  const missing = [];
  const adopting = [];
  const nonAdopting = [];

  for (const target of targets) {
    if (!fileExists(target)) {
      missing.push(target);
      continue;
    }
    if (usesDesignSystem(target)) {
      adopting.push(target);
    } else {
      nonAdopting.push(target);
    }
  }

  const existing = targets.length - missing.length;
  const percentage = existing === 0 ? 0 : Number(((adopting.length / existing) * 100).toFixed(1));

  return {
    name,
    threshold,
    targetCount: targets.length,
    existingCount: existing,
    adoptingCount: adopting.length,
    percentage,
    passed: percentage >= threshold,
    missing,
    nonAdopting,
  };
}

export function runAudit() {
  const storybook = countStoryExports();
  const wave4SurfaceAdoption = auditTargetSet('wave4SurfaceAdoption', 80, WAVE4_LIVE_SURFACE_TARGETS);
  const legacyMigration = auditTargetSet('legacyMigration', 30, LEGACY_MIGRATION_TARGETS);

  return {
    storybook,
    wave4SurfaceAdoption,
    legacyMigration,
    overallPassed:
      storybook.passed && wave4SurfaceAdoption.passed && legacyMigration.passed,
  };
}

const audit = runAudit();

if (process.argv.includes('--json')) {
  console.log(JSON.stringify(audit, null, 2));
} else {
  console.log(
    [
      `[audit:design-system] story exports=${audit.storybook.exports}/${audit.storybook.threshold}`,
      `[audit:design-system] wave4 surface adoption=${audit.wave4SurfaceAdoption.percentage}%`,
      `[audit:design-system] legacy migration=${audit.legacyMigration.percentage}%`,
      `[audit:design-system] overall=${audit.overallPassed ? 'PASS' : 'FAIL'}`,
    ].join('\n'),
  );
}

process.exit(audit.overallPassed ? 0 : 1);
