import {
  fetchAccessLogs as fetchAccessLogsApi,
  type AccessLogEntrySummary,
  type ListAccessLogOptions,
} from '../infrastructure/api/accessLogApi';

export type { AccessLogEntrySummary, ListAccessLogOptions };

export function useAccessLogs() {
  return {
    fetchAccessLogs: (options: ListAccessLogOptions = {}) => fetchAccessLogsApi(options),
  };
}
