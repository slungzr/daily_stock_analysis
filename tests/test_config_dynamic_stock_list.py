# -*- coding: utf-8 -*-
"""Unit tests for dynamic STOCK_LIST loading via pywencai."""

import os
import sys
import tempfile
import types
import unittest

import pandas as pd

# Provide a minimal fallback when python-dotenv is unavailable in test runtime.
try:
    import dotenv  # type: ignore  # noqa: F401
except ModuleNotFoundError:
    def _fallback_dotenv_values(dotenv_path=None):
        values = {}
        if not dotenv_path or not os.path.exists(dotenv_path):
            return values
        with open(dotenv_path, "r", encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
        return values

    def _fallback_load_dotenv(dotenv_path=None):
        for key, value in _fallback_dotenv_values(dotenv_path).items():
            os.environ.setdefault(key, value)
        return True

    sys.modules["dotenv"] = types.SimpleNamespace(
        load_dotenv=_fallback_load_dotenv,
        dotenv_values=_fallback_dotenv_values
    )

from src.config import Config, get_config


class DynamicStockListConfigTestCase(unittest.TestCase):
    """Validate dynamic stock list behavior in Config.refresh_stock_list."""

    def setUp(self) -> None:
        fd, env_path = tempfile.mkstemp(prefix="cfg_dynamic_", suffix=".env", dir=os.getcwd())
        os.close(fd)
        self._env_path = env_path
        self._tracked_env_keys = [
            "ENV_FILE",
            "STOCK_LIST",
            "STOCK_LIST_SOURCE",
            "WENCAI_STOCK_QUERY",
            "WENCAI_COOKIE",
        ]
        self._env_backup = {key: os.environ.get(key) for key in self._tracked_env_keys}
        for key in self._tracked_env_keys:
            os.environ.pop(key, None)

        Config.reset_instance()

    def tearDown(self) -> None:
        Config.reset_instance()
        sys.modules.pop("pywencai", None)

        for key, value in self._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        if os.path.isfile(self._env_path):
            os.remove(self._env_path)

    def _write_env(self, content: str) -> None:
        with open(self._env_path, "w", encoding="utf-8") as env_file:
            env_file.write(content)
        os.environ["ENV_FILE"] = self._env_path

    def test_refresh_stock_list_uses_wencai_when_enabled(self) -> None:
        self._write_env(
            "\n".join(
                [
                    "STOCK_LIST_SOURCE=wencai",
                    "WENCAI_COOKIE=test_cookie",
                    "WENCAI_STOCK_QUERY=昨日连板天梯，非st，主板，今日竞价涨幅大于2，昨日个股热度排名",
                    "STOCK_LIST=300750,002594",
                ]
            )
        )

        calls = []
        result_df = pd.DataFrame(
            {
                "股票简称": ["平安银行", "贵州茅台", "平安银行"],
                "股票代码": ["000001.SZ", "600519.SH", "000001.SZ"],
            }
        )

        def fake_get(query: str, cookie: str = ""):
            calls.append((query, cookie))
            return result_df

        sys.modules["pywencai"] = types.SimpleNamespace(get=fake_get)

        config = get_config()
        config.refresh_stock_list()

        self.assertEqual(config.stock_list, ["000001", "600519"])
        self.assertEqual(config.stock_list_source, "wencai")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], "test_cookie")

    def test_refresh_stock_list_falls_back_to_env_when_wencai_fails(self) -> None:
        self._write_env(
            "\n".join(
                [
                    "STOCK_LIST_SOURCE=wencai",
                    "WENCAI_COOKIE=test_cookie",
                    "WENCAI_STOCK_QUERY=昨日连板天梯，非st，主板，今日竞价涨幅大于2，昨日个股热度排名",
                    "STOCK_LIST=300750,002594",
                ]
            )
        )

        def fake_get(query: str, cookie: str = ""):
            raise RuntimeError("mocked wencai failure")

        sys.modules["pywencai"] = types.SimpleNamespace(get=fake_get)

        config = get_config()
        config.refresh_stock_list()

        self.assertEqual(config.stock_list, ["300750", "002594"])


if __name__ == "__main__":
    unittest.main()
