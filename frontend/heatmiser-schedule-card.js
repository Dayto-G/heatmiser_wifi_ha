/* Heatmiser WiFi schedule card. No build step or external dependencies. */
export function parseSchedule(raw) {
  const parts = typeof raw === "string" ? raw.replace(/,\s*$/, "").split(",") : [];
  if (parts.length !== 12 || parts.some(v => !/^\s*\d+\s*$/.test(v))) throw Error("No valid schedule received.");
  const values = parts.map(Number);
  let previous = -1;
  const rows = [];
  for (let i = 0; i < 12; i += 3) {
    const [h, m, t] = values.slice(i, i + 3);
    if (h > 23 || ![0, 30].includes(m) || t < 5 || t > 30 || h * 60 + m <= previous)
      throw Error("Use four increasing times, 30-minute intervals and 5–30 °C.");
    previous = h * 60 + m;
    rows.push({ time: `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`, temp: t });
  }
  return rows;
}
export function serialize(rows) {
  const raw = rows.map(r => `${Number(r.time.split(":")[0])},${Number(r.time.split(":")[1])},${r.temp}`).join(",");
  parseSchedule(raw);
  return raw;
}
export function stepPath(rows, initial) {
  const x = minute => 42 + minute / 1440 * 540;
  const y = temp => 160 - (temp - 5) / 25 * 130;
  let path = `M42,${y(initial)}`;
  for (const row of rows) {
    const [h, m] = row.time.split(":").map(Number);
    path += ` H${x(h * 60 + m)} V${y(row.temp)}`;
  }
  return path + " H582";
}
const groups = { weekday_triggers: "Weekdays", weekend_triggers: "Weekend" };
class HeatmiserScheduleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.drafts = {};
    this.base = {};
    this.dirty = {};
  }
  static getConfigElement() {
    return document.createElement("heatmiser-schedule-card-editor");
  }
  static getStubConfig(hass) {
    const states = Object.values(hass.states);
    const sensors = states.filter(state => state.entity_id.startsWith("sensor.") &&
      "weekday_triggers" in state.attributes && "weekend_triggers" in state.attributes);
    for (const sensor of sensors) {
      const climateId = sensor.entity_id.replace(/^sensor\./, "climate.").replace(/_program_mode$/, "");
      if (hass.states[climateId]) return { entity: sensor.entity_id, climate_entity: climateId };
    }
    return { entity: sensors.length === 1 ? sensors[0].entity_id : "", climate_entity: "" };
  }
  setConfig(config) {
    if (!config.entity?.startsWith("sensor.") || !config.climate_entity?.startsWith("climate."))
      throw Error("Set entity (the program_mode sensor) and climate_entity.");
    this.config = { ...config };
    this.signature = undefined;
    this.drafts = {}; this.base = {}; this.dirty = {};
    this.render();
  }
  set hass(hass) {
    this._hass = hass;
    const sensor = hass.states[this.config?.entity];
    const climate = hass.states[this.config?.climate_entity];
    const signature = JSON.stringify([sensor, climate]);
    if (signature === this.signature) return;
    this.signature = signature;
    for (const key of Object.keys(groups)) {
      if (!this.dirty[key]) {
        try {
          this.drafts[key] = parseSchedule(sensor?.attributes[key]);
          this.base[key] = serialize(this.drafts[key]);
        } catch { delete this.drafts[key]; }
      }
    }
    this.render();
  }
  getCardSize() { return 12; }
  getGridOptions() { return { columns: 12, min_columns: 6 }; }
  problem() {
    const sensor = this._hass?.states[this.config.entity];
    const climate = this._hass?.states[this.config.climate_entity];
    if (!sensor || !climate || [sensor.state, climate.state].some(s => ["unknown", "unavailable"].includes(s)))
      return "Thermostat or program sensor unavailable.";
    if (sensor.state !== "0") return "This card requires weekday/weekend (5/2) mode.";
    // Climate states usually omit temperature_unit; HA exposes the display
    // unit in its global configuration. The service also checks device units.
    const unit = climate.attributes.temperature_unit ?? this._hass.config?.unit_system?.temperature;
    if (unit !== "°C") return "This card only supports Celsius.";
    return "";
  }
  conflict(key) {
    try { return serialize(parseSchedule(this._hass.states[this.config.entity].attributes[key])) !== this.base[key]; }
    catch { return true; }
  }
  async refresh() {
    // climate.update reads the device; the sensor then formats the shared cache.
    await this._hass.callService("homeassistant", "update_entity", { entity_id: this.config.climate_entity });
    await this._hass.callService("homeassistant", "update_entity", { entity_id: this.config.entity });
  }
  async action(key) {
    if (this.busy) return;
    this.busy = true; this.message = ""; this.render();
    try {
      if (key) {
        if (this.problem()) throw Error(this.problem());
        if (this.conflict(key)) throw Error("The schedule was changed elsewhere. Reload and check your changes first.");
        const values = serialize(this.drafts[key]);
        await this._hass.callService("heatmiser_wifi", "update_triggers", { trigger: key, values });
        await this.refresh();
        // update_entity returns before the state event may reach this browser.
        const states = await this._hass.callWS({ type: "get_states" });
        const sensor = states.find(s => s.entity_id === this.config.entity);
        const actual = serialize(parseSchedule(sensor?.attributes[key]));
        if (actual !== values) throw Error("The schedule read back does not match. Check the thermostat and reload.");
        this.base[key] = actual; this.dirty[key] = false;
        this.message = `${groups[key]} saved and verified against the thermostat.`;
      } else {
        await this.refresh();
        const states = await this._hass.callWS({ type: "get_states" });
        const sensor = states.find(s => s.entity_id === this.config.entity);
        for (const group of Object.keys(groups)) {
          this.drafts[group] = parseSchedule(sensor?.attributes[group]);
          this.base[group] = serialize(this.drafts[group]); this.dirty[group] = false;
        }
        this.message = "Schedule reloaded.";
      }
    } catch (err) { this.message = `Error: ${err.message || err}. After a connection error, changes may already have been applied; reload to check.`; }
    finally { this.busy = false; this.render(); }
  }
  render() {
    if (!this.config || !this._hass) return;
    const root = this.shadowRoot;
    root.innerHTML = `<style>
      :host{display:block}ha-card{display:block;background:var(--ha-card-background,var(--card-background-color));border-radius:var(--ha-card-border-radius,12px);padding:20px;color:var(--primary-text-color)}h2{margin:0 0 8px;font-size:22px}h3{margin-bottom:4px}
      svg{width:100%;height:auto;color:var(--primary-color,#03a9f4)}text{fill:var(--secondary-text-color);font:12px sans-serif}
      .row{display:grid;grid-template-columns:30px 1fr 1fr;gap:12px;align-items:center;margin:8px 0}
      input,button{font:inherit;color:inherit;background:var(--card-background-color);border:1px solid var(--divider-color,#aaa);border-radius:6px;padding:9px;min-width:0}
      button{cursor:pointer;margin:8px 8px 0 0}button:disabled{opacity:.5;cursor:default}label{display:grid;gap:4px;font-size:13px}
      p{line-height:1.5}.status{white-space:pre-wrap}section{border-top:1px solid var(--divider-color,#ddd);margin-top:16px}
      </style><ha-card><h2>Heating schedule</h2><p>Four periods per day group · 5–30 °C · 30-minute intervals</p><div class="problem" role="alert"></div><div class="groups"></div><button id="reload">Reload and discard changes</button><p class="status" role="status" aria-live="polite"></p></ha-card>`;
    this.drawGraphs = [];
    const problem = this.problem();
    root.querySelector(".problem").textContent = problem;
    root.querySelector(".status").textContent = this.busy ? "Working…" : this.message || "";
    const reload = root.querySelector("#reload");
    reload.disabled = !!this.busy; reload.onclick = () => this.action();
    for (const [key, title] of Object.entries(groups)) {
      const section = document.createElement("section");
      root.querySelector(".groups").append(section);
      section.innerHTML = `<h3>${title}</h3>`;
      const rows = this.drafts[key];
      if (!rows) { section.append("No valid schedule. Reload to try again."); continue; }
      let valid = true;
      try { serialize(rows); } catch { valid = false; }
      const previousKey = key === "weekday_triggers" ? "weekend_triggers" : "weekday_triggers";
      // Monday/Saturday begin with the previous day's final setpoint. On other
      // days the same group's final setpoint carries over through midnight.
      const graph = document.createElement("div");
      graph.innerHTML = `<svg viewBox="0 0 610 195" role="img" aria-label="${title}: temperature step chart"><path d="M42 25 V160 H582" fill="none" stroke="currentColor" opacity=".3"/><text x="0" y="35">30 °C</text><text x="0" y="163">5 °C</text><text x="42" y="185">00:00</text><text x="300" y="185">12:00</text><text x="550" y="185">24:00</text></svg>`;
      section.append(graph);
      const draw = () => {
        graph.querySelectorAll(".schedule-line").forEach(n => n.remove());
        try {
          serialize(rows);
          serialize(this.drafts[previousKey]);
          const initial = this.drafts[previousKey][3].temp;
          const svg = graph.querySelector("svg");
          for (const [temp, opacity, dash] of [[rows[3].temp, ".35", "5 4"], [initial, "1", ""]]) {
            const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
            path.setAttribute("class", "schedule-line");path.setAttribute("d", stepPath(rows, temp));
            path.setAttribute("fill", "none");path.setAttribute("stroke", "currentColor");path.setAttribute("stroke-width", "3");
            path.setAttribute("opacity", opacity);path.setAttribute("stroke-dasharray", dash);svg.append(path);
          }
        } catch { /* Invalid input must never be plotted as a valid schedule. */ }
      };
      this.drawGraphs.push(draw);
      draw();
      const note = document.createElement("p");
      note.textContent = "Yesterday’s final temperature applies until the first period. Solid line: Monday/Saturday; dashed line: other days.";
      section.append(note);
      const error = document.createElement("p"); error.setAttribute("role", "alert");
      const save = document.createElement("button");
      const update = () => {
        try { serialize(rows); error.textContent = ""; valid = true; }
        catch (err) { error.textContent = err.message; valid = false; }
        save.disabled = !!(this.busy || problem || !valid || !this.dirty[key] || this.conflict(key));
        if (this.dirty[key] && this.conflict(key)) error.textContent = "The schedule was changed elsewhere. Reload before saving.";
        this.drawGraphs.forEach(drawGraph => drawGraph());
      };
      rows.forEach((row, index) => {
        const line = document.createElement("div"); line.className = "row";
        line.innerHTML = `<span>${index + 1}</span><label>Time<input type="time" step="1800" required></label><label>Temperature °C<input type="number" min="5" max="30" step="1" required></label>`;
        const [time, temp] = line.querySelectorAll("input");
        time.value = row.time; temp.value = row.temp;
        time.disabled = temp.disabled = !!(this.busy || problem);
        time.oninput = () => { row.time = time.value; this.dirty[key] = true; update(); };
        temp.oninput = () => { row.temp = temp.value === "" ? NaN : Number(temp.value); this.dirty[key] = true; update(); };
        section.append(line);
      });
      if (this.dirty[key] && this.conflict(key)) error.textContent = "The schedule was changed elsewhere. Reload before saving.";
      section.append(error);
      save.textContent = `Save ${title.toLowerCase()}`; save.onclick = () => this.action(key);
      section.append(save); update();
    }
  }
}
class HeatmiserScheduleCardEditor extends HTMLElement {
  setConfig(config) { this.config = { ...config }; this.render(); }
  set hass(hass) { this._hass = hass; this.render(); }
  render() {
    if (!this.config || !this._hass) return;
    if (!this.pickers) {
      this.style.display = "grid";
      this.style.gap = "16px";
      this.pickers = {};
      for (const [key, label, domain] of [
        ["entity", "Schedule sensor (program_mode)", "sensor"],
        ["climate_entity", "Heatmiser thermostat", "climate"],
      ]) {
        const picker = document.createElement("ha-entity-picker");
        picker.label = label;
        picker.includeDomains = [domain];
        picker.addEventListener("value-changed", event => {
          event.stopPropagation();
          if (event.detail.value === this.config[key]) return;
          this.config = { ...this.config, [key]: event.detail.value || "" };
          this.dispatchEvent(new CustomEvent("config-changed", {
            detail: { config: this.config }, bubbles: true, composed: true,
          }));
        });
        this.pickers[key] = picker;
        this.append(picker);
      }
    }
    for (const [key, picker] of Object.entries(this.pickers)) {
      picker.hass = this._hass;
      picker.value = this.config[key] || "";
    }
  }
}
if (!customElements.get("heatmiser-schedule-card")) {
  customElements.define("heatmiser-schedule-card", HeatmiserScheduleCard);
}
if (!customElements.get("heatmiser-schedule-card-editor")) {
  customElements.define("heatmiser-schedule-card-editor", HeatmiserScheduleCardEditor);
}
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === "heatmiser-schedule-card")) window.customCards.push({ type: "heatmiser-schedule-card", name: "Heatmiser heating schedule", description: "Edit four periods for weekdays and weekends." });
