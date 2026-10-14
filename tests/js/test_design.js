// Tests for static/js/design.js: the design page paints its token samples.
import { afterEach, describe, expect, it } from 'vitest';

import '../../static/js/design.js';

const { DesignPage } = self;

afterEach(() => {
  document.body.innerHTML = '';
  document.documentElement.style.removeProperty('--brand');
});

describe('paint', () => {
  it('paints each sample with its token', () => {
    document.body.innerHTML = `
      <span data-token="--brand" data-paint="background"></span>
      <span data-token="--radius-card" data-paint="radius"></span>
      <span data-token="--space-lg" data-paint="width"></span>`;
    DesignPage.paint(document);
    const [swatch, corner, bar] = document.querySelectorAll('span');
    expect(swatch.style.getPropertyValue('background')).toBe('var(--brand)');
    expect(corner.style.getPropertyValue('border-radius')).toBe('var(--radius-card)');
    expect(bar.style.getPropertyValue('width')).toBe('var(--space-lg)');
  });

  it('leaves a sample with an unknown paint alone', () => {
    document.body.innerHTML = '<span data-token="--brand" data-paint="outline"></span>';
    DesignPage.paint(document);
    expect(document.querySelector('span').getAttribute('style')).toBeNull();
  });

  it('writes out a token value', () => {
    document.documentElement.style.setProperty('--brand', '#1d4ed8');
    document.body.innerHTML = '<code data-token-value="--brand"></code>';
    DesignPage.paint(document);
    expect(document.querySelector('code').textContent).toBe('#1d4ed8');
  });
});
