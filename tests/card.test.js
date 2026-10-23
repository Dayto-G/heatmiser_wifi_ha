import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';
globalThis.HTMLElement = class {};
let Card;
const registry = new Map();
globalThis.customElements = { get: name => registry.get(name), define: (name, value) => { registry.set(name, value); if (name === 'heatmiser-schedule-card') Card = value; } };
globalThis.window = {};
const { parseSchedule, serialize, stepPath, temperatureScale } = await import('../frontend/heatmiser-schedule-card.js');
const good = '6,30,20,8,0,17,17,0,21,22,30,16';
test('sensor round trip and validation', () => {
  assert.equal(serialize(parseSchedule(good + ',')), good);
  for (const raw of [good + ',,', good.replace('6,30', '6,15'), good.replace('20', '31'), good.replace('20', '20.5'), good.replace('22,30', '8,0'), ''])
    assert.throws(() => parseSchedule(raw));
  assert.throws(() => serialize([{ time: '', temp: 20 }]));
});
test('step graph includes midnight carry and vertical changes', () => {
  const path = stepPath(parseSchedule(good), 16);
  assert.ok(path.startsWith('M42,102.8 H188.25 V82'));
  assert.ok(path.endsWith(' H582'));
  assert.equal((path.match(/ V/g) || []).length, 4);
});
function card() {
  const instance = Object.create(Card.prototype);
  const state = { entity_id: 'sensor.program', state: '0', attributes: { weekday_triggers: good, weekend_triggers: good } };
  instance.config = { entity: 'sensor.program', climate_entity: 'climate.heating' };
  instance.drafts = { weekday_triggers: parseSchedule(good), weekend_triggers: parseSchedule(good) };
  instance.dirty = { weekday_triggers: true }; instance.base = { weekday_triggers: good, weekend_triggers: good };
  instance.render = () => {};
  instance.calls = [];
  instance._hass = {
    states: { 'sensor.program': state, 'climate.heating': { state: 'heat', attributes: { temperature_unit: '°C' } } },
    callService: async (...args) => { instance.calls.push(args); },
    callWS: async () => [state],
  };
  return instance;
}
test('save calls existing service then refreshes climate before sensor and confirms readback', async () => {
  const c = card(); await c.action('weekday_triggers');
  assert.deepEqual(c.calls, [
    ['heatmiser_wifi', 'update_triggers', { trigger: 'weekday_triggers', values: good }],
    ['homeassistant', 'update_entity', { entity_id: 'climate.heating' }],
    ['homeassistant', 'update_entity', { entity_id: 'sensor.program' }],
  ]);
  assert.equal(c.dirty.weekday_triggers, false);
  assert.match(c.message, /saved and verified against the thermostat/);
});
test('write failures and readback mismatches preserve draft', async () => {
  for (const fail of [true, false]) {
    const c = card();
    if (fail) c._hass.callService = async () => { throw Error('offline'); };
    else c._hass.callWS = async () => [{ entity_id: 'sensor.program', attributes: { weekday_triggers: good.replace('20', '19') } }];
    await c.action('weekday_triggers');
    assert.equal(c.dirty.weekday_triggers, true); assert.match(c.message, /^Error:/);
  }
});
test('external changes, unavailable, 7-day and Fahrenheit cannot write', async () => {
  for (const kind of ['conflict', 'unavailable', '7day', 'fahrenheit']) {
    const c = card();
    if (kind === 'conflict') c.base.weekday_triggers = 'old';
    if (kind === 'unavailable') c._hass.states['sensor.program'].state = 'unavailable';
    if (kind === '7day') c._hass.states['sensor.program'].state = '1';
    if (kind === 'fahrenheit') c._hass.states['climate.heating'].attributes.temperature_unit = '°F';
    await c.action('weekday_triggers'); assert.equal(c.calls.length, 0);
  }
});
test('refresh deliberately replaces drafts; background updates preserve dirty drafts', async () => {
  const c = card(); c.drafts.weekday_triggers[0].temp = 19;
  c.hass = { ...c._hass }; assert.equal(c.drafts.weekday_triggers[0].temp, 19);
  await c.action(); assert.equal(c.drafts.weekday_triggers[0].temp, 20);
  assert.equal(c.dirty.weekday_triggers, false);
});

test('HACS integration bundle contains the exact dashboard card', () => {
  assert.equal(
    readFileSync(new URL('../custom_components/heatmiser_wifi/frontend/heatmiser-schedule-card.js', import.meta.url), 'utf8'),
    readFileSync(new URL('../frontend/heatmiser-schedule-card.js', import.meta.url), 'utf8')
  );
});

