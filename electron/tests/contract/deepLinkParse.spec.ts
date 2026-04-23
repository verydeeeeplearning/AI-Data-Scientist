import assert from 'node:assert/strict';

import {
  buildDeepLinkUri,
  DEEP_LINK_RESOURCE_TYPES,
  parseDeepLink,
  type DeepLinkParseError,
} from '../../src/renderer/domain/deepLink/deepLink';

function expectFailure(input: string, error: DeepLinkParseError): void {
  const result = parseDeepLink(input);
  assert.equal(result.ok, false, `Expected failure for ${JSON.stringify(input)}`);
  if (result.ok === false) {
    assert.equal(result.error, error, `Expected error=${error} got=${result.error}`);
  }
}

function run(): void {
  // Happy path: every resource type round-trips.
  for (const resourceType of DEEP_LINK_RESOURCE_TYPES) {
    const uri = `ds-agent://workspace/ws-1/${resourceType}/abc-123`;
    const result = parseDeepLink(uri);
    assert.equal(result.ok, true, `Expected ok for ${uri}`);
    if (result.ok) {
      assert.equal(result.value.workspaceId, 'ws-1');
      assert.equal(result.value.resourceType, resourceType);
      assert.equal(result.value.resourceId, 'abc-123');
      assert.equal(result.value.action, null);
    }
  }

  // Action query param surfaced when present.
  const withAction = parseDeepLink('ds-agent://workspace/ws-1/run/r-9?action=compare');
  assert.equal(withAction.ok, true);
  if (withAction.ok) {
    assert.equal(withAction.value.action, 'compare');
  }

  // build → parse round-trip
  const round = parseDeepLink(
    buildDeepLinkUri({ workspaceId: 'ws-1', resourceType: 'artifact', resourceId: 'art-7', action: 'promote' }),
  );
  assert.equal(round.ok, true);
  if (round.ok) {
    assert.equal(round.value.workspaceId, 'ws-1');
    assert.equal(round.value.resourceType, 'artifact');
    assert.equal(round.value.resourceId, 'art-7');
    assert.equal(round.value.action, 'promote');
  }

  // Sanitize: scheme spoofing
  expectFailure('http://workspace/ws-1/run/r-1', 'invalid_scheme');
  expectFailure('javascript://workspace/ws-1/run/r-1', 'invalid_scheme');

  // Sanitize: wrong host
  expectFailure('ds-agent://settings/ws-1/run/r-1', 'invalid_host');

  // Sanitize: path traversal disguise via extra segments. URL parsing already
  // normalizes literal `..`, so the explicit guard catches the residual case
  // of "more than one segment after the resource type".
  expectFailure('ds-agent://workspace/ws-1/run/r-1/extra', 'path_traversal');
  expectFailure('ds-agent://workspace/ws-1/run/r-1/extra/more', 'path_traversal');

  // Sanitize: oversized URI
  const big = `ds-agent://workspace/ws-1/run/${'x'.repeat(2200)}`;
  expectFailure(big, 'too_long');

  // Sanitize: unknown resource type
  expectFailure('ds-agent://workspace/ws-1/secret/r-1', 'unknown_resource_type');

  // Sanitize: missing parts
  expectFailure('ds-agent://workspace', 'missing_workspace');
  expectFailure('ds-agent://workspace/ws-1', 'unknown_resource_type');
  expectFailure('ds-agent://workspace/ws-1/run', 'missing_resource_id');

  // Sanitize: invalid characters in workspace / id
  expectFailure('ds-agent://workspace/ws%20with%20space/run/r-1', 'invalid_workspace');
  expectFailure('ds-agent://workspace/ws-1/run/r%20one', 'invalid_resource_id');

  // Sanitize: invalid action characters
  expectFailure('ds-agent://workspace/ws-1/run/r-1?action=do%20it', 'invalid_action');

  // Empty / non-string input rejected
  expectFailure('', 'invalid_scheme');

  console.log('[contract] PASS deep-link-parse (16 cases)');
}

run();
