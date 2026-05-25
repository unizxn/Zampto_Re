import os, re, logging, random, json, time
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------- 环境变量 ----------
USERNAME  = os.environ["ZAMPTO_USERNAME"]
PASSWORD  = os.environ["ZAMPTO_PASSWORD"]
SERVER_ID = os.environ.get("ZAMPTO_SERVER_ID", "")

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

# ---------- 解析 expiry 字符串为总分钟数（用于比较）----------
def parse_expiry_minutes(expiry_str: str) -> int:
    """
    将 "1 day 22h 47m" 或 "2 days 1h 5m" 之类解析为总分钟数。
    解析失败返回 -1。
    """
    if not expiry_str:
        return -1
    total = 0
    m = re.search(r'(\d+)\s*day', expiry_str)
    if m:
        total += int(m.group(1)) * 24 * 60
    m = re.search(r'(\d+)\s*h', expiry_str)
    if m:
        total += int(m.group(1)) * 60
    m = re.search(r'(\d+)\s*m', expiry_str)
    if m:
        total += int(m.group(1))
    return total if total > 0 else -1

# ---------- 关闭所有弹窗（广告 + GDPR）----------
def dismiss_all_popups(page):
    """
    关闭页面上所有可能出现的弹窗：
    1. 广告弹窗（有 Close 按钮，或含外部域名链接）
    2. GDPR Cookie 同意弹窗
    每次调用最多等待 5 秒，关掉后继续检测，最多循环 3 轮。
    """
    for round_idx in range(3):
        closed_any = False

        closed = page.evaluate("""() => {
            var count = 0;

            // ① 优先找带明确文字的关闭按钮
            var closeTexts = ['Close', 'close', 'Schließen', '×', 'X'];
            for (var t of closeTexts) {
                var btns = Array.from(document.querySelectorAll('button, a, [role="button"]'));
                for (var b of btns) {
                    if (b.innerText && b.innerText.trim() === t) {
                        // 确认它在某种弹窗/overlay 容器内
                        var parent = b.closest('[class*="modal"],[class*="popup"],[class*="overlay"],[class*="dialog"],[class*="ad-"]');
                        if (parent) { b.click(); count++; break; }
                    }
                }
            }

            // ② aria-label="Close" 的按钮
            var ariaClose = document.querySelector('button[aria-label="Close"], button[aria-label="close"], [aria-label="Dismiss"]');
            if (ariaClose) { ariaClose.click(); count++; }

            // ③ GDPR：Nicht einwilligen / Decline / Reject
            var gdprTexts = ['Nicht einwilligen', 'Decline', 'Reject'];
            for (var gt of gdprTexts) {
                var gb = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === gt);
                if (gb) { gb.click(); count++; break; }
            }

            return count;
        }""")

        if closed and closed > 0:
            log.info(f"  已关闭 {closed} 个弹窗（第 {round_idx+1} 轮）")
            closed_any = True
            time.sleep(1)

        # 检查是否还有可见弹窗
        has_popup = page.evaluate("""() => {
            var selectors = [
                '[class*="modal"]:not([style*="display: none"])',
                '[class*="popup"]:not([style*="display: none"])',
                '[class*="overlay"]:not([style*="display: none"])',
            ];
            for (var s of selectors) {
                var el = document.querySelector(s);
                if (el && el.offsetParent !== null) return true;
            }
            return false;
        }""")

        if not has_popup:
            break

        if not closed_any:
            # 没关掉也没新弹窗，退出
            break

        time.sleep(1)

