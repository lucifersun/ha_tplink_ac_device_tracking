"""数据轮询协调器：拉取 AP 与终端，构建 AP→终端归属映射。"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TpLinkAcClient
from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


def _normalize_mac(mac: str | None) -> str:
    """统一 MAC 格式为大写、去掉分隔符，便于前缀匹配。"""
    if not mac:
        return ""
    return mac.upper().replace(":", "").replace("-", "").replace(".", "")


class TpLinkAcCoordinator(DataUpdateCoordinator):
    """定时从 TP-Link AC 控制器拉取 AP 与终端数据。"""

    def __init__(
        self,
        hass: HomeAssistant,
        client: TpLinkAcClient,
        scan_interval: int,
        ssid_filter: str = "",
        mac_filter: str = "",
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.ssid_filter = ssid_filter
        self.mac_filter = mac_filter

        # 历史累积：见过的客户端 MAC + 最近一次数据缓存（用于离线后保留实体）
        self._seen_clients: set[str] = set()
        self._client_cache: dict[str, dict] = {}

    # ------------------------------------------------------------------ #
    # 数据获取
    # ------------------------------------------------------------------ #
    async def _async_update_data(self) -> dict:
        try:
            aps_raw = await self.client.async_get_aps()
            clients_raw = await self.client.async_get_clients()
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"TP-Link AC 数据拉取失败: {err}") from err

        aps: dict[str, dict] = {}
        for ap in aps_raw:
            mac = ap.get("mac")
            if mac:
                aps[mac] = ap

        clients: dict[str, dict] = {}
        for c in clients_raw:
            mac = c.get("mac")
            if not mac:
                continue
            if not self._client_allowed(c):
                continue
            clients[mac] = c

        # AP 名称 -> AP MAC 反查
        ap_name_to_mac = {
            ap.get("entry_name"): mac for mac, ap in aps.items() if ap.get("entry_name")
        }

        # AP(MAC) → 客户端 MAC 列表
        ap_clients: dict[str, list[str]] = {}
        for mac, c in clients.items():
            ap_mac = ap_name_to_mac.get(c.get("ap_name"))
            if ap_mac:
                ap_clients.setdefault(ap_mac, []).append(mac)

        # 累积历史，缓存最近数据
        self._seen_clients.update(clients.keys())
        self._client_cache.update(clients)

        return {
            "aps": aps,
            "clients": clients,
            "ap_clients": ap_clients,
        }

    # ------------------------------------------------------------------ #
    # 过滤逻辑（SSID 白名单 + MAC 前缀白名单）
    # ------------------------------------------------------------------ #
    def _client_allowed(self, client: dict) -> bool:
        if self.ssid_filter:
            allowed_ssids = {
                s.strip() for s in self.ssid_filter.split(",") if s.strip()
            }
            if client.get("ssid") not in allowed_ssids:
                return False

        if self.mac_filter:
            prefixes = [
                _normalize_mac(m) for m in self.mac_filter.split(",") if m.strip()
            ]
            client_mac = _normalize_mac(client.get("mac"))
            if not any(client_mac.startswith(p) for p in prefixes if p):
                return False

        return True

    # ------------------------------------------------------------------ #
    # 便捷访问
    # ------------------------------------------------------------------ #
    @property
    def aps(self) -> dict[str, dict]:
        return (self.data or {}).get("aps", {})

    @property
    def clients(self) -> dict[str, dict]:
        return (self.data or {}).get("clients", {})

    @property
    def ap_clients(self) -> dict[str, list[str]]:
        return (self.data or {}).get("ap_clients", {})

    @property
    def seen_clients(self) -> set[str]:
        return self._seen_clients

    @property
    def client_cache(self) -> dict[str, dict]:
        return self._client_cache

    def client_data(self, mac: str) -> dict | None:
        return self.clients.get(mac) or self._client_cache.get(mac)

    def clients_of_ap(self, ap_mac: str) -> list[dict]:
        macs = self.ap_clients.get(ap_mac, [])
        return [self.clients[m] for m in macs if m in self.clients]

    def ap_online(self, ap_mac: str) -> bool:
        ap = self.aps.get(ap_mac)
        return bool(ap and ap.get("link_status") == "1")
