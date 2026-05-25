# Zampto 自动续期 & 状态监控

基于 **CloakBrowser + GitHub Actions** 的 Zampto 免费 Minecraft 服务器全自动化工具。每天北京时间 08:00 自动运行，完成登录 → 状态检查 → 启动 → 续期 → 推送通知全流程，无需人工干预。

---

## 功能列表

| 功能 | 说明 |
|------|------|
| 🔐 自动登录 | 支持 Logto 两步登录（用户名 → 密码分页） |
| 📊 状态检测 | 读取服务器真实运行状态（Running / Stopped / Starting） |
| 🚀 自动启动 | 服务器离线时自动点击 Start，轮询等待变为 Running |
| 🔌 端口验证 | TCP 连接验证端口真正可用，面板 Running 不代表实际可连 |
| 🔄 自动重启 | 端口不通时自动点 Restart，再次等待 + 再次验证 |
| 📅 自动续期 | 点击 Renew Server，等待 Cloudflare Turnstile 自动通过 |
| 📨 推送通知 | WxPusher 推送运行结果到微信 |
| 🧹 广告关闭 | 自动关闭 GDPR 弹窗、广告弹窗，避免遮挡操作 |
| 📸 截图调试 | 关键步骤自动截图，保存 3 天供排查问题 |
| 🎥 可选录屏 | 手动触发时可选择是否录制操作视频（默认关闭） |
| 🌐 代理支持 | 通过 Xray + SOCKS5 代理访问，避免地区封锁 |

---

## 目录结构

```
zampto_renew-main/
├── zampto_auto.py                        # 主脚本（登录/启动/续期/推送）
├── requirements.txt                      # Python 依赖
├── README.md                             # 本文件
└── .github/
    └── workflows/
        ├── zampto-auto.yml               # 每日定时续期 + 手动触发
        └── zampto-start-only.yml         # 紧急启动（Uptime Kuma 触发）
```

---

## 快速部署

### 第一步：Fork 仓库

点击右上角 **Fork**，把项目 fork 到自己账号下。

> 也可以新建一个私有仓库，把所有文件上传进去。**建议设为私有**，避免 Secrets 泄露风险。

---

### 第二步：配置 Secrets

进入仓库页面，依次点击：

**Settings → Secrets and variables → Actions → New repository secret**

按下表逐个添加：

| Secret 名称 | 必填 | 说明 |
|---|:---:|---|
| `ZAMPTO_USERNAME` | ✅ | Zampto 登录用户名 |
| `ZAMPTO_PASSWORD` | ✅ | Zampto 登录密码 |
| `ZAMPTO_SERVER_ID` | ✅ | 服务器 ID，见下方获取方法 |
| `V2RAY_CONFIG` | ✅ | Xray 代理配置 JSON 内容（完整 JSON 字符串）|
| `WXPUSHER_TOKEN` | ⬜ | WxPusher App Token，不填则跳过推送 |
| `WXPUSHER_UID` | ⬜ | WxPusher 用户 UID，不填则跳过推送 |

#### 如何获取 Server ID

