import { useEffect, useMemo, useRef, useState } from 'react';
import { Command as CommandIcon, Search } from 'lucide-react';
import {
  loadRecentCommandIds,
  recordRecentCommandId,
} from '../../application/command/registry';
import { resolveCliSlashDispatch } from '../../application/command/cliSlashDispatcher';
import {
  searchCommands,
  type CommandSearchResult,
} from '../../application/command/searchCommands';
import {
  type Command,
  type CommandCategory,
} from '../../domain/command/command';
import { useI18n } from '../../stores/i18nStore';
import { announce } from '../../application/a11y/ariaLive';
import { CommandRow } from './CommandRow';

interface Props {
  readonly open: boolean;
  readonly commands: readonly Command[];
  readonly onSend: (message: string) => void;
  readonly onClose: () => void;
}

type PaletteCategory = CommandCategory;

const PALETTE_CATEGORY_ORDER: readonly PaletteCategory[] = [
  'navigation',
  'file',
  'run',
  'model',
  'policy',
  'slash',
  'agent',
];

const FOCUSABLE_SELECTOR = [
  'button:not([disabled])',
  '[href]',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

function getFocusableElements(container: HTMLElement | null): HTMLElement[] {
  if (!container) {
    return [];
  }

  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (element) => !element.hasAttribute('disabled') && element.getAttribute('aria-hidden') !== 'true',
  );
}

function normalizeCategory(category: string): PaletteCategory {
  if (category === 'file') {
    return 'file';
  }

  switch (category) {
    case 'navigation':
    case 'run':
    case 'model':
    case 'policy':
    case 'slash':
    case 'agent':
      return category;
    default:
      return 'agent';
  }
}

function categoryLabel(
  category: PaletteCategory,
  t: (key: string) => string,
): string {
  const key = `cmd:section.${category}`;
  const localized = t(key);
  if (localized !== key) {
    return localized;
  }

  switch (category) {
    case 'navigation':
      return 'Navigation';
    case 'file':
      return 'Files';
    case 'run':
      return 'Runs';
    case 'model':
      return 'Models';
    case 'policy':
      return 'Policies';
    case 'slash':
      return 'Slash';
    case 'agent':
      return 'Agent';
    default:
      return category;
  }
}

