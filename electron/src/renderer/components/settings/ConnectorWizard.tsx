import { useEffect, useMemo, useState } from 'react';

import { useI18n } from '../../stores/i18nStore';
import type { RpcFn } from './types';

type ConnectorType = 'postgres' | 'bigquery' | 'snowflake';
type PostgresAuthMode = 'password' | 'environment';
type BigQueryAuthMode = 'service_account_json' | 'environment';
type SnowflakeAuthMode = 'password' | 'environment';
type MessageTone = 'info' | 'success' | 'error';

interface ConnectorSummary {
  name: string;
  type: ConnectorType;
  label: string;
  credentialMethod: string;
  credentialRef: string;
  hasCredential: boolean;
  readOnly: boolean;
  timeoutSeconds: number;
  maxRows: number;
  options: Record<string, unknown>;
}

interface ConnectorTestResult {
  ok: boolean;
  latencyMs?: number;
  probeMessage?: string;
  errorCode?: string;
  message: string;
  details: Record<string, unknown>;
  warnings: string[];
}

interface InlineMessage {
  tone: MessageTone;
  text: string;
}

interface CommonDraft {
  name: string;
  label: string;
  credentialRef: string;
  readOnly: boolean;
  timeoutSeconds: string;
  maxRows: string;
}

interface PostgresDraft extends CommonDraft {
  authMode: PostgresAuthMode;
  host: string;
  port: string;
  database: string;
  schema: string;
  username: string;
  password: string;
  ssl: boolean;
}

interface BigQueryDraft extends CommonDraft {
  authMode: BigQueryAuthMode;
  projectId: string;
  dataset: string;
  location: string;
  billingProject: string;
  serviceAccountJson: string;
}

interface SnowflakeDraft extends CommonDraft {
  authMode: SnowflakeAuthMode;
  account: string;
  warehouse: string;
  database: string;
  schema: string;
  username: string;
  role: string;
  password: string;
}

interface DraftByType {
  postgres: PostgresDraft;
  bigquery: BigQueryDraft;
  snowflake: SnowflakeDraft;
}

interface DraftContext {
  editingConnector: ConnectorSummary | null;
}

type Translator = (
  key: string,
  vars?: Record<string, string | number | null | undefined>,
) => string;

function buildConnectorTypes(t: Translator): Array<{ type: ConnectorType; label: string; hint: string }> {
  return [
    {
      type: 'postgres',
      label: t('settings.connectorWizard.type.postgres.label'),
      hint: t('settings.connectorWizard.type.postgres.hint'),
    },
    {
      type: 'bigquery',
      label: t('settings.connectorWizard.type.bigquery.label'),
      hint: t('settings.connectorWizard.type.bigquery.hint'),
    },
    {
      type: 'snowflake',
      label: t('settings.connectorWizard.type.snowflake.label'),
      hint: t('settings.connectorWizard.type.snowflake.hint'),
    },
  ];
}

const DEFAULT_TIMEOUT_SECONDS = '30';
const DEFAULT_MAX_ROWS = '10000';
const CONNECTOR_NAME_PATTERN = /^[A-Za-z0-9_-]+$/;
const fieldClassName =
  'h-10 w-full rounded border border-ds-border bg-ds-bg px-3 text-xs text-ds-text focus:border-ds-accent focus:outline-none';

function createCommonDraft(): CommonDraft {
  return {
    name: '',
    label: '',
    credentialRef: '',
    readOnly: true,
    timeoutSeconds: DEFAULT_TIMEOUT_SECONDS,
    maxRows: DEFAULT_MAX_ROWS,
  };
}

function createDefaultDrafts(): DraftByType {
  return {
    postgres: {
      ...createCommonDraft(),
      authMode: 'password',
      host: '',
      port: '5432',
      database: '',
      schema: 'public',
      username: '',
      password: '',
      ssl: true,
    },
    bigquery: {
      ...createCommonDraft(),
      authMode: 'service_account_json',
      projectId: '',
      dataset: '',
      location: '',
      billingProject: '',
      serviceAccountJson: '',
    },
    snowflake: {
      ...createCommonDraft(),
      authMode: 'password',
      account: '',
      warehouse: '',
      database: '',
      schema: 'public',
      username: '',
      role: '',
      password: '',
    },
  };
}

