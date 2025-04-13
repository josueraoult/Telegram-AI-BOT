import telebot
from telebot import types
import requests
import json
import base64
import io
import speech_recognition as sr
from pydub import AudioSegment

# === CONFIG ===
TELEGRAM_TOKEN = '7728370298:AAH2LROduZRfymFowV3m4c9NE9hlx7ZzgKA'
GEMINI_API_KEY = 'AIzaSyAArErZGDDJx7DJwExgY_pPWmN7Tjai8nk'
RESEMBLE_API_KEY = 'ev6lZTrSDKV5TK2toXibxQtt'
CATBOX_UPLOAD_URL = "https://jonell01-ccprojectsapihshs.hf.space/api/catmoe?url="

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_states = {}  # stocker l'état des utilisateurs

# === LANGUE AU DÉMARRAGE ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Français", callback_data='lang_fr'),
               types.InlineKeyboardButton("English", callback_data='lang_en'))
    bot.send_message(message.chat.id, "Choisis ta langue / Choose your language:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def set_language(call):
    user_id = call.from_user.id
    lang = call.data.split('_')[1]
    user_states[user_id] = {'lang': lang, 'feature': None}
    send_main_menu(call.message)

def send_main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("GPT AI")
    bot.send_message(message.chat.id, "Choisis une fonctionnalité :", reply_markup=markup)

# === FONCTION GPT AI ===
@bot.message_handler(func=lambda m: m.text == "GPT AI")
def activate_gpt(m):
    user_states[m.chat.id] = user_states.get(m.chat.id, {})
    user_states[m.chat.id]['feature'] = 'gpt_ai'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔙 Retour")
    bot.send_message(m.chat.id, "Tu es dans GPT AI. Envoie du texte ou audio :", reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('feature') == 'gpt_ai', content_types=['text'])
def handle_text(message):
    prompt = message.text
    gpt_response = ask_gemini(prompt)
    bot.send_message(message.chat.id, gpt_response)
    audio_url = text_to_speech(gpt_response)
    bot.send_voice(message.chat.id, audio=audio_url)

@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    if user_states.get(message.chat.id, {}).get('feature') != 'gpt_ai':
        return

    file_info = bot.get_file(message.voice.file_id)
    file_url = f'https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}'
    voice_data = requests.get(file_url).content

    # Conversion OGG -> WAV
    audio = AudioSegment.from_file(io.BytesIO(voice_data), format="ogg")
    wav_io = io.BytesIO()
    audio.export(wav_io, format="wav")
    wav_io.seek(0)

    # Reconnaissance vocale
    text = speech_to_text(wav_io)
    if not text:
        return bot.send_message(message.chat.id, "Erreur lors de la conversion de l’audio.")

    gpt_response = ask_gemini(text)
    bot.send_message(message.chat.id, gpt_response)
    audio_url = text_to_speech(gpt_response)
    bot.send_voice(message.chat.id, audio=audio_url)

# === RETOUR AU MENU ===
@bot.message_handler(func=lambda m: m.text == "🔙 Retour")
def back_to_menu(message):
    user_states[message.chat.id]['feature'] = None
    send_main_menu(message)

# === GEMINI ===
def ask_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json().get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'Pas de réponse')

# === SPEECH TO TEXT ===
def speech_to_text(wav_io):
    r = sr.Recognizer()
    with sr.AudioFile(wav_io) as source:
        audio = r.record(source)
    try:
        return r.recognize_google(audio, language='fr-FR')
    except:
        return None

# === TEXT TO SPEECH AVEC RESEMBLE ===
def text_to_speech(text):
    headers = {
        "Authorization": f"Token {RESEMBLE_API_KEY}",
        "Content-Type": "application/json"
    }
    project = requests.get("https://app.resemble.ai/api/v2/projects", headers=headers).json()['items'][0]
    voice = requests.get("https://app.resemble.ai/api/v2/voices", headers=headers).json()['items'][0]
    data = {
        "project_uuid": project['uuid'],
        "voice_uuid": voice['uuid'],
        "body": text
    }
    response = requests.post("https://app.resemble.ai/api/v2/clips", headers=headers, json=data)
    audio_url = response.json()['item']['audio_src']
    return catbox_upload(audio_url)

# === UPLOAD CATBOX ===
def catbox_upload(audio_url):
    upload_url = CATBOX_UPLOAD_URL + audio_url
    response = requests.get(upload_url)
    return response.text.strip()

# === DÉMARRAGE DU BOT ===
print("Bot lancé...")
bot.polling()
