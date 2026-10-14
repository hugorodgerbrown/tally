/*
 * static/js/design.js — paints the design page's token samples.
 *
 * Each sample names its token (data-token) and what to paint with it
 * (data-paint). The CSP allows no inline style, so the samples are painted
 * here; each token's computed value goes beside its name (data-token-value).
 */
(function () {
  'use strict';

  const PAINT = {
    background: 'background',
    radius: 'border-radius',
    shadow: 'box-shadow',
    width: 'width',
    size: 'font-size',
  };

  function paint(root) {
    root.querySelectorAll('[data-token][data-paint]').forEach((el) => {
      const prop = PAINT[el.dataset.paint];
      if (prop) el.style.setProperty(prop, 'var(' + el.dataset.token + ')');
    });
    const styles = getComputedStyle(document.documentElement);
    root.querySelectorAll('[data-token-value]').forEach((el) => {
      el.textContent = styles.getPropertyValue(el.dataset.tokenValue).trim();
    });
  }

  self.DesignPage = { paint: paint };
  if (typeof document !== 'undefined') paint(document);
})();
