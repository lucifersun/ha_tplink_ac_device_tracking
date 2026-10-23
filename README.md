# TP-Link AC Controller (tplink_ac)

Home Assistant 自定义集成，用于连接 **TP-Link 无线 AC 控制器**（Auranet 系列，如 TL-AC100 / TL-AC200 / TL-AC300 等），获取无线 AP 设备与终端信息，并展示**「某台 AP 下连接了哪些终端」**，便于根据手机等终端所处的 AP 判定状态、规划自动化。

> 注意：本集成面向的是**局域网 AC 控制器**（老式 `login.htm` 管理界面），**不是** Omada SDN 控制器（Omada 请用其他集成）。

---

## 功能

- 通过 AC 控制器的管理地址 + 用户名 + 密码登录（凭据在 UI 中配置，不硬编码）
- 获取所有 **AP**（名称、MAC、IP、型号、在线状态、各频段客户端数/信道）
- 获取所有**无线终端**（名称、MAC、IP、SSID、所在 AP、频段、RSSI、协商速率、VLAN）
- 每个终端生成一个 **「所在 AP」枚举传感器**，state 即所在 AP 名（离线时为「离线」），供自动化图形界面下拉选择
- 提供「AP → 终端映射」传感器，直接在 Lovelace 展示谁在哪台 AP 下
- 支持按 **SSID / MAC 前缀**过滤，只追踪你关心的终端（如只追踪手机连的 5G SSID）

---

## 安装

将 `custom_components/tplink_ac` 整个目录复制到 Home Assistant 的 `config/custom_components/` 下：

```
config/
└── custom_components/
    └── tplink_ac/            ← 目录名必须与 domain 完全一致（下划线！）
        ├── __init__.py
        ├── api.py
        ├── binary_sensor.py
        ├── brand/            ← HA 2026.3+：集成图标必须放这里
        │   ├── icon.png      # 256x256
        │   └── icon@2x.png   # 512x512
        ├── config_flow.py
        ├── const.py
        ├── coordinator.py
        ├── manifest.json
        ├── sensor.py
        └── strings.json
```

> **目录名**：必须是 `tplink_ac`（下划线，与 manifest 的 domain 一致）。你 HAOS 上现在是 `tplink-ac`（横杠），务必重命名，否则图标等资源无法定位，未来 HA 版本还可能拒绝加载。
>
> **集成图标（HA 2026.3+ 机制）**：必须放在集成目录的 `brand/` 子目录（`brand/icon.png` 256x256 正方形 + `brand/icon@2x.png` 512x512），由 HA 本地 API `/api/brands/integration/tplink_ac/icon.png` 提供并自动优先于品牌 CDN。放在集成**根目录**的 icon.png 是无效的（此前我的指引有误，HA 任何版本都不支持根目录图标）。

然后**重启 Home Assistant**。

---

## 配置

1. 进入 **设置 → 设备与服务 → 添加集成**，搜索 **TP-Link AC Controller**
2. 填写：
   - **管理地址**：如 `http://192.168.18.253`（就是你在浏览器登录 AC 的那个地址）
   - **用户名** / **密码**
3. 提交，集成会先验证连接与凭据，成功后自动创建实体

### 可选选项（集成右上角「配置」）

| 选项 | 说明 |
|---|---|
| 轮询间隔 | 默认 60 秒（可设 10~3600 秒） |
| SSID 白名单 | 只追踪这些 SSID 的终端，逗号分隔，留空=全部 |
| MAC 前缀白名单 | 只追踪这些 MAC 前缀的终端，逗号分隔，留空=全部 |

> **修改轮询间隔**：设置 → 设备与服务 → TP-Link AC Controller → 集成条目右侧的**齿轮图标 ⚙️**（这就是「配置」入口）。之前点齿轮报错是集成的 bug，已修复；修好后即可在此改轮询间隔/过滤，保存立即生效，无需重启。

> **实用技巧**：如果你的 IoT 设备（开关、空调等）都连在某个专用 2.4G SSID 上，手机连在 5G SSID 上，只需在 SSID 白名单里填手机那个 SSID（如 `Sun Home's Wireless 5G`），「所在 AP」传感器就只会出现手机/电视等，不会被几十个 IoT 设备刷屏。

---

## 实体

### 控制器级传感器（归属「TP-Link AC 控制器」设备）

