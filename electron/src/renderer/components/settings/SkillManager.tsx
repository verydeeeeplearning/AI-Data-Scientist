import { useDeferredValue, useEffect, useState } from 'react';
import {
  FileCode2,
  Globe,
  Loader2,
  Pencil,
  RefreshCcw,
  Save,
  Trash2,
  Upload,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useI18n } from '../../stores/i18nStore';
import type { RpcFn, SkillSummary } from './types';

interface SkillFormState {
  name: string;
  description: string;
  category: string;
  tags: string;
  tools: string;
  network: string;
  filesystem: string;
  content: string;
  enabled: boolean;
}

function buildEmptyForm(): SkillFormState {
  return {
    name: '',
    description: '',
    category: 'custom',
    tags: '',
    tools: '',
    network: '',
    filesystem: 'workspace',
    content: '',
    enabled: true,
  };
}

function parseCsv(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter((item, index, array) => item.length > 0 && array.indexOf(item) === index);
}

function toFormState(skill: SkillSummary): SkillFormState {
  return {
    name: skill.name,
    description: skill.description,
    category: skill.category,
    tags: skill.tags.join(', '),
    tools: skill.tools.join(', '),
    network: skill.permissions.network.join(', '),
    filesystem: skill.permissions.filesystem.join(', '),
    content: skill.content ?? '',
    enabled: skill.enabled,
  };
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function SkillManager({ rpc }: { rpc: RpcFn }) {
  const { t } = useI18n();
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [form, setForm] = useState<SkillFormState>(buildEmptyForm);
  const [importMarkdown, setImportMarkdown] = useState('');
  const [importUrl, setImportUrl] = useState('');
  const [editingName, setEditingName] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyName, setBusyName] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importingUrl, setImportingUrl] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const previewContent = useDeferredValue(form.content);

  const loadSkills = async () => {
    setLoading(true);
    try {
      const result = await rpc('skill.catalog');
      setSkills((result.skills as SkillSummary[]) ?? []);
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSkills();
  }, []);

  const resetForm = () => {
    setForm(buildEmptyForm());
    setEditingName(null);
  };

  const handleEdit = async (name: string) => {
    setBusyName(name);
    try {
      const result = await rpc('skill.get', { name });
      const skill = result.skill as SkillSummary;
      setForm(toFormState(skill));
      setEditingName(skill.name);
      setStatusMessage(`Editing ${skill.name}.`);
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setBusyName(null);
    }
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.description.trim() || !form.content.trim()) {
      setErrorMessage('Name, description, and content are required.');
      return;
    }

    setSaving(true);
    try {
      const result = await rpc('skill.save', {
        existingName: editingName ?? undefined,
        name: form.name.trim(),
        description: form.description.trim(),
        category: form.category.trim() || 'custom',
        tags: parseCsv(form.tags),
        tools: parseCsv(form.tools),
        permissions: {
          network: parseCsv(form.network),
          filesystem: parseCsv(form.filesystem),
        },
        enabled: form.enabled,
        content: form.content.trim(),
      });
      setSkills((result.skills as SkillSummary[]) ?? []);
      const savedSkill = result.skill as SkillSummary | undefined;
      if (savedSkill) {
        setForm(toFormState(savedSkill));
        setEditingName(savedSkill.name);
      }
      setStatusMessage(editingName ? 'Skill updated.' : 'Skill created.');
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (skill: SkillSummary, enabled: boolean) => {
    setBusyName(skill.name);
    try {
      const result = await rpc('skill.toggle', { name: skill.name, enabled });
      setSkills((result.skills as SkillSummary[]) ?? []);
      if (editingName === skill.name && result.skill) {
        setForm(toFormState(result.skill as SkillSummary));
      }
      setStatusMessage(`${skill.name} ${enabled ? 'enabled' : 'disabled'}.`);
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setBusyName(null);
    }
  };

  const handleDelete = async (name: string) => {
    if (!window.confirm(`Delete custom skill "${name}"?`)) {
      return;
    }
    setBusyName(name);
    try {
      const result = await rpc('skill.delete', { name });
      setSkills((result.skills as SkillSummary[]) ?? []);
      if (editingName === name) {
        resetForm();
      }
      setStatusMessage(`${name} deleted.`);
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setBusyName(null);
    }
  };

  const handleImport = async () => {
    if (!importMarkdown.trim()) {
      setErrorMessage('Markdown is required for import.');
      return;
    }
    setImporting(true);
    try {
      const result = await rpc('skill.importMarkdown', { markdown: importMarkdown.trim() });
      setSkills((result.skills as SkillSummary[]) ?? []);
      setImportMarkdown('');
      setStatusMessage('Skill imported.');
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setImporting(false);
    }
  };

  const handleImportUrl = async () => {
    if (!importUrl.trim()) {
      setErrorMessage('URL is required for remote install.');
      return;
    }
    setImportingUrl(true);
    try {
      const result = await rpc('skill.importUrl', { url: importUrl.trim() });
      setSkills((result.skills as SkillSummary[]) ?? []);
      setImportUrl('');
      setStatusMessage('Skill installed from URL.');
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setImportingUrl(false);
    }
  };

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

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="rounded-xl border border-ds-border bg-ds-surface p-4">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <h4 className="text-sm font-semibold text-ds-text">{t('settings.skillManager.title')}</h4>
              <p className="text-[11px] text-ds-muted">
                Enable, edit, and permission-bound local skills available to the agent prompt.
              </p>
            </div>
            <button
              onClick={() => void loadSkills()}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-lg border border-ds-border bg-ds-bg px-2.5 py-1.5 text-[11px] font-medium text-ds-text transition-colors hover:border-ds-accent/50 disabled:opacity-40"
            >
              <RefreshCcw size={12} />
              Refresh
            </button>
          </div>

          {loading ? (
            <div className="flex items-center gap-2 rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-4 text-xs text-ds-muted">
              <Loader2 size={14} className="animate-spin" />
              Loading custom skills...
            </div>
          ) : (
            <div className="space-y-2">
              {skills.length === 0 && (
                <div className="rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-4 text-[11px] text-ds-muted">
                  No custom skills yet. Create one below or import markdown from another workspace.
                </div>
              )}
              {skills.map((skill) => (
                <div key={skill.name} className="rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-3">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-semibold text-ds-text">{skill.name}</span>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] ${
                          skill.enabled
                            ? 'bg-ds-accent/15 text-ds-text'
                            : 'bg-ds-border/40 text-ds-muted'
                        }`}
                        >
                          {skill.enabled ? 'Enabled' : 'Disabled'}
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-ds-muted">{skill.description}</p>
                      <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] text-ds-muted">
                        <Badge label={`tools: ${skill.tools.join(', ') || 'all'}`} />
                        <Badge label={`network: ${skill.permissions.network.join(', ') || 'none'}`} />
                        <Badge label={`fs: ${skill.permissions.filesystem.join(', ') || 'workspace'}`} />
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <label className="flex items-center gap-1 text-[11px] text-ds-muted">
                        <input
                          type="checkbox"
                          checked={skill.enabled}
                          disabled={busyName === skill.name}
                          onChange={(event) => void handleToggle(skill, event.target.checked)}
                          className="h-4 w-4 rounded border-ds-border bg-ds-surface text-ds-accent"
                        />
                        Active
                      </label>
                      <button
                        onClick={() => void handleEdit(skill.name)}
                        disabled={busyName === skill.name}
                        className="rounded-md border border-ds-border bg-ds-surface px-2 py-1.5 text-[11px] font-medium text-ds-text transition-colors hover:border-ds-accent/50 disabled:opacity-40"
                      >
                        <span className="inline-flex items-center gap-1">
                          <Pencil size={11} />
                          Edit
                        </span>
                      </button>
                      <button
                        onClick={() => void handleDelete(skill.name)}
                        disabled={busyName === skill.name}
                        className="rounded-md border border-red-500/30 bg-red-500/10 px-2 py-1.5 text-[11px] font-medium text-red-200 transition-colors hover:border-red-400/50 disabled:opacity-40"
                      >
                        <span className="inline-flex items-center gap-1">
                          <Trash2 size={11} />
                          Delete
                        </span>
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-ds-border bg-ds-surface p-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <h4 className="text-sm font-semibold text-ds-text">
                  {editingName ? `Edit ${editingName}` : t('settings.skillManager.createSkill')}
                </h4>
                <p className="text-[11px] text-ds-muted">
                  Tools and permissions become enforceable metadata during sandboxed execution.
                </p>
              </div>
              <button
                onClick={resetForm}
                className="rounded-lg border border-ds-border bg-ds-bg px-2.5 py-1.5 text-[11px] font-medium text-ds-text transition-colors hover:border-ds-accent/50"
              >
                Reset
              </button>
            </div>

            <div className="grid gap-2">
              <div className="grid gap-2 md:grid-cols-2">
                <InputField
                  label="Name"
                  value={form.name}
                  onChange={(value) => setForm((current) => ({ ...current, name: value }))}
                  placeholder="customer-segmentation"
                />
                <InputField
                  label="Category"
                  value={form.category}
                  onChange={(value) => setForm((current) => ({ ...current, category: value }))}
                  placeholder="custom"
                />
              </div>

              <InputField
                label="Description"
                value={form.description}
                onChange={(value) => setForm((current) => ({ ...current, description: value }))}
                placeholder="What this skill is for and when the agent should use it."
              />

              <div className="grid gap-2 md:grid-cols-2">
                <InputField
                  label="Tags"
                  value={form.tags}
                  onChange={(value) => setForm((current) => ({ ...current, tags: value }))}
                  placeholder="segmentation, retention, uplift"
                />
                <InputField
                  label="Tools"
                  value={form.tools}
                  onChange={(value) => setForm((current) => ({ ...current, tools: value }))}
                  placeholder="execute_code, web_search"
                />
              </div>

              <div className="grid gap-2 md:grid-cols-2">
                <InputField
                  label="Allowed Domains"
                  value={form.network}
                  onChange={(value) => setForm((current) => ({ ...current, network: value }))}
                  placeholder="docs.example.com, api.example.com"
                />
                <InputField
                  label="Filesystem Scope"
                  value={form.filesystem}
                  onChange={(value) => setForm((current) => ({ ...current, filesystem: value }))}
                  placeholder="workspace"
                />
              </div>

              <label className="flex items-center justify-between rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-2">
                <div>
                  <div className="text-[11px] font-medium text-ds-text">Enabled in prompt</div>
                  <p className="text-[10px] text-ds-muted">Disabled skills stay stored but are not injected into runs.</p>
                </div>
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(event) => setForm((current) => ({ ...current, enabled: event.target.checked }))}
                  className="h-4 w-4 rounded border-ds-border bg-ds-surface text-ds-accent"
                />
              </label>

              <div className="grid gap-3 xl:grid-cols-2">
                <label className="space-y-1">
                  <span className="text-[11px] font-medium text-ds-text">Markdown Content</span>
                  <textarea
                    value={form.content}
                    onChange={(event) => setForm((current) => ({ ...current, content: event.target.value }))}
                    rows={16}
                    placeholder="# Customer Segmentation&#10;&#10;Use this skill when..."
                    className="w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
                  />
                </label>

                <div className="space-y-1">
                  <span className="text-[11px] font-medium text-ds-text">Preview</span>
                  <div className="min-h-[22rem] rounded-lg border border-ds-border bg-ds-bg px-3 py-2">
                    {previewContent.trim() ? (
                      <div className="prose prose-invert prose-sm max-w-none
                        prose-headings:text-ds-text prose-p:text-ds-text prose-li:text-ds-text
                        prose-code:text-ds-accent prose-strong:text-ds-text
                        prose-a:text-ds-accent prose-a:no-underline hover:prose-a:underline
                        prose-table:text-ds-text prose-th:text-ds-text prose-td:text-ds-text
                        prose-pre:bg-transparent prose-pre:p-0
                      ">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {previewContent}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <div className="flex h-full min-h-[20rem] items-center justify-center text-[11px] text-ds-muted">
                        Markdown preview appears here.
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  onClick={() => void handleSave()}
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-lg bg-ds-accent px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-ds-accent-hover disabled:opacity-40"
                >
                  <Save size={12} />
                  {saving
                    ? t('settings.skillManager.saving')
                    : editingName
                      ? t('settings.skillManager.saveChanges')
                      : t('settings.skillManager.createSkill')}
                </button>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-ds-border bg-ds-surface p-4">
            <div className="mb-3">
              <h4 className="text-sm font-semibold text-ds-text">{t('settings.skillManager.importMarkdown')}</h4>
              <p className="text-[11px] text-ds-muted">
                Paste an existing skill file with YAML frontmatter to bring it into this workspace.
              </p>
            </div>
            <textarea
              value={importMarkdown}
              onChange={(event) => setImportMarkdown(event.target.value)}
              rows={10}
              placeholder={'---\nname: imported-skill\ndescription: Skill summary\ncategory: custom\ntags: [demo]\ntools: [execute_code]\npermissions:\n  network: []\n  filesystem: [workspace]\nenabled: true\n---\n# Imported Skill\n\nInstructions...'}
              className="w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
            />
            <div className="mt-3 flex justify-end">
              <button
                onClick={() => void handleImport()}
                disabled={importing}
                className="inline-flex items-center gap-2 rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50 disabled:opacity-40"
              >
                {importing ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />}
                {importing
                  ? t('settings.skillManager.importing')
                  : t('settings.skillManager.importSkill')}
              </button>
            </div>

            <div className="mt-4 border-t border-ds-border/60 pt-4">
              <div className="mb-2">
                <h5 className="text-xs font-semibold text-ds-text">{t('settings.skillManager.installFromUrl')}</h5>
                <p className="text-[11px] text-ds-muted">
                  Use a raw GitHub or Gist markdown URL to install a remote skill.
                </p>
              </div>
              <div className="flex flex-col gap-2 md:flex-row">
                <input
                  type="url"
                  value={importUrl}
                  onChange={(event) => setImportUrl(event.target.value)}
                  placeholder="https://example.com/skill.md"
                  className="flex-1 rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
                />
                <button
                  onClick={() => void handleImportUrl()}
                  disabled={importingUrl}
                  className="inline-flex items-center justify-center gap-2 rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50 disabled:opacity-40"
                >
                  {importingUrl ? <Loader2 size={12} className="animate-spin" /> : <Globe size={12} />}
                  {importingUrl
                    ? t('settings.skillManager.installing')
                    : t('settings.skillManager.installFromUrl')}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function InputField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="space-y-1">
      <span className="text-[11px] font-medium text-ds-text">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
      />
    </label>
  );
}

function Badge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-ds-border/70 bg-ds-surface px-2 py-0.5">
      <FileCode2 size={10} />
      {label}
    </span>
  );
}
