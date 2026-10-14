// Tests for static/js/analytics.js: a marked address is sent as its event, once.
import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.resetModules();
  delete window.tally;
  window.history.replaceState(null, '', '/');
});

describe('analytics', () => {
  it('queues the event before fivebar has loaded, and clears the mark', async () => {
    window.history.replaceState(null, '', '/app/?a=1#signed-up');
    await import('../../static/js/analytics.js?queue');
    expect(window.tally).toEqual([['Sign up']]);
    expect(window.location.hash).toBe('');
    expect(window.location.pathname + window.location.search).toBe('/app/?a=1');
  });

  it('calls fivebar directly once it has loaded', async () => {
    window.tally = vi.fn();
    window.history.replaceState(null, '', '/app/#signed-up');
    await import('../../static/js/analytics.js?loaded');
    expect(window.tally).toHaveBeenCalledWith('Sign up');
  });

  it('sends nothing for any other address', async () => {
    window.history.replaceState(null, '', '/app/#top');
    await import('../../static/js/analytics.js?other');
    expect(window.tally).toBeUndefined();
    expect(window.location.hash).toBe('#top');
  });
});