| 实体 | 说明 |
|---|---|
| `sensor.tplink_ac_在线终端总数` | 在线终端数，属性 `per_ap` 是各 AP 的终端数 |
| `sensor.tplink_ac_在线ap数` | 在线 AP 数 |
| `sensor.tplink_ac_ap终端映射` | 属性 `ap_map` = `{AP名: [终端名列表]}`，核心展示数据 |

### 每台 AP（归属对应 AP 设备）

| 实体 | 说明 |
|---|---|
| `binary_sensor.*_在线状态` | AP 是否在线，属性含 IP、型号、终端数 |
| `sensor.*_终端数` | 该 AP 下的在线终端数 |

### 每个终端

| 实体 | 说明 |
|---|---|
| `sensor.<终端名>_所在ap` | **枚举传感器**：state 为终端当前所在 AP 名（离线时为「离线」），`options` 属性为「离线」+ 全部 AP 名列表，供自动化图形界面下拉选择 |

> 每个终端一个「所在 AP」枚举传感器，state 既表达「在哪个 AP」也表达「在线/离线」（离线时 state 为「离线」）。

---

## Lovelace 展示示例

> 传感器 state 是单行文本，终端多时在实体卡片里会挤成一团——**清单展示请用下面的 markdown 卡片**（逐行、按 AP 分组），仓库根目录的 `lovelace_ap_dashboard.yaml` 有完整配置。

```yaml
type: markdown
title: 📶 无线终端分布
content: >
  {% set mapping = state_attr('sensor.tplink_ac_ap终端映射', 'ap_map') or {} %}
  {% for ap, clients in mapping.items() %}
  ### 📡 {{ ap }} · {{ clients | length }} 台

  {% for c in clients %}
  - {{ c }}
  {% endfor %}

  {% endfor %}
```

进阶：装了 HACS 的 `auto-entities` 后，可按 `ap_name` 属性自动列出某 AP 下的终端实体（带在线/离线圆点），配置见 `lovelace_ap_dashboard.yaml` 卡片 2。

---

## 自动化示例

> **推荐写法**：判断终端在哪个 AP 时，用「所在 AP」枚举传感器 `sensor.<终端>_所在ap`。在图形化编辑器里添加「状态」条件并选中它后，状态字段会**自动以下拉框列出所有 AP 名**，点选即可，无需手动输入、也不会拼错。等价 YAML：
>
> ```yaml
> condition: state
> entity_id: sensor.jia_shi_qi_所在ap
> state: 卧室-新
> ```

### 示例 1：设备进入某 AP

```yaml
automation:
  - alias: "洗碗机连上客厅 AP"
    trigger:
      - platform: state
        entity_id: sensor.xi_wan_ji_所在ap
        to: "客厅-新"
    action:
      - service: notify.notify
        data:
          message: "洗碗机已连接到客厅 AP"
```

### 示例 2：设备离开某 AP

```yaml
automation:
  - alias: "洗碗机离开客厅 AP"
    trigger:
      - platform: state
        entity_id: sensor.xi_wan_ji_所在ap
        from: "客厅-新"
    action:
      - service: notify.notify
        data:
          message: "洗碗机已离开客厅 AP"
```

### 示例 3：设备离线

```yaml
automation:
  - alias: "洗碗机离线"
    trigger:
      - platform: state
        entity_id: sensor.xi_wan_ji_所在ap
        to: "离线"
    action:
      - service: notify.notify
        data:
          message: "洗碗机已离线"
```

> 把 AP 名映射到房间（卧室-新 → 卧室、客厅-新 → 客厅），即可实现「人在哪个房间」级别的自动化。

---

## 技术说明

- 协议：TP-Link SLP 私有接口（密码 XOR 查表加密，登录取 `stok`，数据走 `/stok=xxx/ds`）
- 数据接口：
  - AP 列表：`apmng_status` / `ap_list`
  - 客户端列表：`apmng_client` / `client_list`（含 `ap_name` 归属字段）
- 无第三方依赖，纯 `aiohttp` 实现；本地轮询（`local_polling`），凭据经 HA config_flow 加密存储

---

## 排错

- **登录失败 / 无法连接**：确认地址、用户名、密码正确；确认 HA 能 ping 通控制器 IP
- **实体不出现**：查看 HA 日志 `homeassistant.log`；确认控制器里确有在线 AP/终端
- **终端太多**：用「SSID 白名单」只追踪手机连的 SSID
