import { useEffect, useMemo, useState } from 'react';

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

const CONNECTOR_TYPES: { type: ConnectorType; label: string; hint: string }[] = [
  { type: 'postgres', label: 'PostgreSQL', hint: 'Host, database, schema, and read-only login.' },
  {
    type: 'bigquery',
    label: 'BigQuery',
    hint: 'Project, dataset, location, and service-account or ADC auth.',
  },
  {
    type: 'snowflake',
    label: 'Snowflake',
    hint: 'Account, warehouse, database, and schema-aware read-only access.',
  },
];

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

  const currentDraft = drafts[selectedType];
  const currentFingerprint = useMemo(
    () => JSON.stringify({ type: selectedType, draft: currentDraft }),
    [currentDraft, selectedType]
  );
  const validationErrors = useMemo(
    () => validateDraft(selectedType, currentDraft, { editingConnector }),
    [currentDraft, editingConnector, selectedType]
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
        text: error instanceof Error ? error.message : 'Failed to load connectors.',
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
      text: `Preparing a new ${connectorTypeLabel(type)} connector.`,
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
          ? 'Stored credentials can be reused for test/save unless you rename the connector.'
          : `Editing ${connector.label || connector.name}.`,
    });
  };

  const handleDelete = async (connector: ConnectorSummary) => {
    const confirmed = window.confirm(`Delete connector "${connector.label || connector.name}"?`);
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
        text: `Deleted ${connector.label || connector.name}.`,
      });
      await refreshConnectors();
    } catch (error) {
      setMessage({
        tone: 'error',
        text: error instanceof Error ? error.message : 'Failed to delete connector.',
      });
    } finally {
      setDeletingName(null);
    }
  };

  const handleTest = async () => {
    const errors = validateDraft(selectedType, currentDraft, { editingConnector });
    if (errors.length > 0) {
      setMessage({ tone: 'error', text: errors[0] });
      return;
    }

    setTesting(true);
    setMessage(null);
    setTestResult(null);
    try {
      const payload = buildPayload(selectedType, currentDraft, { editingConnector });
      const result = await rpc('connector.test', payload);
      const parsed = parseTestResult(result);
      setTestResult(parsed);
      if (parsed.ok) {
        setTestedFingerprint(currentFingerprint);
        setMessage({
          tone: 'success',
          text: `Connection test passed for ${connectorTypeLabel(selectedType)}.`,
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
        text: error instanceof Error ? error.message : 'Connection test failed.',
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    const errors = validateDraft(selectedType, currentDraft, { editingConnector });
    if (errors.length > 0) {
      setMessage({ tone: 'error', text: errors[0] });
      return;
    }
    if (!isTestFresh || !testResult?.ok) {
      setMessage({
        tone: 'error',
        text: 'Run a successful connection test before saving.',
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
        text: `${saved.label || saved.name} is saved and ready for warehouse access.`,
      });
      await refreshConnectors();
    } catch (error) {
      setMessage({
        tone: 'error',
        text: error instanceof Error ? error.message : 'Failed to save connector.',
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-xs font-medium text-ds-text">Warehouse Connector Setup</div>
            <p className="mt-1 text-[11px] leading-5 text-ds-muted">
              Configure read-only access for PostgreSQL, BigQuery, or Snowflake. Secrets stay in
              secure storage and tests only run a read-only probe.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => void refreshConnectors()}
              disabled={loading}
              className="rounded-lg border border-ds-border bg-ds-surface px-3 py-1.5 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50 disabled:opacity-40"
            >
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
            <button
              onClick={() => handleStartNew(selectedType)}
              disabled={!connectorCreationAllowed}
              className="rounded-lg border border-ds-border bg-ds-surface px-3 py-1.5 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              New Connector
            </button>
          </div>
        </div>
        {!connectorCreationAllowed && (
          <div className="mt-3 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-[11px] text-amber-200">
            Connector creation is currently disabled by organization policy.
          </div>
        )}
      </div>

      {message && <MessageBanner tone={message.tone}>{message.text}</MessageBanner>}

      <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
        <div className="text-xs font-medium text-ds-text">Saved Connectors</div>
        <div className="mt-1 text-[11px] text-ds-muted">
          {connectors.length === 0
            ? 'No database connectors saved yet.'
            : `${connectors.length} connector${connectors.length === 1 ? '' : 's'} configured.`}
        </div>

        <div className="mt-3 space-y-2">
          {loading && (
            <div className="rounded-lg border border-ds-border/60 bg-ds-surface px-3 py-2 text-[11px] text-ds-muted">
              Loading connector inventory...
            </div>
          )}
          {!loading && connectors.length === 0 && (
            <div className="rounded-lg border border-ds-border/60 bg-ds-surface px-3 py-2 text-[11px] text-ds-muted">
              Start with a connector type below, run a read-only test, then save it for reuse.
            </div>
          )}
          {!loading &&
            connectors.map((connector) => {
              const isEditing = editingConnector?.name === connector.name;
              return (
                <div
                  key={connector.name}
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
                        <Badge>{connectorTypeLabel(connector.type)}</Badge>
                        <Badge tone={connector.hasCredential ? 'success' : 'muted'}>
                          {connector.hasCredential ? 'Credential Ready' : 'No Secret Stored'}
                        </Badge>
                        <Badge tone="muted">Read Only</Badge>
                      </div>
                      <div className="mt-1 text-[11px] text-ds-muted">
                        {connector.name} · {describeConnectorTarget(connector)}
                      </div>
                      <div className="mt-1 text-[11px] text-ds-muted/90">
                        {connector.credentialMethod === 'env'
                          ? connector.credentialRef
                            ? `Environment credential ref: ${connector.credentialRef}`
                            : 'Environment / default credentials'
                          : 'Secret stored in backend secure storage'}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleEdit(connector)}
                        className="rounded-lg border border-ds-border bg-ds-bg px-3 py-1.5 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => void handleDelete(connector)}
                        disabled={!connectorCreationAllowed || deletingName === connector.name}
                        className="rounded-lg border border-ds-border bg-ds-bg px-3 py-1.5 text-xs font-medium text-ds-text transition-colors hover:border-ds-error/50 hover:text-ds-error disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {deletingName === connector.name ? 'Deleting...' : 'Delete'}
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
          {CONNECTOR_TYPES.map((entry) => {
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
                  ? `Edit ${editingConnector.label || editingConnector.name}`
                  : `New ${connectorTypeLabel(selectedType)} Connector`}
              </div>
              <div className="text-[11px] text-ds-muted">
                Fill in the connector details, run a read-only probe, then save the configuration.
              </div>
            </div>
            <button
              onClick={() => handleStartNew(selectedType)}
              className="rounded-lg border border-ds-border bg-ds-bg px-3 py-1.5 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50"
            >
              Reset Form
            </button>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <LabeledField label="Connector name" required>
              <input
                type="text"
                value={currentDraft.name}
                onChange={(event) =>
                  updateDraft(selectedType, (draft) => ({ ...draft, name: event.target.value }))
                }
                placeholder="analytics_prod"
                className={fieldClassName}
              />
            </LabeledField>
            <LabeledField label="Display label">
              <input
                type="text"
                value={currentDraft.label}
                onChange={(event) =>
                  updateDraft(selectedType, (draft) => ({ ...draft, label: event.target.value }))
                }
                placeholder={`${connectorTypeLabel(selectedType)} read-only`}
                className={fieldClassName}
              />
            </LabeledField>
            <LabeledField label="Timeout (seconds)" required>
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
                className={fieldClassName}
              />
            </LabeledField>
            <LabeledField label="Max rows" required>
              <input
                type="number"
                min={1}
                value={currentDraft.maxRows}
                onChange={(event) =>
                  updateDraft(selectedType, (draft) => ({ ...draft, maxRows: event.target.value }))
                }
                className={fieldClassName}
              />
            </LabeledField>
          </div>

          <div className="mt-4 rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs font-medium text-ds-text">Read-only guard</div>
                <div className="text-[11px] text-ds-muted">
                  Connector tests and query execution stay in read-only mode.
                </div>
              </div>
              <label className="flex items-center gap-2 text-[11px] text-ds-muted">
                <input type="checkbox" checked={currentDraft.readOnly} readOnly />
                Locked
              </label>
            </div>
          </div>

          {selectedType === 'postgres' && (
            <PostgresFields
              draft={drafts.postgres}
              onChange={(updater) => updateDraft('postgres', updater)}
              showStoredSecretHint={usesStoredSecret}
            />
          )}
          {selectedType === 'bigquery' && (
            <BigQueryFields
              draft={drafts.bigquery}
              onChange={(updater) => updateDraft('bigquery', updater)}
              showStoredSecretHint={usesStoredSecret}
            />
          )}
          {selectedType === 'snowflake' && (
            <SnowflakeFields
              draft={drafts.snowflake}
              onChange={(updater) => updateDraft('snowflake', updater)}
              showStoredSecretHint={usesStoredSecret}
            />
          )}

          {validationErrors.length > 0 && (
            <div className="mt-4 rounded-lg border border-ds-error/30 bg-ds-error/10 px-3 py-2 text-[11px] text-ds-error">
              {validationErrors[0]}
            </div>
          )}

          {testResult && (
            <div className="mt-4 rounded-lg border border-ds-border/60 bg-ds-bg p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-ds-text">Last Connection Test</span>
                <Badge tone={testResult.ok ? 'success' : 'error'}>
                  {testResult.ok ? 'Passed' : 'Failed'}
                </Badge>
                {typeof testResult.latencyMs === 'number' && (
                  <Badge tone="muted">{testResult.latencyMs}ms</Badge>
                )}
                {!isTestFresh && <Badge tone="warning">Draft changed, retest required</Badge>}
              </div>
              <div className="mt-2 text-[11px] text-ds-muted">
                {testResult.probeMessage ?? testResult.message}
              </div>
              {Object.keys(testResult.details).length > 0 && (
                <div className="mt-2 rounded border border-ds-border/50 bg-ds-surface px-3 py-2 text-[11px] text-ds-muted">
                  {formatDetails(testResult.details)}
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
              className="rounded-lg border border-ds-border bg-ds-bg px-3 py-1.5 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {testing ? 'Testing...' : 'Test Connection'}
            </button>
            <button
              onClick={() => void handleSave()}
              disabled={saving || !canSave}
              className="rounded-lg bg-ds-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-ds-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
            >
              {saving ? 'Saving...' : editingConnector ? 'Save Changes' : 'Save Connector'}
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
}: {
  draft: PostgresDraft;
  onChange: (updater: (draft: PostgresDraft) => PostgresDraft) => void;
  showStoredSecretHint: boolean;
}) {
  return (
    <div className="mt-4 space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <LabeledField label="Host" required>
          <input
            type="text"
            value={draft.host}
            onChange={(event) => onChange((current) => ({ ...current, host: event.target.value }))}
            placeholder="localhost"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label="Port">
          <input
            type="number"
            value={draft.port}
            onChange={(event) => onChange((current) => ({ ...current, port: event.target.value }))}
            placeholder="5432"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label="Database" required>
          <input
            type="text"
            value={draft.database}
            onChange={(event) =>
              onChange((current) => ({ ...current, database: event.target.value }))
            }
            placeholder="analytics"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label="Schema">
          <input
            type="text"
            value={draft.schema}
            onChange={(event) => onChange((current) => ({ ...current, schema: event.target.value }))}
            placeholder="public"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label="Username">
          <input
            type="text"
            value={draft.username}
            onChange={(event) =>
              onChange((current) => ({ ...current, username: event.target.value }))
            }
            placeholder="readonly_user"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label="SSL">
          <label className="flex h-10 items-center gap-2 rounded border border-ds-border bg-ds-bg px-3 text-xs text-ds-text">
            <input
              type="checkbox"
              checked={draft.ssl}
              onChange={(event) => onChange((current) => ({ ...current, ssl: event.target.checked }))}
            />
            Require SSL
          </label>
        </LabeledField>
      </div>

      <AuthModePicker<PostgresAuthMode>
        label="Credential source"
        value={draft.authMode}
        options={[
          {
            value: 'password',
            label: 'Secure password',
            description: 'Store the password in backend secure storage.',
          },
          {
            value: 'environment',
            label: 'Environment / DSN',
            description: 'Use an environment variable or a local auth path.',
          },
        ]}
        onChange={(value) => onChange((current) => ({ ...current, authMode: value }))}
      />

      {draft.authMode === 'password' ? (
        <LabeledField label="Password" required={!showStoredSecretHint}>
          <input
            type="password"
            value={draft.password}
            onChange={(event) => onChange((current) => ({ ...current, password: event.target.value }))}
            placeholder={showStoredSecretHint ? 'Stored secret will be reused if left blank' : 'Enter password'}
            className={fieldClassName}
          />
        </LabeledField>
      ) : (
        <LabeledField label="Credential env var">
          <input
            type="text"
            value={draft.credentialRef}
            onChange={(event) =>
              onChange((current) => ({ ...current, credentialRef: event.target.value }))
            }
            placeholder="PG_DSN or PG_READONLY_JSON"
            className={fieldClassName}
          />
        </LabeledField>
      )}

      {showStoredSecretHint && (
        <div className="rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-2 text-[11px] text-ds-muted">
          Existing stored credentials will be reused for test/save unless you rename the connector
          or enter a replacement password.
        </div>
      )}
    </div>
  );
}

function BigQueryFields({
  draft,
  onChange,
  showStoredSecretHint,
}: {
  draft: BigQueryDraft;
  onChange: (updater: (draft: BigQueryDraft) => BigQueryDraft) => void;
  showStoredSecretHint: boolean;
}) {
  return (
    <div className="mt-4 space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <LabeledField label="Project ID" required>
          <input
            type="text"
            value={draft.projectId}
            onChange={(event) =>
              onChange((current) => ({ ...current, projectId: event.target.value }))
            }
            placeholder="my-analytics-project"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label="Dataset">
          <input
            type="text"
            value={draft.dataset}
            onChange={(event) => onChange((current) => ({ ...current, dataset: event.target.value }))}
            placeholder="analytics"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label="Location">
          <input
            type="text"
            value={draft.location}
            onChange={(event) =>
              onChange((current) => ({ ...current, location: event.target.value }))
            }
            placeholder="asia-northeast3"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label="Billing project">
          <input
            type="text"
            value={draft.billingProject}
            onChange={(event) =>
              onChange((current) => ({ ...current, billingProject: event.target.value }))
            }
            placeholder="billing-project-id"
            className={fieldClassName}
          />
        </LabeledField>
      </div>

      <AuthModePicker<BigQueryAuthMode>
        label="Credential source"
        value={draft.authMode}
        options={[
          {
            value: 'service_account_json',
            label: 'Service account JSON',
            description: 'Store the service-account payload in backend secure storage.',
          },
          {
            value: 'environment',
            label: 'Application default credentials',
            description: 'Use local ADC or an env var that points to credentials.',
          },
        ]}
        onChange={(value) => onChange((current) => ({ ...current, authMode: value }))}
      />

      {draft.authMode === 'service_account_json' ? (
        <LabeledField label="Service account JSON" required={!showStoredSecretHint}>
          <textarea
            value={draft.serviceAccountJson}
            onChange={(event) =>
              onChange((current) => ({ ...current, serviceAccountJson: event.target.value }))
            }
            placeholder={
              showStoredSecretHint
                ? 'Stored secret will be reused if left blank'
                : '{ "type": "service_account", ... }'
            }
            rows={8}
            className={`${fieldClassName} min-h-[10rem] py-2 font-mono`}
          />
        </LabeledField>
      ) : (
        <LabeledField label="Credential env var">
          <input
            type="text"
            value={draft.credentialRef}
            onChange={(event) =>
              onChange((current) => ({ ...current, credentialRef: event.target.value }))
            }
            placeholder="GOOGLE_APPLICATION_CREDENTIALS or leave blank for ADC"
            className={fieldClassName}
          />
        </LabeledField>
      )}

      {showStoredSecretHint && (
        <div className="rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-2 text-[11px] text-ds-muted">
          Existing stored service-account credentials will be reused for test/save unless you rename
          the connector or paste a replacement JSON payload.
        </div>
      )}
    </div>
  );
}

function SnowflakeFields({
  draft,
  onChange,
  showStoredSecretHint,
}: {
  draft: SnowflakeDraft;
  onChange: (updater: (draft: SnowflakeDraft) => SnowflakeDraft) => void;
  showStoredSecretHint: boolean;
}) {
  return (
    <div className="mt-4 space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <LabeledField label="Account" required>
          <input
            type="text"
            value={draft.account}
            onChange={(event) =>
              onChange((current) => ({ ...current, account: event.target.value }))
            }
            placeholder="xy12345.ap-northeast-2.aws"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label="Warehouse" required>
          <input
            type="text"
            value={draft.warehouse}
            onChange={(event) =>
              onChange((current) => ({ ...current, warehouse: event.target.value }))
            }
            placeholder="ANALYTICS_WH"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label="Database" required>
          <input
            type="text"
            value={draft.database}
            onChange={(event) =>
              onChange((current) => ({ ...current, database: event.target.value }))
            }
            placeholder="ANALYTICS"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label="Schema">
          <input
            type="text"
            value={draft.schema}
            onChange={(event) => onChange((current) => ({ ...current, schema: event.target.value }))}
            placeholder="PUBLIC"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label="Username" required>
          <input
            type="text"
            value={draft.username}
            onChange={(event) =>
              onChange((current) => ({ ...current, username: event.target.value }))
            }
            placeholder="readonly_user"
            className={fieldClassName}
          />
        </LabeledField>
        <LabeledField label="Role">
          <input
            type="text"
            value={draft.role}
            onChange={(event) => onChange((current) => ({ ...current, role: event.target.value }))}
            placeholder="ANALYST"
            className={fieldClassName}
          />
        </LabeledField>
      </div>

      <AuthModePicker<SnowflakeAuthMode>
        label="Credential source"
        value={draft.authMode}
        options={[
          {
            value: 'password',
            label: 'Secure password',
            description: 'Store the password in backend secure storage.',
          },
          {
            value: 'environment',
            label: 'Environment payload',
            description: 'Use a JSON payload already exposed through an environment variable.',
          },
        ]}
        onChange={(value) => onChange((current) => ({ ...current, authMode: value }))}
      />

      {draft.authMode === 'password' ? (
        <LabeledField label="Password" required={!showStoredSecretHint}>
          <input
            type="password"
            value={draft.password}
            onChange={(event) => onChange((current) => ({ ...current, password: event.target.value }))}
            placeholder={showStoredSecretHint ? 'Stored secret will be reused if left blank' : 'Enter password'}
            className={fieldClassName}
          />
        </LabeledField>
      ) : (
        <LabeledField label="Credential env var">
          <input
            type="text"
            value={draft.credentialRef}
            onChange={(event) =>
              onChange((current) => ({ ...current, credentialRef: event.target.value }))
            }
            placeholder="SNOWFLAKE_READONLY_JSON"
            className={fieldClassName}
          />
        </LabeledField>
      )}

      {showStoredSecretHint && (
        <div className="rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-2 text-[11px] text-ds-muted">
          Existing stored credentials will be reused for test/save unless you rename the connector
          or enter a replacement password.
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
  context: DraftContext
): string[] {
  const errors: string[] = [];
  if (!draft.name.trim()) {
    errors.push('Connector name is required.');
  } else if (!CONNECTOR_NAME_PATTERN.test(draft.name.trim())) {
    errors.push("Connector name may contain only letters, numbers, '_' and '-'.");
  }

  if (!parsePositiveIntegerOrNull(draft.timeoutSeconds)) {
    errors.push('Timeout must be a positive integer.');
  }
  if (!parsePositiveIntegerOrNull(draft.maxRows)) {
    errors.push('Max rows must be a positive integer.');
  }

  if (type === 'postgres') {
    const postgres = draft as PostgresDraft;
    if (!postgres.host.trim()) {
      errors.push('Postgres host is required.');
    }
    if (!postgres.database.trim()) {
      errors.push('Postgres database is required.');
    }
    if (
      postgres.authMode === 'password'
      && !postgres.password.trim()
      && !shouldReuseStoredSecret('postgres', postgres, context.editingConnector)
    ) {
      errors.push('Postgres password is required for secure-password mode.');
    }
  } else if (type === 'bigquery') {
    const bigquery = draft as BigQueryDraft;
    if (!bigquery.projectId.trim()) {
      errors.push('BigQuery project ID is required.');
    }
    if (
      bigquery.authMode === 'service_account_json'
      && !bigquery.serviceAccountJson.trim()
      && !shouldReuseStoredSecret('bigquery', bigquery, context.editingConnector)
    ) {
      errors.push('Service account JSON is required for BigQuery secure-storage mode.');
    }
    if (bigquery.serviceAccountJson.trim()) {
      try {
        const parsed = JSON.parse(bigquery.serviceAccountJson);
        if (!isRecord(parsed)) {
          errors.push('BigQuery service account JSON must decode to an object.');
        }
      } catch {
        errors.push('BigQuery service account JSON must be valid JSON.');
      }
    }
  } else {
    const snowflake = draft as SnowflakeDraft;
    if (!snowflake.account.trim()) {
      errors.push('Snowflake account is required.');
    }
    if (!snowflake.warehouse.trim()) {
      errors.push('Snowflake warehouse is required.');
    }
    if (!snowflake.database.trim()) {
      errors.push('Snowflake database is required.');
    }
    if (!snowflake.username.trim()) {
      errors.push('Snowflake username is required.');
    }
    if (
      snowflake.authMode === 'password'
      && !snowflake.password.trim()
      && !shouldReuseStoredSecret('snowflake', snowflake, context.editingConnector)
    ) {
      errors.push('Snowflake password is required for secure-password mode.');
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

function parseTestResult(payload: Record<string, unknown>): ConnectorTestResult {
  const details = isRecord(payload.details) ? payload.details : {};
  const probe = isRecord(payload.probe) ? payload.probe : {};
  return {
    ok: Boolean(payload.ok),
    latencyMs: typeof payload.latencyMs === 'number' ? payload.latencyMs : undefined,
    probeMessage: asString(probe.message),
    errorCode: asString(payload.errorCode) || undefined,
    message: asString(payload.message) || asString(probe.message) || 'Connection test completed.',
    details,
    warnings: Array.isArray(payload.warnings)
      ? payload.warnings.map((warning) => String(warning))
      : [],
  };
}

function describeConnectorTarget(connector: ConnectorSummary): string {
  if (connector.type === 'postgres') {
    const host = optionAsString(connector.options, 'host');
    const database = optionAsString(connector.options, 'database');
    const schema = optionAsString(connector.options, 'schema', 'public');
    return `${host || 'host?'} / ${database || 'database?'} / ${schema || 'public'}`;
  }
  if (connector.type === 'bigquery') {
    const projectId = optionAsString(connector.options, 'project_id');
    const dataset = optionAsString(connector.options, 'dataset');
    const location = optionAsString(connector.options, 'location');
    return [projectId, dataset || 'all datasets', location || 'default location'].join(' / ');
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

function connectorTypeLabel(type: ConnectorType): string {
  return CONNECTOR_TYPES.find((entry) => entry.type === type)?.label ?? type;
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
