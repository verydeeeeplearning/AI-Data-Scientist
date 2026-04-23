import type { ReactNode } from 'react';
import type { ResultCardRecord } from '../../stores/chatStore';

export type ResultCardActionId =
  | 'pin'
  | 'export_report'
  | 'compare_run'
  | 'rerun'
  | 'request_review'
  | 'open_artifact';

export interface ResultCardTrustSlotProps {
  card: ResultCardRecord;
  cardId: string;
  resultId: string;
  messageId: string;
}

export interface ResultCardActionDescriptor {
  id: ResultCardActionId;
  label: string;
}

export interface ResultCardViewProps {
  card: ResultCardRecord;
  onAction?: (action: ResultCardActionId, card: ResultCardRecord) => void;
  renderTrustStrip?: (props: ResultCardTrustSlotProps) => ReactNode;
}
