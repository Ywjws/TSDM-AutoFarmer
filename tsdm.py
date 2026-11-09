import httpx
import re
import urllib.parse
import time
import os
import sys

# 直接从环境变量获取配置
COOKIE = os.environ.get("TSDM_COOKIE", "")
# 去掉可能混进来的换行/首尾空白，避免 secret 粘贴时带格式
COOKIE = COOKIE.replace("\r", "").replace("\n", "").strip()

if not COOKIE:
    print("❌ 未设置 TSDM_COOKIE 环境变量")
    sys.exit(1)

BASE = "https://www.tsdm39.com"
FORUM_URL = BASE + "/forum.php"
CREDIT_URL = BASE + "/home.php?mod=spacecp&ac=credit&showcredit=1"
SIGN_URL = BASE + "/plugin.php?id=dsu_paulsign%3Asign&operation=qiandao&infloat=1&sign_as=1&inajax=1"
SIGN_PAGE_URL = BASE + "/plugin.php?id=dsu_paulsign%3Asign"
WORK_URL = BASE + "/plugin.php?id=np_cliworkdz%3Awork&inajax=1"
WORK_POST_URL = BASE + "/plugin.php?id=np_cliworkdz:work"

# 刻意不带 br：workflow 只装了 httpx，没有 brotli，
# 声明 br 会拿到未解压的二进制，导致页面解析全部失败。
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "Cookie": COOKIE,
    "Referer": BASE + "/forum.php",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
}

FORMHASH_PATTERN = r'name="formhash"\s+value="([0-9a-zA-Z]+)"'
COOLDOWN_PATTERN = r"您需要等待\d+小时\d+分钟\d+秒后即可进行。"
# Discuz 内核下发的当前用户 ID，游客为 0。与页面模板无关，是最可靠的登录判据。
UID_PATTERN = r"discuz_uid\s*=\s*['\"]?(\d+)"


def send(title, message):
    """日志报告函数"""
    print(f"【{title}】{message}")


def new_client():
    """统一的 client：不自动跟随重定向，这样能看到 Discuz 的 302 跳登录页。"""
    return httpx.Client(headers=HEADERS, follow_redirects=False, timeout=30.0)


def is_login_redirect(response):
    """未登录时 Discuz 会 302 到 member.php?mod=logging&action=login。"""
    if response.status_code not in (301, 302, 303, 307, 308):
        return False
    location = response.headers.get("location", "")
    return "mod=logging" in location and "action=login" in location


def snippet(text, limit=160):
    """把响应体压成一行短片段，方便日志里看出真实返回。"""
    if not text:
        return "（空响应）"
    cleaned = re.sub(r"<!\[CDATA\[|\]\]>", "", text)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "（无文本内容）"
    return cleaned[:limit] + ("…" if len(cleaned) > limit else "")


