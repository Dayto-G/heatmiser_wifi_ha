"""Exercise UI registration and isolation without a thermostat or live HA."""
import ast
from dataclasses import dataclass
from hashlib import sha256
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).parents[1]

@dataclass
class StaticPathConfig:
    url_path: str
    path: str
    cache_headers: bool

class FrontendTests(unittest.IsolatedAsyncioTestCase):
    def load_module(self):
        add_module = Mock()
        modules = {
            'homeassistant': ModuleType('homeassistant'),
            'homeassistant.components': SimpleNamespace(frontend=SimpleNamespace(add_extra_js_url=add_module)),
            'homeassistant.components.http': SimpleNamespace(StaticPathConfig=StaticPathConfig),
            'homeassistant.core': SimpleNamespace(HomeAssistant=object),
        }
        spec = importlib.util.spec_from_file_location('frontend_under_test', ROOT / 'custom_components/heatmiser_wifi/frontend_setup.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules): spec.loader.exec_module(module)
        return module, add_module

    def hass(self):
        async def executor(callback, *args): return callback(*args)
        return SimpleNamespace(data={}, http=SimpleNamespace(async_register_static_paths=AsyncMock()), async_add_executor_job=AsyncMock(side_effect=executor))

    async def test_auto_serves_only_card_and_loads_versioned_module_once(self):
        module, add = self.load_module()
        hass = self.hass()
        await module.async_register_frontend(hass)
        await module.async_register_frontend(hass)
        hass.http.async_register_static_paths.assert_awaited_once()
        config = hass.http.async_register_static_paths.call_args.args[0][0]
        self.assertEqual(config.url_path, '/heatmiser_wifi/heatmiser-schedule-card.js')
        self.assertEqual(Path(config.path).read_bytes(), (ROOT/'frontend/heatmiser-schedule-card.js').read_bytes())
        self.assertFalse(config.cache_headers)
        digest = sha256(Path(config.path).read_bytes()).hexdigest()[:12]
        add.assert_called_once_with(hass, config.url_path + '?v=' + digest)
        hass.async_add_executor_job.assert_awaited_once()

    async def test_registration_failure_does_not_mark_registered(self):
        module, add = self.load_module()
        hass = self.hass()
        hass.http.async_register_static_paths.side_effect = OSError('failed')
        with self.assertRaises(OSError): await module.async_register_frontend(hass)
        self.assertFalse(hass.data.get(module.DATA_REGISTERED))
        add.assert_not_called()

    async def test_device_setup_keeps_working_if_ui_registration_fails(self):
        source = ROOT/'custom_components/heatmiser_wifi/__init__.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        handler = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'async_setup')
        for backend_ok, frontend_fails in [(True, True), (True, False), (False, False)]:
            with self.subTest(backend_ok=backend_ok, frontend_fails=frontend_fails):
                register = AsyncMock(side_effect=RuntimeError('UI failure') if frontend_fails else None)
                setup = Mock(return_value=backend_ok)
                logger = Mock()
                scope = {'HomeAssistant':object,'ConfigType':dict,'setup':setup,'_LOGGER':logger,'__package__':'test_heatmiser'}
                exec(compile(ast.Module(body=[handler],type_ignores=[]),str(source),'exec'),scope)
                with patch.dict(sys.modules, {'test_heatmiser':ModuleType('test_heatmiser'),'test_heatmiser.frontend_setup':SimpleNamespace(async_register_frontend=register)}):
                    hass = self.hass()
                    self.assertEqual(await scope['async_setup'](hass,{}), backend_ok)
                setup.assert_called_once_with(hass,{})
                self.assertEqual(register.await_count, int(backend_ok))
                self.assertEqual(logger.exception.call_count, int(backend_ok and frontend_fails))

if __name__ == '__main__': unittest.main()
