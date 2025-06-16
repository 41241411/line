import requests
from bs4 import BeautifulSoup

def login_and_fetch_scores(student_id, password):
    session = requests.Session()
    base_url = "https://ecare.nfu.edu.tw"
    
    # 取得驗證碼圖片（略，假設你有自己的 OCR 函式）
    captcha_url = base_url + "/ext/authimg"
    captcha_resp = session.get(captcha_url)
    
    from ocr_model import ocr_image_from_bytes
    captcha_text = ocr_image_from_bytes(captcha_resp.content).strip()
    
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
    
    # 不跟隨重定向，才能看到 302 狀態碼
    res = session.post(login_url, data=payload, headers=headers, allow_redirects=False)
    
    # 用 302 判斷登入成功
    if res.status_code == 302:
        print("✅ 登入成功，開始取得成績頁面")
        # 取得重定向的 cookie 和 session 後請求成績頁面
        score_url = base_url + "/aaiqry/studscore"
        score_resp = session.get(score_url)
        if score_resp.status_code != 200:
            return "❌ 無法取得成績頁面"
        
        soup = BeautifulSoup(score_resp.text, "html.parser")

        score_section = soup.find('div', id='showmag')
        table = score_section.find('table', class_='tbcls')  

        if not table:
            print("表格未找到或格式有誤")
            return []

        table_rows = table.find_all('tr')

        result = []
        for row in table_rows[1:]:  # 跳過表頭
            columns = row.find_all('td')
            if len(columns) < 11:
                print(f"警告: 某一列資料不足，跳過這一列")
                continue  # 如果列數不足，跳過這一行
            column_data = {
                "課程名稱": columns[3].text.strip(),
                "學分": columns[5].text.strip(),
                "期中分數": columns[6].text.strip(),
                "學期分數": columns[7].text.strip(),
                "學期單科班排名": columns[8].text.strip(),
            }
            result.append(column_data)

        return result
    else:
        return f"❌ 登入失敗，HTTP狀態碼：{res.status_code}"

