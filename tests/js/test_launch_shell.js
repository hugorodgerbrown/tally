// Tests for static/js/launch_shell.js: the launch screen always goes away.
import { afterEach, describe, expect, it, vi } from 'vitest';

function setUp() {
  document.documentElement.classList.add('app-launching');
  document.body.innerHTML = '<div id="launch-shell"></div>';
}

afterEach(() => {
  vi.useRealTimers();
  vi.resetModules();
  document.documentElement.className = '';
});

describe('launch shell', () => {
  it('leaves on app:ready', async () => {
    vi.useFakeTimers();
    setUp();
    Object.defineProperty(document, 'readyState', { value: 'loading', configurable: true });
    await import('../../static/js/launch_shell.js?ready');
    document.dispatchEvent(new Event('app:ready'));
    expect(document.getElementById('launch-shell').classList).toContain('launch-shell--done');
    vi.advanceTimersByTime(500);
    expect(document.documentElement.classList).not.toContain('app-launching');
  });

  it('leaves after the timeout even if nothing else happens', async () => {
    vi.useFakeTimers();
    setUp();
    Object.defineProperty(document, 'readyState', { value: 'loading', configurable: true });
    await import('../../static/js/launch_shell.js?timeout');
    vi.advanceTimersByTime(self.LaunchShell.TIMEOUT_MS + 500);
    expect(document.documentElement.classList).not.toContain('app-launching');
  });
});
