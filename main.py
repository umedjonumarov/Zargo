from flask import Flask, request, jsonify
import requests
from openai import OpenAI
import os

app = Flask(__name__)

# Green API маълумотлари
ID_INSTANCE = "7107601809"
API_TOKEN = os.environ.get("GREEN_API_TOKEN", "")

# Админ рақами (буюртмаларни қабул қилиш учун)
ADMIN_PHONE = "79099885383"

# OpenAI API
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY)

# Маҳсулотлар рўйхати
PRODUCTS = """
МАВЖУД МАҲСУЛОТЛАР:
- Нон - 3 сомони
- Тухум (10 дона) - 15 сомони
- Сут (1л) - 8 сомони
- Картошка (1кг) - 5 сомони
- Пиёз (1кг) - 4 сомони
- Сабзи (1кг) - 6 сомони
- Помидор (1кг) - 10 сомони
- Бодринг (1кг) - 8 сомони
- Гўшт (1кг) - 80 сомони
- Товуқ (1кг) - 35 сомони
- Гуруч (1кг) - 12 сомони
- Макарон (1кг) - 10 сомони
- Ёғ (1л) - 25 сомони
- Туз (1кг) - 3 сомони
- Шакар (1кг) - 9 сомони
- Чой (100г) - 15 сомони
"""

conversations = {}

def send_whatsapp(phone, message):
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendMessage/{API_TOKEN}"
    payload = {"chatId": f"{phone}@c.us", "message": message}
    response = requests.post(url, json=payload)
    return response.json()

def send_order_to_admin(customer_phone, order_summary):
    """Буюртмани админга юбориш"""
    admin_message = f"🆕 ЯНГИ БУЮРТМА!\n\n"
    admin_message += f"👤 Мижоз: {customer_phone}\n"
    admin_message += f"📋 Буюртма тафсилотлари:\n{order_summary}\n"
    admin_message += f"\n📞 Мижоз билан боғланинг: {customer_phone}"
    
    return send_whatsapp(ADMIN_PHONE, admin_message)

def get_order_summary(phone):
    """Мижознинг буюртма тарихини олиш"""
    if phone not in conversations:
        return ""
    
    # Фақат фойдаланувчи ва ассистент хабарларини олиш
    summary = ""
    for msg in conversations[phone]:
        if msg["role"] in ["user", "assistant"]:
            summary += f"{msg['role']}: {msg['content']}\n\n"
    
    return summary.strip()

def get_ai_response(phone, user_message):
    if phone not in conversations:
        conversations[phone] = [
            {"role": "system", "content": f"""Сен Zargo дўкони учун AI ёрдамчисан. 
Мижозларга озиқ-овқат буюртма беришда ёрдам берасан.
Зарзамин қишлоғи (Хужанд, Тожикистон) учун хизмат кўрсатасан.
Тожик ёки ўзбек тилида гаплашасан.
Қисқа ва дўстона жавоб бер.

{PRODUCTS}

Буюртма йиғилгач, мижоздан қуйидагиларни сўра:
1. Манзил
2. Телефон рақам
3. Тўлов усули (нақд/карта)"""}
        ]
    
    conversations[phone].append({"role": "user", "content": user_message})
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=conversations[phone],
        max_tokens=500
    )
    
    ai_text = response.choices[0].message.content
    conversations[phone].append({"role": "assistant", "content": ai_text})
    return ai_text

@app.route('/', methods=['GET'])
def home():
    return "Zargo Bot ishlayapti!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    if data.get("typeWebhook") == "incomingMessageReceived":
        phone = data["senderData"]["chatId"]
        message_data = data.get("messageData", {})
        text_data = message_data.get("textMessageData", {})
        user_message = text_data.get("textMessage", "")
        
        if user_message:
            ai_response = get_ai_response(phone, user_message)
            send_whatsapp(phone, ai_response)
            
            # Агар бот буюртмани тасдиқлаган бўлса, админга хабар юбориш
            if "Буюртмангизни қабул қилдик" in ai_response or "буюртмангизни қабул қилдик" in ai_response:
                order_summary = get_order_summary(phone)
                if order_summary:
                    send_order_to_admin(phone, order_summary)
    
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