export function ConnectorWizard({ rpc }: { rpc: RpcFn }) {
  const { t } = useI18n();
  const [connectors, setConnectors] = useState<ConnectorSummary[]>([]);
  const [selectedType, setSelectedType] = useState<ConnectorType>('postgres');
  const [drafts, setDrafts] = useState<DraftByType>(() => createDefaultDrafts());
  const [editingConnector, setEditingConnector] = useState<ConnectorSummary | null>(null);
  const [connectorCreationAllowed, setConnectorCreationAllowed] = useState(true);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deletingName, setDeletingName] = useState<string | null>(null);
  const [message, setMessage] = useState<InlineMessage | null>(null);
  const [testResult, setTestResult] = useState<ConnectorTestResult | null>(null);
  const [testedFingerprint, setTestedFingerprint] = useState<string | null>(null);

  const connectorTypes = useMemo(() => buildConnectorTypes(t), [t]);
  const currentDraft = drafts[selectedType];
  const currentFingerprint = useMemo(
    () => JSON.stringify({ type: selectedType, draft: currentDraft }),
    [currentDraft, selectedType]
  );
  const validationErrors = useMemo(
    () => validateDraft(selectedType, currentDraft, { editingConnector }, t),
    [currentDraft, editingConnector, selectedType, t]
  );
  const isTestFresh = testedFingerprint === currentFingerprint;
  const canSave = connectorCreationAllowed && validationErrors.length === 0 && isTestFresh && testResult?.ok;
  const usesStoredSecret = shouldReuseStoredSecret(selectedType, currentDraft, editingConnector);

  useEffect(() => {
    void refreshConnectors();
  }, []);

  const refreshConnectors = async () => {
    setLoading(true);
    try {
      const result = await rpc('connector.list');
      const rawConnectors = Array.isArray(result.connectors) ? result.connectors : [];
      setConnectors(rawConnectors.map(parseConnectorSummary));
      setConnectorCreationAllowed(Boolean(result.connectorCreationAllowed ?? true));
    } catch (error) {
      setMessage({
        tone: 'error',
        text: error instanceof Error ? error.message : t('settings.connectorWizard.message.load_failed'),
      });
    } finally {
      setLoading(false);
    }
  };

  const updateDraft = <K extends ConnectorType>(
    type: K,
    updater: (draft: DraftByType[K]) => DraftByType[K]
  ) => {
    setDrafts((current) => ({
      ...current,
      [type]: updater(current[type]),
    }));
  };

  const resetDraftForType = (type: ConnectorType) => {
    const defaults = createDefaultDrafts()[type];
    updateDraft(type, () => defaults);
    if (selectedType === type) {
      setEditingConnector(null);
      setTestResult(null);
      setTestedFingerprint(null);
    }
  };

  const handleStartNew = (type: ConnectorType = selectedType) => {
    setSelectedType(type);
    resetDraftForType(type);
    setMessage({
      tone: 'info',
      text: t('settings.connectorWizard.message.prepare_new', {
        type: connectorTypeLabel(type, t),
      }),
    });
  };

  const handleEdit = (connector: ConnectorSummary) => {
    setSelectedType(connector.type);
    updateDraft(connector.type, () => draftFromSummary(connector));
    setEditingConnector(connector);
    setTestResult(null);
    setTestedFingerprint(null);
    setMessage({
      tone: 'info',
      text:
        connector.hasCredential && connector.credentialMethod === 'secret_manager'
          ? t('settings.connectorWizard.message.edit_reuse_secret')
          : t('settings.connectorWizard.message.edit_connector', {
              name: connector.label || connector.name,
            }),
    });
  };

  const handleDelete = async (connector: ConnectorSummary) => {
    const confirmed = window.confirm(
      t('settings.connectorWizard.message.confirm_delete', {
        name: connector.label || connector.name,
      }),
    );
    if (!confirmed) {
      return;
    }

    setDeletingName(connector.name);
    setMessage(null);
    try {
      await rpc('connector.delete', { name: connector.name });
      setConnectors((current) => current.filter((entry) => entry.name !== connector.name));
      if (editingConnector?.name === connector.name) {
        resetDraftForType(connector.type);
      }
      setMessage({
        tone: 'success',
        text: t('settings.connectorWizard.message.deleted', {
          name: connector.label || connector.name,
        }),
      });
      await refreshConnectors();
    } catch (error) {
      setMessage({
        tone: 'error',
        text: error instanceof Error ? error.message : t('settings.connectorWizard.message.delete_failed'),
      });
    } finally {
      setDeletingName(null);
    }
  };

  const handleTest = async () => {
    const errors = validateDraft(selectedType, currentDraft, { editingConnector }, t);
    if (errors.length > 0) {
      setMessage({ tone: 'error', text: errors[0] });
      return;
    }

    setTesting(true);
    setMessage(null);
    setTestResult(null);
    try {
      const payload = buildPayload(selectedType, currentDraft, { editingConnector });
      const result = await rpc('connector.test', payload, { timeoutMs: 60_000 });
      const parsed = parseTestResult(result, t);
      setTestResult(parsed);
      if (parsed.ok) {
        setTestedFingerprint(currentFingerprint);
        setMessage({
          tone: 'success',
          text: t('settings.connectorWizard.message.test_passed', {
            type: connectorTypeLabel(selectedType, t),
          }),
        });
      } else {
        setTestedFingerprint(null);
        setMessage({
          tone: 'error',
          text: parsed.message,
        });
      }
    } catch (error) {
      setTestedFingerprint(null);
      setMessage({
        tone: 'error',
        text: error instanceof Error ? error.message : t('settings.connectorWizard.message.test_failed_default'),
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    const errors = validateDraft(selectedType, currentDraft, { editingConnector }, t);
    if (errors.length > 0) {
      setMessage({ tone: 'error', text: errors[0] });
      return;
    }
    if (!isTestFresh || !testResult?.ok) {
      setMessage({
        tone: 'error',
        text: t('settings.connectorWizard.message.save_requires_test'),
      });
      return;
    }

    setSaving(true);
    setMessage(null);
    try {
      const payload = buildPayload(selectedType, currentDraft, { editingConnector });
      const result = await rpc('connector.save', payload);
      const saved = parseConnectorSummary(result.connector);
      setEditingConnector(saved);
      updateDraft(saved.type, () => draftFromSummary(saved));
      setMessage({
        tone: 'success',
        text: t('settings.connectorWizard.message.saved_ready', {
          name: saved.label || saved.name,
        }),
      });
      await refreshConnectors();
    } catch (error) {
      setMessage({
        tone: 'error',
        text: error instanceof Error ? error.message : t('settings.connectorWizard.message.save_failed'),
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="connector-wizard">
      <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-xs font-medium text-ds-text">
              {t('settings.connectorWizard.title')}
            </div>
            <p className="mt-1 text-[11px] leading-5 text-ds-muted">
              {t('settings.connectorWizard.description')}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => void refreshConnectors()}
              disabled={loading}
              data-testid="connector-list-refresh"
              className="rounded-lg border border-ds-border bg-ds-surface px-3 py-1.5 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50 disabled:opacity-40"
            >
              {loading
                ? t('settings.connectorWizard.action.refreshing')
                : t('settings.connectorWizard.action.refresh')}
            </button>
            <button
              onClick={() => handleStartNew(selectedType)}
              disabled={!connectorCreationAllowed}
              className="rounded-lg border border-ds-border bg-ds-surface px-3 py-1.5 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {t('settings.connectorWizard.action.new')}
            </button>
          </div>
        </div>
        {!connectorCreationAllowed && (
          <div className="mt-3 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-[11px] text-amber-200">
            {t('settings.connectorWizard.policy_disabled')}
          </div>
        )}
      </div>

      {message && <MessageBanner tone={message.tone}>{message.text}</MessageBanner>}

      <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
        <div className="text-xs font-medium text-ds-text">
          {t('settings.connectorWizard.saved.title')}
        </div>
        <div className="mt-1 text-[11px] text-ds-muted">
          {connectors.length === 0
            ? t('settings.connectorWizard.saved.empty')
            : t('settings.connectorWizard.saved.count', { count: connectors.length })}
        </div>

        <div className="mt-3 space-y-2">
          {loading && (
            <div className="rounded-lg border border-ds-border/60 bg-ds-surface px-3 py-2 text-[11px] text-ds-muted">
              {t('settings.connectorWizard.saved.loading')}
            </div>
          )}
          {!loading && connectors.length === 0 && (
            <div className="rounded-lg border border-ds-border/60 bg-ds-surface px-3 py-2 text-[11px] text-ds-muted">
              {t('settings.connectorWizard.saved.empty_help')}
            </div>
          )}
          {!loading &&
            connectors.map((connector) => {
              const isEditing = editingConnector?.name === connector.name;
              return (
                <div
                  key={connector.name}
                  data-testid={`connector-list-row-${connector.name}`}
                  className={`rounded-lg border px-3 py-3 ${
                    isEditing
                      ? 'border-ds-accent/50 bg-ds-accent/5'
                      : 'border-ds-border/60 bg-ds-surface'
                  }`}
                >
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-medium text-ds-text">
                          {connector.label || connector.name}
                        </span>
                        <Badge>{connectorTypeLabel(connector.type, t)}</Badge>
                        <Badge tone={connector.hasCredential ? 'success' : 'muted'}>
                          {connector.hasCredential
                            ? t('settings.connectorWizard.badge.credential_ready')
                            : t('settings.connectorWizard.badge.no_secret')}
                        </Badge>
                        <Badge tone="muted">{t('settings.connectorWizard.badge.read_only')}</Badge>
                      </div>
                      <div className="mt-1 text-[11px] text-ds-muted">
                        {connector.name} / {describeConnectorTarget(connector, t)}
                      </div>
                      <div className="mt-1 text-[11px] text-ds-muted/90">
                        {connector.credentialMethod === 'env'
                          ? connector.credentialRef
                            ? t('settings.connectorWizard.saved.credential.env_ref', {
                                credentialRef: connector.credentialRef,
                              })
                            : t('settings.connectorWizard.saved.credential.env_default')
                          : t('settings.connectorWizard.saved.credential.secret_manager')}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleEdit(connector)}
                        data-testid={`connector-list-edit-${connector.name}`}
                        className="rounded-lg border border-ds-border bg-ds-bg px-3 py-1.5 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50"
                      >
                        {t('settings.connectorWizard.action.edit')}
                      </button>
                      <button
                        onClick={() => void handleDelete(connector)}
                        disabled={!connectorCreationAllowed || deletingName === connector.name}
                        data-testid={`connector-list-delete-${connector.name}`}
                        className="rounded-lg border border-ds-border bg-ds-bg px-3 py-1.5 text-xs font-medium text-ds-text transition-colors hover:border-ds-error/50 hover:text-ds-error disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {deletingName === connector.name
                          ? t('settings.connectorWizard.action.deleting')
                          : t('settings.connectorWizard.action.delete')}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
        <div className="flex flex-wrap gap-2">
          {connectorTypes.map((entry) => {
            const active = selectedType === entry.type;
            return (
              <button
                key={entry.type}
                onClick={() => {
                  setSelectedType(entry.type);
                  setTestResult(null);
                  setTestedFingerprint(null);
                  setMessage(null);
                }}
                data-testid={`connector-wizard-type-${entry.type}`}
                className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                  active
                    ? 'border-ds-accent/60 bg-ds-accent/10 text-ds-text'
                    : 'border-ds-border bg-ds-surface text-ds-muted hover:border-ds-accent/40 hover:text-ds-text'
                }`}
              >
                <div className="text-xs font-medium">{entry.label}</div>
                <div className="mt-1 text-[10px] leading-4">{entry.hint}</div>
              </button>
            );
          })}
        </div>

        <div className="mt-4 rounded-lg border border-ds-border/60 bg-ds-surface p-3">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="text-xs font-medium text-ds-text">
                {editingConnector?.name === currentDraft.name && editingConnector?.type === selectedType
                  ? t('settings.connectorWizard.form.edit_title', {
                      name: editingConnector.label || editingConnector.name,
                    })
                  : t('settings.connectorWizard.form.new_title', {
                      type: connectorTypeLabel(selectedType, t),
                    })}
              </div>
              <div className="text-[11px] text-ds-muted">
                {t('settings.connectorWizard.form.description')}
              </div>
            </div>
            <button
              onClick={() => handleStartNew(selectedType)}
              className="rounded-lg border border-ds-border bg-ds-bg px-3 py-1.5 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50"
            >
              {t('settings.connectorWizard.action.reset_form')}
            </button>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <LabeledField label={t('settings.connectorWizard.field.connector_name')} required>
              <input
                type="text"
                value={currentDraft.name}
                onChange={(event) =>
                  updateDraft(selectedType, (draft) => ({ ...draft, name: event.target.value }))
                }
                placeholder="analytics_prod"
                data-testid="connector-wizard-field-name"
                className={fieldClassName}
              />
            </LabeledField>
            <LabeledField label={t('settings.connectorWizard.field.display_label')}>
              <input
                type="text"
                value={currentDraft.label}
                onChange={(event) =>
                  updateDraft(selectedType, (draft) => ({ ...draft, label: event.target.value }))
                }
                placeholder={t('settings.connectorWizard.field.display_label_placeholder', {
                  type: connectorTypeLabel(selectedType, t),
                })}
                data-testid="connector-wizard-field-label"
                className={fieldClassName}
              />
            </LabeledField>
            <LabeledField label={t('settings.connectorWizard.field.timeout')} required>
              <input
                type="number"
                min={1}
                value={currentDraft.timeoutSeconds}
                onChange={(event) =>
                  updateDraft(selectedType, (draft) => ({
                    ...draft,
                    timeoutSeconds: event.target.value,
                  }))
                }
                data-testid="connector-wizard-field-timeout"
                className={fieldClassName}
              />
            </LabeledField>
            <LabeledField label={t('settings.connectorWizard.field.max_rows')} required>
              <input
                type="number"
                min={1}
                value={currentDraft.maxRows}
                onChange={(event) =>
                  updateDraft(selectedType, (draft) => ({ ...draft, maxRows: event.target.value }))
                }
                data-testid="connector-wizard-field-max-rows"
                className={fieldClassName}
              />
            </LabeledField>
          </div>

          <div className="mt-4 rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs font-medium text-ds-text">
                  {t('settings.connectorWizard.read_only.title')}
                </div>
                <div className="text-[11px] text-ds-muted">
                  {t('settings.connectorWizard.read_only.description')}
                </div>
              </div>
              <label className="flex items-center gap-2 text-[11px] text-ds-muted">
                <input type="checkbox" checked={currentDraft.readOnly} readOnly />
                {t('settings.connectorWizard.read_only.locked')}
              </label>
            </div>
          </div>

          {selectedType === 'postgres' && (
            <PostgresFields
              draft={drafts.postgres}
              onChange={(updater) => updateDraft('postgres', updater)}
              showStoredSecretHint={usesStoredSecret}
              t={t}
            />
          )}
          {selectedType === 'bigquery' && (
            <BigQueryFields
              draft={drafts.bigquery}
              onChange={(updater) => updateDraft('bigquery', updater)}
              showStoredSecretHint={usesStoredSecret}
              t={t}
            />
          )}
          {selectedType === 'snowflake' && (
            <SnowflakeFields
              draft={drafts.snowflake}
              onChange={(updater) => updateDraft('snowflake', updater)}
              showStoredSecretHint={usesStoredSecret}
              t={t}
            />
          )}

          {validationErrors.length > 0 && (
            <div
              data-testid="connector-wizard-error"
              className="mt-4 rounded-lg border border-ds-error/30 bg-ds-error/10 px-3 py-2 text-[11px] text-ds-error"
            >
              {validationErrors[0]}
            </div>
          )}

          {testResult && (
            <div data-testid="connector-wizard-test-result" className="mt-4 rounded-lg border border-ds-border/60 bg-ds-bg p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-ds-text">
                  {t('settings.connectorWizard.test.title')}
                </span>
                <Badge tone={testResult.ok ? 'success' : 'error'}>
                  {testResult.ok
                    ? t('settings.connectorWizard.test.passed')
                    : t('settings.connectorWizard.test.failed')}
                </Badge>
                {typeof testResult.latencyMs === 'number' && (
                  <Badge tone="muted">{testResult.latencyMs}ms</Badge>
                )}
                {!isTestFresh && (
                  <Badge tone="warning">{t('settings.connectorWizard.test.retest_required')}</Badge>
                )}
              </div>
              <div className="mt-2 text-[11px] text-ds-muted">
                {testResult.probeMessage ?? testResult.message}
              </div>
              {Object.keys(testResult.details).length > 0 && (
                <div className="mt-2 rounded border border-ds-border/50 bg-ds-surface px-3 py-2 text-[11px] text-ds-muted">
                  {normalizeDetailSummary(formatDetails(testResult.details))}
                </div>
              )}
              {testResult.warnings.length > 0 && (
                <div className="mt-2 rounded border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-[11px] text-amber-200">
                  {testResult.warnings.join(' ')}
                </div>
              )}
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              onClick={() => void handleTest()}
              disabled={!connectorCreationAllowed || testing || validationErrors.length > 0}
              data-testid="connector-wizard-test"
              className="rounded-lg border border-ds-border bg-ds-bg px-3 py-1.5 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {testing
                ? t('settings.connectorWizard.action.testing')
                : t('settings.connectorWizard.action.test')}
            </button>
            <button
              onClick={() => void handleSave()}
              disabled={saving || !canSave}
              data-testid="connector-wizard-save"
              className="rounded-lg bg-ds-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-ds-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
            >
              {saving
                ? t('settings.connectorWizard.action.saving')
                : editingConnector
                  ? t('settings.connectorWizard.action.save_changes')
                  : t('settings.connectorWizard.action.save_connector')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PostgresFields({
  draft,
  onChange,
  showStoredSecretHint,
  t,
}: {
  draft: PostgresDraft;
  onChange: (updater: (draft: PostgresDraft) => PostgresDraft) => void;
  showStoredSecretHint: boolean;
  t: Translator;
}) {
  return (
    <div className="mt-4 space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <LabeledField label={t('settings.connectorWizard.postgres.host')} required>
          <input
            type="text"
            value={draft.host}
            onChange={(event) => onChange((current) => ({ ...current, host: event.target.value }))}
            placeholder="localhost"
            data-testid="connector-wizard-field-host"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label={t('settings.connectorWizard.postgres.port')}>
          <input
            type="number"
            value={draft.port}
            onChange={(event) => onChange((current) => ({ ...current, port: event.target.value }))}
            placeholder="5432"
            data-testid="connector-wizard-field-port"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label={t('settings.connectorWizard.postgres.database')} required>
          <input
            type="text"
            value={draft.database}
            onChange={(event) =>
              onChange((current) => ({ ...current, database: event.target.value }))
            }
            placeholder="analytics"
            data-testid="connector-wizard-field-database"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label={t('settings.connectorWizard.postgres.schema')}>
          <input
            type="text"
            value={draft.schema}
            onChange={(event) => onChange((current) => ({ ...current, schema: event.target.value }))}
            placeholder="public"
            data-testid="connector-wizard-field-schema"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label={t('settings.connectorWizard.postgres.username')}>
          <input
            type="text"
            value={draft.username}
            onChange={(event) =>
              onChange((current) => ({ ...current, username: event.target.value }))
            }
            placeholder="readonly_user"
            data-testid="connector-wizard-field-user"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label={t('settings.connectorWizard.postgres.ssl')}>
          <label className="flex h-10 items-center gap-2 rounded border border-ds-border bg-ds-bg px-3 text-xs text-ds-text">
            <input
              type="checkbox"
              checked={draft.ssl}
              onChange={(event) => onChange((current) => ({ ...current, ssl: event.target.checked }))}
              data-testid="connector-wizard-field-ssl"
            />
            {t('settings.connectorWizard.postgres.require_ssl')}
          </label>
        </LabeledField>
      </div>

      <AuthModePicker<PostgresAuthMode>
        label={t('settings.connectorWizard.auth_source')}
        value={draft.authMode}
        options={[
          {
            value: 'password',
            label: t('settings.connectorWizard.postgres.auth.password.label'),
            description: t('settings.connectorWizard.postgres.auth.password.description'),
          },
          {
            value: 'environment',
            label: t('settings.connectorWizard.postgres.auth.environment.label'),
            description: t('settings.connectorWizard.postgres.auth.environment.description'),
          },
        ]}
        onChange={(value) => onChange((current) => ({ ...current, authMode: value }))}
      />

      {draft.authMode === 'password' ? (
        <LabeledField label={t('settings.connectorWizard.postgres.password')} required={!showStoredSecretHint}>
          <input
            type="password"
            value={draft.password}
            onChange={(event) => onChange((current) => ({ ...current, password: event.target.value }))}
            placeholder={
              showStoredSecretHint
                ? t('settings.connectorWizard.secret.reuse_placeholder')
                : t('settings.connectorWizard.secret.enter_password')
            }
            data-testid="connector-wizard-field-secret"
            className={fieldClassName}
          />
        </LabeledField>
      ) : (
        <LabeledField label={t('settings.connectorWizard.credential_env_var')}>
          <input
            type="text"
            value={draft.credentialRef}
            onChange={(event) =>
              onChange((current) => ({ ...current, credentialRef: event.target.value }))
            }
            placeholder={t('settings.connectorWizard.postgres.env_placeholder')}
            data-testid="connector-wizard-field-credential-ref"
            className={fieldClassName}
          />
        </LabeledField>
      )}

      {showStoredSecretHint && (
        <div className="rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-2 text-[11px] text-ds-muted">
          {t('settings.connectorWizard.postgres.reuse_hint')}
        </div>
      )}
    </div>
  );
}

function BigQueryFields({
  draft,
  onChange,
  showStoredSecretHint,
  t,
}: {
  draft: BigQueryDraft;
  onChange: (updater: (draft: BigQueryDraft) => BigQueryDraft) => void;
  showStoredSecretHint: boolean;
  t: Translator;
}) {
  return (
    <div className="mt-4 space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <LabeledField label={t('settings.connectorWizard.bigquery.project_id')} required>
          <input
            type="text"
            value={draft.projectId}
            onChange={(event) =>
              onChange((current) => ({ ...current, projectId: event.target.value }))
            }
            placeholder="my-analytics-project"
            data-testid="connector-wizard-field-project-id"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label={t('settings.connectorWizard.bigquery.dataset')}>
          <input
            type="text"
            value={draft.dataset}
            onChange={(event) => onChange((current) => ({ ...current, dataset: event.target.value }))}
            placeholder="analytics"
            data-testid="connector-wizard-field-dataset"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label={t('settings.connectorWizard.bigquery.location')}>
          <input
            type="text"
            value={draft.location}
            onChange={(event) =>
              onChange((current) => ({ ...current, location: event.target.value }))
            }
            placeholder="asia-northeast3"
            data-testid="connector-wizard-field-location"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label={t('settings.connectorWizard.bigquery.billing_project')}>
          <input
            type="text"
            value={draft.billingProject}
            onChange={(event) =>
              onChange((current) => ({ ...current, billingProject: event.target.value }))
            }
            placeholder="billing-project-id"
            data-testid="connector-wizard-field-billing-project"
            className={fieldClassName}
          />
        </LabeledField>
      </div>

      <AuthModePicker<BigQueryAuthMode>
        label={t('settings.connectorWizard.auth_source')}
        value={draft.authMode}
        options={[
          {
            value: 'service_account_json',
            label: t('settings.connectorWizard.bigquery.auth.service_account_json.label'),
            description: t('settings.connectorWizard.bigquery.auth.service_account_json.description'),
          },
          {
            value: 'environment',
            label: t('settings.connectorWizard.bigquery.auth.environment.label'),
            description: t('settings.connectorWizard.bigquery.auth.environment.description'),
          },
        ]}
        onChange={(value) => onChange((current) => ({ ...current, authMode: value }))}
      />

      {draft.authMode === 'service_account_json' ? (
        <LabeledField label={t('settings.connectorWizard.bigquery.service_account_json')} required={!showStoredSecretHint}>
          <textarea
            value={draft.serviceAccountJson}
            onChange={(event) =>
              onChange((current) => ({ ...current, serviceAccountJson: event.target.value }))
            }
            placeholder={
              showStoredSecretHint
                ? t('settings.connectorWizard.secret.reuse_placeholder')
                : '{ "type": "service_account", ... }'
            }
            rows={8}
            data-testid="connector-wizard-field-secret"
            className={`${fieldClassName} min-h-[10rem] py-2 font-mono`}
          />
        </LabeledField>
      ) : (
        <LabeledField label={t('settings.connectorWizard.credential_env_var')}>
          <input
            type="text"
            value={draft.credentialRef}
            onChange={(event) =>
              onChange((current) => ({ ...current, credentialRef: event.target.value }))
            }
            placeholder={t('settings.connectorWizard.bigquery.env_placeholder')}
            data-testid="connector-wizard-field-credential-ref"
            className={fieldClassName}
          />
        </LabeledField>
      )}

      {showStoredSecretHint && (
        <div className="rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-2 text-[11px] text-ds-muted">
          {t('settings.connectorWizard.bigquery.reuse_hint')}
        </div>
      )}
    </div>
  );
}

function SnowflakeFields({
  draft,
  onChange,
  showStoredSecretHint,
  t,
}: {
  draft: SnowflakeDraft;
  onChange: (updater: (draft: SnowflakeDraft) => SnowflakeDraft) => void;
  showStoredSecretHint: boolean;
  t: Translator;
}) {
  return (
    <div className="mt-4 space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <LabeledField label={t('settings.connectorWizard.snowflake.account')} required>
          <input
            type="text"
            value={draft.account}
            onChange={(event) =>
              onChange((current) => ({ ...current, account: event.target.value }))
            }
            placeholder="xy12345.ap-northeast-2.aws"
            data-testid="connector-wizard-field-account"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label={t('settings.connectorWizard.snowflake.warehouse')} required>
          <input
            type="text"
            value={draft.warehouse}
            onChange={(event) =>
              onChange((current) => ({ ...current, warehouse: event.target.value }))
            }
            placeholder="ANALYTICS_WH"
            data-testid="connector-wizard-field-warehouse"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label={t('settings.connectorWizard.snowflake.database')} required>
          <input
            type="text"
            value={draft.database}
            onChange={(event) =>
              onChange((current) => ({ ...current, database: event.target.value }))
            }
            placeholder="ANALYTICS"
            data-testid="connector-wizard-field-database"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label={t('settings.connectorWizard.snowflake.schema')}>
          <input
            type="text"
            value={draft.schema}
            onChange={(event) => onChange((current) => ({ ...current, schema: event.target.value }))}
            placeholder="PUBLIC"
            data-testid="connector-wizard-field-schema"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label={t('settings.connectorWizard.snowflake.username')} required>
          <input
            type="text"
            value={draft.username}
            onChange={(event) =>
              onChange((current) => ({ ...current, username: event.target.value }))
            }
            placeholder="readonly_user"
            data-testid="connector-wizard-field-user"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label={t('settings.connectorWizard.snowflake.role')}>
          <input
            type="text"
            value={draft.role}
            onChange={(event) => onChange((current) => ({ ...current, role: event.target.value }))}
            placeholder="ANALYST"
            data-testid="connector-wizard-field-role"
            className={fieldClassName}
          />
        </LabeledField>
      </div>

      <AuthModePicker<SnowflakeAuthMode>
        label={t('settings.connectorWizard.auth_source')}
        value={draft.authMode}
        options={[
          {
            value: 'password',
            label: t('settings.connectorWizard.snowflake.auth.password.label'),
            description: t('settings.connectorWizard.snowflake.auth.password.description'),
          },
          {
            value: 'environment',
            label: t('settings.connectorWizard.snowflake.auth.environment.label'),
            description: t('settings.connectorWizard.snowflake.auth.environment.description'),
          },
        ]}
        onChange={(value) => onChange((current) => ({ ...current, authMode: value }))}
      />

      {draft.authMode === 'password' ? (
        <LabeledField label={t('settings.connectorWizard.snowflake.password')} required={!showStoredSecretHint}>
          <input
            type="password"
            value={draft.password}
            onChange={(event) => onChange((current) => ({ ...current, password: event.target.value }))}
            placeholder={
              showStoredSecretHint
                ? t('settings.connectorWizard.secret.reuse_placeholder')
                : t('settings.connectorWizard.secret.enter_password')
            }
            data-testid="connector-wizard-field-secret"
            className={fieldClassName}
          />
        </LabeledField>
      ) : (
        <LabeledField label={t('settings.connectorWizard.credential_env_var')}>
          <input
            type="text"
            value={draft.credentialRef}
            onChange={(event) =>
              onChange((current) => ({ ...current, credentialRef: event.target.value }))
            }
            placeholder={t('settings.connectorWizard.snowflake.env_placeholder')}
            data-testid="connector-wizard-field-credential-ref"
            className={fieldClassName}
          />
        </LabeledField>
      )}

      {showStoredSecretHint && (
        <div className="rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-2 text-[11px] text-ds-muted">
          {t('settings.connectorWizard.snowflake.reuse_hint')}
        </div>
      )}
    </div>
  );
}

function LabeledField({
  label,
  required = false,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-1 text-[11px] font-medium text-ds-muted">
        {label}
        {required ? ' *' : ''}
      </div>
      {children}
    </label>
  );
}

function MessageBanner({
  tone,
  children,
}: {
  tone: MessageTone;
  children: React.ReactNode;
}) {
  const className =
    tone === 'success'
      ? 'border-ds-success/30 bg-ds-success/10 text-ds-success'
      : tone === 'error'
        ? 'border-ds-error/30 bg-ds-error/10 text-ds-error'
        : 'border-ds-border/60 bg-ds-surface text-ds-muted';
  return <div className={`rounded-lg border px-3 py-2 text-[11px] ${className}`}>{children}</div>;
}

function Badge({
  children,
  tone = 'muted',
}: {
  children: React.ReactNode;
  tone?: 'muted' | 'success' | 'warning' | 'error';
}) {
  const className =
    tone === 'success'
      ? 'bg-ds-success/10 text-ds-success'
      : tone === 'warning'
        ? 'bg-amber-400/15 text-amber-200'
        : tone === 'error'
          ? 'bg-ds-error/10 text-ds-error'
          : 'bg-ds-border/40 text-ds-muted';
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${className}`}>
      {children}
    </span>
  );
}

function AuthModePicker<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string; description: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div className="rounded-lg border border-ds-border/60 bg-ds-bg p-3">
      <div className="text-[11px] font-medium text-ds-muted">{label}</div>
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        {options.map((option) => {
          const active = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange(option.value)}
              className={`rounded-lg border p-3 text-left transition-colors ${
                active
                  ? 'border-ds-accent/60 bg-ds-accent/10'
                  : 'border-ds-border bg-ds-surface hover:border-ds-accent/40'
              }`}
            >
              <div className="text-xs font-medium text-ds-text">{option.label}</div>
              <div className="mt-1 text-[11px] leading-5 text-ds-muted">{option.description}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function draftFromSummary(connector: ConnectorSummary): DraftByType[typeof connector.type] {
  const common = {
    name: connector.name,
    label: connector.label,
    credentialRef: connector.credentialMethod === 'env' ? connector.credentialRef : '',
    readOnly: connector.readOnly,
    timeoutSeconds: String(connector.timeoutSeconds),
    maxRows: String(connector.maxRows),
  };

  if (connector.type === 'postgres') {
    return {
      ...common,
      authMode: connector.credentialMethod === 'env' ? 'environment' : 'password',
      host: optionAsString(connector.options, 'host'),
      port: optionAsString(connector.options, 'port', '5432'),
      database: optionAsString(connector.options, 'database'),
      schema: optionAsString(connector.options, 'schema', 'public'),
      username: optionAsString(connector.options, 'username'),
      password: '',
      ssl: optionAsBool(connector.options, 'ssl', false),
    };
  }

  if (connector.type === 'bigquery') {
    return {
      ...common,
      authMode: connector.credentialMethod === 'env' ? 'environment' : 'service_account_json',
      projectId: optionAsString(connector.options, 'project_id'),
      dataset: optionAsString(connector.options, 'dataset'),
      location: optionAsString(connector.options, 'location'),
      billingProject: optionAsString(connector.options, 'billing_project'),
      serviceAccountJson: '',
    };
  }

  return {
    ...common,
    authMode: connector.credentialMethod === 'env' ? 'environment' : 'password',
    account: optionAsString(connector.options, 'account', optionAsString(connector.options, 'host')),
    warehouse: optionAsString(connector.options, 'warehouse'),
    database: optionAsString(connector.options, 'database'),
    schema: optionAsString(connector.options, 'schema', 'public'),
    username: optionAsString(connector.options, 'username'),
    role: optionAsString(connector.options, 'role'),
    password: '',
  };
}

function buildPayload(
  type: ConnectorType,
  draft: DraftByType[ConnectorType],
  context: DraftContext
): Record<string, unknown> {
  const common = buildCommonPayload(type, draft);

  if (type === 'postgres') {
    const postgres = draft as PostgresDraft;
    const credentialPayload = buildPostgresCredentialPayload(postgres, context);
    return {
      ...common,
      options: {
        host: postgres.host.trim(),
        ...(postgres.port.trim() ? { port: Number(postgres.port) } : {}),
        database: postgres.database.trim(),
        ...(postgres.schema.trim() ? { schema: postgres.schema.trim() } : {}),
        ...(postgres.username.trim() ? { username: postgres.username.trim() } : {}),
        ssl: postgres.ssl,
      },
      credentialMethod: postgres.authMode === 'password' ? 'secret_manager' : 'env',
      credentialRef: postgres.authMode === 'environment' ? postgres.credentialRef.trim() : '',
      ...(credentialPayload ? { credentialPayload } : {}),
    };
  }

  if (type === 'bigquery') {
    const bigquery = draft as BigQueryDraft;
    const credentialPayload = buildBigQueryCredentialPayload(bigquery, context);
    return {
      ...common,
      options: {
        project_id: bigquery.projectId.trim(),
        ...(bigquery.dataset.trim() ? { dataset: bigquery.dataset.trim() } : {}),
        ...(bigquery.location.trim() ? { location: bigquery.location.trim() } : {}),
        ...(bigquery.billingProject.trim()
          ? { billing_project: bigquery.billingProject.trim() }
          : {}),
      },
      credentialMethod: bigquery.authMode === 'service_account_json' ? 'secret_manager' : 'env',
      credentialRef: bigquery.authMode === 'environment' ? bigquery.credentialRef.trim() : '',
      ...(credentialPayload ? { credentialPayload } : {}),
    };
  }

  const snowflake = draft as SnowflakeDraft;
  const credentialPayload = buildSnowflakeCredentialPayload(snowflake, context);
  return {
    ...common,
    options: {
      account: snowflake.account.trim(),
      warehouse: snowflake.warehouse.trim(),
      database: snowflake.database.trim(),
      ...(snowflake.schema.trim() ? { schema: snowflake.schema.trim() } : {}),
      username: snowflake.username.trim(),
      ...(snowflake.role.trim() ? { role: snowflake.role.trim() } : {}),
    },
    credentialMethod: snowflake.authMode === 'password' ? 'secret_manager' : 'env',
    credentialRef: snowflake.authMode === 'environment' ? snowflake.credentialRef.trim() : '',
    ...(credentialPayload ? { credentialPayload } : {}),
  };
}

function buildCommonPayload(
  type: ConnectorType,
  draft: DraftByType[ConnectorType]
): Record<string, unknown> {
  return {
    name: draft.name.trim(),
    type,
    label: draft.label.trim(),
    readOnly: true,
    timeoutSeconds: parsePositiveInteger(draft.timeoutSeconds, 30),
    maxRows: parsePositiveInteger(draft.maxRows, 10_000),
  };
}

function buildPostgresCredentialPayload(
  draft: PostgresDraft,
  context: DraftContext
): Record<string, unknown> | null {
  if (draft.authMode !== 'password') {
    return null;
  }
  const password = draft.password.trim();
  if (!password && shouldReuseStoredSecret('postgres', draft, context.editingConnector)) {
    return null;
  }
  return password ? { kind: 'password', password } : null;
}

function buildBigQueryCredentialPayload(
  draft: BigQueryDraft,
  context: DraftContext
): Record<string, unknown> | null {
  if (draft.authMode !== 'service_account_json') {
    return null;
  }
  const serviceAccountJson = draft.serviceAccountJson.trim();
  if (
    !serviceAccountJson
    && shouldReuseStoredSecret('bigquery', draft, context.editingConnector)
  ) {
    return null;
  }
  return serviceAccountJson ? { kind: 'service_account_json', json: serviceAccountJson } : null;
}

function buildSnowflakeCredentialPayload(
  draft: SnowflakeDraft,
  context: DraftContext
): Record<string, unknown> | null {
  if (draft.authMode !== 'password') {
    return null;
  }
  const password = draft.password.trim();
  if (!password && shouldReuseStoredSecret('snowflake', draft, context.editingConnector)) {
    return null;
  }
  return password ? { kind: 'password', password } : null;
}

function validateDraft(
  type: ConnectorType,
  draft: DraftByType[ConnectorType],
  context: DraftContext,
  t: Translator,
): string[] {
  const errors: string[] = [];
  if (!draft.name.trim()) {
    errors.push(t('settings.connectorWizard.validation.connector_name_required'));
  } else if (!CONNECTOR_NAME_PATTERN.test(draft.name.trim())) {
    errors.push(t('settings.connectorWizard.validation.connector_name_pattern'));
  }

  if (!parsePositiveIntegerOrNull(draft.timeoutSeconds)) {
    errors.push(t('settings.connectorWizard.validation.timeout_positive'));
  }
  if (!parsePositiveIntegerOrNull(draft.maxRows)) {
    errors.push(t('settings.connectorWizard.validation.max_rows_positive'));
  }

  if (type === 'postgres') {
    const postgres = draft as PostgresDraft;
    if (!postgres.host.trim()) {
      errors.push(t('settings.connectorWizard.validation.postgres.host_required'));
    }
    if (!postgres.database.trim()) {
      errors.push(t('settings.connectorWizard.validation.postgres.database_required'));
    }
    if (
      postgres.authMode === 'password'
      && !postgres.password.trim()
      && !shouldReuseStoredSecret('postgres', postgres, context.editingConnector)
    ) {
      errors.push(t('settings.connectorWizard.validation.postgres.password_required'));
    }
  } else if (type === 'bigquery') {
    const bigquery = draft as BigQueryDraft;
    if (!bigquery.projectId.trim()) {
      errors.push(t('settings.connectorWizard.validation.bigquery.project_required'));
    }
    if (
      bigquery.authMode === 'service_account_json'
      && !bigquery.serviceAccountJson.trim()
      && !shouldReuseStoredSecret('bigquery', bigquery, context.editingConnector)
    ) {
      errors.push(t('settings.connectorWizard.validation.bigquery.service_account_required'));
    }
    if (bigquery.serviceAccountJson.trim()) {
      try {
        const parsed = JSON.parse(bigquery.serviceAccountJson);
        if (!isRecord(parsed)) {
          errors.push(t('settings.connectorWizard.validation.bigquery.service_account_object'));
        }
      } catch {
        errors.push(t('settings.connectorWizard.validation.bigquery.service_account_json'));
      }
    }
  } else {
    const snowflake = draft as SnowflakeDraft;
    if (!snowflake.account.trim()) {
      errors.push(t('settings.connectorWizard.validation.snowflake.account_required'));
    }
    if (!snowflake.warehouse.trim()) {
      errors.push(t('settings.connectorWizard.validation.snowflake.warehouse_required'));
    }
    if (!snowflake.database.trim()) {
      errors.push(t('settings.connectorWizard.validation.snowflake.database_required'));
    }
    if (!snowflake.username.trim()) {
      errors.push(t('settings.connectorWizard.validation.snowflake.username_required'));
    }
    if (
      snowflake.authMode === 'password'
      && !snowflake.password.trim()
      && !shouldReuseStoredSecret('snowflake', snowflake, context.editingConnector)
    ) {
      errors.push(t('settings.connectorWizard.validation.snowflake.password_required'));
    }
  }

  return errors;
}

function shouldReuseStoredSecret(
  type: ConnectorType,
  draft: DraftByType[ConnectorType],
  editingConnector: ConnectorSummary | null
): boolean {
  if (!editingConnector) {
    return false;
  }
  if (editingConnector.type !== type) {
    return false;
  }
  if (editingConnector.name !== draft.name.trim()) {
    return false;
  }
  if (!editingConnector.hasCredential || editingConnector.credentialMethod !== 'secret_manager') {
    return false;
  }

  if (type === 'bigquery') {
    return (draft as BigQueryDraft).authMode === 'service_account_json';
  }
  if (type === 'postgres') {
    return (draft as PostgresDraft).authMode === 'password';
  }
  return (draft as SnowflakeDraft).authMode === 'password';
}

function normalizeDetailSummary(value: string): string {
  return value.replace(/ [^\x00-\x7F]{1,3} /g, ' / ');
}

function parseConnectorSummary(value: unknown): ConnectorSummary {
  const record = isRecord(value) ? value : {};
  return {
    name: asString(record.name),
    type: parseConnectorType(record.type),
    label: asString(record.label),
    credentialMethod: asString(record.credentialMethod),
    credentialRef: asString(record.credentialRef),
    hasCredential: Boolean(record.hasCredential),
    readOnly: Boolean(record.readOnly),
    timeoutSeconds: asNumber(record.timeoutSeconds, 30),
    maxRows: asNumber(record.maxRows, 10_000),
    options: isRecord(record.options) ? record.options : {},
  };
}

function parseTestResult(payload: Record<string, unknown>, t: Translator): ConnectorTestResult {
  const details = isRecord(payload.details) ? payload.details : {};
  const probe = isRecord(payload.probe) ? payload.probe : {};
  return {
    ok: Boolean(payload.ok),
    latencyMs: typeof payload.latencyMs === 'number' ? payload.latencyMs : undefined,
    probeMessage: asString(probe.message),
    errorCode: asString(payload.errorCode) || undefined,
    message:
      asString(payload.message)
      || asString(probe.message)
      || t('settings.connectorWizard.message.test_completed'),
    details,
    warnings: Array.isArray(payload.warnings)
      ? payload.warnings.map((warning) => String(warning))
      : [],
  };
}

function describeConnectorTarget(connector: ConnectorSummary, t: Translator): string {
  if (connector.type === 'postgres') {
    const host = optionAsString(connector.options, 'host');
    const database = optionAsString(connector.options, 'database');
    const schema = optionAsString(connector.options, 'schema', 'public');
    return `${host || t('settings.connectorWizard.target.host_unknown')} / ${
      database || t('settings.connectorWizard.target.database_unknown')
    } / ${schema || t('settings.connectorWizard.target.public_schema')}`;
  }
  if (connector.type === 'bigquery') {
    const projectId = optionAsString(connector.options, 'project_id');
    const dataset = optionAsString(connector.options, 'dataset');
    const location = optionAsString(connector.options, 'location');
    return [
      projectId,
      dataset || t('settings.connectorWizard.target.all_datasets'),
      location || t('settings.connectorWizard.target.default_location'),
    ].join(' / ');
  }
  const account = optionAsString(connector.options, 'account', optionAsString(connector.options, 'host'));
  const warehouse = optionAsString(connector.options, 'warehouse');
  const database = optionAsString(connector.options, 'database');
  return [account, warehouse, database].filter(Boolean).join(' / ');
}

function formatDetails(details: Record<string, unknown>): string {
  return Object.entries(details)
    .filter(([, value]) => value !== null && value !== '')
    .map(([key, value]) => `${humanizeKey(key)}: ${String(value)}`)
    .join(' · ');
}

function connectorTypeLabel(type: ConnectorType, t: Translator): string {
  return buildConnectorTypes(t).find((entry) => entry.type === type)?.label ?? type;
}

function parseConnectorType(value: unknown): ConnectorType {
  if (value === 'bigquery' || value === 'snowflake' || value === 'postgres') {
    return value;
  }
  return 'postgres';
}

function optionAsString(options: Record<string, unknown>, key: string, fallback = ''): string {
  const value = options[key];
  if (value === undefined || value === null || value === '') {
    return fallback;
  }
  return String(value);
}

function optionAsBool(options: Record<string, unknown>, key: string, fallback = false): boolean {
  const value = options[key];
  if (typeof value === 'boolean') {
    return value;
  }
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    if (normalized === 'true' || normalized === '1' || normalized === 'yes') {
      return true;
    }
    if (normalized === 'false' || normalized === '0' || normalized === 'no') {
      return false;
    }
  }
  if (typeof value === 'number') {
    return value !== 0;
  }
  return fallback;
}

function parsePositiveInteger(value: string, fallback: number): number {
  return parsePositiveIntegerOrNull(value) ?? fallback;
}

function parsePositiveIntegerOrNull(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : value == null ? '' : String(value);
}

function asNumber(value: unknown, fallback: number): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return fallback;
}

function humanizeKey(value: string): string {
  return value
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
