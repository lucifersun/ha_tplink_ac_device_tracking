"""TP-Link Auranet 无线 AC 控制器（TL-AC100 等）SLP API 客户端。

认证与数据接口均为 TP-Link SLP 私有协议：
- 登录：POST /，密码经 XOR 查表加密，返回 stok
- 数据：POST /stok=<stok>/ds，body 为 {"method":"get", <module>:{table,filter,para}}
"""

from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import unquote

import aiohttp

from .const import (
    AP_LINK_STATUS_ONLINE,
    LOGIN_TIMEOUT,
    MODULE_AP_CLIENT,
    MODULE_AP_STATUS,
    PAGE_END,
    PAGE_START,
    REQUEST_TIMEOUT,
    SECURITY_KEY,
    SECURITY_TABLE,
    TABLE_AP_LIST,
    TABLE_CLIENT_LIST,
)

LOGGER = logging.getLogger(__name__)


class TpLinkAcError(Exception):
    """集成通用异常。"""


class TpLinkAcConnectionError(TpLinkAcError):
    """网络连接失败。"""


class TpLinkAcAuthError(TpLinkAcError):
    """登录失败（凭证错误或控制器不可达）。"""


class TpLinkAcApiError(TpLinkAcError):
    """API 返回错误。"""


def encrypt_password(password: str) -> str:
    """TP-Link 设备的密码加密（XOR 查表）。

    与设备前端 $.su.securityEncode(password, KEY, TABLE) 等价。
    """
    a = password
    b = SECURITY_KEY
    table = SECURITY_TABLE
    result = ""
    g, m, k = len(a), len(b), len(table)
    for i in range(max(g, m)):
        left = 187
        right = 187
        if i >= g:
            right = ord(b[i])
        elif i >= m:
            left = ord(a[i])
        else:
            left = ord(a[i])
            right = ord(b[i])
        result += table[(left ^ right) % k]
    return result


def _decode_strings(obj):
    """递归对字符串值做 URL 解码（设备响应对字符串做了 encodeURIComponent）。"""
    if isinstance(obj, str):
        return unquote(obj)
    if isinstance(obj, list):
        return [_decode_strings(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _decode_strings(v) for k, v in obj.items()}
    return obj


class TpLinkAcClient:
    """TP-Link AC 控制器 SLP API 客户端（异步）。"""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self.host = host.rstrip("/").strip()
        self._username = username
        self._password = password
        self._session = session
        self._stok: str | None = None

    # ------------------------------------------------------------------ #
    # 登录
    # ------------------------------------------------------------------ #
    async def async_login(self) -> None:
        """登录并获取 stok。"""
        body = {
            "method": "do",
            "login": {
                "username": self._username,
                "password": encrypt_password(self._password),
            },
        }
        resp = await self._post_raw(self.host + "/", body)
        if resp.get("error_code") != 0:
            raise TpLinkAcAuthError(f"登录失败: {resp}")
        self._stok = resp.get("stok")
        if not self._stok:
            raise TpLinkAcAuthError(f"登录响应缺少 stok: {resp}")
        LOGGER.info("TP-Link AC 登录成功")

    # ------------------------------------------------------------------ #
    # 数据获取
    # ------------------------------------------------------------------ #
    async def async_get_aps(self) -> list[dict]:
        """获取 AP 列表。"""
        return await self._query_table(
            MODULE_AP_STATUS,
            TABLE_AP_LIST,
            [{"group_id": "-1", "ap_status": "0"}],
        )

    async def async_get_clients(self) -> list[dict]:
        """获取无线客户端列表（含 ap_name 归属）。"""
        return await self._query_table(
            MODULE_AP_CLIENT,
            TABLE_CLIENT_LIST,
            [{"group_id": "-1"}],
        )

    async def _query_table(
        self,
        module: str,
        table: str,
        filters: list[dict],
    ) -> list[dict]:
        body = {
            "method": "get",
            module: {
                "table": table,
                "filter": filters,
                "para": {"start": PAGE_START, "end": PAGE_END},
            },
        }
        resp = await self._post_ds(body)
        if resp.get("error_code") != 0:
            raise TpLinkAcApiError(
                f"{module}/{table} 请求失败: error_code={resp.get('error_code')}"
            )
        raw_list = resp.get(module, {}).get(table, []) or []
        # 展平 {"<table>_<i>": {...}} -> {...}
        result: list[dict] = []
        for item in raw_list:
            if isinstance(item, dict):
                result.append(next(iter(item.values()), item))
            else:
                result.append(item)
        return result

    # ------------------------------------------------------------------ #
    # 底层请求
    # ------------------------------------------------------------------ #
    async def _post_ds(self, body: dict) -> dict:
        """向 /stok=<stok>/ds 发送数据请求；stok 失效时自动重连一次。"""
        if not self._stok:
            raise TpLinkAcError("未登录，缺少 stok")
        try:
            return await self._post_raw(f"{self.host}/stok={self._stok}/ds", body)
        except TpLinkAcAuthError:
            LOGGER.warning("stok 已失效，尝试重新登录")
            await self.async_login()
            return await self._post_raw(f"{self.host}/stok={self._stok}/ds", body)

    async def _post_raw(self, url: str, body: dict) -> dict:
        """发送 JSON POST 并解析、解码响应。"""
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        try:
            async with asyncio.timeout(timeout.total):
                async with self._session.post(
                    url,
                    data=json.dumps(body, ensure_ascii=False),
                    headers=headers,
                    ssl=False,
                ) as resp:
                    if resp.status == 401:
                        raise TpLinkAcAuthError(f"认证失效 HTTP 401 @ {url}")
                    if resp.status != 200:
                        text = await resp.text()
                        raise TpLinkAcConnectionError(
                            f"HTTP {resp.status} @ {url}: {text[:200]}"
                        )
                    data = await resp.json(content_type=None)
        except asyncio.TimeoutError as err:
            raise TpLinkAcConnectionError(f"请求超时 @ {url}") from err
        except aiohttp.ClientError as err:
            raise TpLinkAcConnectionError(f"连接失败 @ {url}: {err}") from err

        if isinstance(data, dict) and data.get("error_code") == -40401:
            raise TpLinkAcAuthError("stok 已失效 (error_code -40401)")

        return _decode_strings(data)
