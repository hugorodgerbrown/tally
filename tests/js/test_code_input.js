// Tests for static/js/code_input.js: six digit boxes in front of the one code field.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '../../static/js/code_input.js';

const { CodeInput } = self;
let form;
let input;
let boxes;
let submitted;

beforeEach(() => {
  document.body.innerHTML = `
    <form>
      <label for="sign-in-code">Code</label>
      <input id="sign-in-code" type="text" name="code" required autofocus data-code-input data-code-length="6">
      <button type="submit">Sign in</button>
    </form>`;
  form = document.querySelector('form');
  input = document.getElementById('sign-in-code');
  submitted = vi.fn((event) => event.preventDefault());
  form.addEventListener('submit', submitted);
  boxes = CodeInput.enhance(input);
});

afterEach(() => {
  document.body.innerHTML = '';
});

function type(box, text) {
  box.value = text;
  box.dispatchEvent(new Event('input', { bubbles: true }));
}

function paste(box, text) {
  const event = new Event('paste', { bubbles: true, cancelable: true });
  event.clipboardData = { getData: () => text };
  box.dispatchEvent(event);
  return event;
}

describe('code boxes', () => {
  it('replaces the field with six boxes, the label pointing at the first', () => {
    expect(boxes).toHaveLength(6);
    expect(input.type).toBe('hidden');
    expect(input.required).toBe(false);
    expect(document.querySelector('label').htmlFor).toBe(boxes[0].id);
    expect(boxes[0].autocomplete).toBe('one-time-code');
    expect(document.activeElement).toBe(boxes[0]);
  });

  it('moves on as each digit is typed, and keeps the field in step', () => {
    type(boxes[0], '1');
    expect(document.activeElement).toBe(boxes[1]);
    type(boxes[1], '2');
    expect(input.value).toBe('12');
    expect(submitted).not.toHaveBeenCalled();
  });

  it('points a wrapping label at the first box', () => {
    document.body.innerHTML = `
      <form><label>Code <input id="wrapped" type="text" name="code" data-code-input></label></form>`;
    const wrapped = CodeInput.enhance(document.getElementById('wrapped'));
    expect(document.querySelector('label').htmlFor).toBe(wrapped[0].id);
  });

  it('holds back a short code and goes to the first empty box', () => {
    type(boxes[0], '1');
    const event = new Event('submit', { cancelable: true });
    form.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(boxes[1]);
    expect(boxes.every((box) => box.required)).toBe(true);
  });

  it('ignores anything but digits', () => {
    type(boxes[0], 'a');
    expect(boxes[0].value).toBe('');
    expect(input.value).toBe('');
  });

  it('spreads a pasted code across every box and submits', () => {
    const event = paste(boxes[0], ' 123 456 ');
    expect(event.defaultPrevented).toBe(true);
    expect(boxes.map((b) => b.value).join('')).toBe('123456');
    expect(input.value).toBe('123456');
    expect(submitted).toHaveBeenCalledTimes(1);
  });

  it('fills from the first box when a whole code lands in any box (autofill)', () => {
    type(boxes[3], '654321');
    expect(input.value).toBe('654321');
    expect(submitted).toHaveBeenCalled();
  });

  it('fills a partial paste from the box it landed in', () => {
    type(boxes[0], '9');
    paste(boxes[1], '87');
    expect(input.value).toBe('987');
    expect(document.activeElement).toBe(boxes[3]);
  });

  it('goes back a box on Backspace in an empty one, clearing it', () => {
    type(boxes[0], '1');
    type(boxes[1], '2');
    boxes[2].dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', cancelable: true }));
    expect(document.activeElement).toBe(boxes[1]);
    expect(input.value).toBe('1');
  });

  it('moves with the arrow keys', () => {
    boxes[2].focus();
    boxes[2].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', cancelable: true }));
    expect(document.activeElement).toBe(boxes[1]);
    boxes[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', cancelable: true }));
    expect(document.activeElement).toBe(boxes[2]);
  });
});
