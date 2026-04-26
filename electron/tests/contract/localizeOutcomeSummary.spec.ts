import assert from 'node:assert/strict';

import { localizeOutcomeSummary } from '../../src/renderer/application/runtime/localizeOutcomeSummary';

type Vars = Record<string, string | number | undefined | null>;

const koTranslations: Record<string, string> = {
  'run.runtime.stageOutcome.dataLoader.loadedRows':
    '{count}개 파일을 적재하고 {rows}개 행을 스캔했습니다.',
  'run.runtime.stageOutcome.dataLoader.loaded': '{count}개 파일을 적재했습니다.',
  'run.runtime.stageOutcome.schemaDiagnose.detected':
    '{count}건의 스키마/품질 이슈를 발견했습니다.',
  'run.runtime.stageOutcome.schemaDiagnose.none': '주요 스키마 이슈는 발견되지 않았습니다.',
  'run.runtime.stageOutcome.evaluation.captured': '평가 신호 {count}건을 캡처했습니다.',
  'run.runtime.stageOutcome.evaluation.completed':
    '{count}개 도구 단계에서 평가를 완료했습니다.',
  'run.runtime.stageOutcome.export.prepared': '내보내기 산출물 {count}개를 준비했습니다.',
  'run.runtime.stageOutcome.eda.completed': '탐색적 분석 단계 {count}개를 완료했습니다.',
  'run.runtime.stageOutcome.featureEngineering.prepared':
    '피처 엔지니어링 단계 {count}개를 준비했습니다.',
  'run.runtime.stageOutcome.baselineModeling.built':
    '기준 모델링 단계 {count}개를 구성했습니다.',
  'run.runtime.stageOutcome.modelComparison.compared':
    '모델 후보 단계 {count}개를 비교했습니다.',
  'run.runtime.stageOutcome.reporting.generated': '보고 산출물 단계 {count}개를 생성했습니다.',
  'run.runtime.stageOutcome.verification.ran': '검증 체크 {count}개를 실행했습니다.',
};

function t(key: string, vars?: Vars): string {
  let template = koTranslations[key] ?? key;
  for (const [name, value] of Object.entries(vars ?? {})) {
    template = template.split(`{${name}}`).join(String(value));
  }
  return template;
}

function run(): void {
  assert.equal(
    localizeOutcomeSummary(t, 'Loaded 1 file(s).'),
    '1개 파일을 적재했습니다.',
  );
  assert.equal(
    localizeOutcomeSummary(t, 'Loaded 2 file(s) and scanned 1,234 rows.'),
    '2개 파일을 적재하고 1,234개 행을 스캔했습니다.',
  );
  assert.equal(
    localizeOutcomeSummary(t, 'Detected 3 schema or quality issue(s).'),
    '3건의 스키마/품질 이슈를 발견했습니다.',
  );
  assert.equal(
    localizeOutcomeSummary(t, 'No major schema issues surfaced.'),
    '주요 스키마 이슈는 발견되지 않았습니다.',
  );
  assert.equal(
    localizeOutcomeSummary(t, 'Captured 4 evaluation signal(s).'),
    '평가 신호 4건을 캡처했습니다.',
  );
  assert.equal(
    localizeOutcomeSummary(t, 'Evaluation completed across 5 tool step(s).'),
    '5개 도구 단계에서 평가를 완료했습니다.',
  );
  assert.equal(
    localizeOutcomeSummary(t, 'Prepared 6 export artifact(s).'),
    '내보내기 산출물 6개를 준비했습니다.',
  );
  assert.equal(
    localizeOutcomeSummary(t, 'Completed 7 exploratory analysis step(s).'),
    '탐색적 분석 단계 7개를 완료했습니다.',
  );
  assert.equal(
    localizeOutcomeSummary(t, 'Prepared 8 feature engineering step(s).'),
    '피처 엔지니어링 단계 8개를 준비했습니다.',
  );
  assert.equal(
    localizeOutcomeSummary(t, 'Built 9 baseline modeling step(s).'),
    '기준 모델링 단계 9개를 구성했습니다.',
  );
  assert.equal(
    localizeOutcomeSummary(t, 'Compared 10 model candidate step(s).'),
    '모델 후보 단계 10개를 비교했습니다.',
  );
  assert.equal(
    localizeOutcomeSummary(t, 'Generated 11 reporting artifact step(s).'),
    '보고 산출물 단계 11개를 생성했습니다.',
  );
  assert.equal(
    localizeOutcomeSummary(t, 'Ran 12 verification check(s).'),
    '검증 체크 12개를 실행했습니다.',
  );
  assert.equal(
    localizeOutcomeSummary(t, 'Custom backend summary.'),
    'Custom backend summary.',
  );
  assert.equal(localizeOutcomeSummary(t, ''), '');

  console.log('[contract] PASS localize-outcome-summary (15 cases)');
}

run();
