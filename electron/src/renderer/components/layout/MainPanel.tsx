/**
 * Main panel layout — Sidebar + Chat + StatusBar.
 */

import { Sidebar } from './Sidebar';
import { StatusBar } from './StatusBar';
import { ChatPanel } from '../chat/ChatPanel';
import { RunDetailDrawer } from '../runtime/RunDetailDrawer';
import type { ModelGroup } from '../../hooks/useModels';
import type { SimpleQualityPreset } from '../../utils/qualityPreset';

interface Props {
  onSend: (message: string) => void;
  onAbort: () => void;
  onRefreshFiles: () => void;
  onChangeModel: (model: string) => void;
  onChangeQualityPreset: (preset: SimpleQualityPreset) => void;
  onChangeMode: (mode: 'auto' | 'supervised' | 'step-by-step') => void;
  onUploadFile: (file: File) => Promise<string | null>;
  onOpenSettings: () => void;
  disabled?: boolean;
  modelGroups: ModelGroup[];
}

export function MainPanel({
  onSend,
  onAbort,
  onRefreshFiles,
  onChangeModel,
  onChangeQualityPreset,
  onChangeMode,
  onUploadFile,
  onOpenSettings,
  disabled,
  modelGroups,
}: Props) {
  return (
    <div className="flex flex-col h-screen bg-ds-bg text-ds-text">
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <Sidebar
          onRefreshFiles={onRefreshFiles}
          onChangeModel={onChangeModel}
          onChangeQualityPreset={onChangeQualityPreset}
          onChangeMode={onChangeMode}
          onUploadFile={onUploadFile}
          onOpenSettings={onOpenSettings}
          modelGroups={modelGroups}
        />

        {/* Chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          <ChatPanel onSend={onSend} onAbort={onAbort} disabled={disabled} />
        </div>

        <RunDetailDrawer />
      </div>

      {/* Status bar */}
      <StatusBar />
    </div>
  );
}