# ---------- CF Turnstile 等待 ----------
def wait_cf_turnstile(page, timeout=60) -> bool:
    """
    等待 Cloudflare Turnstile 验证自动完成。
    同时确认续期弹窗（id=renewModal）是可见的——
    如果弹窗根本不在，说明被广告弹窗打断了，直接返回 False。
    """
    log.info("等待 Cloudflare Turnstile 验证...")

    # 先确认续期弹窗真的出现了
    renew_modal_visible = page.evaluate("""() => {
        var m = document.getElementById('renewModal');
        if (!m) return false;
        return m.offsetParent !== null || m.style.display !== 'none';
    }""")
    if not renew_modal_visible:
        log.warning("⚠️ 续期弹窗未检测到（可能被广告弹窗遮挡或未弹出）")
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        still_verifying = page.evaluate("""() => {
            var frames = document.querySelectorAll('iframe');
            for (var f of frames) {
                if (f.src && f.src.includes('challenges.cloudflare.com')) return true;
            }
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
    login_url = "https://auth.zampto.net/sign-in?app_id=bmhk6c8qdqxphlyscztgl"

    for attempt in range(1, max_retries + 1):
        log.info(f"登录 {attempt}/{max_retries}")
        try:
            page.goto(login_url, timeout=30000, wait_until="domcontentloaded")
        except Exception as e:
            log.warning(f"goto 异常: {e}")

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

        try:
            page.locator('button[name="submit"], button[type="submit"]').first.click()
            log.info("已点击登录按钮（第一步）")
        except Exception as e:
            log.warning(f"点击登录失败: {e}")
            continue

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

        try:
            page.locator('button[name="submit"], button[type="submit"]').first.click()
            log.info("已点击继续按钮（第二步）")
        except Exception as e:
            log.warning(f"点击继续失败: {e}")
            continue

        if wait_for_url_contains(page, "dash.zampto.net", 20):
            log.info("✅ 登录成功，已跳转到 dashboard")
            take_screenshot(page, "01_login_success")
            return True

        time.sleep(3)
        if "dash.zampto.net" in page.url or "zampto.net/server" in page.url:
            log.info("✅ 登录成功")
            take_screenshot(page, "01_login_success")
            return True

        log.warning(f"登录后未跳转，当前 URL: {page.url}")
        take_screenshot(page, f"login_fail_{attempt}")
        time.sleep(2)

    return False

# ---------- 获取服务器信息（expiry + 状态）----------
def get_server_info(page, server_id: str) -> dict:
    """
    访问服务器详情页读取 expiry / lastRenewed / address，
    然后访问 console 页读取真实运行状态（Running / Stopped）。
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
        var body = document.body.innerText || '';
        var expiryMatch  = body.match(/Expiry[^:]*:\\s*([^\\n]+)/i);
        var renewedMatch = body.match(/last renewed[^:]*:\\s*([^\\n]+)/i);
        var addrMatch    = body.match(/node\\d+\\.zampto\\.net:\\d+/i);
        return {
            expiry:      expiryMatch  ? expiryMatch[1].trim()  : null,
            lastRenewed: renewedMatch ? renewedMatch[1].trim() : null,
            address:     addrMatch    ? addrMatch[0]           : null,
        };
    }""")

    # 真实运行状态在 Console 页（server 详情页显示的是账号 Active，不是运行状态）
    console_url = f"{BASE_URL}/server-console?id={server_id}"
    log.info(f"访问 Console 页读取运行状态: {console_url}")
    try:
        page.goto(console_url, timeout=30000, wait_until="domcontentloaded")
    except Exception as e:
        log.warning(f"访问 Console 页超时: {e}")

    time.sleep(3)

    status_text = page.evaluate("""() => {
        var statusEl = document.getElementById('serverStatus');
        if (statusEl) return statusEl.innerText.trim();
        var runEl = document.querySelector('.status-running,.status-stopped,.status-starting');
        if (runEl) return runEl.innerText.trim();
        var body = document.body.innerText || '';
        var sm = body.match(/Running(?:\\s*\\([^)]+\\))?|Stopped|Starting|Stopping/i);
        return sm ? sm[0] : 'Unknown';
    }""")

    info["status"] = status_text or "Unknown"
    log.info(f"服务器信息: {info}")
    return info

# ---------- 启动服务器 ----------
def start_server(page) -> bool:
    console_url = f"{BASE_URL}/server-console?id={SERVER_ID}"
    log.info(f"直接导航到 Console: {console_url}")
    page.goto(console_url, timeout=30000, wait_until="domcontentloaded")
    time.sleep(3)
    take_screenshot(page, "03_console_page")

    try:
        start_btn = page.locator('button:has-text("Start")').first
        if start_btn.is_visible(timeout=5000):
            start_btn.click()
            log.info("✅ 已点击 Start 按钮")
            time.sleep(5)
            take_screenshot(page, "04_after_start")
            body = get_text(page)
            if "Running" in body or "Starting" in body:
                log.info("✅ 服务器正在启动")
            return True
        else:
            log.warning("Start 按钮不可见（服务器可能已在运行）")
            return False
    except Exception as e:
        log.warning(f"点击 Start 失败: {e}")
        return False

# ---------- 续期 ----------
def renew_server(page, server_id: str, expiry_before: str) -> bool:
    """
    访问服务器详情页，关掉所有弹窗后点击 Renew Server，
    等待 CF Turnstile 自动通过，最后用 expiry 是否增加来验证续期成功。

    expiry_before: 续期前的 expiry 字符串，用于对比判断是否真正续期成功。
    """
    server_url = f"{BASE_URL}/server?id={server_id}"
    log.info(f"准备续期，访问: {server_url}")
    try:
        page.goto(server_url, timeout=30000, wait_until="domcontentloaded")
    except Exception as e:
        log.warning(f"访问续期页超时: {e}")

    time.sleep(3)

    # ✅ 关掉所有弹窗（广告/GDPR）再操作，避免广告弹窗拦截点击
    log.info("关闭页面上所有弹窗...")
    dismiss_all_popups(page)
    time.sleep(1)

    # 点击 Renew Server（<a> 标签，onclick，不是 <button>）
    try:
        renew_btn = page.locator(
            'a:has-text("Renew Server"), button:has-text("Renew Server")'
        ).first
        if not renew_btn.is_visible(timeout=8000):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            renew_btn = page.locator(
                'a:has-text("Renew Server"), button:has-text("Renew Server")'
            ).first

        renew_btn.click()
        log.info("已点击 Renew Server 按钮")
        take_screenshot(page, "05_renew_clicked")
    except Exception as e:
        log.warning(f"点击 Renew Server 失败: {e}")
        return False

    time.sleep(2)

    # 如果续期弹窗出现前又跳出广告，再清一次
    dismiss_all_popups(page)
    time.sleep(1)

    take_screenshot(page, "06_renew_modal")

    # 等待 CF Turnstile 验证（会先检查 renewModal 是否真的出现）
    if not wait_cf_turnstile(page, timeout=60):
        log.warning("CF 验证超时或续期弹窗未出现，续期失败")
        take_screenshot(page, "06_cf_timeout")
        return False

    # 等待页面刷新 / 弹窗消失
    time.sleep(5)
    take_screenshot(page, "07_after_renew")

    # ✅ 用 expiry 是否增加来判断是否真正续期成功，不依赖弹窗状态
    info_after = page.evaluate("""() => {
        var body = document.body.innerText || '';
        var m = body.match(/Expiry[^:]*:\\s*([^\\n]+)/i);
        return m ? m[1].trim() : null;
    }""")
    log.info(f"续期后 expiry（页面直读）: {info_after}")

    minutes_before = parse_expiry_minutes(expiry_before)
    minutes_after  = parse_expiry_minutes(info_after)

    log.info(f"续期前 expiry 分钟数: {minutes_before}, 续期后: {minutes_after}")

    # 成功条件：续期后时间 > 续期前时间（增加了说明成功），或续期后时间接近2天（>= 23h）
    if minutes_after > minutes_before or minutes_after >= 23 * 60:
        log.info(f"✅ 续期成功！expiry: {expiry_before} → {info_after}")
        return True

    # 如果数值没变或变小，可能真的没续期成功
    log.warning(f"⚠️ 续期后 expiry 未增加（{expiry_before} → {info_after}），续期可能失败")
    return False

# ---------- 主流程 ----------
def main():
    from cloakbrowser import launch

    if not SERVER_ID:
        log.error("❌ 未配置 ZAMPTO_SERVER_ID 环境变量")
        wxpush("❌ 未配置 ZAMPTO_SERVER_ID，任务中止")
        return

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

        # 2. 关闭 GDPR 同意弹窗
        dismiss_all_popups(page)

        # 3. 获取服务器信息
        info = get_server_info(page, SERVER_ID)
        status     = info.get("status", "Unknown")
        expiry     = info.get("expiry", "未知")
        address    = info.get("address", "未知")
        last_renew = info.get("lastRenewed", "未知")

        log.info(f"服务器状态: {status} | 到期: {expiry} | 地址: {address}")

        # 4. 如果服务器已停止，先启动
        started = False
        if "stopped" in status.lower() or "offline" in status.lower():
            log.info("🔴 服务器已停止，尝试启动...")
            started = start_server(page)
            if started:
                status = "Starting → Running"
                log.info("✅ 已发送启动指令")

        # 5. 续期（传入续期前 expiry 用于对比验证）
        renewed = renew_server(page, SERVER_ID, expiry_before=expiry)

        # 6. 续期后重新读取最新 expiry
        new_expiry = expiry
        if renewed:
            time.sleep(3)
            info2 = get_server_info(page, SERVER_ID)
            new_expiry = info2.get("expiry") or expiry
            log.info(f"续期后到期信息: {new_expiry}")

        # 7. 推送
        lines = ["🖥️ Zampto 服务器日报"]
        lines.append(f"服务器 ID: {SERVER_ID}")
        lines.append(f"地址: {address}")
        lines.append("")
        status_icon = "🟢" if "running" in status.lower() else ("🟡" if "starting" in status.lower() else "🔴")
        lines.append(f"状态: {status_icon} {status}")
        if started:
            lines.append("  → 已自动触发启动 ✅")
        lines.append("")
        lines.append(f"Expiry (Next Renewal): {new_expiry}")
        if last_renew:
            lines.append(f"Last Renewed: {last_renew}")
        if renewed:
            lines.append("  → 已自动续期 ✅")
        else:
            lines.append("  ⚠️ 续期失败，请手动检查")

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
