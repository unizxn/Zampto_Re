---
AIGC: {"Label":"1","ContentProducer":"001191110108MA01KP2T5U00000","ProduceID":"cbe1d54e8303fbe74f7da5dbce29c8eb","ReservedCode1":"","ContentPropagator":"001191110108MA01KP2T5U00000","PropagateID":"cbe1d54e8303fbe74f7da5dbce29c8eb","ReservedCode2":""}
---

# Zampto 自动续期 & 状态监控（Xray 代理版）

基于 CloakBrowser 的 Zampto 免费 Minecraft 服务器自动化工具，每天北京时间 08:00 运行。

> 本项目基于 [zampto_auto](https://github.com/timivest/zampto_auto) 改造，将 Hysteria2 代理替换为 **Xray 代理**，支持 VMess、VLESS、Trojan、Shadowsocks、SOCKS5 等多种代理协议。

## 功能

- ✅ 自动登录 Zampto（Logto 两步登录）
- ✅ 检测服务器状态（Running / Stopped）
- ✅ 服务器离线自动点 Start 启动
- ✅ 自动点击续期，等待 Cloudflare Turnstile 验证自动通过
- ✅ WxPusher 推送服务器状态 + 到期时间
- ✅ **Xray 代理**（支持 SOCKS5 / VMess / VLESS / Trojan / Shadowsocks 等多种协议）

## 部署到 GitHub Actions

### 1. Fork 或新建仓库，上传本项目文件

### 2. 配置 Secrets

进入仓库 **Settings → Secrets and variables → Actions → New repository secret**，添加：

| Secret 名称 | 说明 |
|---|---|
| `ZAMPTO_USERNAME` | Zampto 用户名（如 `ssdXXXXXXXXXX`）|
| `ZAMPTO_PASSWORD` | Zampto 密码 |
| `ZAMPTO_SERVER_ID` | 服务器 ID（URL 中的数字，如 `XXXX`）|
| `WXPUSHER_TOKEN` | WxPusher App Token |
| `WXPUSHER_UID` | WxPusher 用户 UID |
| `V2RAY_CONFIG` | **Xray 完整 JSON 配置**（见下方说明）|

### 3. 获取 Server ID

登录 Zampto Dashboard，点进服务器详情，URL 末尾的数字即为 Server ID：
```
https://dash.zampto.net/server?id=XXXX
```

### 4. 配置 Xray 代理

`V2RAY_CONFIG` Secret 填入完整的 Xray JSON 配置字符串。配置中**必须包含一个 SOCKS5 inbound 监听在 `127.0.0.1:10808`**，outbound 可以是 Xray 支持的任意协议。

#### SOCKS5 代理示例（最简配置）

如果你有一个 SOCKS5 代理服务器（如 `your-socks-server:1080`），配置如下：

```json
{
  "log": { "loglevel": "warning" },
  "inbounds": [
    {
      "tag": "socks",
      "port": 10808,
      "listen": "127.0.0.1",
      "protocol": "socks",
      "settings": {
        "udp": true
      }
    }
  ],
  "outbounds": [
    {
      "tag": "proxy",
      "protocol": "socks",
      "settings": {
        "servers": [
          {
            "address": "your-socks-server",
            "port": 1080
          }
        ]
      }
    },
    {
      "tag": "direct",
      "protocol": "freedom"
    }
  ],
  "routing": {
    "rules": [
      {
        "type": "field",
        "inboundTag": ["socks"],
        "outboundTag": "proxy"
      }
    ]
  }
}
```

#### VMess 代理示例

```json
{
  "log": { "loglevel": "warning" },
  "inbounds": [
    {
      "tag": "socks",
      "port": 10808,
      "listen": "127.0.0.1",
      "protocol": "socks",
      "settings": { "udp": true }
    }
  ],
  "outbounds": [
    {
      "tag": "proxy",
      "protocol": "vmess",
      "settings": {
        "vnext": [
          {
            "address": "your-server.com",
            "port": 443,
            "users": [
              {
                "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                "alterId": 0,
                "security": "auto"
              }
            ]
          }
        ]
      },
      "streamSettings": {
        "network": "ws",
        "security": "tls",
        "wsSettings": { "path": "/vmess-path" }
      }
    },
    { "tag": "direct", "protocol": "freedom" }
  ],
  "routing": {
    "rules": [
      {
        "type": "field",
        "inboundTag": ["socks"],
        "outboundTag": "proxy"
      }
    ]
  }
}
```

#### VLESS + XTLS 示例

```json
{
  "log": { "loglevel": "warning" },
  "inbounds": [
    {
      "tag": "socks",
      "port": 10808,
      "listen": "127.0.0.1",
      "protocol": "socks",
      "settings": { "udp": true }
    }
  ],
  "outbounds": [
    {
      "tag": "proxy",
      "protocol": "vless",
      "settings": {
        "vnext": [
          {
            "address": "your-server.com",
            "port": 443,
            "users": [
              {
                "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                "encryption": "none",
                "flow": "xtls-rprx-vision"
              }
            ]
          }
        ]
      },
      "streamSettings": {
        "network": "tcp",
        "security": "tls",
        "tlsSettings": { "serverName": "your-server.com" }
      }
    },
    { "tag": "direct", "protocol": "freedom" }
  ],
  "routing": {
    "rules": [
      {
        "type": "field",
        "inboundTag": ["socks"],
        "outboundTag": "proxy"
      }
    ]
  }
}
```

#### Trojan 代理示例

```json
{
  "log": { "loglevel": "warning" },
  "inbounds": [
    {
      "tag": "socks",
      "port": 10808,
      "listen": "127.0.0.1",
      "protocol": "socks",
      "settings": { "udp": true }
    }
  ],
  "outbounds": [
    {
      "tag": "proxy",
      "protocol": "trojan",
      "settings": {
        "servers": [
          {
            "address": "your-server.com",
            "port": 443,
            "password": "your-trojan-password"
          }
        ]
      },
      "streamSettings": {
        "network": "tcp",
        "security": "tls"
      }
    },
    { "tag": "direct", "protocol": "freedom" }
  ],
  "routing": {
    "rules": [
      {
        "type": "field",
        "inboundTag": ["socks"],
        "outboundTag": "proxy"
      }
    ]
  }
}
```

> ⚠️ **关键要求**：inbound 必须是 `protocol: "socks"`，监听 `127.0.0.1:10808`，脚本默认通过此地址访问。outbound 协议可以是 Xray 支持的任意协议。

## 推送消息示例

```
🖥️ Zampto 服务器日报
服务器 ID: ***
地址: ***

状态: 🟢 Running

Expiry (Next Renewal): 1 day 23h 53m
Last Renewed: 已自动续期
  → 已自动续期 ✅
```

## 注意事项

- 续期的 CF Turnstile 由 CloakBrowser 自动处理
- Xray 在每次 Actions 运行时自动下载最新版并启动，无需手动维护
- 每次运行保存截图+录像（3 天）供调试
- 服务器离线才触发 Start，不影响正在运行的服务器

## 与原项目的区别

| 项目 | 代理工具 | Secret 名称 | SOCKS5 端口 | 支持协议 |
|------|----------|-------------|-------------|----------|
| zampto_auto（原项目） | Hysteria2 | `HY2_CONFIG` | 1080 | 仅 Hysteria2 |
| 本项目 | Xray | `V2RAY_CONFIG` | 10808 | SOCKS5/VMess/VLESS/Trojan/SS/HTTP 等 |

---
*AI生成*
