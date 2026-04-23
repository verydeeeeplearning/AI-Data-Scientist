import { useEffect, useState, type ReactNode } from 'react';
import { Download, Loader2, Shield, Users, Wallet } from 'lucide-react';
import { AccessLogPanel } from '../sharing/AccessLogPanel';
import type {
  OrganizationSnapshot,
  OrganizationSummary,
  OrgRole,
  RpcFn,
} from './types';

const ROLE_OPTIONS: OrgRole[] = ['admin', 'editor', 'viewer'];

interface OrgSettingsDraft {
  allowedProviders: string;
  maxBudgetUsdPerUser: string;
  maxBudgetUsdPerOrg: string;
  externalDataTransferAllowed: boolean;
  exportAllowed: boolean;
  connectorCreationAllowed: boolean;
}

interface InviteDraft {
  userId: string;
  displayName: string;
  role: OrgRole;
}

function buildDefaultSettingsDraft(): OrgSettingsDraft {
  return {
    allowedProviders: '',
    maxBudgetUsdPerUser: '',
    maxBudgetUsdPerOrg: '',
    externalDataTransferAllowed: true,
    exportAllowed: true,
    connectorCreationAllowed: true,
  };
}

function buildDefaultInviteDraft(): InviteDraft {
  return {
    userId: '',
    displayName: '',
    role: 'viewer',
  };
}

