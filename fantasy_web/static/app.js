"use strict";

const $ = (id) => document.getElementById(id);
const app = { result: null, specs: [], saved: null, lastError: null, polling: false };

/* ---------- tiny DOM helpers (textContent only, so names can't inject HTML) ---------- */
function el(tag, opts = {}, children = []) {
  const node = document.createElement(tag);
  if (opts.class) node.className = opts.class;
  if (opts.text !== undefined) node.textContent = opts.text;
  for (const [key, value] of Object.entries(opts.attrs || {})) node.setAttribute(key, value);
  for (const child of [].concat(children)) if (child) node.append(child);
  return node;
}
const num = (value) => Number(value).toFixed(1);
const signed = (value) => (value > 0 ? "+" : "") + Number(value).toFixed(1);
const slotLabel = (slot) => (slot === "RB/WR/TE" ? "FLEX" : slot);

async function getJSON(url, options) {
  const response = await fetch(url, options);
  return { ok: response.ok, status: response.status, body: await response.json() };
}
const postJSON = (url, payload) => getJSON(url, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload || {}),
});

/* ---------- rendering ---------- */
function playerCell(player) {
  const cell = el("td", {}, [el("span", { text: player.name })]);
  cell.append(el("span", { class: "pos", text: [player.position, player.team].filter(Boolean).join(" · ") }));
  if (player.injury) cell.append(el("span", { class: "badge", text: player.injury }));
  return cell;
}

function renderHeader(result) {
  const parts = [result.league_name, result.team_name, `${result.season} · Week ${result.week}`];
  const model = result.model;
  if (model.type === "xgboost") {
    parts.push(`XGBoost (error ${model.mae_model.toFixed(1)} vs ${model.mae_baseline.toFixed(1)} for a simple average)`);
  } else {
    parts.push("No-ML fallback (not enough training data yet)");
  }
  parts.push("updated " + new Date(result.generated_at).toLocaleTimeString());
  $("subtitle").textContent = parts.join("  ·  ");
}

function renderRoster(result) {
  const head = el("thead", {}, el("tr", {}, [
    el("th", { text: "Slot" }), el("th", { text: "Player" }),
    el("th", { class: "num", text: "ROS pts" }), el("th", { class: "num", text: "VORP" }),
  ]));
  const body = el("tbody");
  let benchShown = false;
  for (const player of result.roster) {
    if (player.slot === "BENCH" && !benchShown) {
      benchShown = true;
      body.append(el("tr", { class: "bench-label" }, el("td", { text: "Bench", attrs: { colspan: "4" } })));
    }
    const row = el("tr", { class: player.slot === "BENCH" ? "" : "starter" }, [
      el("td", {}, el("span", { class: "slot", text: player.slot === "BENCH" ? "" : slotLabel(player.slot) })),
      playerCell(player),
      el("td", { class: "num", text: num(player.ros) }),
      el("td", { class: "num " + (player.vorp >= 0 ? "pos-val" : "neg-val"), text: signed(player.vorp) }),
    ]);
    body.append(row);
  }
  $("roster").replaceChildren(el("table", {}, [head, body]));
}

function moveLine(tagClass, tagText, player) {
  return el("div", { class: "move-line" }, [
    el("span", {}, [el("span", { class: tagClass, text: tagText }),
                    el("span", { text: player.name }),
                    el("span", { class: "pos", text: player.position })]),
    el("span", { class: "muted", text: `${num(player.ros)} ROS` }),
  ]);
}

function renderDropAdd(result) {
  const box = $("dropadd");
  if (!result.drop_add.length) {
    box.replaceChildren(el("p", { class: "muted", text: "No free agent improves your lineup enough. Hold steady." }));
    return;
  }
  box.replaceChildren(...result.drop_add.map((move) => el("div", { class: "card" }, [
    el("div", { class: "card-head" }, [
      el("strong", { text: `Add ${move.add.name}` }),
      el("span", { class: "gain", text: `${signed(move.gain)} pts` }),
    ]),
    moveLine("add-tag", "ADD", move.add),
    moveLine("drop-tag", "DROP", move.drop),
  ])));
}

function tradeList(title, players) {
  const list = el("ul");
  for (const player of players) {
    list.append(el("li", {}, [
      el("span", { text: player.name }),
      el("span", { class: "pos", text: `${player.position} · ${num(player.ros)} ROS` }),
    ]));
  }
  return el("div", {}, [el("h4", { text: title }), list]);
}

