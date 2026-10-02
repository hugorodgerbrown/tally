// Tests for activity/static/activity/engine.js, run with `node --test tests/js/`.
//
// engine.js is a browser script that sets window.Engine, so it is loaded into
// a sandbox with a stand-in window rather than imported.
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";

const source = readFileSync(new URL("../../activity/static/activity/engine.js", import.meta.url), "utf8");
const sandbox = { window: {} };
vm.runInNewContext(source, sandbox);
const E = sandbox.window.Engine;

// Plain copies, so deepStrictEqual compares values, not the sandbox's prototypes.
const plain = (v) => JSON.parse(JSON.stringify(v));

const item = (name, dur, extra = {}) => ({ name, dur, sides: false, types: ["strength"], muscles: ["Core"], ...extra });
const workout = (items, extra = {}) => ({ name: "Test", rest: 10, rounds: 1, roundRest: 60, items, ...extra });

describe("buildTimeline", () => {
  it("starts with get ready and puts rest between exercises, not after the last", () => {
    const t = E.buildTimeline(workout([item("A", 30), item("B", 40)]));
    assert.deepEqual(plain(t.map((s) => [s.type, s.dur])), [["ready", 5], ["work", 30], ["rest", 10], ["work", 40]]);
  });

  it("runs a one-sided exercise as left, switch, right", () => {
    const t = E.buildTimeline(workout([item("Lunge", 20, { sides: true })]));
    assert.deepEqual(plain(t.map((s) => [s.type, s.side ?? null])), [
      ["ready", null], ["work", "Left"], ["switch", "Right"], ["work", "Right"],
    ]);
  });

  it("adds a round break between rounds only", () => {
    const t = E.buildTimeline(workout([item("A", 30)], { rounds: 3, rest: 0 }));
    assert.deepEqual(plain(t.map((s) => s.type)), ["ready", "work", "round", "work", "round", "work"]);
  });

  it("leaves out rests and round breaks set to zero", () => {
    const t = E.buildTimeline(workout([item("A", 30), item("B", 30)], { rest: 0, rounds: 2, roundRest: 0 }));
    assert.deepEqual(plain(t.map((s) => s.type)), ["ready", "work", "work", "work", "work"]);
  });
});

describe("totals", () => {
  const w = workout([item("A", 30), item("B", 20, { sides: true })], { rounds: 2, roundRest: 60 });

  it("totalSeconds adds up every step", () => {
    // ready 5 + 2 rounds × (30 + rest 10 + 20 + switch 5 + 20) + one round break 60
    assert.equal(E.totalSeconds(E.buildTimeline(w)), 5 + 2 * 85 + 60);
  });

  it("workingSeconds counts work only, both sides of one-sided moves", () => {
    assert.equal(E.workingSeconds(w), 2 * (30 + 40));
  });
});