function formatDateInput(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function firstDayOfMonth(): string {
  const now = new Date();
  return formatDateInput(new Date(now.getFullYear(), now.getMonth(), 1));
}

function today(): string {
  return formatDateInput(new Date());
}

function toSettingsDraft(snapshot: OrganizationSnapshot | null): OrgSettingsDraft {
  if (!snapshot) {
    return buildDefaultSettingsDraft();
  }
  const settings = snapshot.organization.settings;
  return {
    allowedProviders: settings.allowedProviders.join(', '),
    maxBudgetUsdPerUser: settings.maxBudgetUsdPerUser?.toString() ?? '',
    maxBudgetUsdPerOrg: settings.maxBudgetUsdPerOrg?.toString() ?? '',
    externalDataTransferAllowed: settings.externalDataTransferAllowed,
    exportAllowed: settings.exportAllowed,
    connectorCreationAllowed: settings.connectorCreationAllowed,
  };
}

function parseCsv(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter((item, index, array) => item.length > 0 && array.indexOf(item) === index);
}

function formatUsd(value: number): string {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function downloadTextFile(filename: string, content: string, contentType: string): void {
  const blob = new Blob([content], { type: `${contentType};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-start justify-between gap-3 rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-2">
      <div>
        <div className="text-xs font-medium text-ds-text">{label}</div>
        <p className="text-[10px] text-ds-muted">{description}</p>
      </div>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1 h-4 w-4 rounded border-ds-border bg-ds-surface text-ds-accent"
      />
    </label>
  );
}

export function AdminConsole({ rpc }: { rpc: RpcFn }) {
  const [snapshot, setSnapshot] = useState<OrganizationSnapshot | null>(null);
  const [settingsDraft, setSettingsDraft] = useState<OrgSettingsDraft>(buildDefaultSettingsDraft);
  const [inviteDraft, setInviteDraft] = useState<InviteDraft>(buildDefaultInviteDraft);
  const [startDate, setStartDate] = useState(firstDayOfMonth);
  const [endDate, setEndDate] = useState(today);
  const [exportFormat, setExportFormat] = useState<'csv' | 'jsonl'>('csv');
  const [loading, setLoading] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [savingMember, setSavingMember] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadSnapshot = async () => {
    setLoading(true);
    try {
      const result = await rpc('org.get');
      const nextSnapshot = result as unknown as OrganizationSnapshot;
      setSnapshot(nextSnapshot);
      setSettingsDraft(toSettingsDraft(nextSnapshot));
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSnapshot();
  }, []);

  const handleSaveSettings = async () => {
    setSavingSettings(true);
    try {
      const result = await rpc('org.updateSettings', {
        settings: {
          allowedProviders: parseCsv(settingsDraft.allowedProviders),
          maxBudgetUsdPerUser: settingsDraft.maxBudgetUsdPerUser === ''
            ? ''
            : Number(settingsDraft.maxBudgetUsdPerUser),
          maxBudgetUsdPerOrg: settingsDraft.maxBudgetUsdPerOrg === ''
            ? ''
            : Number(settingsDraft.maxBudgetUsdPerOrg),
          externalDataTransferAllowed: settingsDraft.externalDataTransferAllowed,
          exportAllowed: settingsDraft.exportAllowed,
          connectorCreationAllowed: settingsDraft.connectorCreationAllowed,
        },
      });
      const nextSnapshot = result as unknown as OrganizationSnapshot;
      setSnapshot(nextSnapshot);
      setSettingsDraft(toSettingsDraft(nextSnapshot));
      setStatusMessage('Organization policy updated.');
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setSavingSettings(false);
    }
  };

  const applyOrganizationUpdate = (organization: OrganizationSummary) => {
    setSnapshot((current) => {
      if (!current) {
        return null;
      }
      return { ...current, organization };
    });
  };

  const handleInvite = async () => {
    if (!inviteDraft.userId.trim()) {
      setErrorMessage('User ID is required.');
      return;
    }
    setSavingMember('invite');
    try {
      const result = await rpc('org.inviteMember', {
        userId: inviteDraft.userId.trim(),
        displayName: inviteDraft.displayName.trim() || undefined,
        role: inviteDraft.role,
      });
      applyOrganizationUpdate(result.organization as OrganizationSummary);
      setInviteDraft(buildDefaultInviteDraft());
      setStatusMessage('Member updated.');
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setSavingMember(null);
    }
  };

  const handleRoleChange = async (userId: string, role: OrgRole) => {
    setSavingMember(userId);
    try {
      const result = await rpc('org.updateMemberRole', { userId, role });
      applyOrganizationUpdate(result.organization as OrganizationSummary);
      setStatusMessage(`${userId} is now ${role}.`);
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setSavingMember(null);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const result = await rpc('org.auditLogExport', {
        startDate,
        endDate,
        format: exportFormat,
      });
      downloadTextFile(
        String(result.filename ?? `audit-log.${exportFormat}`),
        String(result.content ?? ''),
        String(result.contentType ?? 'text/plain'),
      );
      setStatusMessage(`Exported ${Number(result.recordCount ?? 0)} audit records.`);
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-ds-border bg-ds-surface px-4 py-6">
        <div className="flex items-center gap-2 text-xs text-ds-muted">
          <Loader2 size={14} className="animate-spin" />
          Loading organization controls...
        </div>
      </div>
    );
  }

  if (!snapshot) {
    return (
      <div className="rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-4 text-xs text-red-200">
        <p>{errorMessage ?? 'Organization settings are unavailable.'}</p>
        <button
          onClick={() => void loadSnapshot()}
          className="mt-3 rounded-md border border-red-400/40 px-3 py-1.5 text-[11px] font-medium text-red-100"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {(statusMessage || errorMessage) && (
        <div className={`rounded-lg border px-3 py-2 text-[11px] ${
          errorMessage
            ? 'border-red-500/40 bg-red-500/10 text-red-200'
            : 'border-ds-accent/30 bg-ds-accent/10 text-ds-text'
        }`}
        >
          {errorMessage ?? statusMessage}
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-3">
        <MetricCard
          icon={<Shield size={14} />}
          label="Workspace Team"
          value={snapshot.organization.name}
          detail={`${snapshot.organization.members.length} members`}
        />
        <MetricCard
          icon={<Wallet size={14} />}
          label="Month Cost"
          value={formatUsd(snapshot.usage.totalCostUsd)}
          detail={`${snapshot.usage.totalRunCount} tracked runs`}
        />
        <MetricCard
          icon={<Users size={14} />}
          label="Allowed Providers"
          value={snapshot.organization.settings.allowedProviders.length > 0
            ? snapshot.organization.settings.allowedProviders.join(', ')
            : 'All'}
          detail={snapshot.organization.settings.externalDataTransferAllowed ? 'Remote access on' : 'Local only'}
        />
      </div>

      <div className="rounded-xl border border-ds-border bg-ds-surface p-4">
        <div className="mb-3">
          <h4 className="text-sm font-semibold text-ds-text">Organization Policy</h4>
          <p className="text-[11px] text-ds-muted">
            Provider allowlist, monthly budget caps, and export controls for runs started from this workspace.
          </p>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <label className="space-y-1">
            <span className="text-[11px] font-medium text-ds-text">Allowed Providers</span>
            <input
              type="text"
              value={settingsDraft.allowedProviders}
              onChange={(event) => setSettingsDraft((current) => ({
                ...current,
                allowedProviders: event.target.value,
              }))}
              placeholder="anthropic, openai, ollama"
              className="w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
            />
            <p className="text-[10px] text-ds-muted">Leave blank to allow every configured provider.</p>
          </label>

          <label className="space-y-1">
            <span className="text-[11px] font-medium text-ds-text">Per-User Monthly Budget</span>
            <input
              type="number"
              min={0}
              step={0.01}
              value={settingsDraft.maxBudgetUsdPerUser}
              onChange={(event) => setSettingsDraft((current) => ({
                ...current,
                maxBudgetUsdPerUser: event.target.value,
              }))}
              placeholder="Unlimited"
              className="w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
            />
            <p className="text-[10px] text-ds-muted">Clearing the field removes the cap.</p>
          </label>

          <label className="space-y-1">
            <span className="text-[11px] font-medium text-ds-text">Org Monthly Budget</span>
            <input
              type="number"
              min={0}
              step={0.01}
              value={settingsDraft.maxBudgetUsdPerOrg}
              onChange={(event) => setSettingsDraft((current) => ({
                ...current,
                maxBudgetUsdPerOrg: event.target.value,
              }))}
              placeholder="Unlimited"
              className="w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
            />
            <p className="text-[10px] text-ds-muted">Stops new runs once the month total is exhausted.</p>
          </label>
        </div>

        <div className="mt-3 grid gap-2">
          <ToggleRow
            label="External Data Transfer"
            description="Remote model providers and web search can be used for runs in this workspace."
            checked={settingsDraft.externalDataTransferAllowed}
            onChange={(checked) => setSettingsDraft((current) => ({
              ...current,
              externalDataTransferAllowed: checked,
            }))}
          />
          <ToggleRow
            label="Artifact Export"
            description="Report, notebook, slide, and deployment generators are allowed."
            checked={settingsDraft.exportAllowed}
            onChange={(checked) => setSettingsDraft((current) => ({
              ...current,
              exportAllowed: checked,
            }))}
          />
          <ToggleRow
            label="Connector Creation"
            description="Connector setup and future marketplace-style integrations are allowed."
            checked={settingsDraft.connectorCreationAllowed}
            onChange={(checked) => setSettingsDraft((current) => ({
              ...current,
              connectorCreationAllowed: checked,
            }))}
          />
        </div>

        <div className="mt-4 flex justify-end">
          <button
            onClick={() => void handleSaveSettings()}
            disabled={savingSettings}
            className="rounded-lg bg-ds-accent px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-ds-accent-hover disabled:opacity-40"
          >
            {savingSettings ? 'Saving...' : 'Save Policy'}
          </button>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.3fr_0.9fr]">
        <div className="rounded-xl border border-ds-border bg-ds-surface p-4">
          <div className="mb-3">
            <h4 className="text-sm font-semibold text-ds-text">Members</h4>
            <p className="text-[11px] text-ds-muted">Role-based access control for local operators.</p>
          </div>

          <div className="space-y-2">
            {snapshot.organization.members.map((member) => (
              <div
                key={member.userId}
                className="flex flex-col gap-2 rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-2 md:flex-row md:items-center md:justify-between"
              >
                <div>
                  <div className="text-xs font-medium text-ds-text">
                    {member.displayName || member.userId}
                  </div>
                  <div className="text-[10px] text-ds-muted">
                    {member.userId} · invited {new Date(member.invitedAt * 1000).toLocaleDateString()}
                  </div>
                </div>
                <select
                  value={member.role}
                  disabled={savingMember === member.userId}
                  onChange={(event) => void handleRoleChange(member.userId, event.target.value as OrgRole)}
                  className="rounded-lg border border-ds-border bg-ds-surface px-2 py-1.5 text-xs text-ds-text focus:border-ds-accent focus:outline-none disabled:opacity-50"
                >
                  {ROLE_OPTIONS.map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>

          <div className="mt-4 grid gap-2 md:grid-cols-[1.1fr_1fr_0.7fr_auto]">
            <input
              type="text"
              value={inviteDraft.userId}
              onChange={(event) => setInviteDraft((current) => ({ ...current, userId: event.target.value }))}
              placeholder="user-id"
              className="rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
            />
            <input
              type="text"
              value={inviteDraft.displayName}
              onChange={(event) => setInviteDraft((current) => ({ ...current, displayName: event.target.value }))}
              placeholder="Display name"
              className="rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
            />
            <select
              value={inviteDraft.role}
              onChange={(event) => setInviteDraft((current) => ({ ...current, role: event.target.value as OrgRole }))}
              className="rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
            >
              {ROLE_OPTIONS.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
            <button
              onClick={() => void handleInvite()}
              disabled={savingMember === 'invite'}
              className="rounded-lg border border-ds-border bg-ds-surface px-3 py-2 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50 disabled:opacity-40"
            >
              {savingMember === 'invite' ? 'Saving...' : 'Invite'}
            </button>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-ds-border bg-ds-surface p-4">
            <div className="mb-3">
              <h4 className="text-sm font-semibold text-ds-text">Usage Summary</h4>
              <p className="text-[11px] text-ds-muted">Current calendar month spend by operator.</p>
            </div>
            <div className="space-y-2">
              {snapshot.usage.perUser.length === 0 && (
                <div className="rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-2 text-[11px] text-ds-muted">
                  No usage recorded yet.
                </div>
              )}
              {snapshot.usage.perUser.map((item) => (
                <div key={item.actorId} className="rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs font-medium text-ds-text">{item.actorId}</span>
                    <span className="text-[11px] text-ds-text">{formatUsd(item.costUsd)}</span>
                  </div>
                  <div className="mt-1 text-[10px] text-ds-muted">
                    {item.runCount} runs
                    {Object.keys(item.providers).length > 0 && (
                      <span>{` · ${Object.entries(item.providers).map(([provider, cost]) => `${provider}: ${formatUsd(cost)}`).join(', ')}`}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-ds-border bg-ds-surface p-4">
            <div className="mb-3">
              <h4 className="text-sm font-semibold text-ds-text">Audit Export</h4>
              <p className="text-[11px] text-ds-muted">Download tool-level audit records for compliance review.</p>
            </div>
            <div className="grid gap-2">
              <div className="grid gap-2 md:grid-cols-2">
                <label className="space-y-1">
                  <span className="text-[11px] font-medium text-ds-text">Start Date</span>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(event) => setStartDate(event.target.value)}
                    className="w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-[11px] font-medium text-ds-text">End Date</span>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(event) => setEndDate(event.target.value)}
                    className="w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
                  />
                </label>
              </div>
              <div className="flex items-center justify-between gap-3">
                <select
                  value={exportFormat}
                  onChange={(event) => setExportFormat(event.target.value as 'csv' | 'jsonl')}
                  className="rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
                >
                  <option value="csv">CSV</option>
                  <option value="jsonl">JSONL</option>
                </select>
                <button
                  onClick={() => void handleExport()}
                  disabled={exporting}
                  className="inline-flex items-center gap-2 rounded-lg border border-ds-border bg-ds-surface px-3 py-2 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50 disabled:opacity-40"
                >
                  <Download size={12} />
                  {exporting ? 'Exporting...' : 'Download Audit Log'}
                </button>
              </div>
            </div>
          </div>

          <AccessLogPanel />
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  icon,
  label,
  value,
  detail,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-xl border border-ds-border bg-ds-surface p-4">
      <div className="flex items-center gap-2 text-[11px] text-ds-muted">
        <span className="text-ds-accent">{icon}</span>
        {label}
      </div>
      <div className="mt-2 text-sm font-semibold text-ds-text">{value}</div>
      <div className="mt-1 text-[10px] text-ds-muted">{detail}</div>
    </div>
  );
}
