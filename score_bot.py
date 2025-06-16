import requests
from bs4 import BeautifulSoup
from ocr_model import ocr_image_from_bytes
import logging

def login_and_fetch_scores(student_id, password, mode="latest"):
    session = requests.Session()
    base_url = "https://ecare.nfu.edu.tw"
    captcha_url = base_url + "/ext/authimg"

    # 取得驗證碼 + 辨識（最多重試 3 次）
    retry = 0
    captcha_text = ""
    while retry < 3:
        try:
            logging.info("🔄 嘗試取得驗證碼（第 %d 次）", retry + 1)
            captcha_resp = session.get(captcha_url, timeout=5)
            captcha_resp.raise_for_status()
            captcha_text = ocr_image_from_bytes(captcha_resp.content).strip()
            logging.info("🔍 辨識到的驗證碼：%s", captcha_text)
            if len(captcha_text) == 4:
                break
        except requests.exceptions.RequestException as e:
            logging.warning("⚠️ 驗證碼請求失敗：%s", e)
            return "❌ 無法連線到驗證碼伺服器，請稍後再試。"
        retry += 1

    if len(captcha_text) != 4:
        logging.error("❌ 驗證碼辨識失敗，無法進行登入")
        return "❌ 驗證碼辨識失敗，請稍後再試。"

    # 登入
    login_url = base_url + "/login/auth"
    payload = {
        "login_acc": student_id,
        "login_pwd": password,
        "login_chksum": captcha_text,
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": base_url + "/login",
    }

    try:
        logging.info("🔐 嘗試登入帳號 %s", student_id)
        res = session.post(login_url, data=payload, headers=headers, allow_redirects=False, timeout=5)
    except requests.exceptions.RequestException as e:
        logging.error("❌ 登入請求失敗：%s", e)
        return "❌ 無法登入系統，請稍後再試。"

    if res.status_code != 302:
        logging.warning("🚫 登入失敗，可能是帳號或密碼錯誤，HTTP 狀態碼：%d", res.status_code)
        return f"❌ 登入失敗，帳號或密碼可能錯誤。"

    logging.info("✅ 登入成功，準備進入成績查詢")

    # 取得成績頁面
    score_url = base_url + ("/aaiqry/studscore" if mode == "latest" else "/aaiqry/studscore?kind=2")
    try:
        logging.info("📄 請求成績頁面 URL：%s", score_url)
        score_resp = session.get(score_url, timeout=5)
        score_resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error("❌ 成績頁面請求失敗：%s", e)
        return "❌ 無法取得成績頁面，請稍後再試。"

    soup = BeautifulSoup(score_resp.text, "html.parser")
    score_section = soup.find('div', id='showmag')
    if not score_section:
        logging.warning("❌ 找不到成績內容區塊 (div#showmag)")
        return "❌ 找不到成績內容區塊。"

    table = score_section.find('table', class_='tbcls')
    if not table:
        logging.warning("❌ 找不到成績表格 (table.tbcls)")
        return "❌ 找不到成績表格。"

    table_rows = table.find_all('tr')
    logging.info("📊 成績表格共有 %d 列（含標題）", len(table_rows))
    result = []

    for row in table_rows[1:]:
        columns = row.find_all('td')
        try:
            if mode == "latest":
                if len(columns) < 11:
                    logging.debug("🔸 資料列欄位不足，跳過")
                    continue
                column_data = {
                    "課程名稱": columns[3].text.strip(),
                    "學分": columns[5].text.strip(),
                    "期中分數": columns[6].text.strip(),
                    "學期分數": columns[7].text.strip(),
                    "學期單科班排名": columns[8].text.strip(),
                }
            else:  # mode == "all"
                if len(columns) < 7:
                    logging.debug("🔸 歷年列欄位不足，跳過")
                    continue
                column_data = {
                    "課程學年": columns[1].text.strip(),
                    "課程學期": columns[2].text.strip(),
                    "課程名稱": columns[3].text.strip(),
                    "學分": columns[5].text.strip(),
                    "學期分數": columns[6].text.strip(),
                }
            result.append(column_data)
        except Exception as e:
            logging.exception("⚠️ 資料解析錯誤：%s", e)
            continue

    if not result:
        logging.info("🔍 查無任何成績資料")
        return "❌ 查無任何成績資料。"

    logging.info("✅ 成功擷取 %d 筆成績資料", len(result))
    return result
