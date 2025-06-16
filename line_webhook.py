import logging
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from score_bot import login_and_fetch_scores
from linebot.v3.messaging.models import PushMessageRequest
import os
import threading

# 設定 logging 格式與級別
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.getenv('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.getenv('CHANNEL_SECRET')

handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

# 記錄使用者查詢狀態
user_states = {}

def async_fetch_and_push(user_id, student_id, password, mode):
    logging.info(f"📤 背景查詢啟動：user_id={user_id}, mode={mode}")
    try:
        result = login_and_fetch_scores(student_id, password, mode=mode)
        logging.info(f"📊 查詢結果回傳型態：{type(result)}")
        logging.info(f"📊 查詢結果內容：{result}")

        if isinstance(result, list) and result:
            text_lines = []
            for course in result[:50]:  # 限制最多50筆
                line = " - ".join(f"{key}: {value}" for key, value in course.items())
                text_lines.append(line)
            reply_text = "\n".join(text_lines)
        else:
            reply_text = result if isinstance(result, str) else "查無資料或查詢失敗，請確認帳密或稍後再試。"

    except Exception as e:
        logging.exception("❌ 查詢發生例外錯誤")
        reply_text = f"查詢發生錯誤: {e}"

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).push_message(
            push_message_request=PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=reply_text)]
            )
        )
        logging.info("📨 成績推播完成")

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    logging.info("📥 收到 webhook 請求")

    try:
        handler.handle(body, signature)
        logging.info("✅ webhook 驗證成功")
    except InvalidSignatureError:
        logging.warning("🚫 webhook 驗證失敗")
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    msg = event.message.text.strip()
    logging.info(f"💬 使用者訊息：user_id={user_id}, message={msg}")

    if msg in ["成績查詢", "歷年成績查詢"]:
        user_states[user_id] = "latest" if msg == "成績查詢" else "all"
        reply_text = "請輸入帳密，格式為：學號、密碼（例如：11111111、123456789）"
        logging.info(f"🔧 設定 user_states[{user_id}] = {user_states[user_id]}")
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
        return

    if user_id in user_states:
        if "、" in msg:
            try:
                student_id, password = [x.strip() for x in msg.split("、", 1)]
                mode = user_states[user_id]
                logging.info(f"🧾 收到帳密 student_id={student_id}, 啟動查詢模式={mode}")

                # 快速回覆
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="查詢中請稍候...")]
                        )
                    )

                # 背景執行查詢
                threading.Thread(
                    target=async_fetch_and_push,
                    args=(user_id, student_id, password, mode),
                    daemon=True
                ).start()

            except Exception as e:
                logging.exception("❌ 帳密格式解析失敗")
                reply_text = "請輸入帳密，格式為：學號、密碼（例如：11111111、123456789）"
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply_text)]
                        )
                    )
        else:
            logging.warning("⚠️ 使用者輸入未含全形逗號")
            reply_text = "請使用全形逗號「、」分隔帳號與密碼。"
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)]
                    )
                )

        # 清除查詢狀態
        user_states.pop(user_id, None)
        logging.info(f"🧹 清除 user_states[{user_id}]")
        return

    # 預設回覆
    default_reply = "請輸入「成績查詢」或「歷年成績查詢」開始查詢流程。"
    logging.info("📎 回傳預設說明訊息")
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=default_reply)]
            )
        )
