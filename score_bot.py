import requests
from bs4 import BeautifulSoup
from ocr_model import ocr_image_from_bytes

def login_and_fetch_scores(student_id, password, mode="latest"):
    session = requests.Session()
    base_url = "https://ecare.nfu.edu.tw"

    # 取得驗證碼
    captcha_url = base_url + "/ext/authimg"
    captcha_resp = session.get(captcha_url)

    from ocr_model import ocr_image_from_bytes
    captcha_text = ocr_image_from_bytes(captcha_resp.content).strip()

    # 如果驗證碼不是4碼就重試最多3次
    retry = 0
    while len(captcha_text) != 4 and retry < 3:
        retry += 1
        captcha_resp = session.get(captcha_url)
        captcha_text = ocr_image_from_bytes(captcha_resp.content).strip()

    if len(captcha_text) != 4:
        return "❌ 驗證碼辨識失敗，請稍後再試"

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

    res = session.post(login_url, data=payload, headers=headers, allow_redirects=False)

    if res.status_code == 302:
        print("✅ 登入成功，開始取得成績頁面")
        score_url = base_url + ("/aaiqry/studscore" if mode == "latest" else "/aaiqry/studscore?kind=2")
        score_resp = session.get(score_url)
        if score_resp.status_code != 200:
            return "❌ 無法取得成績頁面"

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(score_resp.text, "html.parser")
        score_section = soup.find('div', id='showmag')
        table = score_section.find('table', class_='tbcls')

        if not table:
            return "❌ 找不到成績表格"

        table_rows = table.find_all('tr')
        result = []

        for row in table_rows[1:]:
            columns = row.find_all('td')
            if mode == "latest":
                if len(columns) < 11:
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
                    continue
                column_data = {
                    "課程學年": columns[1].text.strip(),
                    "課程學期": columns[2].text.strip(),
                    "課程名稱": columns[3].text.strip(),
                    "學分": columns[5].text.strip(),
                    "學期分數": columns[6].text.strip(),
                }
            result.append(column_data)

        return result

    else:
        return f"❌ 登入失敗，HTTP 狀態碼：{res.status_code}"
