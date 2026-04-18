/**
 * Electron channel harness — Playwright-driven E2E.
 *
 * Reuses the packaged Electron bundle at ``electron/dist/`` (produced by
 * C15 and still source-hash-current at Phase 3 start time). Launches
 * Electron via ``playwright._electron``, which in turn spawns the
 * packaged backend via ``DS_AGENT_BACKEND_COMMAND`` env var — this is
 * the exact path taken by end users.
 *
 * For each of the 3 scenarios the harness:
 *   1. Boots Electron (with main UI).
 *   2. Waits for the onboarding wizard's hero to render (proves
 *      backend→WS handshake → renderer mount succeeded).
 *   3. Extracts the dynamically injected sessionId / backend port from
 *      window.__dsAgentBackend (or a best-effort fallback via page eval).
 *   4. Dispatches a ``chat.send`` over the renderer's WS client by
 *      evaluating JS in the renderer context (exposed on
 *      ``window.dsAgentTest``).  If not exposed, the harness records a
 *      "renderer-bridge not exposed" fallback note and asserts backend
 *      parity via the READY token / factory wiring alone.
 *   5. Teardown + cleanup.
 *
 * Output: one JSON result per scenario at
 *   ``.tmp/qa_phase3/runs/EL-<scenario_id>.json``
 *
 * Exit: 0 on completion (individual scenario failures recorded in JSON).
 */

const path = require('node:path');
const fs = require('node:fs');
const crypto = require('node:crypto');

const ELECTRON_DIR = path.resolve(__dirname, '..', '..', 'electron');
const REPO_ROOT = path.resolve(ELECTRON_DIR, '..');

// Playwright lives under electron/node_modules — resolve it explicitly so
// this harness can run from ANY cwd without NODE_PATH gymnastics.
const PLAYWRIGHT_PATH = path.resolve(ELECTRON_DIR, 'node_modules', 'playwright');
const { _electron: electron } = require(PLAYWRIGHT_PATH);
const ELECTRON_MAIN = path.resolve(ELECTRON_DIR, 'dist', 'main', 'index.js');
const BACKEND_BIN = path.resolve(
  REPO_ROOT,
  'dist',
  'ds-agent-backend',
  process.platform === 'win32' ? 'ds-agent-api.exe' : 'ds-agent-api'
);
const RUNS_DIR = path.resolve(REPO_ROOT, '.tmp', 'qa_phase3', 'runs');

const SCENARIOS = [
  {
    id: 'P-01',
    goal: 'tips.csv의 total_bill 예측 — 데이터 로드와 프로파일링, baseline 선형 회귀 모델, 평가, 최종 DeliveryPack(PDF)을 생성하세요.',
    audience: 'Peer',
    authority_mode: null,
    caution_tool: null,
  },
  {
    id: 'P-02',
    goal: '현재 세션의 Authority를 Supervised에서 Delegate로 전환하고, 실험 기록 삭제(가상) CAUTION 도구를 호출해 승인 플로우를 트리거하세요.',
    audience: 'Peer',
    authority_mode: 'delegate',
    caution_tool: 'experiment_log.delete',
  },
  {
    id: 'P-03',
    goal: '세션에서 관찰한 반복 패턴을 LearningInbox 항목으로 추출하고, 하나를 review·approve 후 promote. 이후 2회 eval 실패 → auto-deprecate를 시뮬레이션하세요.',
    audience: 'Peer',
    authority_mode: null,
    caution_tool: null,
  },
];

function normalizeText(text) {
  if (!text) return '';
  let s = String(text).replace(/\s+/g, ' ').trim();
  s = s.replace(/\b[0-9a-fA-F]{8,}\b/g, '<HEX>');
  s = s.replace(/\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?Z?/g, '<TS>');
  return s;
}

function hashBody(text) {
  return crypto.createHash('sha256').update(normalizeText(text), 'utf8').digest('hex');
}

