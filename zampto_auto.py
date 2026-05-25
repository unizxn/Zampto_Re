import os, re, logging, random, json, time
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------- 环境变量 ----------
USERNAME = os.environ["ZAMPTO_USERNAME"]   # 用户名或邮箱
PASSWORD = os.environ["ZAMPTO_PASSWORD"]   # 密码
SERVER_ID = os.environ.get("ZAMPTO_SERVER_ID", "")   # 服务器 ID，如 6710

WXPUSHER_TOKEN = os.environ.get("WXPUSHER_TOKEN", "")
WXPUSHER_UID   = os.environ.get("WXPUSHER_UID", "")

BASE_URL    = "https://dash.zampto.net"
AUTH_URL    = "https://auth.zampto.net/sign-in"
SERVERS_URL = f"{BASE_URL}/servers"

SCREENSHOT_DIR = Path("./screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

# ---------- WxPusher ----------
def wxpush(content: str):
    if not WXPUSHER_TOKEN or not WXPUSHER_UID:
        log.warning("📨 WXPUSHER_TOKEN 或 WXPUSHER_UID 未配置，跳过推送")
        return
    import urllib.request
    payload = json.dumps({
        "appToken": WXPUSHER_TOKEN,
        "content":  content,
        "contentType": 1,
        "uids": [WXPUSHER_UID],
    }).encode()
    try:
        req = urllib.request.Request(
            "https://wxpusher.zjiecode.com/api/send/message",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("success"):
                log.info("📨 WxPusher 推送成功")
            else:
                log.warning(f"📨 WxPusher 推送失败: {result}")
    except Exception as e:
        log.warning(f"📨 WxPusher 推送异常: {e}")

# ---------- 工具函数 ----------
def take_screenshot(page, name):
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = str(SCREENSHOT_DIR / f"{ts}_{name}.png")
        page.screenshot(path=path, full_page=False)
        log.info(f"📸 截图: {path}")
    except Exception as e:
        log.warning(f"截图失败: {e}")

def get_text(page) -> str:
    try:
        return page.inner_text("body") or ""
    except:
        return ""

def human_delay(min_s=0.5, max_s=1.2):
    time.sleep(random.uniform(min_s, max_s))

def wait_for_url_contains(page, keyword, timeout=15) -> bool:
    try:
        page.wait_for_url(f"**{keyword}**", timeout=timeout * 1000)
        return True
    except:
        return keyword in page.url

# ---------- CF Turnstile 等待 ----------
def wait_cf_turnstile(page, timeout=60) -> bool:
    """
    等待 Cloudflare Turnstile 验证自动完成。
    CloakBrowser 会自动处理 Turnstile，我们只需等待 loading 消失。
    """
    log.info("等待 Cloudflare Turnstile 验证...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        # 检查 CF 验证 widget 是否还在 loading 状态
        still_verifying = page.evaluate("""() => {
            // 检查 CF Turnstile iframe 是否存在且处于验证中
            var frames = document.querySelectorAll('iframe');
            for (var f of frames) {
                if (f.src && f.src.includes('challenges.cloudflare.com')) {
                    return true;
                }
            }
            // 检查文本 "正在验证"
            var body = document.body.innerText || '';
            return body.includes('正在验证') || body.includes('Verifying');
        }""")
        if not still_verifying:
            log.info("✅ CF Turnstile 验证完成")
            return True
        elapsed = int(time.time() - (deadline - timeout))
        if elapsed % 5 == 0:
            log.info(f"  CF 等待中... {elapsed}s")
        time.sleep(1)
    log.error(f"CF Turnstile 验证超时（{timeout}s）")
    return False

# ---------- 登录 ----------
def login(page, max_retries=3) -> bool:
    """
    Zampto 使用 Logto 登录，分两步：
    1. 输入用户名/邮箱 → 点登录 → 跳转密码页
    2. 输入密码 → 点继续 → 跳转 dash
    """
    # 构造带 app_id 的登录 URL（从图片中获取）
    login_url = f"https://auth.zampto.net/sign-in?app_id=bmhk6c8qdqxphlyscztgl"

    for attempt in range(1, max_retries + 1):
        log.info(f"登录 {attempt}/{max_retries}")
        try:
            page.goto(login_url, timeout=30000, wait_until="domcontentloaded")
        except Exception as e:
            log.warning(f"goto 异常: {e}")

        # 等待用户名输入框
        try:
            page.wait_for_selector(
                'input[name="identifier"], input[autocomplete="username email"]',
                timeout=15000
            )
        except:
            log.warning("找不到用户名输入框，重试")
            take_screenshot(page, f"login_no_input_{attempt}")
            time.sleep(2)
            continue

        # 填写用户名
        try:
            user_el = page.locator('input[name="identifier"]').first
            user_el.click()
            user_el.fill("")
            user_el.type(USERNAME, delay=random.randint(60, 130))
            log.info(f"已填写用户名: {USERNAME}")
        except Exception as e:
            log.warning(f"填写用户名失败: {e}")
            continue

        human_delay()

        # 点击登录按钮（第一步，只提交用户名）
        try:
            page.locator('button[name="submit"], button[type="submit"]').first.click()
            log.info("已点击登录按钮（第一步）")
        except Exception as e:
            log.warning(f"点击登录失败: {e}")
            continue

        # 等待密码页
        try:
            page.wait_for_selector(
                'input[name="password"], input[autocomplete="current-password"]',
                timeout=15000
            )
            log.info("已进入密码输入页")
        except:
            log.warning("未出现密码输入框，重试")
            take_screenshot(page, f"login_no_password_{attempt}")
            continue

        # 填写密码
        try:
            pass_el = page.locator('input[name="password"]').first
            pass_el.click()
            pass_el.fill("")
            pass_el.type(PASSWORD, delay=random.randint(60, 130))
            log.info("已填写密码")
        except Exception as e:
            log.warning(f"填写密码失败: {e}")
            continue

        human_delay()

        # 点击继续按钮
        try:
            page.locator('button[name="submit"], button[type="submit"]').first.click()
            log.info("已点击继续按钮（第二步）")
        except Exception as e:
            log.warning(f"点击继续失败: {e}")
            continue

        # 等待跳转到 dash
        if wait_for_url_contains(page, "dash.zampto.net", 20):
            log.info("✅ 登录成功，已跳转到 dashboard")
            take_screenshot(page, "01_login_success")
            return True

        # 有时会先跳到 overview 或 servers
        time.sleep(3)
        if "dash.zampto.net" in page.url or "zampto.net/server" in page.url:
            log.info("✅ 登录成功")
            take_screenshot(page, "01_login_success")
            return True

        log.warning(f"登录后未跳转，当前 URL: {page.url}")
        take_screenshot(page, f"login_fail_{attempt}")
        time.sleep(2)

    return False

# ---------- 关闭 GDPR/Cookie 同意弹窗 ----------
def dismiss_consent_modal(page):
    """
    登录后可能弹出 GDPR 同意框（德语 Einwilligen / Nicht einwilligen）。
    直接点 Nicht einwilligen（不同意）关掉，不影响功能。
    """
    try:
        page.wait_for_selector(
            'button:has-text("Einwilligen"), button:has-text("Accept")',
            timeout=6000
        )
        declined = page.evaluate("""() => {
            var btns = document.querySelectorAll('button');
            for (var b of btns) {
                var t = b.innerText.trim();
                if (t === 'Nicht einwilligen' || t === 'Decline' || t === 'Reject') {
                    b.click(); return 'declined';
                }
            }
            var close = document.querySelector('button[aria-label="Close"], button[aria-label="close"]');
            if (close) { close.click(); return 'closed'; }
            return null;
        }""")
        if declined:
            log.info(f"✅ 已关闭同意弹窗（{declined}）")
            time.sleep(1)
        else:
            log.info("未找到拒绝按钮")
    except Exception:
        log.info("无 GDPR 弹窗，跳过")

# ---------- 获取服务器信息 ----------
def get_server_info(page, server_id: str) -> dict:
    """
    访问服务器详情页，读取：
    - STATUS（Running / Stopped）
    - Expiry (Next Renewal) 文本
    - 服务器地址
    """
    server_url = f"{BASE_URL}/server?id={server_id}"
    log.info(f"访问服务器详情: {server_url}")

    try:
        page.goto(server_url, timeout=30000, wait_until="domcontentloaded")
    except Exception as e:
        log.warning(f"访问服务器详情超时: {e}")

    time.sleep(3)
    take_screenshot(page, "02_server_page")

    info = page.evaluate("""() => {
        var body = document.body.innerText || document.body.textContent || '';

        // 提取 Expiry 信息（如 "1 day 23h 53m"）
        var expiryMatch = body.match(/Expiry[^:]*:\\s*([^\\n]+)/i);
        var expiry = expiryMatch ? expiryMatch[1].trim() : null;

        // 提取 Last Renewed 时间
        var renewedMatch = body.match(/last renewed[^:]*:\\s*([^\\n]+)/i);
        var lastRenewed = renewedMatch ? renewedMatch[1].trim() : null;

        // 提取服务器地址
        var addrMatch = body.match(/node\\d+\\.zampto\\.net:\\d+/i);
        var address = addrMatch ? addrMatch[0] : null;

        // 判断状态
        var statusEl = document.querySelector('[class*="status"], [class*="Status"]');
        var statusText = statusEl ? statusEl.innerText.trim() : '';
        if (!statusText) {
            // 从 body 文本匹配
            var sm = body.match(/Running|Stopped|Starting|Stopping/i);
            statusText = sm ? sm[0] : 'Unknown';
        }

        return { expiry, lastRenewed, address, status: statusText };
    }""")

    log.info(f"服务器信息: {info}")
    return info

# ---------- 启动服务器 ----------
def start_server(page) -> bool:
    """点击 Console 页面的 Start 按钮启动服务器"""
    # 找到 Console 链接并进入
    try:
        console_btn = page.locator('a[href*="server-console"], button:has-text("Console")').first
        if console_btn.is_visible(timeout=5000):
            console_btn.click()
            log.info("已点击 Console 按钮")
            time.sleep(3)
        else:
            raise Exception("Console 按钮不可见")
    except:
        # 直接构造 console URL
        server_id = SERVER_ID
        console_url = f"{BASE_URL}/server-console?id={server_id}"
        log.info(f"直接导航到 Console: {console_url}")
        page.goto(console_url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(3)

    take_screenshot(page, "03_console_page")

    # 点击 Start 按钮
    try:
        start_btn = page.locator('button:has-text("Start")').first
        if start_btn.is_visible(timeout=5000):
            start_btn.click()
            log.info("✅ 已点击 Start 按钮")
            time.sleep(5)
            take_screenshot(page, "04_after_start")

            # 验证是否正在启动
            body = get_text(page)
            if "Running" in body or "Starting" in body:
                log.info("✅ 服务器正在启动")
                return True
            return True  # 点击成功即视为操作成功
        else:
            log.warning("Start 按钮不可见（服务器可能已在运行）")
            return False
    except Exception as e:
        log.warning(f"点击 Start 失败: {e}")
        return False

# ---------- 续期 ----------
def renew_server(page, server_id: str) -> bool:
    """
    点击 Renew Server 按钮，等待 CF Turnstile 验证自动通过。
    """
    server_url = f"{BASE_URL}/server?id={server_id}"
    log.info(f"准备续期，访问: {server_url}")

    try:
        page.goto(server_url, timeout=30000, wait_until="domcontentloaded")
    except Exception as e:
        log.warning(f"访问续期页超时: {e}")

    time.sleep(3)

    # 点击 Renew Server 按钮
    try:
        renew_btn = page.locator('button:has-text("Renew Server")').first
        if not renew_btn.is_visible(timeout=8000):
            # 尝试滚动到按钮
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            renew_btn = page.locator('button:has-text("Renew Server")').first

        renew_btn.click()
        log.info("已点击 Renew Server 按钮")
        take_screenshot(page, "05_renew_clicked")
    except Exception as e:
        log.warning(f"点击 Renew Server 失败: {e}")
        return False

    time.sleep(2)

    # 等待弹窗出现
    try:
        page.wait_for_selector(
            'text="Renew Server", text="Please complete the security verification"',
            timeout=10000
        )
        log.info("续期弹窗已出现")
    except:
        log.warning("未检测到续期弹窗，继续等待 CF 验证")

    take_screenshot(page, "06_renew_modal")

    # 等待 CF Turnstile 验证（CloakBrowser 会自动处理）
    if not wait_cf_turnstile(page, timeout=60):
        log.warning("CF 验证超时，续期可能失败")
        take_screenshot(page, "06_cf_timeout")
        return False

    # 等待续期完成（弹窗消失或页面刷新）
    time.sleep(3)
    take_screenshot(page, "07_after_renew")

    # 检查是否续期成功（弹窗消失 or 页面刷新后 expiry 更新）
    body = get_text(page)
    modal_gone = page.evaluate("""() => {
        var modal = document.querySelector('[class*="modal"], [class*="Modal"]');
        return !modal || modal.style.display === 'none';
    }""")

    if modal_gone or "Cancel" not in body:
        log.info("✅ 续期完成（弹窗已关闭）")
        return True

    log.warning("续期弹窗仍在，可能未完成")
    return False

# ---------- 主流程 ----------
def main():
    from cloakbrowser import launch

    if not SERVER_ID:
        log.error("❌ 未配置 ZAMPTO_SERVER_ID 环境变量")
        wxpush("❌ 未配置 ZAMPTO_SERVER_ID，任务中止")
        return

    # 代理：Xray 本地 SOCKS5（GitHub Actions 环境通过 V2RAY_CONFIG 启动）
    PROXY_SERVER = "socks5://127.0.0.1:10808"

    log.info("启动 CloakBrowser...")
    browser = launch(
        headless=False,
        humanize=True,
        proxy=PROXY_SERVER,
        geoip=True,
    )
    page = browser.new_page()

    try:
        # 1. 登录
        if not login(page):
            wxpush("❌ Zampto 登录失败，请检查账号密码")
            return

        # 2. 关闭 GDPR 同意弹窗（如有）
        dismiss_consent_modal(page)

        # 3. 获取服务器信息
        info = get_server_info(page, SERVER_ID)
        status     = info.get("status", "Unknown")
        expiry     = info.get("expiry", "未知")
        address    = info.get("address", "未知")
        last_renew = info.get("lastRenewed", "未知")

        log.info(f"服务器状态: {status} | 到期: {expiry} | 地址: {address}")

        # 3. 如果服务器 Stopped，执行启动
        started = False
        if "stopped" in status.lower() or "offline" in status.lower():
            log.info("🔴 服务器已停止，尝试启动...")
            started = start_server(page)
            if started:
                status = "Starting → Running"
                log.info("✅ 已发送启动指令")

        # 4. 续期
        renewed = False
        server_url = f"{BASE_URL}/server?id={SERVER_ID}"
        page.goto(server_url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(3)
        renewed = renew_server(page, SERVER_ID)

        # 5. 续期后重新读取最新 expiry
        if renewed:
            time.sleep(3)
            info2 = get_server_info(page, SERVER_ID)
            new_expiry = info2.get("expiry", expiry)
            if new_expiry:
                expiry = new_expiry
            log.info(f"续期后到期信息: {expiry}")

        # 6. 组装推送消息
        lines = ["🖥️ Zampto 服务器日报"]
        lines.append(f"服务器 ID: {SERVER_ID}")
        lines.append(f"地址: {address}")
        lines.append("")

        # 状态
        status_icon = "🟢" if "running" in status.lower() else ("🟡" if "starting" in status.lower() else "🔴")
        lines.append(f"状态: {status_icon} {status}")
        if started:
            lines.append("  → 已自动触发启动 ✅")

        lines.append("")
        lines.append(f"Expiry (Next Renewal): {expiry}")
        if last_renew:
            lines.append(f"Last Renewed: {last_renew}")
        if renewed:
            lines.append("  → 已自动续期 ✅")

        msg = "\n".join(lines)
        log.info(f"推送内容:\n{msg}")
        wxpush(msg)

    except Exception as e:
        log.exception(e)
        take_screenshot(page, "99_error")
        wxpush(f"❌ Zampto 任务异常: {e}")
    finally:
        time.sleep(3)
        browser.close()
        log.info("任务结束")

if __name__ == "__main__":
    main()
