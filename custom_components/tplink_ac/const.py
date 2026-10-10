"""常量定义 for tplink_ac 集成（TP-Link Auranet 无线 AC 控制器，如 TL-AC100）。"""

from __future__ import annotations

DOMAIN = "tplink_ac"

# 配置键
CONF_URL = "url"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

# 过滤选项（options flow）
CONF_SSID_FILTER = "ssid_filter"      # 逗号分隔的 SSID 白名单，空 = 全部
CONF_MAC_FILTER = "mac_filter"        # 逗号分隔的 MAC 前缀白名单，空 = 全部

# 默认值
DEFAULT_SCAN_INTERVAL = 60            # 秒

# 平台
PLATFORMS = ["sensor", "binary_sensor"]

# 请求超时
LOGIN_TIMEOUT = 15
REQUEST_TIMEOUT = 15

# ------------------------------------------------------------------ #
# TP-Link SLP 接口：密码加密（XOR 查表）
# 全系 TP-Link 设备通用，密钥固定。
# ------------------------------------------------------------------ #
SECURITY_KEY = "RDpbLfCPsJZ7fiv"
SECURITY_TABLE = (
    "yLwVl0zKqws7LgKPRQ84Mdt708T1qQ3Ha7xv3H7NyU84p21BriUWBU43odz3iP4rBL3cD"
    "02KZciXTysVXiV8ngg6vL48rPJyAUw0HurW20xqxv9aYb4M9wK1Ae0wlro510qXeU07kV"
    "57fQMc8L6aLgMLwygtc0F10a0Dg70TOoouyFhdysuRMO51yY5Z"
)

# ------------------------------------------------------------------ #
# SLP 数据接口：模块 + 表
# ------------------------------------------------------------------ #
MODULE_AP_STATUS = "apmng_status"
MODULE_AP_CLIENT = "apmng_client"

TABLE_AP_LIST = "ap_list"
TABLE_CLIENT_LIST = "client_list"

# 列表分页（家庭/小型办公场景足够大）
PAGE_START = 0
PAGE_END = 500

# AP 在线状态（link_status 字符串）
AP_LINK_STATUS_ONLINE = "1"
