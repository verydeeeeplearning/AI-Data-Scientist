import { useId } from 'react';
import { RefreshCw } from 'lucide-react';
import { Badge, Button, Card } from '../../design-system/primitives';
import { useI18n } from '../../stores/i18nStore';
import type {
  WorkspacePinnedProjectionItem,
  WorkspaceReadModel,
} from '../../stores/workspaceStore';
import { WorkspacePinnedProjectionList } from './WorkspacePinnedProjectionList';
import type { EvidenceWorkspaceFocus } from '../../application/workspace/workspaceRoute';

interface Props {
  focus: EvidenceWorkspaceFocus | null;
  readModel: WorkspaceReadModel;
  onOpenPinnedItem: (item: WorkspacePinnedProjectionItem) => void;
  onRefreshFiles: () => void;
  onOpenFiles: () => void;
}

function formatRelative(
  timestamp: number | undefined,
  t: (key: string, vars?: Record<string, string | number | null | undefined>) => string,
): string {
  if (timestamp == null) {
    return t('workspace:format.relative.empty');
  }
  const diff = Date.now() - timestamp;
  if (diff < 60_000) {
    return t('workspace:format.relative.justNow');
  }
  if (diff < 3_600_000) {
    return t('workspace:format.relative.minutes', { value: Math.floor(diff / 60_000) });
  }
  if (diff < 86_400_000) {
    return t('workspace:format.relative.hours', { value: Math.floor(diff / 3_600_000) });
  }
  return t('workspace:format.relative.days', { value: Math.floor(diff / 86_400_000) });
}

export function WorkspaceContextRail({
  focus,
  readModel,
  onOpenPinnedItem,
  onRefreshFiles,
  onOpenFiles,
}: Props) {
  const { t } = useI18n();
  const pinnedEvidenceTitleId = useId();
  const recentFilesTitleId = useId();
  const exportTitleId = useId();
  return (
    <aside className="space-y-4">
      <Card role="region" aria-labelledby={pinnedEvidenceTitleId}>
        <h3 id={pinnedEvidenceTitleId} className="text-sm font-semibold text-ds-text">
          {t('workspace:contextRail.pinnedEvidence.title')}
        </h3>
        <p className="mt-2 text-sm leading-6 text-ds-muted">
          {t('workspace:contextRail.pinnedEvidence.description')}
        </p>
        <div className="mt-4">
          <WorkspacePinnedProjectionList
            items={readModel.pinnedItems}
            pinnedCardCount={readModel.pinnedCardCount}
            status={readModel.pinnedProjectionStatus}
            focus={focus}
            onSelectItem={onOpenPinnedItem}
            variant="rail"
          />
        </div>
      </Card>

      <Card role="region" aria-labelledby={recentFilesTitleId}>
        <div className="flex items-center justify-between gap-3">
          <h3 id={recentFilesTitleId} className="text-sm font-semibold text-ds-text">
            {t('workspace:contextRail.recentFiles.title')}
          </h3>
          <Button
            variant="secondary"
            size="sm"
            leadingIcon={<RefreshCw size={12} aria-hidden="true" />}
            className="shrink-0"
            onClick={onRefreshFiles}
          >
            {t('workspace:contextRail.recentFiles.refresh')}
          </Button>
        </div>
        {readModel.recentFiles.length === 0 ? (
          <p className="mt-3 text-sm leading-6 text-ds-muted">
            {t('workspace:contextRail.recentFiles.empty')}
          </p>
        ) : (
          <ul className="mt-3 space-y-2" aria-labelledby={recentFilesTitleId}>
            {readModel.recentFiles.map((file) => (
              <li
                key={file.path}
                className="rounded-ds-xl border border-ds-border bg-ds-bg/40 px-3 py-3"
              >
                <div className="truncate text-sm font-medium text-ds-text" title={file.name}>
                  {file.name}
                </div>
                <div className="mt-1 truncate text-xs text-ds-muted" title={file.path}>
                  {file.path}
                </div>
                <div className="mt-2">
                  <Badge compact>{formatRelative(file.modifiedAt, t)}</Badge>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card role="region" aria-labelledby={exportTitleId}>
        <h3 id={exportTitleId} className="text-sm font-semibold text-ds-text">
          {t('workspace:contextRail.export.title')}
        </h3>
        <p className="mt-2 text-sm leading-6 text-ds-muted">
          {t('workspace:contextRail.export.description')}
        </p>
        <Button
          variant="secondary"
          size="sm"
          className="mt-4"
          onClick={onOpenFiles}
        >
          {t('workspace:contextRail.export.openFiles')}
        </Button>
      </Card>
    </aside>
  );
}
