import { useCallback, useEffect, useMemo, useState } from 'react';
import { useWs } from './WsProvider';
import type {
  CertificationStatusView,
  CertificationSubmissionView,
} from '../types/certification';

export function useCertificationBoard() {
  const { status, on } = useWs();
  const [missions, setMissions] = useState<CertificationStatusView[]>([]);
  const [selectedMissionName, setSelectedMissionName] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSubmission, setLastSubmission] = useState<CertificationSubmissionView | null>(null);

  const refresh = useCallback(async () => {
    if (!window.electronAPI?.certification) {
      setMissions([]);
      setSelectedMissionName(null);
      setError(null);
      return;
    }

    setLoading(true);
    const result = await window.electronAPI.certification.list();
    if (!result.ok) {
      setMissions([]);
      setSelectedMissionName(null);
      setError(result.error);
      setLoading(false);
      return;
    }

    setMissions(result.missions);
    setSelectedMissionName((current) => {
      if (current && result.missions.some((mission) => mission.mission_name === current)) {
        return current;
      }
      return result.missions[0]?.mission_name ?? null;
    });
    setError(null);
    setLoading(false);
  }, []);

  useEffect(() => {
    if (status === 'connected') {
      void refresh();
      return;
    }
    setMissions([]);
    setSelectedMissionName(null);
    setLastSubmission(null);
    setError(null);
    setLoading(false);
  }, [refresh, status]);

  useEffect(() => on('stream.done', () => {
    void refresh();
  }), [on, refresh]);

  useEffect(() => on('approval.resolved', () => {
    void refresh();
  }), [on, refresh]);

  const selectedMission = useMemo(
    () => missions.find((mission) => mission.mission_name === selectedMissionName) ?? null,
    [missions, selectedMissionName],
  );

  const submit = useCallback(async (params: {
    missionName: string;
    targetLevel: string;
    approvedBy?: string[];
    evidenceRef?: string;
  }) => {
    if (!window.electronAPI?.certification) {
      throw new Error('Certification API is unavailable.');
    }

    const result = await window.electronAPI.certification.submit(params);
    if (!result.ok) {
      throw new Error(result.error);
    }
    setLastSubmission(result.result);
    await refresh();
    return result.result;
  }, [refresh]);

  return {
    missions,
    selectedMission,
    selectedMissionName,
    setSelectedMissionName,
    loading,
    error,
    lastSubmission,
    refresh,
    submit,
  };
}
