"""配置流程：UI 输入管理地址 / 用户名 / 密码，以及过滤选项。"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    TpLinkAcApiError,
    TpLinkAcAuthError,
    TpLinkAcClient,
    TpLinkAcConnectionError,
)
from .const import (
    CONF_MAC_FILTER,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SSID_FILTER,
    CONF_URL,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

LOGGER = logging.getLogger(__name__)


def _build_connection_schema(user_input: dict | None = None) -> vol.Schema:
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_URL, default=user_input.get(CONF_URL, "http://192.168.18.253")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
            ),
            vol.Required(
                CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(
                CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
        }
    )


class TpLinkAcConfigFlow(ConfigFlow, domain=DOMAIN):
    """处理连接配置。"""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._test_connection(user_input)
            except TpLinkAcAuthError:
                errors["base"] = "invalid_auth"
            except TpLinkAcConnectionError:
                errors["base"] = "cannot_connect"
            except TpLinkAcApiError as err:
                LOGGER.warning("TP-Link AC 配置测试失败: %s", err)
                errors["base"] = "unknown"
            except Exception as err:  # noqa: BLE001
                LOGGER.exception("TP-Link AC 配置测试异常: %s", err)
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"TP-Link AC ({user_input.get(CONF_URL)})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_connection_schema(user_input),
            errors=errors,
        )

    async def _test_connection(self, user_input: dict) -> None:
        session = async_get_clientsession(self.hass)
        client = TpLinkAcClient(
            user_input[CONF_URL],
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            session,
        )
        await client.async_login()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TpLinkAcOptionsFlow:
        """创建选项流程。新版 HA 由框架注入 config_entry，不要再手动赋值。"""
        return TpLinkAcOptionsFlow()


class TpLinkAcOptionsFlow(OptionsFlow):
    """处理过滤与扫描间隔选项。

    注意：新版 Home Assistant 中 `config_entry` 是框架注入的只读 property，
    不能在 __init__ 里赋值（会触发 AttributeError: property has no setter）。
    """

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10,
                            max=3600,
                            step=5,
                            unit_of_measurement="seconds",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_SSID_FILTER,
                        default=options.get(CONF_SSID_FILTER, ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT, multiline=False
                        )
                    ),
                    vol.Optional(
                        CONF_MAC_FILTER,
                        default=options.get(CONF_MAC_FILTER, ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT, multiline=False
                        )
                    ),
                }
            ),
        )
