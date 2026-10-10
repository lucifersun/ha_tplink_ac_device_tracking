"""AP 在线状态 binary_sensor。"""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TpLinkAcCoordinator

LOGGER = logging.getLogger(__name__)


def _ap_device_info(ap: dict) -> DeviceInfo:
    mac = ap.get("mac", "")
    return DeviceInfo(
        identifiers={(DOMAIN, f"ap_{mac}")},
        name=ap.get("entry_name") or mac,
        manufacturer="TP-Link",
        model=ap.get("model_name"),
    )


class TpLinkAcApOnlineSensor(CoordinatorEntity, BinarySensorEntity):
    """表示某 AP 是否在线。"""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: TpLinkAcCoordinator, ap_mac: str) -> None:
        # CoordinatorEntity 自动订阅 coordinator，刷新时更新 state/属性。
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._ap_mac = ap_mac
        ap = coordinator.aps.get(ap_mac, {})
        self._attr_unique_id = f"{DOMAIN}_ap_{ap_mac}_online"
        self._attr_name = "在线状态"
        self._attr_device_info = _ap_device_info(ap)

    @property
    def available(self) -> bool:
        """数据拉取失败时标记为不可用。"""
        return bool(self.coordinator.last_update_success)

    @property
    def is_on(self) -> bool:
        return self._coordinator.ap_online(self._ap_mac)

    @property
    def extra_state_attributes(self) -> dict:
        ap = self._coordinator.aps.get(self._ap_mac)
        if not ap:
            return {}
        return {
            "mac": ap.get("mac"),
            "ip": ap.get("ip"),
            "model": ap.get("model_name"),
            "online_time_sec": ap.get("online_time"),
            "client_count": len(self._coordinator.clients_of_ap(self._ap_mac)),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """动态添加 AP 在线状态实体。"""
    coordinator: TpLinkAcCoordinator = hass.data[DOMAIN][entry.entry_id]
    added: set[str] = set()

    @callback
    def _process() -> None:
        new_entities = []
        for ap_mac in coordinator.aps:
            if ap_mac not in added:
                added.add(ap_mac)
                new_entities.append(TpLinkAcApOnlineSensor(coordinator, ap_mac))
        if new_entities:
            async_add_entities(new_entities)

    _process()
    entry.async_on_unload(coordinator.async_add_listener(_process))
