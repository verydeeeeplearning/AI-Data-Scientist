import {
  Archive,
  Bot,
  Brain,
  PanelLeftClose,
  PanelLeftOpen,
  Play,
  Settings2,
  ShieldCheck,
  Target,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { announce } from '../../application/a11y/ariaLive';
import { prefersReducedMotion, subscribeReducedMotion } from '../../application/a11y/reducedMotion';
import {
  ADMIN_SECTION_DESCRIPTORS,
  AREA_DESCRIPTORS,
  isLegacyV3AreaId,
  type AreaId,
  type AreaSelection,
} from '../../domain/navigation/area';
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut';
import { useSidebarCollapse } from '../../hooks/useSidebarCollapse';
import { useI18n } from '../../stores/i18nStore';
import { SIDEBAR_COLLAPSED_WIDTH, SIDEBAR_EXPANDED_WIDTH } from '../../utils/sidebarLayout';
import { SidebarItem } from '../sidebar/SidebarItem';

interface Props {
  selection: AreaSelection;
  onNavigate: (path: string) => void;
}

const AREA_ICONS: Record<AreaId, typeof Target> = {
  mission: Target,
  runs: Play,
  artifacts: Archive,
  governance: ShieldCheck,
  memory: Brain,
  admin: Settings2,
};

export function AreaSidebar({ selection, onNavigate }: Props) {
  const { t } = useI18n();
  const { collapsed, toggleSidebar } = useSidebarCollapse();
  const navRef = useRef<HTMLElement | null>(null);
  const shouldFocusActiveItemRef = useRef(false);
  const [reducedMotion, setReducedMotion] = useState<boolean>(() => prefersReducedMotion());
  const sidebarWidth = collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_EXPANDED_WIDTH;
  const toggleLabel = collapsed ? t('sidebar.toggle.expand') : t('sidebar.toggle.collapse');

  useEffect(() => subscribeReducedMotion(setReducedMotion, { emitInitial: true }), []);

  useEffect(() => {
    announce(collapsed ? t('sidebar.announce.collapsed') : t('sidebar.announce.expanded'));
  }, [collapsed, t]);

  useEffect(() => {
    if (!collapsed || !shouldFocusActiveItemRef.current) {
      return;
    }
    const target = navRef.current?.querySelector<HTMLElement>(
      `[data-testid="area-nav-${selection.areaId}"]`,
    );
    target?.focus();
    shouldFocusActiveItemRef.current = false;
  }, [collapsed, selection.areaId]);

  const handleToggleSidebar = () => {
    const activeElement = typeof document !== 'undefined' ? document.activeElement : null;
    if (!collapsed && activeElement instanceof HTMLElement && navRef.current?.contains(activeElement)) {
      shouldFocusActiveItemRef.current = true;
    }
    toggleSidebar();
  };

  useKeyboardShortcut('ctrl+\\', handleToggleSidebar);
  useKeyboardShortcut('meta+\\', handleToggleSidebar);

  useKeyboardShortcut('ctrl+1', () => onNavigate('/artifacts/files'));
  useKeyboardShortcut('meta+1', () => onNavigate('/artifacts/files'));
  useKeyboardShortcut('ctrl+2', () => onNavigate('/runs'));
  useKeyboardShortcut('meta+2', () => onNavigate('/runs'));
  useKeyboardShortcut('ctrl+3', () => onNavigate('/governance/review'));
  useKeyboardShortcut('meta+3', () => onNavigate('/governance/review'));
  useKeyboardShortcut('ctrl+,', () => onNavigate('/admin/settings'));
  useKeyboardShortcut('meta+,', () => onNavigate('/admin/settings'));

  const adminSectionButtons = useMemo(
    () =>
      ADMIN_SECTION_DESCRIPTORS.map((descriptor) => (
        <button
          key={descriptor.id}
          type="button"
          onClick={() => onNavigate(descriptor.defaultPath)}
          className={`ml-8 flex w-[calc(100%-2rem)] items-center rounded px-2 py-1.5 text-xs transition-colors ${
            selection.adminSectionId === descriptor.id
              ? 'bg-ds-accent/10 text-ds-accent'
              : 'text-ds-muted hover:bg-ds-bg hover:text-ds-text'
          }`}
        >
          {t(descriptor.labelKey)}
        </button>
      )),
    [onNavigate, selection.adminSectionId, t],
  );

  return (
    <nav
      ref={navRef}
      role="navigation"
      aria-label={t('area.sidebar.primaryLabel')}
      className="flex h-full shrink-0 flex-col border-r border-ds-border bg-ds-surface transition-[width] ease-out"
      style={{
        width: `${sidebarWidth}px`,
        transitionDuration: reducedMotion ? '0ms' : '200ms',
      }}
    >
      <div className={`border-b border-ds-border px-2 py-3 ${collapsed ? '' : 'space-y-3'}`}>
        <div className={`flex items-center ${collapsed ? 'justify-center' : 'justify-between gap-2'}`}>
          <div className={`flex items-center ${collapsed ? 'justify-center' : 'min-w-0 gap-2'}`}>
            <Bot size={20} className="shrink-0 text-ds-accent" />
            {!collapsed && (
              <>
                <span className="truncate text-sm font-semibold text-ds-text">DS Agent</span>
                <span className="rounded bg-ds-bg px-1.5 py-0.5 text-[10px] text-ds-muted">
                  IA v3
                </span>
              </>
            )}
          </div>
          <button
            type="button"
            onClick={handleToggleSidebar}
            aria-label={toggleLabel}
            aria-expanded={!collapsed}
            title={`${toggleLabel} (${t('sidebar.toggle.shortcut')})`}
            className="rounded p-1 text-ds-muted transition-colors hover:bg-ds-bg hover:text-ds-text focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/50"
          >
            {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2">
        <div className="space-y-1">
          {AREA_DESCRIPTORS.map((descriptor) => {
            // v3 hides Mission and Memory — they're folded into the
            // MissionContextBar (top strip) and Admin > Memory respectively.
            if (isLegacyV3AreaId(descriptor.id)) {
              return null;
            }
            const Icon = AREA_ICONS[descriptor.id];
            const isAdmin = descriptor.id === 'admin';
            const isActive = selection.areaId === descriptor.id;
            // v3 visually separates the admin "ring" from the primary triad.
            const showDivider = isAdmin;
            return (
              <div key={descriptor.id}>
                {showDivider && (
                  <div className="my-2 border-t border-ds-border" aria-hidden />
                )}
                <SidebarItem
                  icon={Icon}
                  label={t(descriptor.labelKey)}
                  active={isActive}
                  collapsed={collapsed}
                  onClick={() => onNavigate(descriptor.defaultPath)}
                  dataTestId={`area-nav-${descriptor.id}`}
                />
                {!collapsed && isAdmin && (
                  <div className="mt-1 space-y-1">{adminSectionButtons}</div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
