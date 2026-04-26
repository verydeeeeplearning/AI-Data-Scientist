#!/usr/bin/env node
/*
 * Minimal backend fixture for Telegram onboarding smoke tests.
 *
 * It implements the Electron startup contract (`READY:<port>:<token>`),
 * /health, onboarding finalize, and the subset of WebSocket RPC methods the
 * renderer calls while walking through first-run onboarding.
 */

const crypto = require('node:crypto');
const http = require('node:http');
const { URL } = require('node:url');

const TOKEN = 'telegram-smoke-token';
const MODEL_ID = 'ollama/e2e-local';
const PAIRING_HANDLE_ID = 'pairing-smoke-1';
const PAIRING_CODE = '428193';
const CHAT_ID = '900100200';

let paired = false;
let pairingStarted = false;
const sockets = new Set();

function readPort() {
  const index = process.argv.indexOf('--port');
  if (index >= 0 && process.argv[index + 1]) {
    const parsed = Number.parseInt(process.argv[index + 1], 10);
    if (Number.isInteger(parsed) && parsed > 0) {
      return parsed;
    }
  }
  return 18790;
}

function corsHeaders(extra = {}) {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    ...extra,
  };
}

function sendJson(res, status, payload) {
  res.writeHead(status, corsHeaders({ 'Content-Type': 'application/json' }));
  res.end(JSON.stringify(payload));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf8');
      if (!raw.trim()) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(raw));
      } catch (error) {
        reject(error);
      }
    });
    req.on('error', reject);
  });
}

function statusPayload() {
  return {
    model: MODEL_ID,
    qualityPreset: 'balanced',
    mode: 'auto',
    activeSessions: 0,
    autonomousRuntimeEnabled: true,
    autonomousRuntimeRunning: false,
    sensorBacklog: 0,
  };
}

function telegramStatusPayload() {
  return {
    enabled: paired || pairingStarted,
    status: paired ? 'running' : pairingStarted ? 'starting' : 'disabled',
    botUsername: 'ds_agent_smoke_bot',
    botId: 424242,
    firstName: 'DS Agent Smoke',
    pairedChats: paired
      ? [
          {
            chatId: CHAT_ID,
            firstActiveAt: Date.now(),
            lastActiveAt: Date.now(),
          },
        ]
      : [],
    lastError: null,
  };
}

function modelCatalog() {
  return {
    models: [
      {
        id: MODEL_ID,
        provider: 'ollama',
        displayName: 'Local Test Model',
        maxContext: 32768,
        maxOutput: 4096,
        authType: 'local',
        legacy: false,
        capabilityGroup: 'offline_capable',
        capabilityBadges: ['offline', 'fast', 'cheap', 'strong_reasoning'],
        recommendedFor: ['first_run', 'offline'],
      },
    ],
  };
}

function configPayload() {
  return {
    config: {
      agent: {
        language: 'en',
        mode: 'auto',
        workspace_dir: process.cwd(),
      },
      provider: {
        default_model: MODEL_ID,
        quality_preset: 'balanced',
        max_budget_usd: 10,
        budget_warning_threshold_pct: 80,
      },
      observability: {
        sentry_dsn: '',
        error_reporting_enabled: false,
        telemetry_enabled: false,
      },
      channels: {
        telegram: {
          enabled: paired,
          allow_from: paired ? [CHAT_ID] : [],
        },
      },
    },
  };
}

function usageSummaryPayload() {
  return {
    actorId: 'local-user',
    monthlyCostUsd: 0,
    monthlyBudgetUsd: 10,
    budgetUsedPct: 0,
    cacheSavingsUsd: 0,
    sessionCostUsd: 0,
    todayCostUsd: 0,
    remainingBudgetUsd: 10,
    monthRunCount: 0,
    warningLevel: 'ok',
    warningThresholdPct: 80,
    limitExceeded: false,
    byModel: [],
    recentRuns: [],
  };
}

function policyPayload() {
  return {
    automationProfile: 'balanced',
    recurringGoals: [],
    standingOrders: [],
    actionMatrixRows: [],
    actionMatrixOverrides: {},
    actionMatrixOverrideCount: 0,
  };
}

