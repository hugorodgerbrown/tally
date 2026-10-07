/*
 * static/js/styles.js — apply per-element styles that come from data.
 *
 * The CSP forbids inline style attributes, but a few styles are data:
 * an exercise type's colour (stored with the type), the width of a bar,
 * the share of a strip a segment takes. Markup carries them as
 * `data-css="background:#F7C948;flex:40"` instead, and this script sets
 * them through the CSSOM, which the CSP allows. It watches the page, so
 * markup added later (the builder, the phone app) is styled as it lands.
 *
 *   Styles.apply(root)   style root and everything under it now
 *   Styles.parse(text)   [[property, value], ...] (exported for tests)
 *
 * Declarations are set one by one, so a style a script set on the same
 * element (a transform while dragging) is kept.
 */
(function () {
  'use strict';

  function parse(text) {
    return String(text || '')
      .split(';')
      .map((part) => {
        const colon = part.indexOf(':');
        if (colon < 1) return null;
        return [part.slice(0, colon).trim(), part.slice(colon + 1).trim()];
      })
      .filter((pair) => pair && pair[0] && pair[1]);
  }

  function style(el) {
    for (const [property, value] of parse(el.getAttribute('data-css'))) {
      el.style.setProperty(property, value);
    }
  }

  function apply(root) {
    if (!root || root.nodeType !== 1) return;
    if (root.hasAttribute('data-css')) style(root);
    root.querySelectorAll('[data-css]').forEach(style);
  }

  function watch() {
    apply(document.documentElement);
    new MutationObserver((records) => {
      for (const record of records) {
        if (record.type === 'attributes') style(record.target);
        else record.addedNodes.forEach(apply);
      }
    }).observe(document.documentElement, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['data-css'],
    });
  }

  self.Styles = Object.freeze({ apply, parse });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
  else watch();
})();
