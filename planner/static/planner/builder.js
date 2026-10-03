/* Workout builder: library, ordered items, and a live make-up panel.
 * The make-up uses the PWA's own engine, so what you see here is exactly
 * the sequence the phone will play. */
(function () {
  "use strict";

  const data = JSON.parse(document.getElementById("builder-data").textContent);
  const { buildTimeline, totalSeconds, workingSeconds, breakdown, durationParts, durationText } = window.Engine;
  const durationBig = (s) => durationParts(s).map(([v, u]) => `${v}<small>${u}</small>`).join(" ");
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  const mmss = (s) => { s = Math.round(s); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };

  const lib = new Map(data.library.map((e) => [e.id, e]));
  const types = new Map(data.types.map((t) => [t.slug, t]));
  const colour = (slug) => (types.get(slug) || {}).colour || "#999";
  // Server-drawn SVG for the exercise's kit; nothing for bodyweight.
  const kit = new Map((data.equipment || []).map((e) => [e.slug, e.svg]));
  const kitIcon = (slug) => kit.get(slug) || "";
  let nextKey = 1;
  let items = (typeof data.items === "string" ? JSON.parse(data.items || "[]") : data.items)
    .filter((i) => lib.has(i.exercise))
    .map((i) => ({ key: nextKey++, exercise: i.exercise, dur: +i.dur }));
  let filterType = null;
  let dirty = false;

  const form = $("workout-form");
  const fields = { rest: $("id_rest_seconds"), rounds: $("id_rounds"), roundRest: $("id_round_rest_seconds") };
  const num = (el, min) => Math.max(min, parseInt(el.value, 10) || 0);
  const settings = () => ({ rest: num(fields.rest, 0), rounds: num(fields.rounds, 1), roundRest: num(fields.roundRest, 0) });

  const ICON = {
    grip: '<svg viewBox="0 0 24 24" aria-hidden="true"><g fill="currentColor"><circle cx="9" cy="6" r="1.7"/><circle cx="15" cy="6" r="1.7"/><circle cx="9" cy="12" r="1.7"/><circle cx="15" cy="12" r="1.7"/><circle cx="9" cy="18" r="1.7"/><circle cx="15" cy="18" r="1.7"/></g></svg>',
    up: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 15l6-6 6 6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    down: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    x: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>',
    plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>',
  };
  const dots = (slugs) => `<span class="dots">${slugs.map((s) => `<i style="background:${colour(s)}" title="${esc((types.get(s) || {}).name || s)}"></i>`).join("")}</span>`;

  /* ---------- library ---------- */

  function renderTypeFilter() {
    $("lib-types").innerHTML = data.types.map((t) =>
      `<button class="tchip" type="button" data-type="${t.slug}" aria-pressed="${filterType === t.slug}"><i style="background:${t.colour}"></i>${esc(t.name)}</button>`).join("");
  }

  function renderLibrary() {
    const q = $("lib-q").value.trim().toLowerCase();
    const used = new Set(items.map((i) => i.exercise));
    const rows = data.library
      .filter((e) => !filterType || e.types.includes(filterType))
      .filter((e) => !q || e.name.toLowerCase().includes(q) || e.muscles.some((m) => m.toLowerCase().includes(q)))
      .map((e) => `<li><span class="nm">${esc(e.name)} ${kitIcon(e.equipment)}${e.sides ? ' <span class="side">per side</span>' : ""}<small>${used.has(e.id) ? "In this workout · " : ""}${esc(e.muscles.join(", ") || "No muscles set")}</small></span>${dots(e.types)}<button class="icon-btn" type="button" data-add="${e.id}" aria-label="Add ${esc(e.name)}">${ICON.plus}</button></li>`);
    $("lib-list").innerHTML = rows.join("") || '<li class="none">No exercises match. Use New exercise to add one.</li>';
  }

  $("lib-types").addEventListener("click", (e) => {
    const b = e.target.closest("[data-type]");
    if (!b) return;
    filterType = filterType === b.dataset.type ? null : b.dataset.type;
    renderTypeFilter();
    renderLibrary();
  });
  $("lib-q").addEventListener("input", renderLibrary);
  $("lib-list").addEventListener("click", (e) => {
    const b = e.target.closest("[data-add]");
    if (b) addItem(b.dataset.add);
  });

  function addItem(id) {
    const ex = lib.get(id);
    items.push({ key: nextKey++, exercise: id, dur: ex.dur });
    changed();
    const last = $("items").querySelector(".item:last-of-type");
    if (last) last.scrollIntoView({ block: "nearest" });
  }

  /* ---------- items ---------- */

  function renderItems() {
    const { rest, rounds, roundRest } = settings();
    const el = $("items");
    if (!items.length) {
      el.innerHTML = '<li class="items-empty"><b>No exercises yet</b><span>Add exercises from the library on the left. They play in this order.</span></li>';
      return;
    }
    el.innerHTML = items.map((it, i) => {
      const ex = lib.get(it.exercise);
      const restLine = i < items.length - 1 && rest > 0 ? `<li class="restline" aria-hidden="true">rest ${rest} s</li>` : "";
      return `<li class="item" data-key="${it.key}">
        <span class="grip" title="Drag to reorder" data-grip>${ICON.grip}</span>
        <span class="n">${i + 1}</span>
        <span class="name"><span>${esc(ex.name)}</span>${kitIcon(ex.equipment)}${dots(ex.types)}</span>
        <span class="sidecell">${ex.sides ? '<span class="side" title="Runs left then right, with a 5 s switch">per side</span>' : ""}</span>
        <div class="dur sm"><input type="number" min="5" max="3600" value="${it.dur}" data-dur aria-label="Seconds for ${esc(ex.name)}${ex.sides ? " per side" : ""}"></div>
        <span class="tools">
          <button class="icon-btn bare" type="button" data-move="-1" aria-label="Move ${esc(ex.name)} up"${i === 0 ? " disabled" : ""}>${ICON.up}</button>
          <button class="icon-btn bare" type="button" data-move="1" aria-label="Move ${esc(ex.name)} down"${i === items.length - 1 ? " disabled" : ""}>${ICON.down}</button>
          <button class="icon-btn bare" type="button" data-remove aria-label="Remove ${esc(ex.name)}">${ICON.x}</button>
        </span></li>${restLine}`;
    }).join("") + (rounds > 1
      ? `<li class="restline roundline">× ${rounds} rounds${roundRest ? `, ${durationText(roundRest)} break between rounds` : ""}</li>` : "");
  }

  const itemIndex = (el) => items.findIndex((i) => i.key === +el.closest(".item").dataset.key);

  $("items").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    const i = itemIndex(b);
    if (b.hasAttribute("data-remove")) {
      items.splice(i, 1);
      changed();
      return;
    }
    const to = i + +b.dataset.move;
    if (to < 0 || to >= items.length) return;
    [items[i], items[to]] = [items[to], items[i]];
    changed();
    const again = $("items").querySelector(`[data-key="${items[to].key}"] [data-move="${b.dataset.move}"]`);
    (again && !again.disabled ? again : $("items").querySelector(`[data-key="${items[to].key}"] [data-remove]`)).focus();
  });

  $("items").addEventListener("input", (e) => {
    if (!e.target.matches("[data-dur]")) return;
    items[itemIndex(e.target)].dur = Math.max(5, parseInt(e.target.value, 10) || 0);
    dirty = true;
    renderMakeup();
  });

  /* Drag to reorder, started from the grip so the duration field stays usable. */
  let dragKey = null;
  $("items").addEventListener("pointerdown", (e) => {
    const grip = e.target.closest("[data-grip]");
    if (grip) grip.closest(".item").draggable = true;
  });
  $("items").addEventListener("dragstart", (e) => {
    const li = e.target.closest(".item");
    dragKey = +li.dataset.key;
    li.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(dragKey));
  });
  $("items").addEventListener("dragover", (e) => {
    const li = e.target.closest(".item");
    if (dragKey === null || !li) return;
    e.preventDefault();
    const after = e.offsetY > li.offsetHeight / 2 || e.clientY > li.getBoundingClientRect().top + li.offsetHeight / 2;
    $("items").querySelectorAll(".drop-before,.drop-after").forEach((x) => x.classList.remove("drop-before", "drop-after"));
    li.classList.add(after ? "drop-after" : "drop-before");
  });
  $("items").addEventListener("drop", (e) => {
    const li = e.target.closest(".item");
    if (dragKey === null || !li) return;
    e.preventDefault();
    const after = li.classList.contains("drop-after");
    const from = items.findIndex((i) => i.key === dragKey);
    const [moved] = items.splice(from, 1);
    let to = items.findIndex((i) => i.key === +li.dataset.key);
    if (to < 0) to = from; else if (after) to += 1;
    items.splice(to, 0, moved);
    changed();
  });
  $("items").addEventListener("dragend", () => {
    dragKey = null;
    $("items").querySelectorAll(".item").forEach((x) => { x.draggable = false; x.classList.remove("dragging", "drop-before", "drop-after"); });
  });

  /* ---------- make-up ---------- */

  function workoutShape() {
    const s = settings();
    return {
      rest: s.rest, rounds: s.rounds, roundRest: s.roundRest,
      items: items.map((it) => { const e = lib.get(it.exercise); return { name: e.name, dur: it.dur, sides: e.sides, types: e.types, muscles: e.muscles }; }),
    };
  }

  function renderMakeup() {
    const w = workoutShape();
    $("round-rest-field").style.opacity = w.rounds > 1 ? "1" : ".5";
    if (!w.items.length) {
      $("mu-total").innerHTML = durationBig(0);
      $("mu-end").textContent = "0:00";
      $("mu-kv").innerHTML = "<div><b>0</b>exercises</div>";
      $("mu-strip").innerHTML = "";
      $("mu-mix").innerHTML = "";
      $("mu-mix-legend").innerHTML = "";
      $("mu-muscles").innerHTML = '<li class="muted" style="display:block">Add an exercise to see what it works.</li>';
      return;
    }
    const t = buildTimeline(w);
    const total = totalSeconds(t);
    $("mu-total").innerHTML = durationBig(total);
    $("mu-end").textContent = mmss(total);
    $("mu-kv").innerHTML = `<div><b>${w.items.length}</b>exercise${w.items.length > 1 ? "s" : ""}</div><div><b>${durationText(workingSeconds(w))}</b>working</div><div><b>${w.rounds}</b>round${w.rounds > 1 ? "s" : ""}</div>`;
    $("mu-strip").innerHTML = t.map((s) => `<span class="${s.type}" style="flex:${s.dur}" title="${esc(s.type === "work" ? w.items[s.ex].name + (s.side ? " · " + s.side.toLowerCase() : "") : s.type)} · ${s.dur} s"></span>`).join("");
    const log = w.items.map((i) => i.dur * (i.sides ? 2 : 1) * w.rounds);
    const { types: mix, muscles } = breakdown(w, log);
    $("mu-mix").innerHTML = mix.map(([k, v]) => `<span style="flex:${v};background:${colour(k)}"></span>`).join("");
    $("mu-mix-legend").innerHTML = mix.map(([k, v]) => `<span><i class="dot" style="background:${colour(k)}"></i>${esc((types.get(k) || {}).name || k)} <span class="mono">${mmss(v)}</span></span>`).join("");
    const top = muscles.slice(0, 8);
    const max = top.length ? top[0][1] : 1;
    $("mu-muscles").innerHTML = top.map(([k, v]) => `<li><span title="${esc(k)}">${esc(k)}</span><b><s style="width:${((v / max) * 100).toFixed(0)}%"></s></b><em>${mmss(v)}</em></li>`).join("")
      || '<li class="muted" style="display:block">No muscles set on these exercises.</li>';
  }

  function changed() {
    dirty = true;
    renderItems();
    renderLibrary();
    renderMakeup();
  }

  Object.values(fields).forEach((el) => el.addEventListener("input", () => { dirty = true; renderItems(); renderMakeup(); }));
  $("id_name").addEventListener("input", (e) => { dirty = true; $("title").textContent = e.target.value.trim() || "New workout"; });
  $("id_description").addEventListener("input", () => (dirty = true));

  form.addEventListener("submit", () => {
    $("id_items").value = JSON.stringify(items.map((i) => ({ exercise: i.exercise, dur: i.dur })));
    dirty = false;
  });
  window.addEventListener("beforeunload", (e) => { if (dirty) { e.preventDefault(); e.returnValue = ""; } });

  /* ---------- new exercise ---------- */

  const dialog = $("ex-dialog");
  const exForm = $("ex-form");
  $("new-ex").addEventListener("click", () => {
    $("ex-errors").innerHTML = "";
    const q = $("lib-q").value.trim();
    if (q && !exForm.elements.name.value) exForm.elements.name.value = q[0].toUpperCase() + q.slice(1);
    dialog.showModal();
    exForm.elements.name.focus();
  });
  $("ex-cancel").addEventListener("click", () => dialog.close());
  exForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await fetch(exForm.action, { method: "POST", body: new FormData(exForm), headers: { Accept: "application/json" }, credentials: "same-origin" });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const errs = Object.entries(body.errors || { form: [{ message: "Could not save the exercise. Try again." }] })
        .flatMap(([, list]) => list.map((x) => x.message));
      $("ex-errors").innerHTML = errs.map((m) => `<li>${esc(m)}</li>`).join("");
      return;
    }
    const ex = body.exercise;
    data.library.push(ex);
    data.library.sort((a, b) => a.name.localeCompare(b.name));
    lib.set(ex.id, ex);
    exForm.reset();
    dialog.close();
    $("lib-q").value = "";
    addItem(ex.id);
  });

  renderTypeFilter();
  renderLibrary();
  renderItems();
  renderMakeup();
})();
