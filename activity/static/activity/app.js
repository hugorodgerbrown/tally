/* Activity-mode PWA: workout list, summary, full-screen timer, finish. */
(function () {
  "use strict";

  const { Timer, model, breakdown, buildTimeline, totalSeconds, durationParts, durationText } = window.Engine;
  const durationBig = (s) => durationParts(s).map(([v, u]) => `<span>${v}<small>${u}</small></span>`).join("");
  const root = document.getElementById("app");

  let library = null;          // {types, workouts}
  let typeInfo = {};           // slug -> {name, colour}
  let run = null;              // {w, timer, ...} while a workout is on screen
  let interval = null;
  let wakeLock = null;
  let audio = null;
  let tv = false;              // TV mode: full screen, sized for across the room

  /* ---------- helpers ---------- */

  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  const fmt = (s) => { s = Math.max(0, Math.ceil(s - 1e-9)); return s < 60 ? String(s) : Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
  const fmtL = (s) => { s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
  const fmtLeft = (s) => fmtL(Math.ceil(s - 1e-9));
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) => (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)));
  const typeName = (slug) => (typeInfo[slug] ? typeInfo[slug].name : slug);
  const typeColour = (slug) => (typeInfo[slug] ? typeInfo[slug].colour : "#999");

  const I = {
    play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4.5v15l12.5-7.5z" fill="currentColor"/></svg>',
    back: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5h2.4v14H6zM19 5v14L9.6 12z" fill="currentColor"/></svg>',
    skip: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15.6 5H18v14h-2.4zM5 5v14l9.4-7z" fill="currentColor"/></svg>',
    end: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5.5" y="5.5" width="13" height="13" rx="2.5" fill="currentColor"/></svg>',
    swap: '<svg class="bigicon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h15m0 0-4-4m4 4-4 4M20 16H5m0 0 4-4m-4 4 4 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    left: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    tv: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M8 20.5h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    cloud: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 18h10a4 4 0 0 0 .6-8 6 6 0 0 0-11.4 1.6A3.3 3.3 0 0 0 7 18z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
  };

  /* ---------- sound and screen ---------- */

  function beep(freq, len) {
    if (!audio) return;
    try {
      const o = audio.createOscillator(), g = audio.createGain();
      o.frequency.value = freq;
      o.type = "sine";
      g.gain.setValueAtTime(0.0001, audio.currentTime);
      g.gain.exponentialRampToValueAtTime(0.4, audio.currentTime + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, audio.currentTime + len);
      o.connect(g).connect(audio.destination);
      o.start();
      o.stop(audio.currentTime + len + 0.02);
    } catch (e) { /* sound is best effort */ }
  }

  async function keepAwake() {
    try { if ("wakeLock" in navigator && !wakeLock) wakeLock = await navigator.wakeLock.request("screen"); } catch (e) { /* not supported or denied */ }
    if (wakeLock) wakeLock.addEventListener("release", () => (wakeLock = null), { once: true });
  }
  function releaseAwake() { if (tv) return; try { wakeLock && wakeLock.release(); } catch (e) { /* ignore */ } wakeLock = null; }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && tv) keepAwake();
    if (document.visibilityState === "visible" && run && !run.timer.finished) {
      keepAwake();
      if (audio && audio.state === "suspended") audio.resume();
      tick();
    } else if (document.visibilityState === "hidden" && run && !run.timer.finished) {
      checkpoint();
    }
  });

  /* ---------- TV mode ----------
   * For casting to a TV: the page goes full screen, the layout is sized to
   * be read from across the room, the screen stays awake and the cursor
   * hides. It is driven from the keyboard of the laptop doing the casting.
   * Leaving full screen (Esc) leaves TV mode. ?tv=1 turns the layout on
   * without full screen, for a browser that is already full screen. */

  const canFullscreen = () => !!(document.fullscreenEnabled && document.documentElement.requestFullscreen);

  async function setTv(on) {
    tv = on;
    document.documentElement.classList.toggle("tv", on);
    armIdle();
    if (on) {
      keepAwake();
      if (canFullscreen() && !document.fullscreenElement) {
        try { await document.documentElement.requestFullscreen({ navigationUI: "hide" }); } catch (e) { /* stays in the TV layout, windowed */ }
      }
    } else {
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
      if (!run || !run.timer.startedAt || run.timer.finished) releaseAwake();
    }
    lastHtml = "";
    render();
  }

  document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement && tv) setTv(false);
  });

  // The cursor hides after a moment still, counted from entering TV mode too.
  let idleTimer = null;
  function armIdle() {
    document.documentElement.classList.remove("idle");
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => tv && document.documentElement.classList.add("idle"), 2500);
  }
  document.addEventListener("pointermove", armIdle);

  const tvButton = () => `<button class="tvbtn" type="button" data-act="tv" aria-pressed="${tv}" title="${tv ? "Leave TV mode (Esc)" : "TV mode: full screen for casting (F)"}">${I.tv}TV</button>`;

  /* ---------- screens ---------- */

  function statusLine() {
    const s = window.Store.status();
    const n = pendingCount;
    if (s === "signed-out") return `<a class="status warn" href="/login/?next=/">${I.cloud}Signed out. Sign in to sync${n ? ` ${n} session${n > 1 ? "s" : ""}` : ""}.</a>`;
    if (n) return `<div class="status">${I.cloud}${n} session${n > 1 ? "s" : ""} waiting to sync${s === "offline" ? " (offline)" : ""}</div>`;
    if (s === "offline") return `<div class="status">${I.cloud}Offline. Workouts are stored on this phone.</div>`;
    return `<div class="status ok">${I.check}All sessions synced</div>`;
  }

  /* The top-right controls, the same as the planner's header: the mode
   * switch, then Sign out. Manage and Sign out need the server, so they are
   * disabled offline; once signed out, Sign out becomes Sign in. */
  function modeSwitch() {
    const s = window.Store.status();
    const offline = s === "offline" || !navigator.onLine;
    const manage = offline
      ? '<span class="mode-off" aria-disabled="true" title="Manage needs a connection">Manage</span>'
      : '<a href="/workouts/">Manage</a>';
    const account = s === "signed-out"
      ? '<a class="signout" href="/login/?next=/">Sign in</a>'
      : offline
        ? '<span class="signout off" aria-disabled="true" title="Signing out needs a connection">Sign out</span>'
        : `<form method="post" action="/logout/"><input type="hidden" name="next" value="/login/?next=/"><input type="hidden" name="csrfmiddlewaretoken" value="${esc(window.Store.csrfToken())}"><button class="signout" type="submit">Sign out</button></form>`;
    return `<div class="hctl"><nav class="modes" aria-label="Mode"><span aria-current="page">Activity</span>${manage}</nav>${account}</div>`;
  }

  function homeScreen() {
    const ws = library ? library.workouts : [];
    const list = ws.map((w) => {
      const total = totalSeconds(buildTimeline(w));
      const types = [...new Set(w.items.flatMap((i) => i.types))];
      return `<li><a href="#/w/${w.id}"><span class="wn">${esc(w.name)}</span>
        <span class="wm"><b>${durationText(total)}</b> · ${w.items.length} exercises${w.rounds > 1 ? ` · ${w.rounds} rounds` : ""}</span>
        <span class="wt">${types.map((t) => `<s style="background:${typeColour(t)}" title="${esc(typeName(t))}"></s>`).join("")}</span></a></li>`;
    }).join("");
    const empty = library
      ? `<p class="empty">No workouts yet. Build one in <a href="/workouts/new/">Manage</a>.</p>`
      : `<p class="empty">Workouts appear here after the first sync. Connect to the internet and reopen the app.</p>`;
    return `<div class="scr s-done s-home"><div class="main" style="justify-content:flex-start;gap:5cqw">
      <div class="hrow"><div class="eb">Tally</div>${modeSwitch()}</div><div class="name">Workouts</div>
      ${ws.length ? `<ul class="wlist">${list}</ul>` : empty}</div>${statusLine()}</div>`;
  }

  function summaryScreen(w) {
    const total = totalSeconds(buildTimeline(w));
    const used = [...new Set(w.items.flatMap((i) => i.types))];
    const list = w.items.map((it, i) => `<li><i>${i + 1}</i><span>${esc(it.name)}${it.sides ? " <small>each side</small>" : ""}<b>${it.types.map((t) => `<s style="background:${typeColour(t)}" title="${esc(typeName(t))}"></s>`).join("")}</b></span><em>${it.dur} s</em></li>`).join("");
    return `<div class="scr s-done s-sum"><div class="main" style="justify-content:flex-start;gap:3.4cqw">
      <div class="hrow"><a class="backlink" href="#/">${I.left}Workouts</a>${tvButton()}</div>
      <div class="name" style="font-size:9cqw">${esc(w.name)}</div>
      <div class="bigtime" aria-label="Total time ${durationText(total)}">${durationBig(total)}</div>
      <ol class="slist${w.items.length > 10 ? " long" : ""}" style="--rows:${Math.ceil(w.items.length / 2)}">${list}</ol>
      <div class="sleg">${used.map((t) => `<span><s style="background:${typeColour(t)}"></s>${esc(typeName(t))}</span>`).join("")}<span>${w.rest ? `${w.rest} s rest between` : "No rest between"}${w.rounds > 1 ? ` · ${w.rounds} rounds, ${durationText(w.roundRest)} between` : ""}</span></div></div>
      <button class="play" type="button" data-act="start">${I.play}Start workout</button></div>`;
  }

  function doneScreen() {
    const { w, timer, rating } = run;
    const log = timer.log.map((s) => Math.round(s));
    const worked = log.reduce((a, b) => a + b, 0);
    const exDone = log.filter((x) => x > 0).length;
    const { types, muscles } = breakdown(w, log);
    const ml = muscles.slice(0, 6);
    const mmax = ml.length ? ml[0][1] : 1;
    const partial = timer.endedEarly;
    const bar = types.map(([k, v]) => `<span style="flex:${v};background:${typeColour(k)}"></span>`).join("");
    const legend = types.map(([k, v]) => `<li><i style="background:${typeColour(k)}"></i><span>${esc(typeName(k))}</span><em>${fmtL(v)}</em></li>`).join("");
    const mrows = ml.map(([k, v]) => `<li><span>${esc(k)}</span><b><s style="width:${((v / mmax) * 100).toFixed(0)}%"></s></b><em>${fmtL(v)}</em></li>`).join("");
    const saved = run.confirmDiscard
      ? "Discard this session? It won't be logged."
      : run.saved
        ? `${I.check}Saved to your log${partial ? " (time actually worked)" : ""}`
        : "Nothing worked yet, so nothing was logged";
    // Discard asks first, in place: the line above becomes the question.
    const buttons = run.confirmDiscard
      ? '<button class="dbtn" type="button" data-act="discard-no">Keep</button><button class="dbtn danger" type="button" data-act="discard-yes">Discard</button>'
      : `${run.saved ? '<button class="dbtn quiet" type="button" data-act="discard">Discard</button>' : ""}<button class="dbtn pri" type="button" data-act="close">Done</button>`;
    return `<div class="scr s-done"><div class="main" style="justify-content:flex-start;gap:3.6cqw">
      <div class="eb">${partial ? "Ended early" : "Workout complete"}</div><div class="name" style="font-size:8.5cqw">${esc(w.name)}</div>
      <div class="stats"><div><b>${durationText(worked)}</b>worked</div><div><b>${exDone}/${w.items.length}</b>exercises</div>${w.rounds > 1 ? `<div><b>${w.rounds}</b>rounds</div>` : ""}</div>
      <div class="sub">Where it went</div>
      <div class="tbar">${bar || '<span style="flex:1;opacity:.2;background:currentColor"></span>'}</div>
      <ul class="tleg">${legend}</ul>
      <div class="sub">Muscles worked</div>
      <ul class="mus">${mrows || '<li style="display:block;opacity:.6">Nothing logged</li>'}</ul>
      ${run.saved ? `<div class="sub">How hard was it? <span style="text-transform:none;letter-spacing:0;font-weight:600">(optional)</span></div>
      <div class="rate" role="group" aria-label="Effort from 1 to 10">${Array.from({ length: 10 }, (_, k) => `<button type="button" data-act="rate" data-v="${k + 1}" aria-pressed="${rating === k + 1}" class="${rating && k + 1 <= rating ? "on" : ""}">${k + 1}</button>`).join("")}</div>` : ""}
      <div class="saved${run.confirmDiscard ? " ask" : ""}" role="status">${saved}</div></div>
      <div class="drow">${buttons}</div></div>`;
  }

  function activityScreen(m, o) {
    const top = `<div class="top"><div class="segs">${m.segs.map((g) => (g.k === "dot" ? `<span class="rdot ${g.st}"></span>` : `<span class="seg"><span style="width:${(g.f * 100).toFixed(1)}%"></span></span>`)).join("")}</div>
      <div class="meta"><span>${m.rounds > 1 ? `Round ${m.round}/${m.rounds} · ` : ""}${m.exNum} of ${m.exTotal}</span><span>${fmtLeft(m.left)} left</span></div></div>`;
    const chip = m.side ? `<span class="chip">${m.side} side <i>${Array.from({ length: m.sn }, (_, k) => `<b class="${k === m.si ? "on" : ""}"></b>`).join("")}</i></span>` : "";
    const c = fmt(m.rem);
    const cc = c.length > 2 ? "clock mm" : "clock";
    const next = `<div class="next"><span class="nl">Next</span><span class="nn">${esc(m.next.name)}</span><span class="nd">${m.next.dur ? m.next.dur + " s" : ""}</span></div>`;
    const fin = m.rem <= 3 && m.rem > 0 && !m.paused ? " final" : "";
    const fill = `<div class="fill" style="height:${m.pct.toFixed(2)}%"></div>`;

    if (m.paused) {
      return `<div class="scr s-paused">${top}
        <div class="main"><div class="eb">Paused</div><div class="name">${esc(m.name)}</div>${chip}<div class="clock sm">${c}</div></div>
        <div class="pctl"><button class="resume" type="button" data-act="resume" aria-label="Resume">${I.play}</button>
        <div class="prow"><button class="pbtn" type="button" data-act="back">${I.back}Back</button><button class="pbtn" type="button" data-act="skip">${I.skip}Skip</button><button class="pbtn end" type="button" data-act="end">${I.end}End</button></div></div></div>`;
    }
    if (m.phase === "round" || m.phase === "rest") {
      const head = m.phase === "round" ? `Round ${m.round - 1} of ${m.rounds} done` : "Rest";
      const lead = m.phase === "round" ? `Round ${m.round} starts with` : "Up next";
      return `<div class="scr s-${m.phase}${fin}">${fill}${top}
        <div class="main" style="gap:4cqw"><div class="eb">${head}</div><div class="${cc}">${c}</div></div>
        <div class="upnext"><span class="nl eb">${lead}</span>
          <div class="name">${esc(m.name)}</div><div class="d">${m.updur} s${m.side ? " · " + m.side.toLowerCase() + " side first" : ""}</div></div></div>`;
    }
    const eb = { work: "Work", ready: "Get ready", switch: "Switch sides" }[m.phase];
    const hint = o.hint ? `<div class="hint">${tv ? "<kbd>Space</kbd> pauses · <kbd>←</kbd> <kbd>→</kbd> back and skip" : "Tap anywhere to pause"}</div>` : "";
    const icon = m.phase === "switch" ? I.swap : "";
    return `<div class="scr s-${m.phase}${fin}">${fill}${top}
      <div class="main">${icon}<div class="eb">${eb}</div><div class="name">${esc(m.name)}</div>${chip}<div class="lclock"><div class="${cc}">${c}</div></div></div>
      ${hint}${next}</div>`;
  }

  /* ---------- rendering ---------- */

  let pendingCount = 0;
  let lastHtml = "";
  function paint(html) {
    if (html !== lastHtml) { root.innerHTML = html; lastHtml = html; }
  }

  function render() {
    if (run) {
      const t = run.timer;
      if (t.finished) return paint(doneScreen());
      if (!t.startedAt) return paint(summaryScreen(run.w));
      const m = model(run.w, t.t, t.idx, t.rem());
      m.paused = t.paused;
      return paint(activityScreen(m, { hint: t.t[t.idx].type === "work" && t.idx === 1 }));
    }
    const route = location.hash.match(/^#\/w\/([0-9a-f-]{36})/);
    if (route && library) {
      const w = library.workouts.find((x) => String(x.id) === route[1]);
      if (w) { openWorkout(w); return render(); }
    }
    paint(homeScreen());
  }

  function tick() {
    if (!run || !run.timer.startedAt || run.timer.finished) return;
    run.timer.tick();
    render();
  }

  /* ---------- workout lifecycle ---------- */

  function openWorkout(w) {
    run = { w, uuid: uuid(), rating: null, saved: false };
    run.timer = new Timer(w, {
      onStep: (idx, catchingUp) => { if (!catchingUp) beep(1320, 0.35); checkpoint(); },
      onCount: () => beep(880, 0.15),
      onFinish: () => finish(),
    });
  }

  async function start() {
    try { audio = audio || new (window.AudioContext || window.webkitAudioContext)(); if (audio.state === "suspended") audio.resume(); } catch (e) { audio = null; }
    keepAwake();
    // The back button pauses rather than leaving mid-workout.
    history.pushState({ running: true }, "", location.hash);
    run.timer.start();
    clearInterval(interval);
    interval = setInterval(tick, 100);
    render();
  }

  function sessionRecord() {
    const { w, timer } = run;
    return {
      uuid: run.uuid,
      workoutId: w.id,
      workoutName: w.name,
      startedAt: timer.startedAt.toISOString(),
      endedAt: (timer.endedAt || new Date()).toISOString(),
      completed: timer.finished && !timer.endedEarly,
      rounds: w.rounds,
      effort: run.rating,
      entries: w.items.map((it, i) => ({ exerciseId: it.exerciseId, name: it.name, seconds: Math.round(timer.log[i]) })),
    };
  }

  /* Save progress while running, so a killed app still logs the work done. */
  function checkpoint() {
    if (!run || !run.timer.startedAt || run.timer.finished) return;
    window.Store.set("current", { ...sessionRecord(), checkpointAt: Date.now() });
  }

  async function finish() {
    clearInterval(interval);
    interval = null;
    releaseAwake();
    beep(1320, 0.5);
    run.saved = run.timer.secondsWorked() >= 1;
    await window.Store.del("current");
    if (run.saved) await window.Store.saveSession(sessionRecord());
    refreshPending();
    render();
  }

  function close() {
    clearInterval(interval);
    interval = null;
    releaseAwake();
    run = null;
    if (history.state && history.state.running) history.replaceState(null, "", "#/");
    else location.hash = "#/";
    lastHtml = "";
    render();
  }

  /* A workout interrupted by the app being closed: log what was done. */
  async function recoverCheckpoint() {
    const cp = await window.Store.get("current");
    if (!cp) return;
    await window.Store.del("current");
    if (!cp.entries.some((e) => e.seconds > 0)) return;
    await window.Store.saveSession({ ...cp, endedAt: new Date(cp.checkpointAt).toISOString(), completed: false });
  }

  async function refreshPending() {
    pendingCount = (await window.Store.pending()).filter((s) => !s.discarded).length;
    if (!run) render();
  }

  /* ---------- input ---------- */

  root.addEventListener("click", (e) => {
    const b = e.target.closest("[data-act]");
    const act = b && b.dataset.act;
    if (act === "tv") return setTv(!tv);
    if (!run) return;
    const t = run.timer;
    if (act === "start") return start();
    if (act === "close") return close();
    if (act === "discard" || act === "discard-no") { run.confirmDiscard = act === "discard"; return render(); }
    if (act === "discard-yes") { window.Store.discardSession(run.uuid).then(refreshPending); return close(); }
    if (act === "rate") {
      const v = +b.dataset.v;
      run.rating = run.rating === v ? null : v;
      window.Store.saveSession(sessionRecord()).then(refreshPending);
      return render();
    }
    if (t.finished || !t.startedAt) return;
    if (act === "resume") t.resume();
    else if (act === "skip") t.skip();
    else if (act === "back") t.back();
    else if (act === "end") t.end();
    else if (!act) t.paused ? t.resume() : t.pause();
    checkpoint();
    render();
  });

  /* Keys, for a laptop casting to a TV: Space pauses, the arrows go back
   * and skip, F toggles TV mode. */
  document.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if ((e.key === "f" || e.key === "F") && !e.repeat) { e.preventDefault(); return setTv(!tv); }
    if (!run || !run.timer.startedAt || run.timer.finished) return;
    const t = run.timer;
    if (e.key === " ") { e.preventDefault(); t.paused ? t.resume() : t.pause(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); t.skip(); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); t.back(); }
    else return;
    checkpoint();
    render();
  });

  window.addEventListener("popstate", () => {
    if (run && run.timer.startedAt && !run.timer.finished) {
      run.timer.pause();
      history.pushState({ running: true }, "", location.hash);
      render();
    }
  });

  window.addEventListener("hashchange", () => {
    if (run && run.timer.startedAt && !run.timer.finished) return;
    if (run && !location.hash.startsWith("#/w/" + run.w.id)) run = null;
    render();
  });

  /* ---------- boot ---------- */

  window.Store.onStatus(() => { refreshPending(); });

  async function boot() {
    if (new URLSearchParams(location.search).get("tv") === "1") { tv = true; document.documentElement.classList.add("tv"); keepAwake(); armIdle(); }
    if ("serviceWorker" in navigator) {
      // A new version took over: reload to use it, unless a workout is on screen.
      const hadController = !!navigator.serviceWorker.controller;
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (hadController && !run) location.reload();
      });
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
    }
    if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
    const cached = await window.Store.get("library");
    if (cached) setLibrary(cached);
    render();
    await recoverCheckpoint();
    const fresh = await window.Store.loadWorkouts();
    if (fresh) setLibrary(fresh);
    await window.Store.flush();
    await refreshPending();
    if (!run) render();
  }

  function setLibrary(data) {
    library = data;
    typeInfo = Object.fromEntries(data.types.map((t) => [t.slug, t]));
  }

  boot();
})();