function handleRpc(method, params) {
  switch (method) {
    case 'ping':
      return {};
    case 'status.get':
      return statusPayload();
    case 'provider.models':
      return modelCatalog();
    case 'provider.authStatus':
      return { statuses: { ollama: 'local' } };
    case 'provider.health':
      return {
        providers: [
          {
            id: 'ollama',
            label: 'Ollama',
            status: 'ok',
            hasCredentials: true,
            authStatus: 'local',
            latencyMs: 1,
            message: 'Local model fixture ready.',
            checkedAt: Date.now(),
            modelCount: 1,
          },
        ],
      };
    case 'oauth.status':
      return { providers: {} };
    case 'config.getApiKeys':
      return { keys: {} };
    case 'config.get':
      return configPayload();
    case 'config.set':
    case 'config.setApiKey':
    case 'chat.abort':
      return { ok: true };
    case 'files.list':
      return { files: [] };
    case 'files.upload':
      return { path: 'workspace/sample.csv', size: 128, type: 'csv' };
    case 'approval.list':
      return { approvals: [] };
    case 'session.list':
      return { sessions: [] };
    case 'run.list':
      return { runs: [] };
    case 'task.list':
      return { tasks: [] };
    case 'runtime.events.list':
      return { events: [] };
    case 'policy.get':
      return policyPayload();
    case 'project.list':
      return { projects: [] };
    case 'usage.summary':
      return usageSummaryPayload();
    case 'telegram.status':
      return telegramStatusPayload();
    case 'telegram.test':
      return {
        ok: true,
        botUsername: 'ds_agent_smoke_bot',
        botId: 424242,
        firstName: 'DS Agent Smoke',
      };
    case 'telegram.startPairing':
      pairingStarted = true;
      setTimeout(confirmTelegramPairing, 500);
      broadcastEvent('telegram.statusChanged', telegramStatusPayload());
      return {
        handleId: PAIRING_HANDLE_ID,
        code: PAIRING_CODE,
        state: 'pending',
        expiresAt: Date.now() + 60_000,
        botUsername: 'ds_agent_smoke_bot',
        botId: 424242,
        firstName: 'DS Agent Smoke',
      };
    case 'telegram.pairingStatus':
      return { state: paired ? 'paired' : 'pending' };
    case 'telegram.cancelPairing':
      pairingStarted = false;
      return { ok: true };
    case 'telegram.sendTestMessage':
      return { ok: true, chatId: params && params.chatId ? String(params.chatId) : CHAT_ID };
    case 'telegram.disconnect':
      paired = false;
      pairingStarted = false;
      broadcastEvent('telegram.statusChanged', telegramStatusPayload());
      return { ok: true };
    case 'telegram.reconnect':
      paired = true;
      broadcastEvent('telegram.statusChanged', telegramStatusPayload());
      return { ok: true };
    default:
      return { ok: true };
  }
}

function confirmTelegramPairing() {
  if (paired) {
    return;
  }
  paired = true;
  pairingStarted = true;
  broadcastEvent('telegram.paired', {
    handleId: PAIRING_HANDLE_ID,
    chatId: CHAT_ID,
    persistToken: true,
  });
  broadcastEvent('telegram.statusChanged', telegramStatusPayload());
}

function createServer() {
  return http.createServer(async (req, res) => {
    const url = new URL(req.url || '/', 'http://127.0.0.1');
    if (req.method === 'OPTIONS') {
      res.writeHead(204, corsHeaders());
      res.end();
      return;
    }

    if (req.method === 'GET' && url.pathname === '/health') {
      sendJson(res, 200, { ok: true, status: 'ok' });
      return;
    }

    if (req.method === 'POST' && url.pathname === '/api/onboarding/finalize') {
      const body = await readBody(req).catch(() => ({}));
      const sessionId =
        body && typeof body.sessionId === 'string' && body.sessionId.trim()
          ? body.sessionId.trim()
          : 'session-telegram-smoke';
      sendJson(res, 200, {
        sessionId,
        createdSession: true,
        goalSeeded: true,
        taskId: 'task-telegram-smoke',
        mission: {
          goal: {
            title: 'Telegram smoke onboarding',
          },
        },
      });
      return;
    }

    if (req.method === 'GET' && url.pathname === '/api/task-contracts/active') {
      sendJson(res, 200, {
        contract: {
          contract: {
            task_id: 'task-telegram-smoke',
            status: 'draft',
            business_goal: 'Telegram smoke onboarding prediction workflow',
          },
        },
      });
      return;
    }

    sendJson(res, 404, { detail: `Unhandled fixture route: ${req.method} ${url.pathname}` });
  });
}

function acceptKey(key) {
  return crypto
    .createHash('sha1')
    .update(`${key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`)
    .digest('base64');
}

