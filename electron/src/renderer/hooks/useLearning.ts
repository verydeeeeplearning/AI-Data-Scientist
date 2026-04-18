import { useCallback, useState } from 'react';
import { useWs } from './WsProvider';

export interface LearningItemView {
  item_id: string;
  type: string;
  status: string;
  title: string;
  priority_score: number;
  evidence_count: number;
  conflict_count: number;
  scope: string;
  tags: string[];
  created_at: string;
}

export interface LearningInboxView {
  items: LearningItemView[];
  total: number;
}

const EMPTY_INBOX: LearningInboxView = { items: [], total: 0 };

export function useLearning() {
  const { rpc } = useWs();
  const [inbox, setInbox] = useState<LearningInboxView>(EMPTY_INBOX);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshInbox = useCallback(
    async (status = 'proposed', itemType = 'all') => {
      setLoading(true);
      setError(null);
      try {
        const result = await rpc('learning.inbox', { status, itemType, limit: 30 });
        setInbox(result as unknown as LearningInboxView);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    [rpc],
  );

  const reviewItem = useCallback(
    async (itemId: string, decision: string, comment = '') => {
      await rpc('learning.review', { itemId, decision, comment });
      await refreshInbox();
    },
    [rpc, refreshInbox],
  );

  return { inbox, loading, error, refreshInbox, reviewItem };
}