describe("Timer", () => {
  const record = () => {
    const events = { steps: [], counts: [], finished: 0 };
    const cb = {
      onStep: (i, catchingUp) => events.steps.push([i, catchingUp]),
      onCount: (n) => events.counts.push(n),
      onFinish: () => (events.finished += 1),
    };
    return { events, cb };
  };

  it("moves through steps on the wall clock and logs work time only", () => {
    const { events, cb } = record();
    const timer = new E.Timer(workout([item("A", 10), item("B", 10)], { rest: 5 }), cb);
    timer.start(0);
    for (let ms = 0; ms <= 30_000; ms += 250) timer.tick(ms);
    assert.deepEqual(events.steps.map(([i]) => i), [0, 1, 2, 3]);
    assert.equal(events.finished, 1);
    assert.equal(timer.finished, true);
    assert.equal(timer.endedEarly, false);
    assert.deepEqual(plain(timer.log), [10, 10]);
    assert.equal(timer.secondsWorked(), 20);
  });

  it("counts down 3, 2, 1 before each step ends", () => {
    const { events, cb } = record();
    const timer = new E.Timer(workout([item("A", 10)]), cb);
    timer.start(0);
    for (let ms = 0; ms < 5_000; ms += 100) timer.tick(ms);
    assert.deepEqual(events.counts, [3, 2, 1]);
  });

  it("catches up after the tab sleeps, flagging the steps it skipped through", () => {
    const { events, cb } = record();
    const timer = new E.Timer(workout([item("A", 10), item("B", 10)], { rest: 5 }), cb);
    timer.start(0);
    timer.tick(15_500); // asleep through ready and A, waking just into rest
    assert.equal(timer.idx, 2);
    assert.deepEqual(plain(events.steps), [[0, false], [1, true], [2, false]]);
    assert.deepEqual(plain(timer.log), [10, 0]);
  });

  it("does not log time spent paused", () => {
    const timer = new E.Timer(workout([item("A", 30)]), {});
    timer.start(0);
    timer.tick(10_000); // 5 s into A
    timer.pause(10_000);
    timer.tick(60_000);
    timer.resume(60_000);
    timer.tick(65_000);
    assert.equal(timer.log[0], 10);
    assert.equal(timer.rem(65_000), 20);
  });

  it("skip moves to the next step and logs the work done so far", () => {
    const timer = new E.Timer(workout([item("A", 30), item("B", 30)], { rest: 0 }), {});
    timer.start(0);
    timer.tick(15_000); // 10 s into A
    timer.skip(15_000);
    assert.equal(timer.t[timer.idx].ex, 1);
    assert.equal(timer.log[0], 10);
  });

  it("back restarts the step, or goes to the previous one in its first 3 seconds", () => {
    const timer = new E.Timer(workout([item("A", 30), item("B", 30)], { rest: 0 }), {});
    timer.start(0);
    timer.tick(45_000); // 10 s into B (step 2)
    timer.back(45_000);
    assert.equal(timer.idx, 2);
    assert.equal(timer.rem(45_000), 30);
    timer.back(46_000);
    assert.equal(timer.idx, 1);
  });

  it("end stops early and keeps the partial log", () => {
    const { events, cb } = record();
    const timer = new E.Timer(workout([item("A", 30), item("B", 30)]), cb);
    timer.start(0);
    timer.tick(20_000);
    timer.end(20_000);
    assert.equal(timer.finished, true);
    assert.equal(timer.endedEarly, true);
    assert.equal(events.finished, 1);
    assert.deepEqual(plain(timer.log), [15, 0]);
  });
});

describe("model", () => {
  const w = workout([item("Squat", 30), item("Lunge", 20, { sides: true })]);
  const t = E.buildTimeline(w);

  it("shows the coming exercise during get ready", () => {
    const m = E.model(w, t, 0, 5);
    assert.equal(m.phase, "ready");
    assert.equal(m.name, "Squat");
    assert.equal(m.next.name, "Lunge · left");
    assert.equal(m.left, E.totalSeconds(t));
  });

  it("names the other side as next on a one-sided move", () => {
    const leftIdx = t.findIndex((s) => s.side === "Left");
    assert.equal(E.model(w, t, leftIdx, 20).next.name, "Right side");
  });

  it("shows Finish after the last interval", () => {
    const m = E.model(w, t, t.length - 1, 10);
    assert.equal(m.next.name, "Finish");
    assert.equal(m.next.dur, null);
    assert.equal(m.pct, 50);
  });
});

describe("breakdown", () => {
  it("splits time evenly across an exercise's types and in full to each muscle", () => {
    const w = workout([
      item("Swing", 40, { types: ["strength", "aerobic"], muscles: ["Glutes", "Core"] }),
      item("Plank", 30, { types: ["strength"], muscles: ["Core"] }),
    ]);
    const b = E.breakdown(w, [40, 30]);
    assert.deepEqual(plain(b.types), [["strength", 50], ["aerobic", 20]]);
    assert.deepEqual(plain(b.muscles), [["Core", 70], ["Glutes", 40]]);
  });
});

describe("durationText", () => {
  for (const [seconds, text] of [
    [0, "0 s"], [45, "45 s"], [60, "1 min"], [470, "7 min 50 s"], [3600, "1 h"], [3900, "1 h 5 min"],
  ]) {
    it(`${seconds} s reads as ${text}`, () => assert.equal(E.durationText(seconds), text));
  }
});
