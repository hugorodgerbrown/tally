// Tests for static/js/activity_app.js: the workout screen's exercise notes, and focus kept across a redraw.
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

const WORKOUT = '11111111-1111-4111-8111-111111111111';
const item = (name, description) => ({
  exerciseId: crypto.randomUUID(), name, description, dur: 30, sides: false,
  equipment: '', movement: 'dynamic', types: ['strength'], muscles: [],
});
const library = {
  types: [{ slug: 'strength', name: 'Strength', colour: '#fc0' }],
  equipment: [],
  workouts: [{
    id: WORKOUT, name: 'Knees', description: '', rest: 15, rounds: 1, roundRest: 60, status: 'active',
    items: [item('Hip hinge', 'Push your hips back.\nKeep a flat back.'), item('Wall slide', ''), item('Toe lift', '<b>lift</b>')],
  }],
};

const row = (name) => [...document.querySelectorAll('.slist li')].find((li) => li.textContent.includes(name));

beforeAll(async () => {
  document.body.innerHTML = '<div id="app"></div>';
  location.hash = `#/w/${WORKOUT}`;
  window.Store = {
    status: () => 'online', onStatus: () => {}, get: async (k) => (k === 'library' ? library : null),
    ready: async () => {}, migrateLegacy: async () => {}, del: async () => {}, set: async () => {},
    loadWorkouts: async () => library, flush: async () => {}, pending: async () => [],
    saveSession: async () => {}, discardSession: async () => {},
  };
  await import('../../static/js/engine.js');
  await import('../../static/js/activity_app.js');
  await vi.waitFor(() => expect(document.querySelector('.s-sum')).not.toBeNull());
});

afterEach(() => {
  document.querySelectorAll('.srow[aria-expanded="true"]').forEach((b) => b.click());
});

describe('exercise notes on the workout screen', () => {
  it('makes a row with notes a closed button, with its notes hidden', () => {
    const button = row('Hip hinge').querySelector('button.srow');
    expect(button.getAttribute('aria-expanded')).toBe('false');
    expect(button.querySelector('svg.more')).not.toBeNull();
    const notes = document.getElementById(button.getAttribute('aria-controls'));
    expect(notes.hidden).toBe(true);
  });

  it('gives a row without notes nothing to tap', () => {
    const li = row('Wall slide');
    expect(li.querySelector('button')).toBeNull();
    expect(li.querySelector('svg.more')).toBeNull();
  });

  it('opens and closes the notes on a tap', () => {
    row('Hip hinge').querySelector('button.srow').click();
    let button = row('Hip hinge').querySelector('button.srow');
    expect(button.getAttribute('aria-expanded')).toBe('true');
    const notes = row('Hip hinge').querySelector('.snote');
    expect(notes.hidden).toBe(false);
    expect(notes.textContent).toBe('Push your hips back.\nKeep a flat back.');
    button.click();
    button = row('Hip hinge').querySelector('button.srow');
    expect(button.getAttribute('aria-expanded')).toBe('false');
  });

  it('keeps notes text as text', () => {
    row('Toe lift').querySelector('button.srow').click();
    const notes = row('Toe lift').querySelector('.snote');
    expect(notes.querySelector('b')).toBeNull();
    expect(notes.textContent).toBe('<b>lift</b>');
  });

  it('keeps the list where it was scrolled when a row opens', () => {
    document.querySelector('.s-sum .main').scrollTop = 120;
    row('Hip hinge').querySelector('button.srow').click();
    expect(row('Hip hinge').querySelector('.snote').hidden).toBe(false);
    expect(document.querySelector('.s-sum .main').scrollTop).toBe(120);
  });

  it('keeps the focus on the tapped row', () => {
    row('Toe lift').querySelector('button.srow').focus();
    row('Toe lift').querySelector('button.srow').click();
    expect(document.activeElement).toBe(row('Toe lift').querySelector('button.srow'));
  });

  it('does not start the workout when a row is tapped', () => {
    row('Hip hinge').querySelector('button.srow').click();
    expect(document.querySelector('.s-sum')).not.toBeNull();
  });
});

describe('focus on the finish screen', () => {
  it('stays on the rating that was chosen', async () => {
    document.querySelector('[data-act="start"]').click();
    await vi.waitFor(() => expect(document.querySelector('.s-sum')).toBeNull());
    // Twenty seconds in, so there is time worked to save and rate.
    const later = Date.now() + 20000;
    vi.spyOn(Date, 'now').mockReturnValue(later);
    document.querySelector('.scr').click(); // a tap anywhere pauses
    await vi.waitFor(() => expect(document.querySelector('[data-act="end"]')).not.toBeNull());
    document.querySelector('[data-act="end"]').click();
    await vi.waitFor(() => expect(document.querySelector('[data-act="rate"]')).not.toBeNull());
    document.querySelector('[data-act="rate"][data-v="8"]').focus();
    document.querySelector('[data-act="rate"][data-v="8"]').click();
    expect(document.activeElement).toBe(document.querySelector('[data-act="rate"][data-v="8"]'));
    expect(document.activeElement.getAttribute('aria-pressed')).toBe('true');
    vi.restoreAllMocks();
  });
});
