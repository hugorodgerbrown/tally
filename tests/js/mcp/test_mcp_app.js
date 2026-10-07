// Tests for apps/mcp/ui/bridge.js and the notes view: the MCP Apps handshake as a host drives it.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const SCRIPTS = {
  'bridge.js': () => import('../../../apps/mcp/ui/bridge.js'),
  'notes_list.js': () => import('../../../apps/mcp/ui/notes_list.js'),
};
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

let host;

// The host frame: records what the view sends and answers ui/initialize.
function fakeHost(hostContext) {
  const sent = [];
  const frame = {
    postMessage: vi.fn((message) => {
      sent.push(message);
      if (message.method === 'ui/initialize') {
        deliver({ jsonrpc: '2.0', id: message.id, result: { protocolVersion: '2026-01-26', hostContext } });
      }
    }),
  };
  vi.spyOn(window, 'parent', 'get').mockReturnValue(frame);
  return { frame, sent };
}

function deliver(data, source) {
  const event = new MessageEvent('message', { data });
  Object.defineProperty(event, 'source', { value: source === undefined ? window.parent : source });
  window.dispatchEvent(event);
}

async function load(scripts, hostContext = {}) {
  document.documentElement.removeAttribute('data-theme');
  document.documentElement.removeAttribute('style');
  host = fakeHost(hostContext);
  vi.resetModules();
  for (const name of scripts) await SCRIPTS[name]();
  await self.McpApp.ready;
  await flush();
}

afterEach(() => {
  vi.restoreAllMocks();
  delete self.McpApp;
});

describe('bridge', () => {
  it('initialises, then says so, and applies the host theme and variables', async () => {
    await load(['bridge.js'], { theme: 'dark', styles: { variables: { '--color-text-primary': 'red', bad: 'x' } } });
    const methods = host.sent.map((m) => m.method);
    expect(methods.slice(0, 2)).toEqual(['ui/initialize', 'ui/notifications/initialized']);
    expect(host.sent[0].params.protocolVersion).toBe('2026-01-26');
    expect(host.sent[0].params.appInfo.name).toBeTruthy();
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement.style.getPropertyValue('--color-text-primary')).toBe('red');
    expect(methods).toContain('ui/notifications/size-changed');
  });

  it('hands tool input and results to listeners, late ones included', async () => {
    await load(['bridge.js']);
    const early = vi.fn();
    self.McpApp.onToolResult(early);
    deliver({ jsonrpc: '2.0', method: 'ui/notifications/tool-input', params: { arguments: { limit: 3 } } });
    deliver({ jsonrpc: '2.0', method: 'ui/notifications/tool-result', params: { structuredContent: { n: 1 } } });
    const late = vi.fn();
    self.McpApp.onToolResult(late);
    const input = vi.fn();
    self.McpApp.onToolInput(input);
    expect(early).toHaveBeenCalledWith({ structuredContent: { n: 1 } });
    expect(late).toHaveBeenCalledWith({ structuredContent: { n: 1 } });
    expect(input).toHaveBeenCalledWith({ limit: 3 });
  });

  it('ignores messages from anyone but the host', async () => {
    await load(['bridge.js']);
    const listener = vi.fn();
    self.McpApp.onToolResult(listener);
    deliver({ jsonrpc: '2.0', method: 'ui/notifications/tool-result', params: {} }, window);
    deliver('not json-rpc');
    expect(listener).not.toHaveBeenCalled();
  });

  it('answers host requests and follows context changes', async () => {
    await load(['bridge.js']);
    deliver({ jsonrpc: '2.0', id: 'td', method: 'ui/resource-teardown', params: {} });
    expect(host.sent.at(-1)).toEqual({ jsonrpc: '2.0', id: 'td', result: {} });
    deliver({ jsonrpc: '2.0', method: 'ui/notifications/host-context-changed', params: { theme: 'light' } });
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('calls a tool through the host and settles with its answer', async () => {
    await load(['bridge.js']);
    const ok = self.McpApp.callTool('add_note', { text: 'hi' });
    const call = host.sent.at(-1);
    expect(call).toMatchObject({ method: 'tools/call', params: { name: 'add_note', arguments: { text: 'hi' } } });
    deliver({ jsonrpc: '2.0', id: call.id, result: { content: [] } });
    await expect(ok).resolves.toEqual({ content: [] });

    const refused = self.McpApp.callTool('nope');
    deliver({ jsonrpc: '2.0', id: host.sent.at(-1).id, error: { code: -32602, message: 'Unknown tool' } });
    await expect(refused).rejects.toThrow('Unknown tool');
  });
});

describe('notes view', () => {
  beforeEach(() => {
    const html = readFileSync(resolve('apps/mcp/ui/notes_list.html'), 'utf8');
    document.body.innerHTML = html.slice(html.indexOf('<body>') + 6, html.indexOf('</body>'));
  });

  const result = (params) => deliver({ jsonrpc: '2.0', method: 'ui/notifications/tool-result', params });

  it('draws each note as text', async () => {
    await load(['bridge.js', 'notes_list.js']);
    result({ structuredContent: { notes: [{ text: '<b>hi</b>', written_at: '2026-10-07T09:00:00Z' }] } });
    const items = document.querySelectorAll('[data-notes] li');
    expect(items).toHaveLength(1);
    expect(items[0].querySelector('[data-text]').textContent).toBe('<b>hi</b>');
    expect(items[0].querySelector('b')).toBeNull();
    expect(items[0].querySelector('time').dateTime).toBe('2026-10-07T09:00:00Z');
    expect(document.querySelector('[data-status]').hidden).toBe(true);
  });

  it('says when there are none, and shows a tool error', async () => {
    await load(['bridge.js', 'notes_list.js']);
    result({ structuredContent: { notes: [] } });
    expect(document.querySelector('[data-status]').textContent).toBe('No notes yet.');
    result({ isError: true, content: [{ type: 'text', text: 'limit must be a whole number' }] });
    expect(document.querySelector('[data-status]').textContent).toBe('limit must be a whole number');
  });
});