登录 [Zampto Dashboard](https://dash.zampto.net/servers)，点进服务器详情页，地址栏 URL 末尾的数字即为 Server ID：

```
https://dash.zampto.net/server?id=****
                                    ^^^^
                               这就是 Server ID
```

#### 如何获取 WxPusher Token 和 UID

1. 访问 [WxPusher 官网](https://wxpusher.zjiecode.com) 注册账号
2. 创建应用，获得 **App Token**（格式：`AT_xxxxxxxxxxxxxxxx`）
3. 关注应用的公众号，在「我的」页面找到 **UID**（格式：`UID_xxxxxxxx`）

---

### 第三步：启用 Actions

进入仓库的 **Actions** 标签页，如果看到提示「Workflows are disabled」，点击 **Enable** 按钮启用。

---

### 第四步：手动测试运行

1. 点击 **Actions → 🔄 Zampto 自动续期 & 状态监控**
2. 点击右侧 **Run workflow**
3. 按需填写参数（默认全 false 即可）
4. 点击绿色 **Run workflow** 按钮
5. 等待约 5-15 分钟，查看运行日志

---

## 两个 Workflow 说明

### zampto-auto.yml — 每日自动续期

**触发方式：**
- 定时：每天 UTC 00:00（北京时间 08:00）自动执行
- 手动：Actions 页面手动触发，支持以下参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `force_renew` | `false` | 强制续期，不论剩余天数 |
| `enable_recording` | `false` | 启用录屏，true 时录制 mp4 并上传到 Artifacts |

**执行流程：**

```
启动 CloakBrowser（headless=False + 代理）
        ↓
登录 Zampto（最多重试 3 次）
        ↓
关闭 GDPR / 广告弹窗
        ↓
读取服务器状态 + 到期时间
        ↓
     服务器离线？
    ↙          ↘
  是             否
点击 Start        跳过
等待 Running
验证 TCP 端口
  端口不通？
点 Restart 再试
        ↓
续期（SKIP_RENEW=false 时）
点 Renew Server
等待 CF Turnstile 通过
比对 expiry 确认成功
        ↓
WxPusher 推送结果
```

---

### zampto-start-only.yml — 紧急启动

**触发方式：**
- Uptime Kuma Webhook（`repository_dispatch` 事件，type: `server-down`）
- 手动触发（测试用）

**用途：** 当 Uptime Kuma 监测到服务器端口不可达时，自动触发此 Workflow，**只做启动，不做续期**，最快速地恢复服务器。

同样支持 `enable_recording` 参数，默认不录屏。

---

## Uptime Kuma 配置详解

Uptime Kuma 是一个开源的自托管监控工具，可以监测服务器端口是否在线，离线时自动触发 GitHub Actions 紧急启动。

### 前提条件

- 已自托管 Uptime Kuma（Docker 或直装均可）
- 已准备好 GitHub Personal Access Token（PAT）

### 第一步：创建 GitHub Personal Access Token

1. 登录 GitHub，进入 **Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. 点击 **Generate new token (classic)**
3. 填写备注，例如：`uptime-kuma-zampto`
4. 勾选权限：`repo`（完整仓库权限，用于触发 workflow）
5. 点击生成，**立即复制保存**（只显示一次）

### 第二步：在 Uptime Kuma 中添加监控项

1. 登录 Uptime Kuma 控制台
2. 点击 **Add New Monitor**
3. 填写配置：

| 字段 | 填写内容 |
|---|---|
| Monitor Type | `TCP Port` |
| Friendly Name | `Zampto 服务器`（随意） |
| Hostname | 你的服务器地址 |
| Port | 你的服务器端口 |
| Heartbeat Interval | `60`（每 60 秒检测一次） |
| Retries | `2`（连续失败 3 次才告警） |
|连续失败时重复发送通知的间隔次数 (每 9999 次失败则重复发送一次)|

4. 点击 **Save**

### 第三步：添加 Webhook 通知

1. 进入 Uptime Kuma **Settings → Notifications**
2. 点击 **Add Notification**
3. 按如下填写各字段：

**通知类型：** `Webhook`

**显示名称：** `Zampto 紧急启动`（随意）

**Post URL：**
```
https://api.github.com/repos/你的用户名/你的仓库名/dispatches
```
例如：
```
https://api.github.com/repos/zhangsan/zampto_renew/dispatches
```

**请求体** → 选择 `自定义内容`，填入：
```json
{
  "event_type": "server-down",
  "client_payload": {
    "reason": "Uptime Kuma alert",
    "heartbeat": "{{heartbeatJSON}}"
  }
}
```

**额外 Header** → 开启开关，填入以下 JSON：
```json
{
  "Authorization": "Bearer ghp_你的PAT令牌",
  "Accept": "application/vnd.github+json",
  "X-GitHub-Api-Version": "2022-11-28"
}
```

4. 点击 **Test** 测试是否能成功触发 GitHub Actions
5. 点击 **Save**

### 第四步：将通知绑定到监控项

1. 回到刚才创建的 Zampto 监控项，点击编辑
2. 在 **Notifications** 一栏，勾选刚才创建的 Webhook 通知
3. 将触发条件设置为：**Down**（仅离线时触发，避免恢复时重复触发）
4. 保存

### 验证配置

在 GitHub Actions 的 **zampto-start-only** workflow 历史中，如果看到由 `repository_dispatch` 触发的运行记录，说明配置成功。

> **注意：** Uptime Kuma 的通知默认在每次状态变化时都发送。建议在通知设置里启用「**Send only on status change**」，避免服务器频繁重启时反复触发。

---

## 录屏功能说明

录屏默认**关闭**，不影响日常自动运行（节省 CI 时间和存储）。

**开启方法：** 手动触发 workflow 时，将 `enable_recording` 改为 `true`。

录制完成后，视频和日志会上传到 Actions **Artifacts**，保留 3 天：

```
debug-<运行编号>/
├── 20260525_080001_01_login_success.png
├── 20260525_080012_02_server_page.png
├── ...（其他截图）
├── recording.mp4    ← 完整操作录像（仅 enable_recording=true 时有）
└── ffmpeg.log       ← 录屏日志
```

下载方式：进入 Actions → 点击对应的运行记录 → 底部 **Artifacts** 区域下载。

---

## 推送消息示例

**正常续期：**
```
🖥️ Zampto 服务器日报
服务器 ID: ***
地址: ***

状态: 🟢 Running

Expiry (Next Renewal): 1 day 23h 53m
Last Renewed: May 25, 2026 10:29 AM
  → 已自动续期 ✅
```

**离线后启动：**
```
🖥️ Zampto 服务器日报
服务器 ID: ***
地址: ***

状态: 🟢 Running
  → 已启动，面板 Running + 端口可连接 ✅

Expiry (Next Renewal): 1 day 22h 10m
  → 已自动续期 ✅
```

**紧急启动（Uptime Kuma 触发）：**
```
🚨 Zampto 紧急启动报告
服务器 ID: ***
地址: ***

状态: 🟢 Running
  → 已启动，面板 Running + 端口可连接 ✅

Expiry (Next Renewal): 1 day 20h 5m
  （续期已跳过，仅紧急启动）
```

---

## 截图脱敏说明

脚本在每次截图前会自动将页面上所有邮箱地址替换为 `***@***.***`，截图上传到 Artifacts 后不会包含真实账号信息。

截图仍会上传到 GitHub Actions Artifacts，建议注意以下几点：

1. **将仓库设为私有**（最重要，防止外部访问）
2. Artifact 保留天数已设为 3 天，到期自动清除
3. 如需提前删除：进入 Actions → 点击对应运行记录 → Artifacts 右侧点 **Delete**

---

## 常见问题

**Q: 登录失败怎么办？**
A: 检查 `ZAMPTO_USERNAME` 和 `ZAMPTO_PASSWORD` 是否正确。

**Q: CF Turnstile 验证总是超时？**
A: 通常是代理 IP 被 Cloudflare 识别。尝试更换 `V2RAY_CONFIG` 中的节点，或检查代理是否正常工作（日志中会打印代理 IP）。

**Q: 端口验证失败但面板显示 Running？**
A: Zampto 服务器启动后端口不一定立即开放，脚本会等待最多 120 秒，超时后自动点 Restart 再试。如果多次失败，可能是服务器本身问题，需登录面板手动处理。

**Q: 续期后 expiry 没有增加？**
A: 可能是 GDPR 或广告弹窗遮挡了 Renew 按钮，或 CF Turnstile 未通过。开启 `enable_recording` 录制一次操作视频，下载后查看具体卡在哪一步。

**Q: Uptime Kuma Webhook 测试返回 422？**
A: 检查 Request Body 里的 `event_type` 是否与 `zampto-start-only.yml` 中 `types: [server-down]` 完全一致，大小写敏感。

---

## 依赖说明

| 依赖 | 用途 |
|---|---|
| `cloakbrowser` | 反指纹浏览器，自动处理 CF Turnstile |
| `playwright` | 浏览器自动化底层（cloakbrowser 内置） |
| `xvfb` | Linux 虚拟显示器，运行 headless 浏览器 |
| `ffmpeg` | 录制虚拟屏幕（可选） |
| `xray` | 代理客户端，运行时动态下载 |

---

## License

MIT
