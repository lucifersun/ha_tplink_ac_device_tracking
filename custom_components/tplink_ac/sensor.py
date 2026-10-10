"""传感器：在线终端/AP 计数、AP→终端归属映射。"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TpLinkAcCoordinator

LOGGER = logging.getLogger(__name__)


def _client_display_name(client: dict) -> str:
    return client.get("name") or client.get("mac") or "?"


def _controller_device_info(entry_id: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="TP-Link AC 控制器",
        manufacturer="TP-Link",
        model="AC Controller",
    )


def _ap_device_info(ap: dict) -> DeviceInfo:
    mac = ap.get("mac", "")
    return DeviceInfo(
        identifiers={(DOMAIN, f"ap_{mac}")},
        name=ap.get("entry_name") or mac,
        manufacturer="TP-Link",
        model=ap.get("model_name"),
    )


class TpLinkAcBaseSensor(CoordinatorEntity, SensorEntity):
    """集成通用传感器基类。

    继承 CoordinatorEntity，自动订阅 coordinator；数据刷新时
    _handle_coordinator_update 会被调用，从而刷新 state 与属性。
    """

    _attr_should_poll = False

    def __init__(self, coordinator: TpLinkAcCoordinator) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator

    @property
    def available(self) -> bool:
        """数据拉取失败时标记为不可用。"""
        return bool(self.coordinator.last_update_success)

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


# ---------------------------------------------------------------------- #
# 控制器级传感器
# ---------------------------------------------------------------------- #
class TpLinkAcTotalClientsSensor(TpLinkAcBaseSensor):
    """在线终端总数。"""

    _attr_icon = "mdi:account-multiple"

    def __init__(self, coordinator: TpLinkAcCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_total_clients"
        self._attr_name = "在线终端总数"
        self._attr_device_info = _controller_device_info(entry_id)

    @property
    def native_value(self) -> int:
        return len(self._coordinator.clients)

    @property
    def extra_state_attributes(self) -> dict:
        breakdown = {
            ap.get("entry_name") or ap.get("mac"): len(
                self._coordinator.clients_of_ap(ap.get("mac", ""))
            )
            for ap in self._coordinator.aps.values()
        }
        return {"per_ap": breakdown}


class TpLinkAcTotalApsSensor(TpLinkAcBaseSensor):
    """在线 AP 总数。"""

    _attr_icon = "mdi:wifi"

    def __init__(self, coordinator: TpLinkAcCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_total_aps"
        self._attr_name = "在线 AP 数"
        self._attr_device_info = _controller_device_info(entry_id)

    @property
    def native_value(self) -> int:
        return sum(1 for mac in self._coordinator.aps if self._coordinator.ap_online(mac))


class TpLinkAcApClientMapSensor(TpLinkAcBaseSensor):
    """AP → 终端归属映射（核心展示数据源）。"""

    _attr_icon = "mdi:access-point-network"

    def __init__(self, coordinator: TpLinkAcCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_ap_client_map"
        self._attr_name = "AP 终端映射"
        self._attr_device_info = _controller_device_info(entry_id)

    @property
    def native_value(self) -> int:
        return len(self._coordinator.clients)

    @property
    def extra_state_attributes(self) -> dict:
        ap_map: dict[str, list[str]] = {}
        for ap_mac, ap in self._coordinator.aps.items():
            ap_name = ap.get("entry_name") or ap_mac
            ap_map[ap_name] = [
                _client_display_name(c)
                for c in self._coordinator.clients_of_ap(ap_mac)
            ]
        return {"ap_map": ap_map}


# ---------------------------------------------------------------------- #
# AP 级传感器
# ---------------------------------------------------------------------- #
class TpLinkAcApClientCountSensor(TpLinkAcBaseSensor):
    """某 AP 下的在线终端数。"""

    _attr_icon = "mdi:account-multiple"

    def __init__(self, coordinator: TpLinkAcCoordinator, ap_mac: str) -> None:
        super().__init__(coordinator)
        self._ap_mac = ap_mac
        ap = coordinator.aps.get(ap_mac, {})
        self._attr_unique_id = f"{DOMAIN}_ap_{ap_mac}_client_count"
        self._attr_name = "终端数"
        self._attr_device_info = _ap_device_info(ap)

    @property
    def native_value(self) -> int:
        return len(self._coordinator.clients_of_ap(self._ap_mac))


class TpLinkAcApClientListSensor(TpLinkAcBaseSensor):
    """某 AP 下的在线终端列表（state 直接显示终端名称）。"""

    _attr_icon = "mdi:format-list-bulleted"

    def __init__(self, coordinator: TpLinkAcCoordinator, ap_mac: str) -> None:
        super().__init__(coordinator)
        self._ap_mac = ap_mac
        ap = coordinator.aps.get(ap_mac, {})
        self._attr_unique_id = f"{DOMAIN}_ap_{ap_mac}_client_list"
        self._attr_name = "终端列表"
        self._attr_device_info = _ap_device_info(ap)

    @property
    def native_value(self) -> str:
        try:
            clients = self._coordinator.clients_of_ap(self._ap_mac)
            names = [_client_display_name(c) for c in clients]
            if not names:
                return "无在线终端"
            text = "、".join(names)
            if len(text) > 200:
                text = text[:200] + f"… 等 {len(names)} 台"
            return text
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("生成终端列表失败 (AP=%s): %s", self._ap_mac, err)
            return "获取失败"

    @property
    def extra_state_attributes(self) -> dict:
        clients = self._coordinator.clients_of_ap(self._ap_mac)
        return {
            "count": len(clients),
            "clients": [
                {
                    "name": _client_display_name(c),
                    "mac": c.get("mac"),
                    "ip": c.get("ip"),
                    "ssid": c.get("ssid"),
                    "band": (c.get("rf_entry") or [{}])[0].get("freq_name"),
                    "rssi": (c.get("rf_entry") or [{}])[0].get("rssi"),
                }
                for c in clients
            ],
        }


class TpLinkAcClientApSensor(CoordinatorEntity, SensorEntity):
    """终端当前所在 AP（枚举传感器）。

    state 为终端当前连接的 AP 名称，离线时为「离线」；`options` 属性为
    「离线」+ 所有 AP 名列表。HA 前端自动化编辑器会对 device_class=enum 且带
    options 属性的 sensor 的 state 字段提供下拉选项，从而在图形界面直接选择。
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_should_poll = False

    # 离线时的 state 值
    STATE_OFFLINE = "离线"

    def __init__(self, coordinator: TpLinkAcCoordinator, mac: str) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._mac = mac
        self._attr_unique_id = f"{DOMAIN}_client_{mac}_ap"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"client_{mac}")},
            name=mac,
            manufacturer="TP-Link",
        )

    @property
    def name(self) -> str:
        data = self._coordinator.client_data(self._mac) or {}
        client_name = data.get("name") or data.get("mac") or self._mac
        return f"{client_name} 所在 AP"

    @property
    def available(self) -> bool:
        return bool(self.coordinator.last_update_success)

    @property
    def native_value(self) -> str:
        if self._mac in self._coordinator.clients:
            ap_name = self._coordinator.clients[self._mac].get("ap_name")
            return ap_name or "未知"
        return self.STATE_OFFLINE

    @property
    def extra_state_attributes(self) -> dict:
        ap_names = [
            ap.get("entry_name")
            for ap in self._coordinator.aps.values()
            if ap.get("entry_name")
        ]
        return {"options": [self.STATE_OFFLINE, *ap_names]}

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """添加控制器级传感器，并动态添加 AP 级传感器与终端所在 AP 传感器。"""
    coordinator: TpLinkAcCoordinator = hass.data[DOMAIN][entry.entry_id]
    entry_id = entry.entry_id

    async_add_entities(
        [
            TpLinkAcTotalClientsSensor(coordinator, entry_id),
            TpLinkAcTotalApsSensor(coordinator, entry_id),
            TpLinkAcApClientMapSensor(coordinator, entry_id),
        ]
    )

    added_aps: set[str] = set()

    @callback
    def _process_aps() -> None:
        new_entities = []
        for ap_mac in coordinator.aps:
            if ap_mac not in added_aps:
                added_aps.add(ap_mac)
                new_entities.append(TpLinkAcApClientCountSensor(coordinator, ap_mac))
                new_entities.append(TpLinkAcApClientListSensor(coordinator, ap_mac))
        if new_entities:
            async_add_entities(new_entities)

    _process_aps()
    entry.async_on_unload(coordinator.async_add_listener(_process_aps))

    added_clients: set[str] = set()

    @callback
    def _process_clients() -> None:
        new_entities = []
        for mac in coordinator.seen_clients:
            if mac not in added_clients:
                added_clients.add(mac)
                new_entities.append(TpLinkAcClientApSensor(coordinator, mac))
        if new_entities:
            async_add_entities(new_entities)

    _process_clients()
    entry.async_on_unload(coordinator.async_add_listener(_process_clients))
