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
    msg = event.message.text.strip()

    if msg == "成績查詢":
        # 先回覆一則「查詢中請等待」
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="查詢中請等待...")]
                )
            )
        
        # 查成績
        student_id = "41241411"
        password = "$412414Qazwsx"
        result = login_and_fetch_scores(student_id, password)

        # 整理成文字
        if isinstance(result, list):
            text_lines = []
            for course in result:
                line = f"{course['課程名稱']} - 學期分數: {course['學期分數']}"
                text_lines.append(line)
            reply_text = "\n".join(text_lines)
        else:
            reply_text = "查詢成績時發生錯誤。"

        # 用 Push Message 再發一則真正成績訊息
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            push_request = PushMessageRequest(
                to=event.source.user_id,
                messages=[TextMessage(text=reply_text)]
            )
            line_bot_api.push_message(push_message_request=push_request)

    else:
        reply_text = "請輸入『成績查詢』來查詢你的成績。"
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))


