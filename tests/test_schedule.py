import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('schedule', Path(__file__).parents[1] / 'custom_components/heatmiser_wifi/schedule.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
validate = module.validate_schedule
GOOD = '6,30,20,8,0,17,17,0,21,22,30,16'

class ScheduleTests(unittest.TestCase):
    def test_existing_sensor_format(self):
        self.assertEqual(validate('weekday_triggers', GOOD + ','), [6,30,20,8,0,17,17,0,21,22,30,16])

    def test_reject_bad_values(self):
        for raw in [GOOD.replace('6,30', '6,15'), GOOD.replace('22,30,16', '8,0,16'),
                    GOOD.replace('22,30,16', '7,30,16'), GOOD.replace('20', '31'),
                    GOOD.replace('20', '20.5'), GOOD + ',,', GOOD.replace('6,30', '24,30'),
                    GOOD.replace('6,30', '-1,30'), GOOD.replace('20', '4'),
                    '6,,20,8,0,17,17,0,21,22,30,16', None, [1] * 12]:
            with self.subTest(raw=raw), self.assertRaises((ValueError, TypeError)):
                validate('weekend_triggers', raw)

    def test_reject_other_targets(self):
        for target in ['mon_triggers', 'weekday_hw_triggers', None]:
            with self.assertRaises(ValueError): validate(target, GOOD)

import ast
from types import SimpleNamespace

class ServiceTests(unittest.TestCase):
    def handler(self, mode='2/5 mode', unit='Celsius', fail=False):
        source = Path(__file__).parents[1] / 'custom_components/heatmiser_wifi/__init__.py'
        tree = ast.parse(source.read_text())
        setup = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'setup')
        handler = next(n for n in setup.body if isinstance(n, ast.FunctionDef) and n.name == 'update_triggers')
        calls = []
        class Device:
            def connect(self): calls.append('connect')
            def disconnect(self): calls.append('disconnect')
            def get_info(self):
                calls.append('read')
                return {'program_mode': mode, 'temperature_format': unit}
            def set_value(self, *args):
                calls.append(('write', args))
                if fail: raise OSError('network failure')
        hass = SimpleNamespace(data={'heatmiser_wifi': {'heatmiser': Device()}})
        scope = {'hass': hass, 'DOMAIN': 'heatmiser_wifi', 'validate_schedule': validate, 'HomeAssistantError': RuntimeError}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), str(source), 'exec'), scope)
        return scope['update_triggers'], calls, hass

    def test_service_reads_back_and_disconnects(self):
        handler, calls, hass = self.handler()
        handler(SimpleNamespace(data={'trigger': 'weekday_triggers', 'values': GOOD}))
        self.assertEqual(calls[0:2], ['connect', 'read'])
        self.assertEqual(calls[-2:], ['read', 'disconnect'])
        self.assertIn('heatmiser_info', hass.data['heatmiser_wifi'])

    def test_invalid_input_never_connects(self):
        handler, calls, _ = self.handler()
        with self.assertRaises(RuntimeError): handler(SimpleNamespace(data={'trigger': 'mon_triggers', 'values': GOOD}))
        self.assertEqual(calls, [])

    def test_modes_and_failures_disconnect(self):
        for options in [{'mode': '7 day mode'}, {'mode': None}, {'unit': 'Fahrenheit'}, {'fail': True}]:
            handler, calls, _ = self.handler(**options)
            with self.assertRaises((RuntimeError, OSError)):
                handler(SimpleNamespace(data={'trigger': 'weekday_triggers', 'values': GOOD}))
            self.assertEqual(calls[-1], 'disconnect')
            if not options.get('fail'):
                self.assertFalse(any(isinstance(c, tuple) for c in calls))

if __name__ == '__main__': unittest.main()
