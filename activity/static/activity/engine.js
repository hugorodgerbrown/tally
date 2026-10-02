/* Workout timeline and timer.
 *
 * A workout becomes a flat timeline of steps: get ready, work, switch
 * sides, rest, round break. The timer runs against the wall clock, so a
 * throttled or backgrounded tab catches up correctly when it wakes.
 */
(function () {
  "use strict";

  const READY_SECONDS = 5;
  const SWITCH_SECONDS = 5;

  function buildTimeline(w) {
    const t = [{ type: "ready", dur: READY_SECONDS, ex: 0, r: 0 }];
    for (let r = 0; r < w.rounds; r++) {
      w.items.forEach((it, i) => {
        const sides = it.sides ? ["Left", "Right"] : [null];
        sides.forEach((side, si) => {
          if (si > 0) t.push({ type: "switch", dur: SWITCH_SECONDS, ex: i, side, r });
          t.push({ type: "work", dur: it.dur, ex: i, side, si, sn: sides.length, r });
        });
        if (i < w.items.length - 1 && w.rest > 0) t.push({ type: "rest", dur: w.rest, ex: i + 1, r });
      });
      if (r < w.rounds - 1 && w.roundRest > 0) t.push({ type: "round", dur: w.roundRest, ex: 0, r: r + 1 });
    }
    return t;
  }

  const totalSeconds = (t) => t.reduce((a, s) => a + s.dur, 0);
  const workingSeconds = (w) => w.items.reduce((a, i) => a + i.dur * (i.sides ? 2 : 1), 0) * w.rounds;

  function nextWork(t, from) {
    for (let j = from; j < t.length; j++) if (t[j].type === "work") return j;
    return -1;
  }

  /* Everything a screen needs for step `idx` with `rem` seconds left. */
  function model(w, t, idx, rem) {
    const st = t[idx];
    const m = { phase: st.type, dur: st.dur, rem, pct: Math.min(100, Math.max(0, (1 - rem / st.dur) * 100)) };
    const upIdx = st.type === "work" ? idx : nextWork(t, idx + 1);
    const up = t[upIdx];
    m.name = w.items[up.ex].name;
    m.side = up.side;
    m.si = up.si;
    m.sn = up.sn;
    m.updur = up.dur;
    const nx = nextWork(t, upIdx + 1);
    if (nx < 0) m.next = { name: "Finish", dur: null };
    else {
      const s = t[nx];
      const name = s.ex === up.ex && s.r === up.r ? s.side + " side" : w.items[s.ex].name + (s.side ? " · " + s.side.toLowerCase() : "");
      m.next = { name, dur: s.dur };
    }
    m.exNum = up.ex + 1;
    m.exTotal = w.items.length;
    m.round = up.r + 1;
    m.rounds = w.rounds;
    m.segs = [];
    w.items.forEach((_, i) => {
      let tot = 0, done = 0;
      t.forEach((s, k) => {
        if (s.type !== "work" || s.ex !== i || s.r !== up.r) return;
        tot += s.dur;
        if (k < idx) done += s.dur;
        else if (k === idx) done += s.dur - rem;
      });
      m.segs.push({ k: "bar", f: tot ? done / tot : 0 });
      const rk = t.findIndex((s) => s.type === "rest" && s.r === up.r && s.ex === i + 1);
      if (rk >= 0) m.segs.push({ k: "dot", st: rk < idx ? "done" : rk === idx ? "cur" : "" });
    });
    let left = rem;
    for (let j = idx + 1; j < t.length; j++) left += t[j].dur;
    m.left = left;
    return m;
  }

  /* Seconds of work per exercise -> time by type (split evenly) and by muscle. */
  function breakdown(w, log) {
    const types = {}, muscles = {};
    w.items.forEach((it, i) => {
      const s = log[i];
      if (!s) return;
      it.types.forEach((k) => (types[k] = (types[k] || 0) + s / it.types.length));
      it.muscles.forEach((k) => (muscles[k] = (muscles[k] || 0) + s));
    });
    const sort = (o) => Object.entries(o).sort((a, b) => b[1] - a[1]);
    return { types: sort(types), muscles: sort(muscles) };
  }

  /* Timer: call tick() often; it reports events through callbacks.
   *   onStep(idx, catchingUp)  a new step started
   *   onCount(n)               3, 2, 1 before a step ends
   *   onFinish()               the timeline ran out
   * `log` holds seconds worked per workout item, summed across rounds. */
  class Timer {
    constructor(workout, cb) {
      this.w = workout;
      this.t = buildTimeline(workout);
      this.cb = cb;
      this.idx = 0;
      this.paused = false;
      this.finished = false;
      this.log = workout.items.map(() => 0);
      this.startedAt = null;
    }

    start(now = Date.now()) {
      this.startedAt = new Date(now);
      this.endsAt = now + this.t[0].dur * 1000;
      this.credited = now;
      this.lastTick = now;
      this.cb.onStep && this.cb.onStep(0, false);
    }

    rem(now = Date.now()) {
      return this.paused ? this.remPaused : Math.max(0, (this.endsAt - now) / 1000);
    }

    credit(until) {
      const st = this.t[this.idx];
      if (st.type === "work" && until > this.credited) this.log[st.ex] += (until - this.credited) / 1000;
      this.credited = Math.max(this.credited, until);
    }

    tick(now = Date.now()) {
      if (this.paused || this.finished) return;
      const before = Math.ceil((this.endsAt - this.lastTick) / 1000);
      while (true) {
        const end = this.endsAt;
        this.credit(Math.min(now, end));
        if (now < end) break;
        if (this.idx + 1 >= this.t.length) return this.finish(end);
        this.idx += 1;
        this.endsAt = end + this.t[this.idx].dur * 1000;
        this.credited = end;
        this.cb.onStep && this.cb.onStep(this.idx, now - end > 1000);
      }
      const after = Math.ceil((this.endsAt - now) / 1000);
      if (after < before && after >= 1 && after <= 3) this.cb.onCount && this.cb.onCount(after);
      this.lastTick = now;
    }

    pause(now = Date.now()) {
      if (this.paused || this.finished) return;
      this.tick(now);
      if (this.finished) return;
      this.credit(now);
      this.remPaused = Math.max(0, (this.endsAt - now) / 1000);
      this.paused = true;
    }

    resume(now = Date.now()) {
      if (!this.paused) return;
      this.paused = false;
      this.endsAt = now + this.remPaused * 1000;
      this.credited = now;
      this.lastTick = now;
    }

    jump(idx, now = Date.now()) {
      if (!this.paused) this.credit(now);
      if (idx >= this.t.length) return this.finish(now);
      this.idx = Math.max(0, idx);
      this.endsAt = now + this.t[this.idx].dur * 1000;
      this.remPaused = this.t[this.idx].dur;
      this.credited = now;
      this.lastTick = now;
      this.cb.onStep && this.cb.onStep(this.idx, false);
    }

    skip(now = Date.now()) { this.jump(this.idx + 1, now); }

    /* Back restarts the current step, or goes to the previous one if the
     * current step started less than 3 seconds ago. */
    back(now = Date.now()) {
      const elapsed = this.t[this.idx].dur - this.rem(now);
      this.jump(elapsed > 3 ? this.idx : this.idx - 1, now);
    }

    end(now = Date.now()) {
      if (!this.paused) this.credit(now);
      this.finish(now, true);
    }

    finish(at, early = false) {
      if (this.finished) return;
      this.finished = true;
      this.endedEarly = early;
      this.endedAt = new Date(at);
      this.cb.onFinish && this.cb.onFinish();
    }

    secondsWorked() { return this.log.reduce((a, b) => a + b, 0); }
  }

  window.Engine = { buildTimeline, totalSeconds, workingSeconds, model, breakdown, Timer, READY_SECONDS };
})();
