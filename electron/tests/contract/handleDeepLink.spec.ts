import assert from 'node:assert/strict';

import {
  buildDeepLinkRoute,
  handleDeepLink,
  type DeepLinkHandlerDeps,
  type DeepLinkReauthPolicy,
} from '../../src/renderer/application/deepLink/handleDeepLink';
import {
  parseDeepLink,
  type DeepLinkParseError,
} from '../../src/renderer/domain/deepLink/deepLink';

interface CallLog {
  navigate: string[];
  warn: Array<{ error: DeepLinkParseError; uri: string }>;
  reauthRequests: number;
  markedSessionReauthed: number;
}

function makeDeps(overrides: Partial<DeepLinkHandlerDeps> = {}, log?: CallLog): {
  deps: DeepLinkHandlerDeps;
  log: CallLog;
} {
  const callLog: CallLog = log ?? {
    navigate: [],
    warn: [],
    reauthRequests: 0,
    markedSessionReauthed: 0,
  };
  let sessionReauthed = false;
  const deps: DeepLinkHandlerDeps = {
    parseUri: parseDeepLink,
    navigate: (path) => {
      callLog.navigate.push(path);
    },
    warnInvalid: (error, uri) => {
      callLog.warn.push({ error, uri });
    },
    getReauthPolicy: () => 'none',
    requestReauth: async () => {
      callLog.reauthRequests += 1;
      return true;
    },
    hasReauthedThisSession: () => sessionReauthed,
    markSessionReauthed: () => {
      sessionReauthed = true;
      callLog.markedSessionReauthed += 1;
    },
    ...overrides,
  };
  return { deps, log: callLog };
}

async function run(): Promise<void> {
  // Case 1: valid URI → navigate called with correct path
  {
    const { deps, log } = makeDeps();
    await handleDeepLink('ds-agent://workspace/ws-1/run/r-1', deps);
    assert.deepEqual(log.navigate, ['/workspace/ws-1/run/r-1']);
    assert.equal(log.warn.length, 0);
  }

  // Case 2: valid URI with action → path includes ?action=
  {
    const { deps, log } = makeDeps();
    await handleDeepLink('ds-agent://workspace/ws-1/run/r-9?action=compare', deps);
    assert.deepEqual(log.navigate, ['/workspace/ws-1/run/r-9?action=compare']);
  }

  // Case 3: invalid URI (scheme spoofing) → warn, no navigate
  {
    const { deps, log } = makeDeps();
    await handleDeepLink('http://workspace/ws-1/run/r-1', deps);
    assert.equal(log.navigate.length, 0);
    assert.equal(log.warn.length, 1);
    assert.equal(log.warn[0].error, 'invalid_scheme');
  }

  // Case 4: invalid URI (extra segment / path traversal) → warn
  {
    const { deps, log } = makeDeps();
    await handleDeepLink('ds-agent://workspace/ws-1/run/r-1/extra', deps);
    assert.equal(log.navigate.length, 0);
    assert.equal(log.warn[0].error, 'path_traversal');
  }

  // Case 5: invalid URI (too long)
  {
    const { deps, log } = makeDeps();
    const big = `ds-agent://workspace/ws-1/run/${'x'.repeat(2200)}`;
    await handleDeepLink(big, deps);
    assert.equal(log.navigate.length, 0);
    assert.equal(log.warn[0].error, 'too_long');
  }

  // Case 6: reauth policy 'none' → requestReauth never called
  {
    const { deps, log } = makeDeps({ getReauthPolicy: () => 'none' });
    await handleDeepLink('ds-agent://workspace/ws-1/run/r-1', deps);
    assert.equal(log.reauthRequests, 0);
    assert.equal(log.navigate.length, 1);
  }

  // Case 7: 'once-per-session' + not authed → requestReauth called, marked
  {
    const { deps, log } = makeDeps({ getReauthPolicy: () => 'once-per-session' });
    await handleDeepLink('ds-agent://workspace/ws-1/run/r-1', deps);
    assert.equal(log.reauthRequests, 1);
    assert.equal(log.markedSessionReauthed, 1);
    assert.equal(log.navigate.length, 1);
  }

  // Case 8: 'once-per-session' + already authed → no reauth, navigate
  {
    let sessionReauthed = true;
    const log: CallLog = { navigate: [], warn: [], reauthRequests: 0, markedSessionReauthed: 0 };
    const deps: DeepLinkHandlerDeps = {
      parseUri: parseDeepLink,
      navigate: (path) => {
        log.navigate.push(path);
      },
      warnInvalid: (error, uri) => {
        log.warn.push({ error, uri });
      },
      getReauthPolicy: () => 'once-per-session',
      requestReauth: async () => {
        log.reauthRequests += 1;
        return true;
      },
      hasReauthedThisSession: () => sessionReauthed,
      markSessionReauthed: () => {
        sessionReauthed = true;
        log.markedSessionReauthed += 1;
      },
    };
    await handleDeepLink('ds-agent://workspace/ws-1/run/r-1', deps);
    assert.equal(log.reauthRequests, 0);
    assert.equal(log.navigate.length, 1);
  }

  // Case 9: 'always' → reauth every invocation
  {
    const { deps, log } = makeDeps({ getReauthPolicy: () => 'always' });
    await handleDeepLink('ds-agent://workspace/ws-1/run/r-1', deps);
    await handleDeepLink('ds-agent://workspace/ws-1/run/r-2', deps);
    assert.equal(log.reauthRequests, 2);
    assert.equal(log.markedSessionReauthed, 0); // never marked under 'always'
    assert.equal(log.navigate.length, 2);
  }

  // Case 10: reauth returns false (denied) → no navigate
  {
    const { deps, log } = makeDeps({
      getReauthPolicy: () => 'always',
      requestReauth: async () => false,
    });
    await handleDeepLink('ds-agent://workspace/ws-1/run/r-1', deps);
    assert.equal(log.navigate.length, 0);
  }

  // Case 11: workspace_id preserved in path
  {
    const { deps, log } = makeDeps();
    await handleDeepLink('ds-agent://workspace/proj-7/artifact/art-99', deps);
    assert.equal(log.navigate[0], '/workspace/proj-7/artifact/art-99');
  }

  // Case 12: all 4 resource types navigate correctly
  {
    const types = ['run', 'artifact', 'checkpoint', 'verifier_result'] as const;
    for (const type of types) {
      const { deps, log } = makeDeps();
      await handleDeepLink(`ds-agent://workspace/ws-1/${type}/id-1`, deps);
      assert.equal(log.navigate[0], `/workspace/ws-1/${type}/id-1`);
    }
  }

  // Pure helper: buildDeepLinkRoute is consistent with handler output
  assert.equal(
    buildDeepLinkRoute({
      workspaceId: 'ws-1',
      resourceType: 'run',
      resourceId: 'r-1',
      action: null,
    }),
    '/workspace/ws-1/run/r-1',
  );
  assert.equal(
    buildDeepLinkRoute({
      workspaceId: 'ws-1',
      resourceType: 'artifact',
      resourceId: 'art-1',
      action: 'promote',
    }),
    '/workspace/ws-1/artifact/art-1?action=promote',
  );

  // Type guard: DeepLinkReauthPolicy values exist
  const policies: DeepLinkReauthPolicy[] = ['none', 'once-per-session', 'always'];
  assert.equal(policies.length, 3);

  console.log('[contract] PASS deep-link-handler (12 cases)');
}

void run();
