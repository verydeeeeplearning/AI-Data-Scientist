#!/usr/bin/env node
/**
 * One-shot: ensure Phase C mission keys are present in
 * public/locales/<lng>/mission.json. Idempotent — only adds missing keys.
 *
 * Phase C added: drawer.* / dropdown.* / connection.tooltip.* /
 * budgetAlert.* (pause/snooze/dismiss/snoozedFor/pauseFailed/paused) +
 * collapse copy switched to Korean/Japanese.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = resolve(fileURLToPath(new URL('.', import.meta.url)));
const ROOT = resolve(__dirname, '..');
const OUT_DIR = resolve(ROOT, 'public/locales');

const PATCHES = {
  en: {
    'header.collapse.expand': 'Expand Header',
    'header.collapse.collapse': 'Compact Header',
    'header.collapse.shortcut': 'Ctrl+Shift+M',
    'header.budgetAlert.continue': 'Keep working',
    'header.budgetAlert.pause': 'Pause agent',
    'header.budgetAlert.dismiss': 'Dismiss for this session',
    'header.budgetAlert.snoozeLabel': 'Snooze warnings',
    'header.budgetAlert.snooze.5m': '5 minutes',
    'header.budgetAlert.snooze.30m': '30 minutes',
    'header.budgetAlert.snooze.1h': '1 hour',
    'header.budgetAlert.snoozedFor': 'Snoozed for {duration}',
    'header.budgetAlert.pauseFailed': 'Could not pause the agent: {reason}',
    'header.budgetAlert.paused': 'Agent paused. Review the budget before resuming.',
    'drawer.title.goal': 'Edit goal',
    'drawer.title.dataSources': 'Manage data sources',
    'drawer.title.deliverables': 'Manage deliverables',
    'drawer.title.constraints': 'Edit constraints',
    'drawer.title.stage': 'Stage progress',
    'drawer.title.budget': 'Budget controls',
    'drawer.description.goal':
      'Update the mission goal and success criteria captured for this run.',
    'drawer.description.dataSources':
      'Inspect the data sources currently attached to this mission.',
    'drawer.description.deliverables':
      'Inspect the deliverables expected for this mission.',
    'drawer.description.constraints':
      'Inspect language, approval, and locality constraints.',
    'drawer.description.stage': 'Read-only stage timeline for the active mission.',
    'drawer.description.budget': 'Inspect spend and configure budget warnings.',
    'drawer.close': 'Close',
    'drawer.save': 'Save',
    'drawer.cancel': 'Cancel',
    'drawer.readonly': 'Read only — edits land in upcoming Workspace work.',
    'dropdown.mode.title': 'Select execution mode',
    'dropdown.model.title': 'Select model',
    'dropdown.empty': 'No options available yet.',
    'connection.tooltip.label': 'Connection details',
    'connection.tooltip.healthy': 'Live connection to the backend.',
    'connection.tooltip.reconnecting': 'Reconnecting — events may be delayed.',
    'connection.tooltip.disconnected':
      'Disconnected — Mission Header is showing the last known state.',
  },
  ko: {
    'header.collapse.expand': '헤더 펼치기',
    'header.collapse.collapse': '헤더 접기',
    'header.collapse.shortcut': 'Ctrl+Shift+M',
    'header.budgetAlert.warningTitle': '예산 경고',
    'header.budgetAlert.warningBody':
      '현재 실행이 세션 예산 한도({spend})에 근접했습니다. 비용이 더 늘기 전에 예산을 검토하거나 일시정지하세요.',
    'header.budgetAlert.errorTitle': '예산 한도 도달',
    'header.budgetAlert.errorBody':
      '현재 실행이 설정된 세션 예산({spend})에 도달했거나 초과했습니다. 예산을 검토하거나 실행을 중단하세요.',
    'header.budgetAlert.review': '예산 검토',
    'header.budgetAlert.abort': '실행 중단',
    'header.budgetAlert.continue': '계속 진행',
    'header.budgetAlert.pause': '에이전트 일시정지',
    'header.budgetAlert.dismiss': '이 세션에서 무시',
    'header.budgetAlert.snoozeLabel': '경고 미루기',
    'header.budgetAlert.snooze.5m': '5분',
    'header.budgetAlert.snooze.30m': '30분',
    'header.budgetAlert.snooze.1h': '1시간',
    'header.budgetAlert.snoozedFor': '{duration} 동안 미룸',
    'header.budgetAlert.pauseFailed': '에이전트를 일시정지하지 못했습니다: {reason}',
    'header.budgetAlert.paused': '에이전트가 일시정지되었습니다. 예산을 검토한 후 재개하세요.',
    'drawer.title.goal': '목표 편집',
    'drawer.title.dataSources': '데이터 소스 관리',
    'drawer.title.deliverables': '산출물 관리',
    'drawer.title.constraints': '제약 편집',
    'drawer.title.stage': '단계 진행 상황',
    'drawer.title.budget': '예산 제어',
    'drawer.description.goal': '이번 실행에 적용된 미션 목표와 성공 기준을 갱신합니다.',
    'drawer.description.dataSources': '현재 미션에 연결된 데이터 소스를 확인합니다.',
    'drawer.description.deliverables': '이 미션의 산출물을 확인합니다.',
    'drawer.description.constraints': '언어, 승인, 로컬 모델 제약을 확인합니다.',
    'drawer.description.stage': '활성 미션의 단계 타임라인 (읽기 전용)입니다.',
    'drawer.description.budget': '사용액을 확인하고 예산 경고를 설정합니다.',
    'drawer.close': '닫기',
    'drawer.save': '저장',
    'drawer.cancel': '취소',
    'drawer.readonly': '읽기 전용 — 편집은 차후 Workspace 작업에서 다룹니다.',
    'dropdown.mode.title': '실행 모드 선택',
    'dropdown.model.title': '모델 선택',
    'dropdown.empty': '선택 가능한 옵션이 없습니다.',
    'connection.tooltip.label': '연결 정보',
    'connection.tooltip.healthy': '백엔드와 정상 연결되어 있습니다.',
    'connection.tooltip.reconnecting': '재연결 중 — 이벤트 갱신이 지연될 수 있습니다.',
    'connection.tooltip.disconnected': '연결 끊김 — 마지막으로 알려진 상태를 표시합니다.',
  },
  ja: {
    'header.collapse.expand': 'ヘッダーを展開',
    'header.collapse.collapse': 'ヘッダーをコンパクトに',
    'header.collapse.shortcut': 'Ctrl+Shift+M',
    'header.budgetAlert.warningTitle': '予算警告',
    'header.budgetAlert.warningBody':
      'この実行はセッション予算の上限({spend})に近づいています。コストが膨らむ前に予算を確認するか、一時停止してください。',
    'header.budgetAlert.errorTitle': '予算上限に到達',
    'header.budgetAlert.errorBody':
      'この実行は設定済みの予算({spend})に到達または超過しました。予算を確認するか、実行を中止してください。',
    'header.budgetAlert.review': '予算を確認',
    'header.budgetAlert.abort': '実行を中止',
    'header.budgetAlert.continue': '続行',
    'header.budgetAlert.pause': 'エージェントを一時停止',
    'header.budgetAlert.dismiss': 'このセッションでは無視',
    'header.budgetAlert.snoozeLabel': '警告をスヌーズ',
    'header.budgetAlert.snooze.5m': '5分',
    'header.budgetAlert.snooze.30m': '30分',
    'header.budgetAlert.snooze.1h': '1時間',
    'header.budgetAlert.snoozedFor': '{duration} スヌーズ中',
    'header.budgetAlert.pauseFailed': 'エージェントを一時停止できませんでした: {reason}',
    'header.budgetAlert.paused':
      'エージェントを一時停止しました。予算を確認してから再開してください。',
    'drawer.title.goal': '目標を編集',
    'drawer.title.dataSources': 'データソースを管理',
    'drawer.title.deliverables': '成果物を管理',
    'drawer.title.constraints': '制約を編集',
    'drawer.title.stage': 'ステージの進行',
    'drawer.title.budget': '予算コントロール',
    'drawer.description.goal':
      'この実行に紐づくミッションの目標と成功基準を更新します。',
    'drawer.description.dataSources':
      '現在ミッションに接続されているデータソースを確認します。',
    'drawer.description.deliverables': 'このミッションの成果物を確認します。',
    'drawer.description.constraints': '言語、承認、ローカル専用の制約を確認します。',
    'drawer.description.stage':
      'アクティブなミッションのステージタイムライン (読み取り専用)。',
    'drawer.description.budget': '使用額を確認し、予算警告を設定します。',
    'drawer.close': '閉じる',
    'drawer.save': '保存',
    'drawer.cancel': 'キャンセル',
    'drawer.readonly': '読み取り専用 — 編集は今後のWorkspaceで対応します。',
    'dropdown.mode.title': '実行モードを選択',
    'dropdown.model.title': 'モデルを選択',
    'dropdown.empty': '選択可能なオプションがありません。',
    'connection.tooltip.label': '接続情報',
    'connection.tooltip.healthy': 'バックエンドにライブ接続中です。',
    'connection.tooltip.reconnecting': '再接続中 — イベントが遅延する可能性があります。',
    'connection.tooltip.disconnected': '切断中 — 最後に確認した状態を表示しています。',
  },
};

for (const [lng, patches] of Object.entries(PATCHES)) {
  const file = join(OUT_DIR, lng, 'mission.json');
  const data = JSON.parse(readFileSync(file, 'utf8'));
  let added = 0;
  let updated = 0;
  for (const [k, v] of Object.entries(patches)) {
    if (!(k in data)) {
      data[k] = v;
      added += 1;
    } else if (data[k] !== v) {
      data[k] = v;
      updated += 1;
    }
  }
  // sort keys for stable output
  const sorted = Object.fromEntries(Object.entries(data).sort(([a], [b]) => a.localeCompare(b)));
  writeFileSync(file, `${JSON.stringify(sorted, null, 2)}\n`, 'utf8');
  console.log(`[${lng}/mission] +${added} new, ${updated} updated, total=${Object.keys(sorted).length}`);
}
