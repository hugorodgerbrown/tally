// Tests for static/js/copy.js: the copy button beside an address.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '../../static/js/copy.js';

const { CopyButton } = self;
let button;

beforeEach(() => {
  document.body.innerHTML = `
    <code id="address">https://example.test/mcp</code>
    <button type="button" data-copy="https://example.test/mcp" data-copy-target="address" data-copied-label="Copied" hidden>Copy</button>`;
  button = document.querySelector('button');
});

afterEach(() => {
  document.body.innerHTML = '';
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('enhance', () => {
  it('shows the button, which stays hidden without the script', () => {
    CopyButton.enhance(document);
    expect(button.hidden).toBe(false);
  });
});

describe('copy', () => {
  it('puts the address on the clipboard and says so for a moment', async () => {
    vi.useFakeTimers();
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });

    expect(await CopyButton.copy(button)).toBe(true);
    expect(writeText).toHaveBeenCalledWith('https://example.test/mcp');
    expect(button.textContent).toBe('Copied');

    vi.advanceTimersByTime(CopyButton.SHOWN_MS);
    expect(button.textContent).toBe('Copy');
  });

  it('keeps its own label when tapped twice', async () => {
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
    await CopyButton.copy(button);
    await CopyButton.copy(button);
    expect(button.dataset.label).toBe('Copy');
  });

  it('selects the address when the clipboard is refused', async () => {
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn().mockRejectedValue(new Error('no')) } });
    expect(await CopyButton.copy(button)).toBe(false);
    expect(window.getSelection().toString()).toBe('https://example.test/mcp');
    expect(button.textContent).toBe('Copy');
  });

  it('runs on a click', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    button.click();
    await Promise.resolve();
    expect(writeText).toHaveBeenCalledOnce();
  });
});
