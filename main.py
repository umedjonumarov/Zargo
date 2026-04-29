from flask import Flask, request, jsonify
import requests
from openai import OpenAI
import os
import logging
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- SOZLAMALAR ---
ID_INSTANCE = "7107601809"
API_TOKEN = os.environ.get("GREEN_API_TOKEN", "")
BOT_PHONE = "79099885383"
ADMIN_PHONE = "992927909698"
APP_URL = "https://zargo.onrender.com"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY)

conversations = {}

SYSTEM_PROMPT = """Сен Zargo дўкони ёрдамчисисан. Хужанд вилояти, Зарзамин қишлоғига уйга озиқ-овқат етказиб берамиз. Жавобларинг қисқа, дўстона ва тожик ёки ўзбек тилида бўлсин.

МАҲСУЛОТЛАР РЎЙХАТИ ВА НАРХЛАР:
- Нон — 3 сомони
- Тухум (10 дона) — 15 сомони
- Сут (1л) — 8 сомони
- Картошка (1кг) — 5 сомони
- Пиёз (1кг) — 4 сомони
- Сабзи (1кг) — 6 сомони
- Помидор (1кг) — 10 сомони
- Бодринг (1кг) — 8 сомони
- Гўшт (1кг) — 80 сомони
- Товуқ (1кг) — 35 сомони
- Гуруч (1кг) — 12 сомони
- Макарон (1кг) — 10 сомони
- Ёғ (1л) — 25 сомони
- Туз (1кг) — 3 сомони
- Шакар (1кг) — 9 сомони
- Чой (100г) — 15 сомони

БУЮРТМА ЖАРАЁНИ:
1. Мижоз маҳсулотларни танлайди
2. Манзилини айтади
3. Телефон рақамини айтади
4. Тўлов усулини айтади (нақд / карта)
5. Сен тасдиқлайсан ва жавобингнинг охирида АЙНАН "Буюртмангизни қабул қилдик" деб ёзасан.

ДИҚҚАТ: "Буюртмангизни қабул қилдик" жумласини ФАҚАТ мижоз манзил, телефон ва тўлов усулини айтганда ёзасан."""


def send_whatsapp(chat_id, message):
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendMessage/{API_TOKEN}"
    payload = {"chatId": chat_id, "message": message}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        logger.info(f"Yuborildi {chat_id}: {resp.status_code}")
        return resp.json()
    except Exception as e:
        logger.error(f"Yuborishda xato: {e}")
        return None


def get_order_history(phone):
    if phone not in conversations:
        return "Tarix topilmadi."
    history = ""
    for msg in conversations[phone]:
        if msg["role"] == "user":
            history += f"Mijoz: {msg['content']}\n"
        elif msg["role"] == "assistant":
            history += f"Bot: {msg['content']}\n"
    return history


def get_ai_response(phone, user_message):
    if phone not in conversations:
        conversations[phone] = [{"role": "system", "content": SYSTEM_PROMPT}]

    conversations[phone].append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversations[phone],
            temperature=0.7,
            max_tokens=500
        )
        ai_text = response.choices[0].message.content
        conversations[phone].append({"role": "assistant", "content": ai_text})
        return ai_text
    except Exception as e:
        logger.error(f"OpenAI xato: {e}")
        return "Kechirasiz, texnik xatolik yuz berdi. Qaytadan urinib ko'ring."


def keep_alive():
    """Render free tier uxlamasligi uchun har 10 daqiqada o'ziga ping"""
    while True:
        time.sleep(600)
        try:
            requests.get(f"{APP_URL}/ping", timeout=10)
            logger.info("Keep-alive ping yuborildi")
        except Exception as e:
            logger.warning(f"Keep-alive ping xato: {e}")


@app.route('/')
def index():
    return "Zargo Bot ishlayapti! ✅", 200


@app.route('/ping')
def ping():
    return "pong", 200


@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("=== WEBHOOK SO'ROV KELDI ===")

    data = request.json
    if not data:
        logger.warning("Bo'sh so'rov keldi")
        return jsonify({"status": "empty"}), 200

    logger.info(f"Webhook turi: {data.get('typeWebhook')}")

    if data.get("typeWebhook") != "incomingMessageReceived":
        return jsonify({"status": "ignored"}), 200

    try:
        sender_data = data.get("senderData", {})
        chat_id = sender_data.get("chatId", "")
        sender = sender_data.get("sender", "")
        sender_number = sender.split('@')[0] if sender else ""

        logger.info(f"Yuboruvchi: {sender_number}, chatId: {chat_id}")

        # Bot o'ziga javob bermasin
        if sender_number == BOT_PHONE:
            logger.info("Bot o'z xabari — e'tiborga olinmadi")
            return jsonify({"status": "ignored"}), 200

        message_data = data.get("messageData", {})

        # Matn xabarini olish
        user_message = ""
        if "textMessageData" in message_data:
            user_message = message_data["textMessageData"].get("textMessage", "")
        elif "extendedTextMessageData" in message_data:
            user_message = message_data["extendedTextMessageData"].get("text", "")

        if not user_message:
            logger.info("Matn xabari yo'q — e'tiborga olinmadi")
            return jsonify({"status": "no_text"}), 200

        logger.info(f"Xabar: {user_message[:100]}")

        ai_response = get_ai_response(chat_id, user_message)
        logger.info(f"AI javob: {ai_response[:100]}")

        send_whatsapp(chat_id, ai_response)

        # Buyurtma aniqlash
        if "буюртмангизни қабул қилдик" in ai_response.lower():
            history = get_order_history(chat_id)
            admin_msg = (
                f"🛒 *YANGI BUYURTMA!*\n"
                f"📱 Mijoz: +{sender_number}\n"
                f"{'─' * 25}\n"
                f"{history}"
            )
            send_whatsapp(f"{ADMIN_PHONE}@c.us", admin_msg)
            logger.info(f"Buyurtma adminga yuborildi: +{ADMIN_PHONE}")

    except Exception as e:
        logger.error(f"Webhook xato: {e}", exc_info=True)

    return jsonify({"status": "ok"}), 200


@app.route('/setup-webhook', methods=['GET'])
def setup_webhook():
    """Green API da webhook URL ni o'rnatish"""
    webhook_url = f"{APP_URL}/webhook"
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/setSettings/{API_TOKEN}"
    payload = {
        "webhookUrl": webhook_url,
        "webhookUrlToken": "",
        "delaySendMessagesMilliseconds": 500,
        "markIncomingMessagesReaded": "yes",
        "incomingWebhook": "yes",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        result = resp.json()
        logger.info(f"Webhook sozlandi: {result}")
        return jsonify({"webhook_url": webhook_url, "result": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/check-settings', methods=['GET'])
def check_settings():
    """Green API sozlamalarini tekshirish"""
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/getSettings/{API_TOKEN}"
    try:
        resp = requests.get(url, timeout=10)
        return jsonify(resp.json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Keep-alive thread ni ishga tushirish
    t = threading.Thread(target=keep_alive, daemon=True)
    t.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
