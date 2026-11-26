// PawSOS Goa product site. Plain JS, no framework.

// Theme: follows the system until the visitor picks one. Storage may be unavailable.
(() => {
  const root = document.documentElement;
  const btn = document.getElementById("theme");
  let saved = null;
  try { saved = localStorage.getItem("pawsos-theme"); } catch {}
  if (saved) root.dataset.theme = saved;
  const isDark = () => root.dataset.theme
    ? root.dataset.theme === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  const paint = () => {
    btn.innerHTML = isDark() ? '<i class="ph ph-sun"></i>' : '<i class="ph ph-moon"></i>';
    btn.setAttribute("aria-label", isDark() ? "Switch to light theme" : "Switch to dark theme");
  };
  btn.addEventListener("click", () => {
    root.dataset.theme = isDark() ? "light" : "dark";
    try { localStorage.setItem("pawsos-theme", root.dataset.theme); } catch {}
    paint();
  });
  paint();
})();

// Hero chat. Text is PawSOS's own message copy (app/messages.py); the triage steps are an example.
(() => {
  const chat = document.getElementById("chat");
  const status = document.getElementById("phone-status");
  if (!chat) return;
  const CASE = '<b class="case">PAW-0041</b>';
  const script = [
    { dir: "in", html: '<span class="attach"><i class="ph ph-image"></i>Photo</span>' },
    { dir: "out", html: "Thank you, photo received. Now please share where the animal is: tap attach, then Location." },
    { dir: "in", html: '<span class="attach"><i class="ph-fill ph-map-pin"></i>Panaji</span>' },
    { dir: "out", html: `Your report is logged. Case ID: ${CASE}. We are finding the nearest team and will message you here.` },
    { dir: "out", html: `Case ${CASE}: <span class="urgent">this looks urgent.</span>\n\nWhile you wait:\n1. Keep people and traffic away.\n2. Stay a few metres back.\n3. Do not try to feed or move the animal.<span class="fine">This is general safety guidance from a photo, not a diagnosis.</span>` },
    { dir: "out", html: `Case ${CASE} is in the Panaji area. We are alerting a rescue team now.` },
    { dir: "out", html: `Good news. Panaji partner team has accepted case ${CASE} and is on the way.` },
    { dir: "out", html: `Update on case ${CASE}: the team has reached the animal.` },
    { dir: "out", html: `Case ${CASE} is resolved. The team has attended to the animal. Thank you for reporting.` },
  ];

  const bubble = (m) => {
    const li = document.createElement("li");
    li.className = `msg ${m.dir}`;
    li.innerHTML = m.html;
    return li;
  };

  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) {
    // Static: show the outcome only, no loop.
    script.slice(-4).forEach((m) => chat.append(bubble(m)));
    return;
  }

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const trim = () => { while (chat.scrollHeight > chat.clientHeight && chat.children.length > 1) chat.firstElementChild.remove(); };

  async function run() {
    for (;;) {
      // Fade the finished conversation out instead of blanking the phone.
      chat.style.transition = "opacity .5s";
      chat.style.opacity = "0";
      await wait(chat.children.length ? 500 : 0);
      chat.replaceChildren();
      chat.style.opacity = "1";
      for (const m of script) {
        if (m.dir === "out") {
          status.textContent = "typing…";
          const t = document.createElement("li");
          t.className = "typing";
          t.innerHTML = "<span></span><span></span><span></span>";
          chat.append(t); trim();
          await wait(m.html.length > 120 ? 1300 : 800);
          t.remove();
          status.textContent = "online";
        } else {
          await wait(700);
        }
        chat.append(bubble(m)); trim();
        await wait(m.dir === "in" ? 500 : 900);
      }
      await wait(4000);
    }
  }
  // Show a finished exchange straight away so the phone is never empty, then loop.
  script.slice(0, 4).forEach((m) => { const b = bubble(m); b.style.animation = "none"; chat.append(b); });
  // Only animate while the phone is on screen.
  let started = false;
  new IntersectionObserver(([e]) => { if (e.isIntersecting && !started) { started = true; run(); } }, { threshold: .3 }).observe(chat);
})();

// How it works: the step in the middle of the screen is highlighted, and its screen shown.
(() => {
  const steps = [...document.querySelectorAll(".how-steps li")];
  const shots = [...document.querySelectorAll(".how-shot img")];
  if (!steps.length) return;
  const show = (li) => {
    steps.forEach((s) => s.classList.toggle("is-active", s === li));
    shots.forEach((img) => { img.hidden = img.dataset.shot !== li.dataset.shot; });
  };
  let current = null;
  // Whenever any step moves on or off screen, pick the one nearest the middle.
  const io = new IntersectionObserver(() => {
    const mid = innerHeight / 2;
    const nearest = steps.reduce((best, s) => {
      const r = s.getBoundingClientRect();
      const d = Math.abs(r.top + r.height / 2 - mid);
      return d < best.d ? { s, d } : best;
    }, { s: steps[0], d: Infinity }).s;
    if (nearest !== current) { current = nearest; show(nearest); }
  }, { threshold: [0, 1], rootMargin: "-49% 0px -49% 0px" });  // a thin line across the middle
  steps.forEach((s) => io.observe(s));
})();