def page_text(html):
    if not html:
        return ""
    cleaned = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    cleaned = re.sub(r"<style[\s\S]*?</style>", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_sign_stats(html):
    text = page_text(html)
    stats = {
        "headline": None,
        "user": None,
        "total_days": None,
        "month_days": None,
        "last_time": None,
        "total_reward": None,
        "last_reward": None,
        "level": None,
    }

    match = re.search(r'<h1 class="mt">([^<]+)</h1>', html or "")
    if match:
        stats["headline"] = match.group(1).strip()

    match = re.search(r"<b>([^<]+)</b>\s*(?:</font>\s*)?,\s*您累计已签到:\s*<b>(\d+)</b>\s*天", html or "")
    if match:
        stats["user"] = match.group(1).strip()
        stats["total_days"] = match.group(2)

    match = re.search(r"本月已累计签到:\s*<b>(\d+)</b>\s*天", html or "")
    if match:
        stats["month_days"] = match.group(1)

    match = re.search(r"上次签到时间:\s*<font[^>]*>([^<]+)</font>", html or "")
    if match:
        stats["last_time"] = match.group(1).strip()

    match = re.search(r"总奖励为:\s*天使币\s*<font[^>]*>\s*<b>(\d+)</b>", html or "")
    if match:
        stats["total_reward"] = match.group(1)

    match = re.search(r"上次获得的奖励为:\s*天使币\s*<font[^>]*>\s*<b>(\d+)</b>", html or "")
    if match:
        stats["last_reward"] = match.group(1)

    match = re.search(r"您目前的等级:\s*<font[^>]*>\s*<b>([^<]+)</b>", html or "")
    if match:
        stats["level"] = match.group(1).strip()

    return stats


def format_sign_stats(stats):
    """把 parse_sign_stats 的结果拼成一行人类可读的日志。"""
    parts = []
    if stats.get("user"):
        parts.append(f"用户 {stats['user']}")
    if stats.get("total_days"):
        parts.append(f"累计已签到 {stats['total_days']} 天")
    if stats.get("month_days"):
        parts.append(f"本月已签到 {stats['month_days']} 天")
    if stats.get("last_time"):
        parts.append(f"上次签到 {stats['last_time']}")
    if stats.get("total_reward"):
        parts.append(f"累计奖励 天使币 {stats['total_reward']}")
    if stats.get("last_reward"):
        parts.append(f"上次奖励 天使币 {stats['last_reward']}")
    if stats.get("level"):
        parts.append(f"等级 {stats['level']}")
    return " | ".join(parts)


def check_login(client):
    response = client.get(CREDIT_URL)

    if is_login_redirect(response):
        return {"ok": False, "score": None, "reason": "积分页被重定向到登录页"}

    text = response.text
    if "您需要先登录" in text or "请先登录" in text:
        return {"ok": False, "score": None, "reason": "服务器提示需要先登录（cookie 无效或已过期）"}

    match = re.search(UID_PATTERN, text)
    if not match:
        return {"ok": False, "score": None, "reason": "积分页里找不到 discuz_uid，无法判断登录状态"}

    uid = int(match.group(1))
    if uid == 0:
        return {"ok": False, "score": None, "reason": "服务器把你当游客（discuz_uid = 0）"}

    # 先去掉 <script>，否则会命中 JS 配置里 creditnotice 的「天使币」
    cleaned = page_text(text)
    score_match = re.search(r"天使币\s*[:：]?\s*(\d+)", cleaned)

    if score_match:
        return {"ok": True, "score": score_match.group(1), "reason": f"已登录（uid={uid}）"}
    return {"ok": True, "score": None, "reason": f"已登录（uid={uid}），但未解析出天使币"}


def tsdm_check_in():
    log = ""
    stats_summary = ""

    with new_client() as client:
        try:
            state = check_login(client)
            if not state["ok"]:
                log = f"❌ 签到异常: 未登录（{state['reason']}）"
                send("签到结果", log)
                return log

            # 获得 formhash
            response = client.get(FORUM_URL)
            if response.status_code != 200:
                log = f"❌ 签到异常: 论坛首页返回 HTTP {response.status_code}"
                send("签到结果", log)
                return log

            match = re.search(FORMHASH_PATTERN, response.text)
            if not match:
                log = f"❌ 签到异常: 首页未找到 formhash（HTTP {response.status_code}，{len(response.text)} 字符）"
                send("签到结果", log)
                return log

            formhash_value = match.group(1)
            encoded_formhash = urllib.parse.quote(formhash_value)

            # 签到
            payload = {"formhash": encoded_formhash, "qdxq": "kx", "qdmode": "3", "todaysay": "", "fastreply": "1"}
            response = client.post(SIGN_URL, data=payload)

            if is_login_redirect(response):
                log = "❌ 签到异常: 未登录（签到接口被重定向到登录页）"
            else:
                text = page_text(response.text)
                if "签到成功" in text:
                    log = "✅ 签到成功"
                elif "已经签到" in text or "已签到" in text:
                    log = "ℹ️ 今日已签到，无需重复签到"
                else:
                    log = f"❌ 签到异常: 未知响应（HTTP {response.status_code}，内容: {snippet(text)}）"

            # 无论签到结果如何，都再抓一次签到页，把累计统计带进日志。
            # 这段信息只用于展示，解析失败不影响签到本身的结论。
            try:
                page = client.get(SIGN_PAGE_URL)
                if page.status_code == 200:
                    stats_line = format_sign_stats(parse_sign_stats(page.text))
                    if stats_line:
                        stats_summary = stats_line
            except Exception as e:
                stats_summary = f"⚠️ 读取签到统计失败: {type(e).__name__}: {e}"

        except Exception as e:
            log = f"❌ 签到异常: {type(e).__name__}: {e}"

        send("签到结果", log)
        if stats_summary:
            send("签到统计", stats_summary)
        return log


def tsdm_work():
    log = ""

    with new_client() as client:
        try:
            # 查询是否可以打工
            response = client.get(WORK_URL)

            if is_login_redirect(response):
                log = "❌ 打工异常: 未登录（打工接口被重定向到登录页）"
                send("打工结果", log)
                return log

            match = re.search(COOLDOWN_PATTERN, response.text)
            if match:
                log = f"⏳ 打工冷却中: {match.group()}"
                send("打工结果", log)
                return log

            # 从页面里取广告 id，逐个点击。
            # 真实请求必须带 advid（见插件 plugin.js：{act:'clickad', advid:advid}），
            # 不带 advid 时服务端会认为在作弊，getcre 只会返回「不要作弊哦」。
            advids = re.findall(r'id="np_advid(\d+)"', response.text)
            if not advids:
                log = "❌ 打工异常: 打工页里找不到广告（未登录或页面结构变化）"
                send("打工结果", log)
                return log

            failure = None
            for index, advid in enumerate(advids, start=1):
                response = client.post(WORK_POST_URL, data={"act": "clickad", "advid": advid})
                if is_login_redirect(response):
                    failure = f"第 {index} 个广告（advid={advid}）被重定向到登录页"
                    break
                if response.status_code >= 400:
                    failure = f"第 {index} 个广告（advid={advid}）返回 HTTP {response.status_code}"
                    break
                time.sleep(3)

            if failure:
                log = f"❌ 打工异常: {failure}"
                send("打工结果", log)
                return log

            # 获取奖励
            response = client.post(WORK_POST_URL, data={"act": "getcre"})
            text = page_text(response.text)

            if is_login_redirect(response):
                log = "❌ 打工异常: 领取奖励时被重定向到登录页"
            elif "不要作弊" in text:
                log = "❌ 打工异常: 服务端判定未完成点击（返回「不要作弊哦」）"
            elif "您需要等待" in text or "必须与上一次间隔" in text:
                # 冷却中说明服务端已认可这次打工，只是还没到结算时间
                match = re.search(r"您需要等待[^ ]*", text)
                log = f"⏳ 打工冷却中: {match.group() if match else snippet(text)}"
            else:
                match = re.search(r"天使币\s*\+?\s*(\d+)", text)
                if match:
                    log = f"✅ 打工完成（获得天使币 +{match.group(1)}）"
                else:
                    log = f"⚠️ {len(advids)} 个广告已点击，但未确认奖励（响应: {snippet(text)}）"

        except Exception as e:
            log = f"❌ 打工异常: {type(e).__name__}: {e}"

        send("打工结果", log)
        return log


def get_score():
    try:
        with new_client() as client:
            state = check_login(client)
        if state["ok"]:
            if state["score"]:
                return state["score"]
            send("查询异常", f"❌ 获取天使币失败: {state['reason']}")
            return "未知"
        send("查询异常", f"❌ 获取天使币失败: {state['reason']}")
        return "未知"
    except Exception as e:
        send("查询异常", f"❌ 获取天使币失败: {type(e).__name__}: {e}")
        return "未知"


def run_checkin():
    checkin_log = tsdm_check_in()
    score = get_score()
    send("签到完成", f"{checkin_log} | 当前天使币: {score}")


def run_work():
    work_log = tsdm_work()
    score = get_score()
    send("打工完成", f"{work_log} | 当前天使币: {score}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "checkin":
            run_checkin()
        elif sys.argv[1] == "work":
            run_work()
        else:
            print("Invalid command. Use 'checkin' or 'work'")
    else:
        run_checkin()
        run_work()
