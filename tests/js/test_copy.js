// Tests for static/js/copy.js: the Copy button beside a piece of text.
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../static/js/copy.js';

const { Copy } = self;

afterEach(() => {
  vi.useRealTimers();
  delete navigator.clipboard;
});

describe('Copy', () => {
  it('stays hidden without the Clipboard API', () => {
    document.body.innerHTML = '<code id="u">x</code><button data-copy="u" hidden></button>';
    Copy.init();
    expect(document.querySelector('button').hidden).toBe(true);
  });

  it('shows, copies the text, and says so for a moment', async () => {
    vi.useFakeTimers();
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    document.body.innerHTML =
      '<code id="u"> https://example.com/mcp </code><button data-copy="u" aria-label="Copy the address" hidden></button>';
    Copy.init();
    const button = document.querySelector('button');
    expect(button.hidden).toBe(false);
    button.click();
    await Promise.resolve();
    expect(writeText).toHaveBeenCalledWith('https://example.com/mcp');
    expect(button.getAttribute('aria-label')).toBe('Copied');
    vi.advanceTimersByTime(2000);
    expect(button.getAttribute('aria-label')).toBe('Copy the address');
  });
});
