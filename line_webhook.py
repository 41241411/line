# line_webhook.py
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

app = Flask(__name__)

# 改為你的 LINE 設定
CHANNEL_ACCESS_TOKEN = 'zhrm3qGUvqKvcoxQCewe3LCWT5HYULuv863JjsAGrDr/MrCgZn6ycfbRiSoncjMnsbkc5vF/48tvo3ZDmtrRJai3nY8JhEBpktoo+mHK9MI8RSMQjW7en1OXrCIvGMMT3uHlVONG6Gn+dJbPbId2/wdB04t89/1O/w1cDnyilFU='
CHANNEL_SECRET = '7cbaf99b55226d5299d644baeff61efd'

handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

user_states = {}

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

    if msg == "成績查詢":
        user_states[user_id] = "awaiting_credentials"

        reply_text = "請輸入帳密，格式為：學號、密碼（例如：11111111、123456789）"
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
        return
    
    # 如果使用者先前已輸入「成績查詢」，現在應該給帳密
    if user_states.get(user_id) == "awaiting_credentials":
        if "、" in msg:
            try:
                student_id, password = msg.split("、")
                student_id = student_id.strip()
                password = password.strip()

                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="查詢中請稍候...")]
                        )
                    )

                result = login_and_fetch_scores(student_id, password)

                if isinstance(result, list):
                    text_lines = [
                        f"{course['課程名稱']} - 學期分數: {course['學期分數']}"
                        for course in result
                    ]
                    reply_text = "\n".join(text_lines)
                else:
                    reply_text = "查詢成績失敗，請確認帳密是否正確。"

                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).push_message(
                        push_message_request=PushMessageRequest(
                            to=user_id,
                            messages=[TextMessage(text=reply_text)]
                        )
                    )
            except Exception:
                reply_text = "格式錯誤，請輸入正確的帳密（例如：41241411、$412414Qazwsx）"
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

        # 清除使用者狀態
        user_states.pop(user_id, None)
        return

    # 預設回覆
    default_reply = "請輸入『成績查詢』來開始查詢流程。"
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=default_reply)]
            )
        )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)


