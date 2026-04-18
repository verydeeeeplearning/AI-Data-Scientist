/**
 * i18n store — Korean/English translations.
 *
 * Simple key-value approach. Default language detected from system locale.
 */

import { create } from 'zustand';

export type Locale = 'ko' | 'en';

const translations: Record<Locale, Record<string, string>> = {
  en: {
    // Splash
    'splash.starting': 'Starting backend...',
    'splash.disconnected': 'Unable to connect to backend',
    'splash.retry': 'Retry',
    'splash.waiting': 'Make sure the Python backend is running, or wait for it to start automatically.',

    // Onboarding
    'onboarding.title': 'DS Agent',
    'onboarding.subtitle': 'AI Data Scientist',
    'onboarding.choose': 'Choose an LLM provider to get started:',
    'onboarding.login': 'Login (No API key needed)',
    'onboarding.freeApi': 'Free API Key',
    'onboarding.paidApi': 'Paid API Key',
    'onboarding.local': 'Local',
    'onboarding.enterKey': 'Enter your API key',
    'onboarding.keyStored': 'Your key is stored locally and never sent anywhere except the provider API.',
    'onboarding.continue': 'Continue',
    'onboarding.back': 'Back',
    'onboarding.ready': 'Ready to go!',
    'onboarding.using': 'Using',
    'onboarding.start': 'Start DS Agent',
    'onboarding.different': 'Choose a different provider',

    // Chat
    'chat.empty.title': 'DS Agent',
    'chat.empty.desc': 'AI Data Scientist ready to help.',
    'chat.empty.hint': 'Send a message to start a data science session.',
    'chat.input.placeholder': 'Send a message... (Enter to send, Shift+Enter for newline)',
    'chat.you': 'You',
    'chat.agent': 'DS Agent',
    'chat.toolActivity': 'Tool Activity',

    // Sidebar
    'sidebar.files': 'Files',
    'sidebar.plots': 'Plots',
    'sidebar.model': 'Model',
    'sidebar.mode': 'Mode',
    'sidebar.upload': 'Upload files',
    'sidebar.dropHere': 'Drop files here',
    'sidebar.noFiles': 'No files yet',
    'sidebar.noPlots': 'No plots yet',
    'sidebar.onlyPlots': 'Only plots — see Plots section',
    'sidebar.refreshFiles': 'Refresh files',
    'sidebar.preview': 'Preview',
    'sidebar.exportAs': 'Export as',
    'sidebar.delete': 'Delete',
    'sidebar.deleteConfirm': 'Delete {{name}}?',
    'sidebar.deleteFailed': 'Delete failed: {{message}}',
    'sidebar.exportFailed': 'Export failed: {{message}}',
    'sidebar.exportDesktopOnly': 'Export is only available in the desktop app.',
    'sidebar.importFiles': 'Import files',
    'sidebar.dropToImport': 'Drop files to import',
    'sidebar.supportsUpTo': 'Supports data files up to 100 MB each',
    'sidebar.uploaded': 'Uploaded {{name}}.',
    'sidebar.uploadedCount': 'Uploaded {{count}} files.',
    'sidebar.partialUpload': 'Uploaded {{count}} file(s), but some items failed. {{message}}',
    'sidebar.uploadFailed': 'Upload failed.',
    'sidebar.unsupportedType': 'Unsupported file type: {{ext}}.',
    'sidebar.oversize': '{{name}} is too large ({{size}}).',
    'sidebar.oversizeHint':
      'Try a representative extract first, convert the file to Parquet for a smaller upload, or move the dataset into the workspace outside the UI if you need the full file.',
    'sidebar.exceedsLimit': 'File exceeds the 100 MB upload limit ({{size}}).',

    // Mode
    'mode.auto': 'Auto',
    'mode.auto.desc': 'Agent runs freely',
    'mode.supervised': 'Supervised',
    'mode.supervised.desc': 'Confirm before actions',
    'mode.step': 'Step-by-Step',
    'mode.step.desc': 'Approve each step',

    // Settings
    'settings.title': 'Settings',
    'settings.appearance': 'Appearance',
    'settings.theme': 'Theme',
    'settings.dark': 'Dark',
    'settings.light': 'Light',
    'settings.model': 'Model',
    'settings.mode': 'Mode',
    'settings.budget': 'Budget Limit',
    'settings.budgetUnit': 'USD per session',
    'settings.shortcuts': 'Keyboard Shortcuts',
    'settings.send': 'Send message',
    'settings.newline': 'New line',
    'settings.abort': 'Abort current run',
    'settings.cycleMode': 'Cycle mode',
    'settings.openSettings': 'Open settings',

    // Status
    'status.running': 'Running',
    'status.reconnecting': 'Reconnecting...',
    'status.lost': 'Connection lost',
    'status.lostDesc': 'Waiting for backend to restart...',

    // Errors
    'error.title': 'Something went wrong',
    'error.desc': 'An unexpected error occurred in the application.',
    'error.retry': 'Try Again',

    // Sidebar tabs
    'sidebar.tab.files': 'Files',
    'sidebar.tab.workflow': 'Workflow',
    'sidebar.tab.experiments': 'Experiments',

    // Workflow Progress
    'workflow.title': 'Workflow',
    'workflow.scoping': 'Scoping',
    'workflow.data_loading': 'Data Loading',
    'workflow.profiling': 'Profiling',
    'workflow.eda': 'EDA',
    'workflow.feature_eng': 'Feature Eng',
    'workflow.modeling': 'Modeling',
    'workflow.evaluation': 'Evaluation',
    'workflow.reporting': 'Reporting',

    // Quality Panel
    'quality.title': 'Quality',
    'quality.grade.A': 'Production Ready',
    'quality.grade.B': 'Good',
    'quality.grade.C': 'Needs Improvement',
    'quality.grade.D': 'Below Standard',
    'quality.grade.F': 'Unacceptable',

    // Experiment Table
    'experiments.title': 'Experiments',
    'experiments.model': 'Model',
    'experiments.time': 'Time',
    'experiments.best': 'best',
    'experiments.baseline': 'baseline',

    // Alert Banner
    'alert.leakage': 'Data Leakage Detected',
    'alert.overfitting': 'Overfitting Detected',
    'alert.baseline_missing': 'No Baseline Established',

    // Budget Bar
    'budget.title': 'Budget',
    'budget.context': 'Context',

    // Auto-update (P1-14)
    'update.available': 'Version {{version}} is available',
    'update.downloading': 'Downloading update... {{percent}}%',
    'update.ready': 'Update ready. Restart now?',
    'update.download_btn': 'Download',
    'update.install_btn': 'Restart now',
    'update.later_btn': 'Later',
    'update.defer_btn': 'Install next time',

    // Generic
    'common.close': 'Close',
    'common.error': 'Something went wrong',
  },

  ko: {
    // Splash
    'splash.starting': '백엔드 시작 중...',
    'splash.disconnected': '백엔드에 연결할 수 없습니다',
    'splash.retry': '재시도',
    'splash.waiting': 'Python 백엔드가 실행 중인지 확인하거나 자동 시작을 기다려 주세요.',

    // Onboarding
    'onboarding.title': 'DS Agent',
    'onboarding.subtitle': 'AI 데이터 사이언티스트',
    'onboarding.choose': 'LLM 프로바이더를 선택하세요:',
    'onboarding.login': '로그인 (API key 불필요)',
    'onboarding.freeApi': '무료 API Key',
    'onboarding.paidApi': '유료 API Key',
    'onboarding.local': '로컬',
    'onboarding.enterKey': 'API key를 입력하세요',
    'onboarding.keyStored': '키는 로컬에 저장되며 프로바이더 API 외에는 전송되지 않습니다.',
    'onboarding.continue': '계속',
    'onboarding.back': '뒤로',
    'onboarding.ready': '준비 완료!',
    'onboarding.using': '사용 모델:',
    'onboarding.start': 'DS Agent 시작',
    'onboarding.different': '다른 프로바이더 선택',

    // Chat
    'chat.empty.title': 'DS Agent',
    'chat.empty.desc': 'AI 데이터 사이언티스트가 준비되었습니다.',
    'chat.empty.hint': '메시지를 보내 데이터 사이언스 세션을 시작하세요.',
    'chat.input.placeholder': '메시지를 입력하세요... (Enter 전송, Shift+Enter 줄바꿈)',
    'chat.you': '사용자',
    'chat.agent': 'DS Agent',
    'chat.toolActivity': '도구 활동',

    // Sidebar
    'sidebar.files': '파일',
    'sidebar.plots': '플롯',
    'sidebar.model': '모델',
    'sidebar.mode': '모드',
    'sidebar.upload': '파일 업로드',
    'sidebar.dropHere': '여기에 파일을 놓으세요',
    'sidebar.noFiles': '파일 없음',
    'sidebar.noPlots': '플롯 없음',
    'sidebar.onlyPlots': '플롯 전용 — Plots 섹션을 확인하세요',
    'sidebar.refreshFiles': '파일 새로고침',
    'sidebar.preview': '미리보기',
    'sidebar.exportAs': '내보내기',
    'sidebar.delete': '삭제',
    'sidebar.deleteConfirm': '{{name}} 파일을 삭제할까요?',
    'sidebar.deleteFailed': '삭제 실패: {{message}}',
    'sidebar.exportFailed': '내보내기 실패: {{message}}',
    'sidebar.exportDesktopOnly': '내보내기는 데스크톱 앱에서만 사용할 수 있습니다.',
    'sidebar.importFiles': '파일 가져오기',
    'sidebar.dropToImport': '파일을 여기에 놓으면 가져옵니다',
    'sidebar.supportsUpTo': '파일당 최대 100MB까지 지원합니다',
    'sidebar.uploaded': '{{name}} 업로드 완료.',
    'sidebar.uploadedCount': '파일 {{count}}개 업로드 완료.',
    'sidebar.partialUpload': '{{count}}개 업로드 완료, 일부 실패. {{message}}',
    'sidebar.uploadFailed': '업로드에 실패했습니다.',
    'sidebar.unsupportedType': '지원하지 않는 파일 형식: {{ext}}.',
    'sidebar.oversize': '{{name}} 파일이 너무 큽니다 ({{size}}).',
    'sidebar.oversizeHint':
      '대표 샘플만 먼저 업로드하거나 Parquet으로 변환해 크기를 줄이세요. 전체 데이터가 필요하면 UI 외부에서 워크스페이스로 옮기는 방법도 있습니다.',
    'sidebar.exceedsLimit': '100MB 업로드 한도를 초과했습니다 ({{size}}).',

    // Mode
    'mode.auto': '자동',
    'mode.auto.desc': '에이전트가 자유롭게 실행',
    'mode.supervised': '감독',
    'mode.supervised.desc': '작업 전 확인',
    'mode.step': '단계별',
    'mode.step.desc': '각 단계 승인',

    // Settings
    'settings.title': '설정',
    'settings.appearance': '외관',
    'settings.theme': '테마',
    'settings.dark': '다크',
    'settings.light': '라이트',
    'settings.model': '모델',
    'settings.mode': '모드',
    'settings.budget': '예산 한도',
    'settings.budgetUnit': '세션당 USD',
    'settings.shortcuts': '키보드 단축키',
    'settings.send': '메시지 전송',
    'settings.newline': '줄바꿈',
    'settings.abort': '실행 중단',
    'settings.cycleMode': '모드 전환',
    'settings.openSettings': '설정 열기',

    // Status
    'status.running': '실행 중',
    'status.reconnecting': '재연결 중...',
    'status.lost': '연결 끊김',
    'status.lostDesc': '백엔드 재시작 대기 중...',

    // Errors
    'error.title': '오류가 발생했습니다',
    'error.desc': '애플리케이션에서 예기치 않은 오류가 발생했습니다.',
    'error.retry': '다시 시도',

    // Sidebar tabs
    'sidebar.tab.files': '파일',
    'sidebar.tab.workflow': '워크플로우',
    'sidebar.tab.experiments': '실험',

    // Workflow Progress
    'workflow.title': '워크플로우',
    'workflow.scoping': '범위 정의',
    'workflow.data_loading': '데이터 로딩',
    'workflow.profiling': '프로파일링',
    'workflow.eda': '탐색적 분석',
    'workflow.feature_eng': '피처 엔지니어링',
    'workflow.modeling': '모델링',
    'workflow.evaluation': '평가',
    'workflow.reporting': '보고서',

    // Quality Panel
    'quality.title': '품질',
    'quality.grade.A': '프로덕션 준비 완료',
    'quality.grade.B': '양호',
    'quality.grade.C': '개선 필요',
    'quality.grade.D': '기준 미달',
    'quality.grade.F': '부적합',

    // Experiment Table
    'experiments.title': '실험',
    'experiments.model': '모델',
    'experiments.time': '시간',
    'experiments.best': '최고',
    'experiments.baseline': '기준선',

    // Alert Banner
    'alert.leakage': '데이터 누수 감지',
    'alert.overfitting': '과적합 감지',
    'alert.baseline_missing': '기준선 미수립',

    // Budget Bar
    'budget.title': '예산',
    'budget.context': '컨텍스트',

    // Auto-update (P1-14)
    'update.available': '새 버전 {{version}} 이 있습니다',
    'update.downloading': '업데이트 다운로드 중... {{percent}}%',
    'update.ready': '업데이트 준비 완료. 지금 재시작하시겠습니까?',
    'update.download_btn': '다운로드',
    'update.install_btn': '지금 재시작',
    'update.later_btn': '나중에',
    'update.defer_btn': '다음 시작 시 설치',

    // Generic
    'common.close': '닫기',
    'common.error': '문제가 발생했습니다',
  },
};

function detectLocale(): Locale {
  try {
    const lang = navigator.language.toLowerCase();
    if (lang.startsWith('ko')) return 'ko';
  } catch {}
  return 'en';
}

function loadLocale(): Locale {
  try {
    const saved = localStorage.getItem('ds-agent-locale') as Locale | null;
    if (saved && (saved === 'ko' || saved === 'en')) return saved;
  } catch {}
  return detectLocale();
}

type Interpolations = Record<string, string | number | undefined>;

interface I18nState {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string, vars?: Interpolations) => string;
}

function interpolate(template: string, vars?: Interpolations): string {
  if (!vars) return template;
  return template.replace(/\{\{\s*(\w+)\s*\}\}/g, (_match, name: string) => {
    const value = vars[name];
    return value === undefined || value === null ? '' : String(value);
  });
}

export const useI18n = create<I18nState>((set, get) => ({
  locale: loadLocale(),

  setLocale: (l) => {
    try { localStorage.setItem('ds-agent-locale', l); } catch {}
    set({ locale: l });
  },

  t: (key, vars) => {
    const { locale } = get();
    const template = translations[locale][key] ?? translations.en[key] ?? key;
    return interpolate(template, vars);
  },
}));
