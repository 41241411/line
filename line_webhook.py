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
from linebot.v3.messaging.models import PushMessageRequest, TextMessage
import os
import threading

# 設定 logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.getenv('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.getenv('CHANNEL_SECRET')

handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

user_states = {}

def async_fetch_and_push(user_id, student_id, password, mode):
    try:
        result = login_and_fetch_scores(student_id, password, mode=mode)
        logging.info(f"查詢結果: {result}")
        if isinstance(result, list) and result:
            text_lines = []
            for course in result[:50]:  # 最多50筆避免過長
                line = " - ".join(f"{key}: {value}" for key, value in course.items())
                text_lines.append(line)
            reply_text = "\n".join(text_lines)
        else:
            reply_text = "查無資料或查詢失敗，請確認帳密或稍後再試。"

    except Exception as e:
        logging.error(f"查詢發生錯誤: {e}", exc_info=True)
        reply_text = f"查詢發生錯誤: {e}"

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).push_message(
            push_message_request=PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=reply_text)]
            )
        )

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    msg = event.message.text.strip()
    logging.info(f"收到訊息：user_id={user_id}, message={msg}")

    if msg in ["成績查詢", "歷年成績查詢"]:
        user_states[user_id] = "latest" if msg == "成績查詢" else "all"
        reply_text = "請輸入帳密，格式為：學號、密碼（例如：11111111、123456789）"
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

                # 先快速回覆
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="查詢中請稍候...")]
                        )
                    )

                # 啟動背景執行緒查詢並推播
                threading.Thread(
                    target=async_fetch_and_push,
                    args=(user_id, student_id, password, mode),
                    daemon=True
                ).start()

            except Exception:
                logging.exception("帳密格式錯誤")
                reply_text = "請輸入帳密，格式為：學號、密碼（例如：11111111、123456789）"
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply_text)]
                        )
                    )
        else:
            reply_text = "請使用全形逗號「、」分隔帳號與密碼。"
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)]
                    )
                )

        user_states.pop(user_id, None)
        return

    # 預設回覆
    default_reply = "請輸入「成績查詢」或「歷年成績查詢」開始查詢流程。"
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=default_reply)]
            )
        )
