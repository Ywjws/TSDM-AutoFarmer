import httpx
import re
import urllib.parse
import time
import os
import sys
from bs4 import BeautifulSoup

# 直接从环境变量获取配置
COOKIE = os.environ['TSDM_COOKIE']

def send(title, message):
    """日志报告函数"""
    print(f"【{title}】{message}")

def tsdm_check_in():
    log = ""
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Cookie": COOKIE,
        "Referer": "https://www.tsdm39.com/forum.php",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
    }

    with httpx.Client(headers=headers) as client:
        try:
            # 获得formhash
            response = client.get("https://www.tsdm39.com/forum.php")
            pattern = r'formhash=(.+?)"'
            match = re.search(pattern, response.text)
            if match:
                formhash_value = match.group(1)
                encoded_formhash = urllib.parse.quote(formhash_value)

                # 签到
                payload = {"formhash": encoded_formhash, "qdxq": "kx", "qdmode": "3", "todaysay": "", "fastreply": "1"}
                response = client.post(
                    "https://www.tsdm39.com/plugin.php?id=dsu_paulsign%3Asign&operation=qiandao&infloat=1&sign_as=1&inajax=1",
                    data=payload)
                
                if "签到成功" in response.text:
                    log = "✅ 签到成功"
                else:
                    log = "❌ 签到异常: 未知响应"
            else:
                log = "❌ 签到异常: 获取formhash失败"
        except Exception as e:
            log = f"❌ 签到异常: {str(e)}"
        
        send("签到结果", log)
        return log

def tsdm_work():
    log = ""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko',
        'cookie': COOKIE,
        'connection': 'Keep-Alive',
        'x-requested-with': 'XMLHttpRequest',
        'referer': 'https://www.tsdm39.net/plugin.php?id=np_cliworkdz:work',
        'content-type': 'application/x-www-form-urlencoded'
    }

    with httpx.Client(headers=headers) as client:
        try:
            # 查询是否可以打工
            response = client.get("https://www.tsdm39.com/plugin.php?id=np_cliworkdz%3Awork&inajax=1", headers=headers)
            pattern = r"您需要等待\d+小时\d+分钟\d+秒后即可进行。"
            match = re.search(pattern, response.text)
            if match:
                log = f"⏳ 打工冷却中: {match.group()}"
            else:
                # 必须连续6次！
                for i in range(6):
                    response = client.post("https://www.tsdm39.com/plugin.php?id=np_cliworkdz:work", 
                                        headers=headers, 
                                        data={"act": "clickad"})
                    time.sleep(3)

                # 获取奖励
                response = client.post("https://www.tsdm39.com/plugin.php?id=np_cliworkdz:work", 
                                    headers=headers, 
                                    data={"act": "getcre"})
                log = "✅ 打工完成"
        except Exception as e:
            log = f"❌ 打工异常: {str(e)}"
        
        send("打工结果", log)
        return log

def get_score():
    try:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Cookie": COOKIE,
            "Referer": "https://www.tsdm39.com/forum.php",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
        }
        with httpx.Client(headers=headers) as client:
            response = client.get("https://www.tsdm39.com/home.php?mod=spacecp&ac=credit&showcredit=1")
            soup = BeautifulSoup(response.text, 'html.parser')
            ul_element = soup.find('ul', class_='creditl')
            li_element = ul_element.find('li', class_='xi1')
            angel_coins = li_element.get_text(strip=True).replace("天使币:", "").strip()
            return angel_coins
    except Exception as e:
        send("查询异常", f"❌ 获取天使币失败: {str(e)}")
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