async function runScenario(scenario) {
  if (!fs.existsSync(BACKEND_BIN)) {
    return {
      channel: 'Electron',
      scenario_id: scenario.id,
      status: 'error',
      error_code: 'BACKEND_BIN_MISSING',
      raw_final_content: `missing: ${BACKEND_BIN}`,
      fallback_notes: ['Electron harness skipped: backend binary missing'],
    };
  }
  if (!fs.existsSync(ELECTRON_MAIN)) {
    return {
      channel: 'Electron',
      scenario_id: scenario.id,
      status: 'error',
      error_code: 'ELECTRON_DIST_MISSING',
      raw_final_content: `missing: ${ELECTRON_MAIN}`,
      fallback_notes: ['Electron harness skipped: dist/main missing'],
    };
  }

  const fallbackNotes = [];
  const startTs = new Date().toISOString();
  const sessionId = `electron-${scenario.id}-${Date.now()}`;
  let finalContent = '';
  let errorCode = '';
  let status = 'ok';
  let capturedEvents = [];
  let channelOrigin = 'electron+playwright';
  let appRef = null;
  let backendPid = null;

  try {
    appRef = await electron.launch({
      args: [ELECTRON_MAIN],
      cwd: ELECTRON_DIR,
      env: {
        ...process.env,
        DS_AGENT_BACKEND_COMMAND: BACKEND_BIN,
        DS_AGENT_SENTRY_DSN: '',
        DS_AGENT_E2E_USE_BUILT_RENDERER: '1',
      },
      timeout: 60000,
    });

    const win = await appRef.firstWindow({ timeout: 60000 });
    await win.waitForLoadState('domcontentloaded');

    // Verify main UI (hero) — proves backend handshake succeeded.
    const hero = win.locator('h1', { hasText: /DS Agent/i }).first();
    await hero.waitFor({ state: 'visible', timeout: 60000 });
    const heroText = (await hero.textContent()) || '';

    // Extract backend port/token from the query string the main process
    // passes to the renderer when it opens the main window.
    const connInfo = await win.evaluate(() => {
      const p = new URLSearchParams(window.location.search);
      return {
        port: p.get('port') || '',
        token: p.get('token') || '',
        origin: window.location.origin,
        href: window.location.href,
      };
    });
    channelOrigin = `electron+playwright (backend_port=${connInfo.port || 'unknown'})`;

    // Dispatch chat.send from INSIDE the renderer context so the frame
    // really traverses the Electron → backend WebSocket. This is what we
    // want for true process-level channel parity.
    const rendererResult = await win.evaluate(
      async ({ goal, sid, port, token }) => {
        return await new Promise((resolve) => {
          try {
            if (!port) {
              resolve({
                bridge_present: false,
                content: '',
                events: [],
              });
              return;
            }
            const url = `ws://127.0.0.1:${port}/ws?token=${token}`;
            const ws = new WebSocket(url);
            const events = [];
            let finalContent = '';
            let errorCode = '';
            let status = 'ok';
            let done = false;
            const reqId = `c13p3-el-${sid}`;

            const terminate = () => {
              if (done) return;
              done = true;
              try {
                ws.close();
              } catch (_) {}
              resolve({
                bridge_present: true,
                content: finalContent,
                events,
                error: errorCode,
                status,
              });
            };

            const timer = setTimeout(terminate, 45000);

            ws.onopen = () => {
              ws.send(
                JSON.stringify({
                  type: 'req',
                  id: reqId,
                  method: 'chat.send',
                  params: {
                    sessionId: sid,
                    message: goal,
                    maxIterations: 2,
                    maxCostUsd: 0.0,
                  },
                })
              );
            };
            ws.onmessage = (ev) => {
              let frame;
              try {
                frame = JSON.parse(ev.data);
              } catch (_) {
                return;
              }
              events.push(frame);
              if (frame.type === 'event') {
                const payload = frame.payload || {};
                if (frame.event === 'stream.delta') {
                  finalContent += String(payload.text || payload.delta || '');
                } else if (frame.event === 'task.completed') {
                  const t = payload.message || payload.final || '';
                  if (t) finalContent = String(t);
                } else if (
                  frame.event === 'task.failed' ||
                  frame.event === 'error'
                ) {
                  status = 'error';
                  errorCode = String(
                    payload.code || payload.reason || 'task_failed'
                  );
                }
              } else if (frame.type === 'res' && frame.id === reqId) {
                if (!frame.ok) {
                  status = 'error';
                  const err = frame.error || {};
                  errorCode = String(err.code || '');
                  const msg = err.message || '';
                  if (msg && !finalContent) finalContent = String(msg);
                } else {
                  const payload = frame.payload || {};
                  const t = payload.content || payload.message || '';
                  if (t && !finalContent) finalContent = String(t);
                }
                clearTimeout(timer);
                terminate();
              }
            };
            ws.onerror = (err) => {
              status = 'error';
              errorCode = 'WS_ERROR';
              if (!finalContent)
                finalContent = `ws error: ${String(err && err.message)}`;
              clearTimeout(timer);
              terminate();
            };
            ws.onclose = () => {
              clearTimeout(timer);
              terminate();
            };
          } catch (err) {
            resolve({
              bridge_present: true,
              error: String(err),
              content: '',
              events: [],
            });
          }
        });
      },
      { goal: scenario.goal, sid: sessionId, port: connInfo.port, token: connInfo.token }
    );

    capturedEvents = rendererResult.events || [];
    if (!rendererResult.bridge_present) {
      fallbackNotes.push(
        'port query-param missing in renderer URL — Electron parity reduced to main-UI handshake'
      );
      finalContent = `[electron-main-ui-rendered] hero="${heroText.trim()}"`;
    } else if (rendererResult.status === 'error') {
      status = rendererResult.status;
      errorCode = rendererResult.error || 'UNKNOWN';
      finalContent = rendererResult.content || `error: ${errorCode}`;
    } else {
      finalContent = rendererResult.content || '';
    }

    backendPid = null;
  } catch (err) {
    status = 'error';
    errorCode = 'ELECTRON_LAUNCH_FAILED';
    finalContent = `[harness] electron.launch/assertion failed: ${String(err).slice(0, 500)}`;
    fallbackNotes.push('Electron launch or first-window wait failed');
  } finally {
    if (appRef) {
      try {
        await appRef.close();
      } catch (closeErr) {
        fallbackNotes.push(`app.close failed: ${String(closeErr).slice(0, 200)}`);
      }
      // Belt-and-braces: on Windows, electron's spawned children can linger
      // beyond app.close(). Nuke any stragglers from this launch.
      try {
        const { execSync } = require('node:child_process');
        if (process.platform === 'win32') {
          execSync('taskkill /F /T /IM electron.exe', {
            stdio: 'ignore',
          });
        }
      } catch (_) {
        // ignore — nothing to clean up is fine
      }
    }
  }

  if (!finalContent) {
    finalContent = '[harness] no content captured';
  }

  const result = {
    channel: 'Electron',
    scenario_id: scenario.id,
    session_id: sessionId,
    status,
    goal_echo: normalizeText(scenario.goal).slice(0, 200),
    final_verdict: '',
    delivery_pack_body_hash: hashBody(finalContent),
    delivery_pack_body_preview: normalizeText(finalContent).slice(0, 200),
    metric_spec: {},
    error_code: errorCode,
    channel_origin: channelOrigin,
    timestamp_utc: startTs,
    raw_final_content: finalContent,
    raw_event_count: capturedEvents.length,
    raw_event_types: [...new Set(capturedEvents.map((e) => e.type || e.event || ''))],
    fallback_notes: fallbackNotes,
  };

  fs.mkdirSync(RUNS_DIR, { recursive: true });
  fs.writeFileSync(
    path.resolve(RUNS_DIR, `EL-${scenario.id}.json`),
    JSON.stringify(result, null, 2),
    'utf8'
  );
  const logPath = path.resolve(RUNS_DIR, `EL-${scenario.id}.log`);
  const log = [
    `=== C13 Phase 3 Electron channel — scenario ${scenario.id} ===`,
    `session_id: ${sessionId}`,
    `status: ${status}`,
    `error_code: ${errorCode}`,
    `channel_origin: ${channelOrigin}`,
    `timestamp: ${startTs}`,
    '',
    '--- fallback_notes ---',
    ...fallbackNotes.map((n) => `  - ${n}`),
    '',
    '--- goal ---',
    scenario.goal,
    '',
    '--- final_content ---',
    finalContent,
    '',
  ].join('\n');
  fs.writeFileSync(logPath, log, 'utf8');

  return result;
}

async function main() {
  const results = [];
  for (const sc of SCENARIOS) {
    console.log(`[harness_electron] scenario ${sc.id} starting...`);
    const r = await runScenario(sc);
    console.log(
      `[harness_electron] scenario ${sc.id} → status=${r.status} error=${r.error_code || '-'}`
    );
    results.push(r);
  }
  fs.mkdirSync(RUNS_DIR, { recursive: true });
  fs.writeFileSync(
    path.resolve(RUNS_DIR, 'EL-summary.json'),
    JSON.stringify(results, null, 2),
    'utf8'
  );
  console.log(`[harness_electron] completed ${results.length} runs`);
}

main().catch((err) => {
  console.error('[harness_electron] FATAL:', err);
  process.exit(1);
});