test('card picker discovers the matching thermostat and exposes a visual editor', () => {
  const c = card();
  c._hass.states['sensor.heating_program_mode'] = {
    entity_id: 'sensor.heating_program_mode', attributes: { weekday_triggers: good, weekend_triggers: good }
  };
  c._hass.states['climate.heating'] = { entity_id: 'climate.heating', attributes: {} };
  assert.deepEqual(Card.getStubConfig(c._hass), { entity: 'sensor.heating_program_mode', climate_entity: 'climate.heating' });
  assert.ok(registry.has('heatmiser-schedule-card-editor'));
  assert.equal(window.customCards.length, 1);
});
test('visual editor keeps selectors in sync and emits configuration changes', () => {
  const previousDocument = globalThis.document;
  const pickers = [];
  globalThis.document = { createElement: tag => {
    const element = { tag, addEventListener: (_name, listener) => { element.change = listener; } };
    return element;
  } };
  try {
    const Editor = registry.get('heatmiser-schedule-card-editor');
    const editor = Object.create(Editor.prototype);
    editor.style = {};
    editor.append = picker => pickers.push(picker);
    const events = [];
    editor.dispatchEvent = event => events.push(event);
    editor.setConfig({ type: 'custom:heatmiser-schedule-card', entity: 'sensor.program', climate_entity: 'climate.heating' });
    editor.hass = card()._hass;
    assert.equal(pickers.length, 2);
    assert.deepEqual(pickers[0].includeDomains, ['sensor']);
    assert.equal(pickers[0].value, 'sensor.program');
    pickers[1].change({ stopPropagation() {}, detail: { value: 'climate.upstairs' } });
    assert.equal(events[0].type, 'config-changed');
    assert.equal(events[0].detail.config.climate_entity, 'climate.upstairs');
    assert.equal(events[0].detail.config.entity, 'sensor.program');
    assert.equal(events[0].bubbles, true);
    editor.hass = card()._hass;
    assert.equal(pickers.length, 2);
    assert.equal(pickers[1].value, 'climate.upstairs');
    assert.equal(Card.getConfigElement().tag, 'heatmiser-schedule-card-editor');
  } finally { globalThis.document = previousDocument; }
});

test('loading another version does not register the card or picker entry twice', async () => {
  await import('../frontend/heatmiser-schedule-card.js?duplicate');
  assert.equal(registry.get('heatmiser-schedule-card'), Card);
  assert.equal(window.customCards.length, 1);
});

test('standard HA climate states use the configured temperature unit', () => {
  const c = card();
  delete c._hass.states['climate.heating'].attributes.temperature_unit;
  c._hass.config = { unit_system: { temperature: '°C' } };
  assert.equal(c.problem(), '');
  c._hass.config.unit_system.temperature = '°F';
  assert.match(c.problem(), /only supports Celsius/);
  delete c._hass.config;
  assert.match(c.problem(), /only supports Celsius/);
  c._hass.config = { unit_system: { temperature: '°C' } };
  c._hass.states['climate.heating'].attributes.temperature_unit = '°F';
  assert.match(c.problem(), /only supports Celsius/);
});


test('shared automatic scale includes both schedules with one degree margin', () => {
  const weekday = parseSchedule('7,30,18,9,0,17,16,0,18,22,30,16');
  const weekend = parseSchedule('8,0,18,10,0,17,16,0,18,23,0,16');
  assert.deepEqual(temperatureScale([weekday, weekend]), { min: 15, max: 19 });
  weekend[0].temp = 25;
  assert.deepEqual(temperatureScale([weekday, weekend]), { min: 15, max: 26 });
  assert.deepEqual(temperatureScale([weekday.map(row => ({ ...row, temp: 18 }))]), { min: 17, max: 19 });
  assert.deepEqual(temperatureScale([undefined, []]), { min: 5, max: 30 });
  weekend[0].temp = NaN;
  assert.deepEqual(temperatureScale([weekday, weekend]), { min: 15, max: 19 });
});

test('automatic path keeps extreme legal setpoints and midnight carry within graph', () => {
  const rows = parseSchedule('0,0,5,6,0,30,12,0,5,23,30,30');
  const scale = temperatureScale([rows]);
  assert.deepEqual(scale, { min: 4, max: 31 });
  const path = stepPath(rows, 30, scale);
  assert.ok(!/NaN|Infinity/.test(path));
  const heights = [...path.matchAll(/(?:M42,| V)([\d.]+)/g)].map(match => Number(match[1]));
  assert.ok(heights.every(y => y > 30 && y < 160));
});
