/**
 * Settings panel for approval grants (W2-F phase 2).
 *
 * Lists session/workspace grants persisted by the backend approval pipeline
 * and lets the operator revoke them. Receives ports as props so the
 * component layer never imports from infrastructure (Clean Arch compliance).
 */

import { useCallback, useEffect, useState } from 'react';
import { RefreshCw, ShieldAlert, ShieldOff } from 'lucide-react';
import { Badge, Button, Card } from '../../design-system/primitives';
import { useI18n } from '../../stores/i18nStore';
import type {
  ApprovalGrantSummary,
  ListApprovalGrantsPort,
  RevokeApprovalGrantPort,
} from '../../application/approval/approvalGrantsPort';

const SESSION_TIMEOUT_MINUTES = 30;

interface Props {
  listGrants: ListApprovalGrantsPort;
  revokeGrant: RevokeApprovalGrantPort;
}

export function ApprovalGrantsPanel({ listGrants, revokeGrant }: Props) {
  const { t } = useI18n();
  const [grants, setGrants] = useState<ApprovalGrantSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadGrants = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await listGrants();
      setGrants(next);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(t('approval:grant.list.error', { message }));
    } finally {
      setLoading(false);
    }
  }, [listGrants, t]);

  useEffect(() => {
    void loadGrants();
  }, [loadGrants]);

  const handleRevoke = async (grantId: string) => {
    setRevokingId(grantId);
    setError(null);
    setNotice(null);
    try {
      const updated = await revokeGrant(grantId);
      setGrants((current) => current.filter((entry) => entry.grantId !== updated.grantId));
      setNotice(t('approval:grant.list.revokeSuccess'));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(t('approval:grant.list.revokeError', { message }));
    } finally {
      setRevokingId(null);
    }
  };

  return (
    <section
      className="space-y-ds-4"
      aria-labelledby="approval-grants-title"
      aria-describedby="approval-grants-description"
      aria-busy={loading}
    >
      <header className="flex flex-wrap items-start justify-between gap-ds-3">
        <div>
          <h3
            id="approval-grants-title"
            className="flex items-center gap-ds-2 text-ds-sm font-semibold text-ds-text"
          >
            <ShieldAlert size={14} aria-hidden="true" />
            {t('approval:grant.list.title')}
          </h3>
          <p
            id="approval-grants-description"
            className="mt-ds-1 text-ds-xs leading-5 text-ds-muted"
          >
            {t('approval:grant.list.description')}
          </p>
        </div>
        <Button
          type="button"
          onClick={() => void loadGrants()}
          variant="secondary"
          size="sm"
          loading={loading}
          leadingIcon={<RefreshCw size={14} aria-hidden="true" />}
          aria-describedby="approval-grants-description"
          className="min-h-8 gap-ds-1 px-ds-3 text-ds-xs"
        >
          {t('approval:grant.list.refresh')}
        </Button>
      </header>

      {error && (
        <Card
          tone="danger"
          role="alert"
          className="flex items-start gap-ds-2 p-ds-3 text-ds-xs text-ds-error shadow-none"
        >
          <ShieldAlert size={14} aria-hidden="true" className="mt-0.5 shrink-0" />
          {error}
        </Card>
      )}
      {notice && !error && (
        <Card
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className="flex items-start gap-ds-2 border-ds-success/30 bg-ds-success/10 p-ds-3 text-ds-xs text-ds-success shadow-none"
        >
          <ShieldOff size={14} aria-hidden="true" className="mt-0.5 shrink-0" />
          {notice}
        </Card>
      )}

      {grants.length === 0 ? (
        <Card
          role="status"
          aria-live="polite"
          className="bg-ds-bg/40 p-ds-3 text-ds-xs text-ds-muted shadow-none"
        >
          {t('approval:grant.list.empty')}
        </Card>
      ) : (
        <Card className="overflow-hidden p-0 shadow-none">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-ds-xs" aria-describedby="approval-grants-description">
              <caption className="sr-only">{t('approval:grant.list.description')}</caption>
              <thead className="bg-ds-bg/40 text-ds-muted">
                <tr>
                  <th scope="col" className="px-ds-3 py-ds-2 font-semibold">
                    {t('approval:grant.list.scope')}
                  </th>
                  <th scope="col" className="px-ds-3 py-ds-2 font-semibold">
                    {t('approval:grant.list.risk')}
                  </th>
                  <th scope="col" className="px-ds-3 py-ds-2 font-semibold">
                    {t('approval:grant.list.kind')}
                  </th>
                  <th scope="col" className="px-ds-3 py-ds-2 font-semibold">
                    {t('approval:grant.list.expiresAt')}
                  </th>
                  <th scope="col" className="px-ds-3 py-ds-2 text-right font-semibold">
                    {t('approval:grant.list.actions')}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ds-border">
                {grants.map((grant) => {
                  const isRevoking = revokingId === grant.grantId;
                  return (
                    <tr key={grant.grantId} className="bg-ds-surface/60">
                      <td className="px-ds-3 py-ds-2 align-top">
                        <ScopeBadge scope={grant.scope} />
                      </td>
                      <td className="px-ds-3 py-ds-2 align-top text-ds-text">{grant.riskCode}</td>
                      <td className="px-ds-3 py-ds-2 align-top text-ds-muted">{grant.kind}</td>
                      <td className="px-ds-3 py-ds-2 align-top text-ds-muted">
                        {grant.expiresAt
                          ? new Date(grant.expiresAt * 1000).toLocaleString()
                          : t('approval:grant.list.expiresAt.never')}
                      </td>
                      <td className="px-ds-3 py-ds-2 align-top text-right">
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => void handleRevoke(grant.grantId)}
                          loading={isRevoking}
                          leadingIcon={<ShieldOff size={14} aria-hidden="true" />}
                          className="min-h-8 gap-ds-1 border-ds-error/30 bg-ds-error/10 px-ds-3 text-ds-xs text-ds-error hover:border-ds-error/40 hover:bg-ds-error/15 hover:text-ds-error"
                        >
                          {isRevoking
                            ? t('approval:grant.list.revoking')
                            : t('approval:grant.list.revoke')}
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </section>
  );

  function ScopeBadge({ scope }: { scope: ApprovalGrantSummary['scope'] }) {
    if (scope === 'session') {
      return (
        <Badge compact tone="accent">
          {t('approval:grant.timeoutBadge.session', { minutes: SESSION_TIMEOUT_MINUTES })}
        </Badge>
      );
    }
    return (
      <Badge compact tone="warning">
        {t('approval:grant.timeoutBadge.workspace')}
      </Badge>
    );
  }
}
