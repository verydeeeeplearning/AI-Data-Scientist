import { ChatPanel } from '../../components/chat/ChatPanel';
import { MissionBriefPanel } from '../../components/mission/MissionBriefPanel';

interface Props {
  onSend: (message: string) => void;
  onAbort: () => void;
  disabled?: boolean;
}

export function MissionPage({ onSend, onAbort, disabled }: Props) {
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="shrink-0 overflow-y-auto border-b border-ds-border">
        <MissionBriefPanel />
      </div>
      <div className="min-h-0 flex-1">
        <ChatPanel onSend={onSend} onAbort={onAbort} disabled={disabled} />
      </div>
    </div>
  );
}