export function CommandPalette({ open, commands, onSend, onClose }: Props) {
  const { t } = useI18n();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [recentIds, setRecentIds] = useState<string[]>([]);

  useEffect(() => {
    if (!open) {
      return;
    }
    previousFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    setQuery('');
    setSelectedIndex(0);
    setRecentIds(loadRecentCommandIds());
    queueMicrotask(() => inputRef.current?.focus());
    return () => {
      previousFocusRef.current?.focus();
    };
  }, [open]);

  const results = useMemo(
    () => searchCommands(query, commands, recentIds),
    [commands, query, recentIds],
  );
  const resultsByCategory = useMemo(() => {
    const grouped = new Map<PaletteCategory, CommandSearchResult[]>();
    for (const category of PALETTE_CATEGORY_ORDER) {
      grouped.set(category, []);
    }

    for (const result of results) {
      const category = normalizeCategory(result.command.category);
      grouped.get(category)?.push(result);
    }

    const orderedResults: CommandSearchResult[] = [];
    let firstCategoryWithResults: PaletteCategory | null = null;
    for (const category of PALETTE_CATEGORY_ORDER) {
      const categoryResults = grouped.get(category) ?? [];
      if (categoryResults.length > 0 && firstCategoryWithResults === null) {
        firstCategoryWithResults = category;
      }
      orderedResults.push(...categoryResults);
    }

    return {
      firstCategoryWithResults,
      grouped,
      orderedResults,
    };
  }, [results]);
  const orderedResults = resultsByCategory.orderedResults;
  const selectedResult = orderedResults[selectedIndex] ?? null;

  useEffect(() => {
    if (selectedIndex < orderedResults.length) {
      return;
    }
    setSelectedIndex(orderedResults.length === 0 ? 0 : orderedResults.length - 1);
  }, [orderedResults.length, selectedIndex]);

  useEffect(() => {
    if (!open || selectedResult == null) {
      return;
    }
    const row = document.getElementById(`command-palette-option-${selectedIndex}`);
    row?.scrollIntoView({ block: 'nearest' });
  }, [open, selectedIndex, selectedResult]);

  if (!open) {
    return null;
  }

  const announceSentToChat = (label: string, category: 'slash' | 'agent') => {
    // Slash and agent prompts are dispatched into the mission chat rather
    // than navigating to a route, so screen-reader users get no focus
    // change to anchor on. Announce the dispatch via aria-live so the
    // outcome is perceivable. Route-style commands (navigation/file/run/
    // model/policy) already trigger a focus change downstream.
    const messageKey = category === 'slash' ? 'cmd:announce.sentToChat' : 'cmd:announce.agentSentToChat';
    const variableKey = category === 'slash' ? 'slash' : 'label';
    const localized = t(messageKey, { [variableKey]: label });
    const message = localized && localized !== messageKey ? localized : `Sent ${label} to chat`;
    announce(message, { politeness: 'polite', clearAfterMs: 2000 });
  };

  const announceCliOnlySlash = (slash: string) => {
    const messageKey = 'cmd:announce.cliOnlyUnavailable';
    const localized = t(messageKey, { slash });
    const message = localized && localized !== messageKey
      ? localized
      : `${slash} is available in the CLI only, not in the desktop palette`;
    announce(message, { politeness: 'polite', clearAfterMs: 2500 });
  };

  const executeSelected = async (command: Command | null, input?: string) => {
    if (!command) {
      return;
    }
    const nextRecentIds = recordRecentCommandId(command.id);
    setRecentIds(nextRecentIds);
    try {
      await command.execute({ input });
      if (command.category === 'slash') {
        announceSentToChat(input?.trim() || command.title || command.id, 'slash');
      } else if (command.category === 'agent') {
        announceSentToChat(command.title || command.id, 'agent');
      }
      onClose();
    } catch (error) {
      console.warn('[CommandPalette] command execution failed:', error);
    }
  };

  const executeSlashFallback = (value: string) => {
    onSend(value);
    announceSentToChat(value, 'slash');
    onClose();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      onClose();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    if (event.key === 'Tab') {
      const focusableElements = getFocusableElements(dialogRef.current);
      if (focusableElements.length === 0) {
        event.preventDefault();
        event.stopPropagation();
        dialogRef.current?.focus();
        return;
      }

      const activeElement = document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
      const currentIndex = activeElement == null
        ? -1
        : focusableElements.findIndex((element) => element === activeElement);
      const nextIndex = currentIndex === -1
        ? event.shiftKey ? focusableElements.length - 1 : 0
        : (currentIndex + (event.shiftKey ? -1 : 1) + focusableElements.length)
          % focusableElements.length;

      event.preventDefault();
      event.stopPropagation();
      focusableElements[nextIndex]?.focus();
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      event.stopPropagation();
      setSelectedIndex((current) => (
        orderedResults.length === 0 ? 0 : (current + 1) % orderedResults.length
      ));
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      event.stopPropagation();
      setSelectedIndex((current) =>
        orderedResults.length === 0
          ? 0
          : (current - 1 + orderedResults.length) % orderedResults.length,
      );
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      event.stopPropagation();
      if (query.trim().startsWith('/')) {
        const slashResolution = resolveCliSlashDispatch(query, commands);
        if (slashResolution?.kind === 'palette') {
          if (slashResolution.command) {
            void executeSelected(slashResolution.command, slashResolution.normalizedInput);
            return;
          }
          executeSlashFallback(slashResolution.normalizedInput);
          return;
        }
        if (slashResolution?.kind === 'cli-only') {
          announceCliOnlySlash(slashResolution.slashToken);
          return;
        }
        executeSlashFallback(query.trim());
        return;
      }
      void executeSelected(selectedResult?.command ?? null);
    }
  };

  let flatIndex = -1;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 px-4 py-10 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="command-palette-title"
        aria-describedby="command-palette-description"
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={handleKeyDown}
        className="w-[min(760px,100%)] overflow-hidden rounded-[28px] border border-ds-border bg-ds-surface shadow-2xl"
      >
        <div className="border-b border-ds-border px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-ds-border bg-ds-bg/50 text-ds-accent">
              <CommandIcon size={18} />
            </div>
            <div className="min-w-0 flex-1">
              <div id="command-palette-title" className="text-sm font-semibold text-ds-text">
                {t('cmd:title')}
              </div>
              <div id="command-palette-description" className="mt-1 text-xs text-ds-muted">
                {t('cmd:description')}
              </div>
            </div>
            <div className="rounded-full border border-ds-border px-3 py-1 text-[11px] text-ds-muted">
              {t('cmd:shortcutHint')}
            </div>
          </div>

          <label className="mt-4 flex items-center gap-2 rounded-2xl border border-ds-border bg-ds-bg/50 px-3 py-3">
            <Search size={16} className="text-ds-muted" />
            <input
              ref={inputRef}
              role="combobox"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setSelectedIndex(0);
              }}
              aria-autocomplete="list"
              aria-activedescendant={
                selectedResult ? `command-palette-option-${selectedIndex}` : undefined
              }
              aria-controls={orderedResults.length > 0 ? 'command-palette-listbox' : undefined}
              aria-describedby="command-palette-description"
              aria-expanded={orderedResults.length > 0}
              aria-haspopup="listbox"
              aria-label={t('cmd:searchLabel')}
              placeholder={t('cmd:searchPlaceholder')}
              className="w-full bg-transparent text-sm text-ds-text outline-none placeholder:text-ds-muted"
            />
          </label>
          <div className="sr-only" aria-live="polite">
            {orderedResults.length === 0
              ? t('cmd:empty.title')
              : `${orderedResults.length} commands. ${selectedResult?.command.title ?? ''}`}
          </div>
        </div>

        <div className="max-h-[60vh] overflow-y-auto px-5 py-4">
          {orderedResults.length === 0 ? (
            <div className="rounded-2xl border border-ds-border bg-ds-bg/40 px-4 py-8 text-center">
              <div className="text-sm font-medium text-ds-text">{t('cmd:empty.title')}</div>
              <div className="mt-2 text-xs text-ds-muted">{t('cmd:empty.description')}</div>
            </div>
          ) : (
            <div id="command-palette-listbox" role="listbox" className="space-y-4">
              {PALETTE_CATEGORY_ORDER.map((category) => {
                const categoryResults = resultsByCategory.grouped.get(category) ?? [];
                if (categoryResults.length === 0) {
                  return null;
                }
                return (
                  <section key={category} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ds-muted">
                        {categoryLabel(category, t)}
                      </div>
                      {query.length === 0
                        && category === resultsByCategory.firstCategoryWithResults && (
                        <div className="text-[10px] text-ds-muted">{t('cmd:recentHint')}</div>
                      )}
                    </div>
                    <div className="space-y-2">
                      {categoryResults.map((result) => {
                        flatIndex += 1;
                        const rowIndex = flatIndex;
                        const command = result.command;
                        return (
                          <CommandRow
                            key={command.id}
                            command={command}
                            index={rowIndex}
                            selected={selectedResult?.command.id === command.id}
                            totalCount={orderedResults.length}
                            onPointerEnter={() => setSelectedIndex(rowIndex)}
                            onSelect={() => {
                              void executeSelected(command);
                            }}
                          />
                        );
                      })}
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
