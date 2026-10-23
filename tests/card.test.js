import { test } from 'node:test';
import assert from 'node:assert/strict';
globalThis.HTMLElement = class {};
let Card;
globalThis.customElements = { define: (_name, value) => { Card = value; } };
globalThis.window = {};
const { parseSchedule, serialize, stepPath } = await import('../frontend/heatmiser-schedule-card.js');
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
