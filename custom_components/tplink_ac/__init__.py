"""tplink_ac 集成入口。

创建 TP-Link AC 客户端并登录、创建数据轮询协调器、转发到各平台。
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TpLinkAcClient
from .const import (
    CONF_MAC_FILTER,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SSID_FILTER,
    CONF_URL,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import TpLinkAcCoordinator

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """配置入口加载。"""
    session = async_get_clientsession(hass)
    client = TpLinkAcClient(
        entry.data[CONF_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session,
    )

    try:
        await client.async_login()
    except Exception as err:  # noqa: BLE001
        LOGGER.error("TP-Link AC 登录失败，集成无法加载: %s", err)
        return False

    options = entry.options
    coordinator = TpLinkAcCoordinator(
        hass,
        client,
        scan_interval=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        ssid_filter=options.get(CONF_SSID_FILTER, ""),
        mac_filter=options.get(CONF_MAC_FILTER, ""),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """选项变化时更新过滤规则与轮询间隔。"""
    coordinator: TpLinkAcCoordinator = hass.data[DOMAIN][entry.entry_id]
    options = entry.options

    coordinator.ssid_filter = options.get(CONF_SSID_FILTER, "")
    coordinator.mac_filter = options.get(CONF_MAC_FILTER, "")
    coordinator.update_interval = timedelta(
        seconds=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    await coordinator.async_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载配置入口。"""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