function sendFrame(socket, opcode, payload) {
  const data = Buffer.isBuffer(payload) ? payload : Buffer.from(String(payload), 'utf8');
  let header;
  if (data.length < 126) {
    header = Buffer.from([0x80 | opcode, data.length]);
  } else if (data.length <= 0xffff) {
    header = Buffer.alloc(4);
    header[0] = 0x80 | opcode;
    header[1] = 126;
    header.writeUInt16BE(data.length, 2);
  } else {
    header = Buffer.alloc(10);
    header[0] = 0x80 | opcode;
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(data.length), 2);
  }
  socket.write(Buffer.concat([header, data]));
}

function sendText(socket, payload) {
  sendFrame(socket, 0x1, JSON.stringify(payload));
}

function broadcastEvent(event, payload) {
  for (const socket of sockets) {
    sendText(socket, {
      type: 'event',
      event,
      version: '1.0',
      ts: Date.now(),
      source: 'telegram-fake-backend',
      payload,
    });
  }
}

function tryDecodeFrame(buffer) {
  if (buffer.length < 2) {
    return null;
  }

  const first = buffer[0];
  const second = buffer[1];
  const opcode = first & 0x0f;
  const masked = (second & 0x80) !== 0;
  let length = second & 0x7f;
  let offset = 2;

  if (length === 126) {
    if (buffer.length < offset + 2) {
      return null;
    }
    length = buffer.readUInt16BE(offset);
    offset += 2;
  } else if (length === 127) {
    if (buffer.length < offset + 8) {
      return null;
    }
    const bigLength = buffer.readBigUInt64BE(offset);
    if (bigLength > BigInt(Number.MAX_SAFE_INTEGER)) {
      throw new Error('Frame too large');
    }
    length = Number(bigLength);
    offset += 8;
  }

  const maskLength = masked ? 4 : 0;
  if (buffer.length < offset + maskLength + length) {
    return null;
  }

  const mask = masked ? buffer.subarray(offset, offset + 4) : null;
  offset += maskLength;
  const payload = Buffer.from(buffer.subarray(offset, offset + length));
  if (mask) {
    for (let index = 0; index < payload.length; index += 1) {
      payload[index] ^= mask[index % 4];
    }
  }

  return {
    opcode,
    payload,
    rest: buffer.subarray(offset + length),
  };
}

function handleWsMessage(socket, raw) {
  let message;
  try {
    message = JSON.parse(raw);
  } catch (error) {
    return;
  }

  if (!message || message.type !== 'req' || typeof message.id !== 'string') {
    return;
  }

  try {
    const payload = handleRpc(String(message.method || ''), message.params || {});
    sendText(socket, {
      type: 'res',
      id: message.id,
      ok: true,
      payload,
    });
  } catch (error) {
    sendText(socket, {
      type: 'res',
      id: message.id,
      ok: false,
      error: {
        code: 'fixture_error',
        message: error instanceof Error ? error.message : String(error),
      },
    });
  }
}

function attachWebSocket(server) {
  server.on('upgrade', (req, socket) => {
    const url = new URL(req.url || '/', 'http://127.0.0.1');
    if (url.pathname !== '/ws') {
      socket.destroy();
      return;
    }

    const key = req.headers['sec-websocket-key'];
    if (typeof key !== 'string') {
      socket.destroy();
      return;
    }

    socket.write(
      [
        'HTTP/1.1 101 Switching Protocols',
        'Upgrade: websocket',
        'Connection: Upgrade',
        `Sec-WebSocket-Accept: ${acceptKey(key)}`,
        '',
        '',
      ].join('\r\n'),
    );

    sockets.add(socket);
    let pending = Buffer.alloc(0);

    socket.on('data', (chunk) => {
      pending = Buffer.concat([pending, chunk]);
      while (pending.length > 0) {
        const frame = tryDecodeFrame(pending);
        if (!frame) {
          break;
        }
        pending = frame.rest;
        if (frame.opcode === 0x8) {
          socket.end();
          return;
        }
        if (frame.opcode === 0x9) {
          sendFrame(socket, 0xA, frame.payload);
          continue;
        }
        if (frame.opcode === 0x1) {
          handleWsMessage(socket, frame.payload.toString('utf8'));
        }
      }
    });

    socket.on('close', () => sockets.delete(socket));
    socket.on('error', () => sockets.delete(socket));
  });
}

const port = readPort();
const server = createServer();
attachWebSocket(server);

server.listen(port, '127.0.0.1', () => {
  process.stdout.write(`READY:${port}:${TOKEN}\n`);
});

function shutdown() {
  for (const socket of sockets) {
    socket.destroy();
  }
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 500).unref();
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
