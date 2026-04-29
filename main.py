from flask import Flask, request, jsonify
import requests
from openai import OpenAI
import os
import logging

# Хатоларни кузатиш (Лог)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- СОЗЛАМАЛАР ---
ID_INSTANCE = "7107601809"
API_TOKEN = os.environ.get("GREEN_API_TOKEN", "")

# РАҚАМЛАР
BOT_PHONE = "79099885383"       # Ботнинг ўз рақами
ADMIN_PHONE = "992927909698"    # Сизнинг шахсий рақамингиз

# OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY)

# Суҳбатлар тарихи
conversations = {}

def send_whatsapp(chatId, message):
    """WhatsApp га хабар юбориш функцияси"""
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendMessage/{API_TOKEN}"
    payload = {"chatId": chatId, "message": message}
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        logger.error(f"Хабар юборишда хато: {e}")
        return None

def get_order_history(phone):
    """Мижознинг бутун буюртма тарихини йиғиш"""
    if phone not in conversations:
        return "Тарих топилмади."
    
    history = ""
    for msg in conversations[phone]:
        role = "Мижоз" if msg["role"] == "user" else "Бот"
        if msg["role"] != "system":
            history += f"{role}: {msg['content']}\n"
    return history

def get_ai_response(phone, user_message):
    """OpenAI дан жавоб олиш ва инструкцияни мажбурлаш"""
    if phone not in conversations:
        conversations[phone] = [
            {"role": "system", "content": """Сен Zargo дўкони ёрдамчисисан. 
            Мижоз маҳсулотларни танлаб, манзил, телефон ва тўлов турини айтганидан кейин, 
            жавобингнинг энг охирида АЙНАН 'Буюртмангизни қабул қилдик' деган жумлани ёзишинг ШАРТ. 
            Бу жумласиз буюртма базага тушмайди. Қисқа ва дўстона гаплаш."""}
        ]
    
    conversations[phone].append({"role": "user", "content": user_message})
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversations[phone],
            temperature=0.7
        )
        ai_text = response.choices[0].message.content
        conversations[phone].append({"role": "assistant", "content": ai_text})
        return ai_text
    except Exception as e:
        return f"Хатолик юз берди: {str(e)}"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    # Фақат янги келган хабарларни қайта ишлаймиз
    if data.get("typeWebhook") == "incomingMessageReceived":
        chatId = data["senderData"]["chatId"]
        sender_number = data["senderData"]["sender"].split('@')[0]
        
        # 1. БОТ ЎЗИГА-ЎЗИ ЖАВОБ БЕРМАСЛИГИ УЧУН (Loop prevention)
        if sender_number == BOT_PHONE:
            return jsonify({"status": "ignored"}), 200

        message_data = data.get("messageData", {})
        text_data = message_data.get("textMessageData", {})
        user_message = text_data.get("textMessage", "")

        if user_message:
            # 2. Мижозга жавоб қайтариш
            ai_response = get_ai_response(chatId, user_message)
            send_whatsapp(chatId, ai_response)
            
            # 3. БУЮРТМАНИ АНИҚЛАШ ВА АДМИНГА ЙЎНАЛТИРИШ
            # Кичик ёки катта ҳарф билан ёзилганда ҳам ишлайдиган қилинди
            trigger = "буюртмангизни қабул қилдик"
            if trigger in ai_response.lower():
                full_history = get_order_history(chatId)
                admin_msg = (
                    f"🚀 *ЯНГИ БУЮРТМА!*\n"
                    f"📱 Мижоз: +{sender_number}\n"
                    f"--------------------------\n"
                    f"📝 *СУҲБАТ ТАФСИЛОТЛАРИ:*\n\n{full_history}"
                )
                
                # Админ рақамига юбориш
                send_whatsapp(f"{ADMIN_PHONE}@c.us", admin_msg)
                logger.info(f"Буюртма админга (+{ADMIN_PHONE}) юборилди.")

    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))