function renderTrades(result) {
  const box = $("trades");
  if (!result.trades.length) {
    box.replaceChildren(el("p", { class: "muted",
      text: "No trades met the fairness limits. Loosen the trade settings and reload." }));
    return;
  }
  box.replaceChildren(...result.trades.map((trade) => {
    const ratio = trade.value_ratio === null ? "n/a" : trade.value_ratio.toFixed(2);
    return el("div", { class: "card" }, [
      el("div", { class: "card-head" }, [
        el("strong", { text: `With ${trade.team}` }),
        el("span", { class: "gain", text: `${signed(trade.my_gain)} pts` }),
      ]),
      el("div", { class: "trade-cols" }, [tradeList("You give", trade.give), tradeList("You get", trade.get)]),
      el("div", { class: "trade-foot",
        text: `You ${signed(trade.my_gain)} · Them ${signed(trade.their_gain)} · value ratio ${ratio}` }),
    ]);
  }));
}

function render(result) {
  renderHeader(result);
  renderRoster(result);
  renderDropAdd(result);
  renderTrades(result);
}

/* ---------- status, banner, polling ---------- */
function settingsPending() {
  if (!app.result || !app.saved) return false;
  return app.specs.some((spec) => Number(app.result.settings[spec.key]) !== Number(app.saved[spec.key]));
}

function updateBanner() {
  const banner = $("banner");
  const pending = settingsPending();
  if (app.lastError) {
    banner.className = "banner error";
    banner.textContent = `Reload failed: ${app.lastError}` + (app.result ? " (showing previous results)" : "");
    banner.hidden = false;
  } else if (pending) {
    banner.className = "banner info";
    banner.textContent = "Settings changed. Press Reload to retrain the model and apply them.";
    banner.hidden = false;
  } else {
    banner.hidden = true;
  }
  $("reload-btn").classList.toggle("attention", pending);
}

function showStatus(status) {
  const running = status.status === "running";
  $("status-bar").hidden = !running;
  $("status-text").textContent = status.message;
  $("progress-fill").style.width = `${status.progress}%`;
  $("reload-btn").disabled = running;
  $("reload-btn").textContent = running ? "Working..." : "\u21BB Reload";
  app.lastError = status.status === "error" ? status.error : null;
}

async function loadData() {
  const { body } = await getJSON("/api/data");
  if (body.ready) {
    app.result = body;
    render(body);
  } else if (!app.result) {
    for (const id of ["roster", "dropadd", "trades"]) {
      $(id).replaceChildren(el("p", { class: "muted", text: "Waiting for the first run to finish..." }));
    }
  }
  updateBanner();
}

async function poll() {
  if (app.polling) return;
  app.polling = true;
  try {
    for (;;) {
      const { body: status } = await getJSON("/api/status");
      showStatus(status);
      if (status.status !== "running") break;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    await loadData();
  } finally {
    app.polling = false;
  }
}

/* ---------- settings dialog ---------- */
function buildSettingsForm() {
  const holder = $("settings-fields");
  holder.replaceChildren();
  let group = null;
  for (const spec of app.specs) {
    if (spec.group !== group) {
      group = spec.group;
      holder.append(el("h3", { text: group }));
    }
    const input = el("input", { attrs: {
      type: "number", name: spec.key, min: spec.min, max: spec.max, step: spec.step,
    } });
    input.value = app.saved[spec.key];
    holder.append(el("label", { class: "field" }, [
      el("span", { class: "label", text: spec.label }),
      input,
      el("small", { class: "help", text: spec.help }),
      el("small", { class: "error", attrs: { "data-error-for": spec.key } }),
    ]));
  }
}

function showFieldErrors(errors) {
  for (const node of document.querySelectorAll("[data-error-for]")) {
    node.textContent = errors[node.dataset.errorFor] || "";
  }
}

async function openSettings() {
  const { body } = await getJSON("/api/settings");
  app.specs = body.specs;
  app.saved = body.values;
  buildSettingsForm();
  showFieldErrors({});
  $("settings-dialog").showModal();
}

async function saveSettings(event) {
  event.preventDefault();
  const form = $("settings-form");
  const values = Object.fromEntries(app.specs.map((spec) => [spec.key, form.elements[spec.key].value]));
  const { ok, body } = await postJSON("/api/settings", values);
  if (!ok) {
    showFieldErrors(body.errors || {});
    return;
  }
  app.saved = body.values;
  $("settings-dialog").close();
  updateBanner();
}

async function resetSettings() {
  const { body } = await postJSON("/api/settings/reset");
  app.saved = body.values;
  buildSettingsForm();
  showFieldErrors({});
  updateBanner();
}

async function reload() {
  const { status } = await postJSON("/api/reload");
  if (status === 202 || status === 409) poll();
}

/* ---------- start ---------- */
async function init() {
  $("settings-btn").addEventListener("click", openSettings);
  $("settings-cancel").addEventListener("click", () => $("settings-dialog").close());
  $("settings-reset").addEventListener("click", resetSettings);
  $("settings-form").addEventListener("submit", saveSettings);
  $("reload-btn").addEventListener("click", reload);

  const { body } = await getJSON("/api/settings");
  app.specs = body.specs;
  app.saved = body.values;
  poll();
}

init();
