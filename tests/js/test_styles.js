// Tests for static/js/styles.js: data-css declarations applied through the CSSOM.
import { describe, expect, it } from 'vitest';

import '../../static/js/styles.js';

const { Styles } = self;
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('parse', () => {
  it('splits declarations and drops empty or broken ones', () => {
    expect(Styles.parse('background: #F7C948; flex:40;; :x; width:')).toEqual([
      ['background', '#F7C948'],
      ['flex', '40'],
    ]);
    expect(Styles.parse(null)).toEqual([]);
  });
});

describe('apply', () => {
  it('styles markup already on the page, and markup added later', async () => {
    document.body.innerHTML = '<span data-css="width:40%"></span>';
    Styles.apply(document.body);
    expect(document.querySelector('span').style.width).toBe('40%');

    const added = document.createElement('div');
    added.innerHTML = '<i data-css="opacity:.5"></i>';
    document.body.append(added);
    await tick();
    expect(added.querySelector('i').style.opacity).toBe('0.5');
  });

  it('keeps a style a script set, and follows a changed data-css', async () => {
    document.body.innerHTML = '<b data-css="width:10%"></b>';
    const el = document.querySelector('b');
    Styles.apply(el);
    el.style.transform = 'translateY(4px)';
    el.setAttribute('data-css', 'width:20%');
    await tick();
    expect(el.style.width).toBe('20%');
    expect(el.style.transform).toBe('translateY(4px)');
  });
});