// Try it live: a private sandbox through the real PawSOS code path (/sandbox/*).
(() => {
  const root = document.getElementById("sandbox");
  if (!root) return;
  const $ = (id) => document.getElementById(id);
  const citizenChat = $("sb-citizen"), teamChat = $("sb-team"), teamSelect = $("sb-teams");
  const place = $("sb-place"), status = $("sb-status");
  const state = { who: "c1", team: null, last: {}, places: [], started: false };

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  async function api(path, options = {}) {
    const res = await fetch(path, { credentials: "same-origin", ...options });
    if (res.status === 429) throw new Error("Too many requests from your connection. Please wait a minute.");
    if (!res.ok) {
      let detail = "";
      try { detail = (await res.json()).detail; } catch {}
      if (res.status >= 500) throw new Error("The live demo is not reachable right now. Please try again in a minute.");
      throw new Error(typeof detail === "string" && detail ? detail : "That did not work. Please try again.");
    }
    return res.json();
  }

  function say(text, warn = false) {
    status.textContent = text;
    status.classList.toggle("warn", warn);
  }

  function render(list, m, chatOwner) {
    const empty = list.querySelector(".sb-empty");
    if (empty) empty.remove();
    const li = document.createElement("li");
    li.className = `msg ${m.direction}`;
    let body = "";
    if (m.media_url) body += `<img src="${esc(m.media_url)}" alt="Photo" loading="lazy">`;
    if (m.latitude != null) {
      const label = state.places.find((p) => Math.abs(p.latitude - m.latitude) < 1e-4)?.label || "Location";
      body += `<span class="attach"><i class="ph-fill ph-map-pin"></i>${esc(label)}</span>`;
    } else if (!(m.media_url && m.text === "Photo")) {
      body += esc(m.text).replace(/PAW-\d{4,}/g, (id) => `<b class="case">${id}</b>`);
    }
    if (m.buttons?.length && m.direction === "out") {
      body += `<div class="msg-btns">${m.buttons.map((b) =>
        `<button type="button" data-id="${esc(b.id)}">${esc(b.title)}</button>`).join("")}</div>`;
    }
    if (m.location_request && m.direction === "out" && chatOwner !== "team") {
      body += `<div class="msg-btns"><button type="button" data-send-location>Send location</button></div>`;
    }
    li.innerHTML = body;
    li.querySelectorAll("[data-id]").forEach((btn) => btn.addEventListener("click", () => press(btn, chatOwner)));
    li.querySelector("[data-send-location]")?.addEventListener("click", sendLocation);
    list.append(li);
    list.scrollTop = list.scrollHeight;
  }

  async function press(btn, chatOwner) {
    btn.closest(".msg-btns").querySelectorAll("button").forEach((b) => (b.disabled = true));
    const who = chatOwner === "team" ? state.team : state.who;
    try {
      await api("/sandbox/inbound", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ who, kind: "button", button_id: btn.dataset.id, text: btn.textContent }),
      });
      await poll();
    } catch (e) { say(e.message, true); }
  }

  async function load(list, who, owner) {
    const key = `${owner}:${who}`;
    const after = state.last[key] || 0;
    const msgs = await api(`/sandbox/messages?who=${encodeURIComponent(who)}&after=${after}`);
    // The visitor may have switched chats while this request was in flight.
    if ((owner === "citizen" ? state.who : state.team) !== who) return;
    msgs.forEach((m) => {
      if (m.id <= (state.last[key] || 0)) return;  // already shown
      render(list, m, owner);
      state.last[key] = m.id;
    });
  }

  function resetChat(list, text) {
    list.innerHTML = `<li class="sb-empty">${esc(text)}</li>`;
  }

  async function refreshTeams() {
    const info = await api("/sandbox/session");
    if (!info.teams.length) return;
    const before = [...teamSelect.options].map((o) => o.value);
    if (before.join() !== info.teams.map((t) => t.who).join()) {
      teamSelect.innerHTML = info.teams.map((t) => `<option value="${esc(t.who)}">${esc(t.label)}</option>`).join("");
      teamSelect.disabled = false;
      // Follow a newly alerted team (an escalation moves the case on), or keep the visitor's choice.
      const added = info.teams.filter((t) => !before.includes(t.who));
      if (added.length || !info.teams.some((t) => t.who === state.team)) {
        state.team = (added.length ? added : info.teams)[added.length ? added.length - 1 : info.teams.length - 1].who;
        resetChat(teamChat, "Loading the team's chat…");
        delete state.last[`team:${state.team}`];
        if (before.length && before[0] !== "No team alerted yet") say("No answer in time, so the case moved to the next team.");
      }
      teamSelect.value = state.team;
    }
  }

  // One poll at a time: a second request arriving mid-poll runs once the first finishes.
  let polling = false, again = false;
  async function poll() {
    if (polling) { again = true; return; }
    polling = true;
    try {
      await load(citizenChat, state.who, "citizen");
      await refreshTeams();
      if (state.team) await load(teamChat, state.team, "team");
    } catch (e) { say(e.message, true); }
    polling = false;
    if (again) { again = false; poll(); }
  }

  async function sendPhoto(blob, name) {
    const form = new FormData();
    form.append("who", state.who);
    form.append("file", blob, name);
    say("Sending the photo. Triage takes a few seconds…");
    try {
      await api("/sandbox/inbound/photo", { method: "POST", body: form });
      await poll();
      say("Photo sent. Now send the location.");
    } catch (e) { say(e.message, true); }
  }

  async function sendLocation() {
    const p = state.places[place.selectedIndex];
    if (!p) return;
    say("Sending the location. If a photo is waiting, this opens the case and runs triage…");
    $("sb-loc").disabled = true;
    try {
      await api("/sandbox/inbound", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ who: state.who, kind: "location", latitude: p.latitude, longitude: p.longitude }),
      });
      await poll();
      say("Done. Switch to the team on the right to accept, or wait and watch it escalate.");
    } catch (e) { say(e.message, true); }
    $("sb-loc").disabled = false;
  }

  $("sb-sample").addEventListener("click", async (ev) => {
    const btn = ev.currentTarget;  // null after the first await, so keep it
    btn.disabled = true;
    try {
      const blob = await (await fetch("/static/site/img/sample_street_dog.jpg")).blob();
      await sendPhoto(blob, "street_dog.jpg");
    } finally { btn.disabled = false; }
  });
  $("sb-file").addEventListener("change", (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { say("That photo is over 10 MB. Please choose a smaller one.", true); return; }
    sendPhoto(file, file.name);
    ev.target.value = "";
  });
  $("sb-loc").addEventListener("click", sendLocation);
  $("sb-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const input = $("sb-text");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    try {
      await api("/sandbox/inbound", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ who: state.who, kind: "text", text }),
      });
      await poll();
    } catch (e) { say(e.message, true); }
  });
  root.querySelectorAll(".seg button").forEach((btn) => btn.addEventListener("click", () => {
    root.querySelectorAll(".seg button").forEach((b) => b.setAttribute("aria-selected", String(b === btn)));
    state.who = btn.dataset.who;
    delete state.last[`citizen:${state.who}`];
    resetChat(citizenChat, state.who === "c1"
      ? "Start with a photo of the animal, then share where it is."
      : "A second person near the same animal. Send a photo and the same place to see the reports merge.");
    poll();
  }));
  teamSelect.addEventListener("change", () => {
    state.team = teamSelect.value;
    delete state.last[`team:${state.team}`];
    resetChat(teamChat, "Loading the team's chat…");
    poll();
  });

  // Start only when the section is near the screen, then poll while it is visible.
  let timer = null;
  const start = async () => {
    if (!state.started) {
      state.started = true;
      try {
        const info = await api("/sandbox/session");
        state.places = info.locations;
        place.innerHTML = info.locations.map((p) => `<option>${esc(p.label)}</option>`).join("");
      } catch (e) { say(e.message, true); return; }
    }
    poll();
    timer ??= setInterval(() => { if (document.visibilityState === "visible") poll(); }, 2000);
  };
  const stop = () => { clearInterval(timer); timer = null; };
  new IntersectionObserver(([e]) => (e.isIntersecting ? start() : stop()), { rootMargin: "200px" }).observe(root);
})();

// Film: if a film file has been published, play it in the frame.
(() => {
  const frame = document.getElementById("film-frame");
  if (!frame) return;
  fetch("/static/site/film/PawSOS_Goa_demo.mp4?v=3", { method: "HEAD" }).then((r) => {
    if (!r.ok) return;
    frame.innerHTML = '<video controls preload="metadata" poster="/static/site/film/poster.jpg?v=3" src="/static/site/film/PawSOS_Goa_demo.mp4?v=3"><track kind="captions" src="/static/site/film/captions.vtt?v=3" srclang="en-IN" label="English"></video>';
  }).catch(() => {});
})();
