import eventlet
eventlet.monkey_patch()
from data_aggregator import vitals_aggregator
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, send_file
from flask_socketio import SocketIO
import pandas as pd
from datetime import datetime, timedelta
import os
from nlp_engine import nlp_engine
import matplotlib
import uuid
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import threading
import time
import re
import boto3
import json
from io import StringIO
from dotenv import load_dotenv
import logging
from functools import wraps
import pickle
import requests
import hashlib
import csv
import textwrap
import tempfile
import shutil
import mimetypes
import smtplib
from PIL import Image, ImageDraw, ImageFont
from email.message import EmailMessage
from mqtt_client import MQTTClient
from mqtt_config import MQTTConfig
from werkzeug.utils import secure_filename
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "remoni-secret-key-2024")
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

app.config.update(
    SESSION_COOKIE_SECURE=False,  # Set to True if using HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),  # Session lasts 24 hours
    SESSION_REFRESH_EACH_REQUEST=True 
)
# AWS S3 Configuration
S3_KEY_ID = os.getenv("S3_KEY_ID", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "remonitest")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
PATIENT_ID = os.getenv("PATIENT_ID", "00001")
S3_POLL_INTERVAL = 5
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID_ENV = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_FORWARD_CHAT = os.getenv("TELEGRAM_FORWARD_CHAT", "true").strip().lower() in (
    "1", "true", "yes", "y", "on"
)
TELEGRAM_CHAT_ID_FILE = os.path.join('static', 'local_data', 'telegram_chat_id.json')
telegram_chat_id_cache = None
telegram_chat_id_lock = threading.Lock()
telegram_last_update_fetch = 0
telegram_last_update_id = None
telegram_clients = {}
telegram_clients_lock = threading.Lock()
TELEGRAM_ALERT_CARD_DIR = os.path.join('static', 'local_data', 'telegram_alert_cards')

# User database file
USERS_FILE = 'users_database.pkl'
PROCESSED_FALLS_FILE = 'processed_fall_alerts.json'
PROCESSED_EMERGENCY_FILE = 'processed_emergency_alerts.json'
ADVICE_FILE = os.path.join('static', 'local_data', 'doctor_advices.json')
WEEKLY_ANALYSIS_FILE = os.path.join('static', 'local_data', 'weekly_analysis_data.json')
WEEKLY_REPORTS_DIR = os.path.join('static', 'local_data', 'weekly_reports')
DOCTOR_PROFILE_UPLOAD_DIR = os.path.join('static', 'local_data', 'doctor_profiles')
REMONI_ADVICE_INTERVAL_DAYS = 3
REMONI_ADVICE_LOOKBACK_DAYS = 3
REMONI_ADVICE_CHECK_INTERVAL_SECONDS = 6 * 60 * 60
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME).strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() in ("1", "true", "yes", "on")

emergency_alerts = []
patient_meta_cache = None
patient_meta_cache_lock = threading.Lock()
advice_lock = threading.Lock()
watch_status_by_patient = {}
watch_status_lock = threading.Lock()
WATCH_STATUS_MAX_AGE_MINUTES = 8
watch_status_request_lock = threading.Lock()
last_watch_status_request = {}
WATCH_STATUS_REQUEST_COOLDOWN_SECONDS = 30
librelink_status_lock = threading.Lock()
librelink_last_check = {}
LIBRELINK_CHECK_COOLDOWN_SECONDS = 120


def load_advices():
    """Load stored doctor advices from local JSON file."""
    default_text = "eat more rice"
    if not os.path.exists(ADVICE_FILE):
        default_entry = {
            PATIENT_ID: [{
                "id": str(uuid.uuid4()),
                "text": default_text,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "time": datetime.now().strftime("%I:%M %p"),
                "source": "Doctor",
                "approved": True,
                "approved_by": "system",
                "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }]
        }
        save_advices(default_entry)
        return default_entry
    try:
        with open(ADVICE_FILE, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
            if isinstance(data, dict):
                changed = False
                for pid, advices in list(data.items()):
                    if str(pid) != str(PATIENT_ID) and isinstance(advices, list):
                        filtered = [
                            a for a in advices
                            if str(a.get("source", "")).lower() != "remoni"
                        ]
                        if len(filtered) != len(advices):
                            data[pid] = filtered
                            changed = True
                if changed:
                    save_advices(data)
                if not data.get(PATIENT_ID):
                    data[PATIENT_ID] = [{
                        "id": str(uuid.uuid4()),
                        "text": default_text,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "time": datetime.now().strftime("%I:%M %p"),
                        "source": "Doctor",
                        "approved": True,
                        "approved_by": "system",
                        "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }]
                    save_advices(data)
                return data
    except Exception as e:
        logger.error(f"Error loading advices: {e}")
    return {}


def save_advices(data):
    """Save doctor advices to local JSON file."""
    try:
        os.makedirs(os.path.dirname(ADVICE_FILE), exist_ok=True)
        with open(ADVICE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving advices: {e}")


def _get_recent_date_list(days):
    """Return a list of YYYY-MM-DD strings for the last N days (inclusive)."""
    base = datetime.now().date()
    return [(base - timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(days)]


def _get_latest_remoni_advice_time(advices):
    """Return the latest Remoni advice datetime if available."""
    latest = None
    for item in advices:
        if str(item.get("source", "")).lower() != "remoni":
            continue
        candidate = parse_timestamp(item.get("generated_at") or item.get("approved_at"))
        if not candidate and item.get("date"):
            candidate = parse_timestamp(f"{item.get('date')} {item.get('time') or ''}".strip())
        if candidate and (latest is None or candidate > latest):
            latest = candidate
    return latest


def _build_remoni_advice_text(vitals_df, glucose_df):
    """Generate a Remoni advice from recent vitals and glucose."""
    notes = []
    lookback_days = REMONI_ADVICE_LOOKBACK_DAYS
    period_text = f"the past {lookback_days} days"

    if not glucose_df.empty and "glucose" in glucose_df.columns:
        glucose_values = pd.to_numeric(glucose_df["glucose"], errors="coerce").dropna()
        if not glucose_values.empty:
            avg_glucose = glucose_values.mean()
            max_glucose = glucose_values.max()
            min_glucose = glucose_values.min()
            if avg_glucose > 180 or max_glucose > 250:
                notes.append(
                    f"Over {period_text}, your glucose has been high "
                    f"(avg {int(round(avg_glucose))} mg/dL). "
                    "Limit sugary foods and follow your diabetes plan."
                )
            elif avg_glucose < 70 or min_glucose < 65:
                notes.append(
                    f"Over {period_text}, your glucose has been low "
                    f"(avg {int(round(avg_glucose))} mg/dL). "
                    "Consider a small snack and monitor closely."
                )

    if not vitals_df.empty:
        hr = pd.to_numeric(vitals_df.get("heart_rate"), errors="coerce").dropna()
        spo2 = pd.to_numeric(vitals_df.get("spo2"), errors="coerce").dropna()
        temp = pd.to_numeric(vitals_df.get("skin_temperature"), errors="coerce").dropna()
        resp = pd.to_numeric(vitals_df.get("respiratory_rate"), errors="coerce").dropna()
        sys_bp = pd.to_numeric(vitals_df.get("systolic_pressure"), errors="coerce").dropna()
        dia_bp = pd.to_numeric(vitals_df.get("diastolic_pressure"), errors="coerce").dropna()

        if not sys_bp.empty and not dia_bp.empty:
            avg_sys = sys_bp.mean()
            avg_dia = dia_bp.mean()
            if avg_sys > 140 or avg_dia > 90:
                notes.append(
                    f"Over {period_text}, your average blood pressure is "
                    f"{int(round(avg_sys))}/{int(round(avg_dia))}. "
                    "Limit salty foods, stay hydrated, and monitor daily."
                )

        if not hr.empty and hr.mean() > 110:
            notes.append(
                f"Over {period_text}, your heart rate has been elevated "
                f"(avg {int(round(hr.mean()))} bpm). "
                "Rest and avoid strenuous activity."
            )
        if not spo2.empty and spo2.mean() < 92:
            notes.append(
                f"Over {period_text}, your oxygen saturation looks low "
                f"(avg {int(round(spo2.mean()))}%). "
                "Rest and contact your care team if this continues."
            )
        if not temp.empty and temp.mean() > 37.8:
            notes.append(
                f"Over {period_text}, your temperature has been a bit high "
                f"(avg {temp.mean():.1f} C). "
                "Stay hydrated and monitor for symptoms."
            )
        if not resp.empty and (resp.mean() < 10 or resp.mean() > 22):
            notes.append(
                f"Over {period_text}, your breathing rate is outside the usual range "
                f"(avg {resp.mean():.1f} breaths/min). "
                "Take it easy and monitor."
            )

    if not notes:
        notes.append(
            f"Over {period_text}, your readings look stable. "
            "Keep regular meals, hydrate well, and stay lightly active."
        )

    return " ".join(notes)


def _polite_advice_text(text):
    """Normalize advice tone to be polite and friendly without forcing 'Please'."""
    if not text:
        return ""
    cleaned = str(text).strip()
    if not cleaned:
        return ""
    cleaned = cleaned if cleaned.endswith(".") else f"{cleaned}."
    lower = cleaned.lower()
    if lower.startswith(("please ", "kindly ", "consider ", "it may help", "it might help")):
        return _capitalize_sentences(cleaned)
    # Add a gentle, clinical suggestion prefix.
    if lower.startswith(("over ", "recent ", "your ")):
        return _capitalize_sentences(cleaned)
    return _capitalize_sentences(f"It may help to {cleaned[0].lower() + cleaned[1:]}")


def _capitalize_sentences(text):
    """Capitalize the first letter of each sentence."""
    if not text:
        return ""
    normalized = re.sub(r'\s+', ' ', text.strip())
    normalized = re.sub(r'([.!?])(?=\S)', r'\1 ', normalized)
    sentences = re.split(r'([.!?]\s+)', normalized)
    out = []
    for i in range(0, len(sentences), 2):
        chunk = sentences[i].strip()
        if not chunk:
            continue
        first = chunk[0].upper()
        out.append(first + chunk[1:])
        if i + 1 < len(sentences):
            out.append(sentences[i + 1])
    return "".join(out).strip()


def maybe_generate_remoni_advice(patient_id):
    """Generate a Remoni advice entry if the interval has elapsed."""
    if not s3_client:
        return False

    with advice_lock:
        data = load_advices()
        advices = data.get(str(patient_id), [])
        latest_time = _get_latest_remoni_advice_time(advices)
        if latest_time and datetime.now() - latest_time < timedelta(days=REMONI_ADVICE_INTERVAL_DAYS):
            return False

    date_list = _get_recent_date_list(REMONI_ADVICE_LOOKBACK_DAYS)
    vitals_df = load_patient_vitals_from_s3(patient_id, date_list=date_list)
    glucose_df = load_patient_glucose_from_s3(patient_id, date_list=date_list)

    if not vitals_df.empty and "time_stamp" in vitals_df.columns:
        cutoff = datetime.now() - timedelta(days=REMONI_ADVICE_LOOKBACK_DAYS)
        vitals_df = vitals_df[vitals_df["time_stamp"] >= cutoff]

    if not glucose_df.empty and "time_stamp" in glucose_df.columns:
        cutoff = datetime.now() - timedelta(days=REMONI_ADVICE_LOOKBACK_DAYS)
        glucose_df = glucose_df[glucose_df["time_stamp"] >= cutoff]

    if vitals_df.empty and glucose_df.empty:
        return False

    advice_text = _polite_advice_text(_build_remoni_advice_text(vitals_df, glucose_df))
    now = datetime.now()
    advice_item = {
        "id": str(uuid.uuid4()),
        "text": advice_text,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%I:%M %p"),
        "source": "Remoni",
        "approved": False,
        "approved_by": None,
        "approved_at": None,
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S")
    }

    with advice_lock:
        data = load_advices()
        data.setdefault(str(patient_id), [])
        data[str(patient_id)].insert(0, advice_item)
        save_advices(data)

    return True


def start_remoni_advice_scheduler():
    """Start background scheduler that generates Remoni advice every few days."""
    def _loop():
        while True:
            try:
                # Only generate Remoni advice for the active real patient.
                for pid in [PATIENT_ID]:
                    try:
                        maybe_generate_remoni_advice(pid)
                    except Exception as e:
                        logger.error(f"Remoni advice error for {pid}: {e}")
                time.sleep(REMONI_ADVICE_CHECK_INTERVAL_SECONDS)
            except Exception as e:
                logger.error(f"Remoni advice scheduler error: {e}")
                time.sleep(REMONI_ADVICE_CHECK_INTERVAL_SECONDS)

    threading.Thread(target=_loop, daemon=True).start()

def load_patient_meta():
    """Load patient meta data from local CSV (cached)."""
    global patient_meta_cache
    with patient_meta_cache_lock:
        if patient_meta_cache is not None:
            return patient_meta_cache

        csv_path = os.path.join(app.root_path, 'static', 'local_data', 'fake_patient_meta_data.csv')
        patients = []
        try:
            with open(csv_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    patient_id = normalize_patient_id(row.get('patient_id'))
                    row['patient_id'] = patient_id
                    if 'name' in row and isinstance(row['name'], str):
                        row['name'] = row['name'].strip()
                    phone = row.get('phone')
                    if isinstance(phone, str) and 'E' in phone.upper():
                        try:
                            row['phone'] = str(int(float(phone)))
                        except Exception:
                            row['phone'] = phone
                    patients.append(row)
        except Exception as e:
            logger.error(f"Error loading patient meta CSV: {e}")
        patient_meta_cache = patients
        return patients
pending_mqtt_glucose_requests = {}
# ✅ NEW: Track active timeout threads to prevent duplicates
active_timeout_threads = set()
timeout_threads_lock = threading.Lock()
pending_vitals_requests = {}
last_mqtt_vitals_received = {}
glucose_source_by_patient = {}
def load_processed_emergency_alerts():
    """Load list of already processed emergency alert IDs"""
    if os.path.exists(PROCESSED_EMERGENCY_FILE):
        try:
            with open(PROCESSED_EMERGENCY_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    processed_ids = set(data.get('processed_ids', []))
                elif isinstance(data, list):
                    processed_ids = set(data)
                else:
                    processed_ids = set()
                logger.info(f"📋 Loaded {len(processed_ids)} processed emergency alert IDs")
                return processed_ids
        except Exception as e:
            logger.error(f"Error loading processed emergency alerts: {e}")
            return set()
    return set()


mqtt_client = None
mqtt_connection_thread = None
mqtt_keep_running = True

def normalize_patient_id(value):
    if value is None:
        return None
    s = str(value).strip()
    if s.isdigit() and len(s) < 5:
        s = s.zfill(5)
    return s


def _load_telegram_chat_id():
    if os.path.exists(TELEGRAM_CHAT_ID_FILE):
        try:
            with open(TELEGRAM_CHAT_ID_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get('chat_id') is not None:
                return str(data.get('chat_id'))
            if isinstance(data, str):
                return data
        except Exception as e:
            logger.error(f"Error loading Telegram chat id: {e}")
    return None


def _save_telegram_chat_id(chat_id, chat_title=None):
    try:
        os.makedirs(os.path.dirname(TELEGRAM_CHAT_ID_FILE), exist_ok=True)
        payload = {"chat_id": str(chat_id)}
        if chat_title:
            payload["chat_title"] = str(chat_title)
        with open(TELEGRAM_CHAT_ID_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving Telegram chat id: {e}")
        return False


def _fetch_telegram_chat_id_from_updates():
    global telegram_last_update_fetch, telegram_last_update_id
    if not TELEGRAM_BOT_TOKEN:
        return None
    now = time.time()
    if telegram_last_update_fetch and now - telegram_last_update_fetch < 30:
        return None
    telegram_last_update_fetch = now
    try:
        params = {"timeout": 0}
        if telegram_last_update_id is not None:
            params["offset"] = telegram_last_update_id + 1
        resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
            params=params,
            timeout=5
        )
        data = resp.json() if resp.ok else {}
        updates = data.get("result") if isinstance(data, dict) else None
        if not updates:
            return None
        latest = updates[-1]
        telegram_last_update_id = latest.get("update_id", telegram_last_update_id)
        message = (
            latest.get("message")
            or latest.get("edited_message")
            or latest.get("channel_post")
            or {}
        )
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return None
        _save_telegram_chat_id(chat_id, chat.get("title") or chat.get("username"))
        return str(chat_id)
    except Exception as e:
        logger.error(f"Error fetching Telegram chat id from updates: {e}")
        return None


def get_telegram_chat_id():
    if TELEGRAM_CHAT_ID_ENV:
        return TELEGRAM_CHAT_ID_ENV
    with telegram_chat_id_lock:
        global telegram_chat_id_cache
        if telegram_chat_id_cache:
            return telegram_chat_id_cache
        chat_id = _load_telegram_chat_id()
        if not chat_id:
            chat_id = _fetch_telegram_chat_id_from_updates()
        if chat_id:
            telegram_chat_id_cache = chat_id
        return chat_id


def _split_telegram_text(text, max_len=3900):
    if not text:
        return []
    text = str(text)
    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return parts


def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN:
        return False
    chat_id = get_telegram_chat_id()
    if not chat_id:
        logger.warning("Telegram chat id is not set yet; send /start to the bot to link.")
        return False
    try:
        for chunk in _split_telegram_text(text):
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "disable_web_page_preview": True
                },
                timeout=5
            )
            if not resp.ok:
                logger.error(f"Telegram send failed: {resp.text}")
                return False
        return True
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        return False


def send_telegram_photo(photo_url, caption=None):
    if not TELEGRAM_BOT_TOKEN:
        return False
    chat_id = get_telegram_chat_id()
    if not chat_id:
        logger.warning("Telegram chat id is not set yet; send /start to the bot to link.")
        return False
    try:
        payload = {"chat_id": chat_id, "photo": photo_url}
        if caption:
            payload["caption"] = caption
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
            json=payload,
            timeout=10
        )
        if not resp.ok:
            logger.error(f"Telegram photo send failed: {resp.text}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error sending Telegram photo: {e}")
        return False


def send_telegram_photo_file(file_path, caption=None):
    if not TELEGRAM_BOT_TOKEN:
        return False
    chat_id = get_telegram_chat_id()
    if not chat_id:
        logger.warning("Telegram chat id is not set yet; send /start to the bot to link.")
        return False
    try:
        with open(file_path, 'rb') as photo_file:
            files = {"photo": photo_file}
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data=data,
                files=files,
                timeout=15
            )
        if not resp.ok:
            logger.error(f"Telegram photo upload failed: {resp.text}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error sending Telegram photo file: {e}")
        return False


def queue_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN:
        return False

    def _worker(msg):
        send_telegram_message(msg)

    threading.Thread(target=_worker, args=(text,), daemon=True).start()
    return True


def queue_telegram_photos(photo_urls):
    if not TELEGRAM_BOT_TOKEN:
        return False
    if not photo_urls:
        return False

    def _worker(urls):
        for url in urls:
            send_telegram_photo(url)

    threading.Thread(target=_worker, args=(photo_urls,), daemon=True).start()
    return True


def queue_telegram_photo_files(photo_paths):
    if not TELEGRAM_BOT_TOKEN:
        return False
    if not photo_paths:
        return False

    def _worker(paths):
        for path in paths:
            send_telegram_photo_file(path)

    threading.Thread(target=_worker, args=(photo_paths,), daemon=True).start()
    return True


def _format_telegram_alert(payload, alert_kind="Emergency Alert"):
    payload = payload or {}
    patient_id = payload.get("patient_id") or PATIENT_ID
    patient_name = payload.get("patient_name") or get_patient_name_by_id(patient_id) or "Unknown"
    alert_title = payload.get("alert_title") or payload.get("reason") or alert_kind
    alert_type = payload.get("type") or alert_kind
    alert_time = payload.get("datetime") or payload.get("timestamp") or "Unknown"
    confidence = payload.get("confidence")
    value = payload.get("value") or payload.get("details")

    lines = [
        alert_kind,
        f"Patient: {patient_name} ({patient_id})",
        f"Title: {alert_title}",
        f"Type: {alert_type}",
        f"Time: {alert_time}"
    ]
    if confidence is not None:
        lines.append(f"Confidence: {confidence}%")
    if value:
        lines.append(f"Details: {value}")
    return "\n".join(lines)


def _alert_card_lines(payload, alert_kind):
    payload = payload or {}
    patient_id = payload.get("patient_id") or PATIENT_ID
    alert_time = payload.get("datetime") or payload.get("timestamp") or "Unknown"
    confidence = payload.get("confidence")
    title = payload.get("alert_title") or payload.get("reason") or alert_kind
    alert_type = payload.get("type") or ""
    lines = [
        f"Patient {patient_id} - {title}",
        f"Time: {alert_time}"
    ]
    if confidence is not None:
        lines.append(f"Confidence: {confidence}%")
    if alert_type and title != alert_type:
        lines.append(f"Type: {alert_type}")
    return lines


def render_telegram_alert_card(payload, alert_kind="Emergency Alert"):
    try:
        os.makedirs(TELEGRAM_ALERT_CARD_DIR, exist_ok=True)
        width, height = 720, 360
        bg_color = (255, 214, 214)
        border_color = (255, 170, 170)
        title_color = (220, 0, 0)
        text_color = (30, 30, 30)
        accent_color = (220, 0, 0)

        image = Image.new("RGB", (width, height), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        pad = 24
        draw.rounded_rectangle(
            [pad, pad, width - pad, height - pad],
            radius=22,
            fill=bg_color,
            outline=border_color,
            width=3
        )

        try:
            title_font = ImageFont.truetype("arial.ttf", 28)
            body_font = ImageFont.truetype("arial.ttf", 22)
        except Exception:
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        title_text = "EMERGENCY ALERT!"
        alert_type = str(payload.get("type", "")).lower()
        if "fall" in alert_type:
            title_text = "FALL DETECTED!"
        elif "threshold" in alert_type:
            title_text = "VITAL ALERT!"

        draw.text((pad + 22, pad + 18), f"🚨 {title_text}", fill=title_color, font=title_font)

        lines = _alert_card_lines(payload, alert_kind)
        y = pad + 78
        for idx, line in enumerate(lines):
            color = accent_color if idx == 0 else text_color
            for wrapped in textwrap.wrap(str(line), width=40):
                draw.text((pad + 22, y), wrapped, fill=color, font=body_font)
                y += 28
            y += 4

        footer = "Please check on the patient immediately."
        for wrapped in textwrap.wrap(footer, width=44):
            draw.text((pad + 22, y + 6), wrapped, fill=text_color, font=body_font)
            y += 26

        filename = f"alert_{int(time.time() * 1000)}.png"
        file_path = os.path.join(TELEGRAM_ALERT_CARD_DIR, filename)
        image.save(file_path, format="PNG")
        return file_path
    except Exception as e:
        logger.error(f"Error rendering Telegram alert card: {e}")
        return None


def notify_telegram_alert(payload, alert_kind="Emergency Alert"):
    text = _format_telegram_alert(payload, alert_kind=alert_kind)
    card_path = render_telegram_alert_card(payload, alert_kind=alert_kind)
    if card_path:
        queue_telegram_photo_files([card_path])
    return queue_telegram_message(text)


def notify_telegram_chat_message(msg, patient_id=None):
    if not TELEGRAM_FORWARD_CHAT:
        return False
    msg = msg or {}
    text = msg.get("text") or msg.get("message") or ""
    sender = msg.get("senderName") or msg.get("sender") or "unknown"
    patient = patient_id or msg.get("patient_id") or PATIENT_ID
    patient_name = get_patient_name_by_id(patient) or "Unknown"
    lines = [
        "Remoni Chat Message",
        f"From: {sender}",
        f"Patient: {patient_name} ({patient})",
        f"Message: {text}"
    ]
    return queue_telegram_message("\n".join(lines))


def _get_or_create_telegram_client(chat_id):
    with telegram_clients_lock:
        client = telegram_clients.get(chat_id)
        if not client:
            client = app.test_client()
            telegram_clients[chat_id] = client
    with client.session_transaction() as sess:
        if 'username' not in sess:
            sess['username'] = f"telegram_{chat_id}"
            sess['role'] = 'doctor'
            sess['name'] = 'RemoniChatBot'
            sess['patient_id'] = PATIENT_ID
    return client


def _handle_telegram_chat_message(chat_id, text, base_url):
    client = _get_or_create_telegram_client(chat_id)
    try:
        resp = client.post("/chat", json={"message": text})
        data = resp.get_json(silent=True) if resp is not None else None
        if not isinstance(data, dict):
            queue_telegram_message("Sorry, I could not process that request.")
            return
        answer = str(data.get("answer") or "").strip()
        if answer:
            queue_telegram_message(answer)
        plots = data.get("plots") or []
        if plots and base_url:
            photo_urls = []
            for plot_path in plots:
                if isinstance(plot_path, dict):
                    plot_path = plot_path.get("path")
                if not plot_path:
                    continue
                path = str(plot_path)
                if path.startswith("http://") or path.startswith("https://"):
                    photo_urls.append(path)
                else:
                    photo_urls.append(f"{base_url}{path if path.startswith('/') else '/' + path}")
            if photo_urls:
                queue_telegram_photos(photo_urls)
    except Exception as e:
        logger.error(f"Telegram chat handling error: {e}")
        queue_telegram_message("Sorry, something went wrong processing your request.")


def handle_mqtt_emergency_alert(topic: str, payload: dict):
    """✅ FIXED: Handle immediate emergency alerts from MQTT without duplicates"""
    try:
        payload = payload or {}
        patient_id = payload.get('patient_id') or PATIENT_ID

        # ✅ Only accept alerts for the active patient (00001)
        if str(patient_id) != str(PATIENT_ID):
            logger.info(f"⚠️ Ignoring emergency alert for patient {patient_id} (active: {PATIENT_ID})")
            return

        payload['patient_id'] = str(patient_id)

        logger.warning(f"🚨 ==========================================")
        logger.warning(f"🚨 IMMEDIATE EMERGENCY ALERT VIA MQTT!")
        logger.warning(f"🚨 ==========================================")
        logger.warning(f"   Type: {payload.get('type')}")
        logger.warning(f"   Title: {payload.get('alert_title')}")
        logger.warning(f"   Patient: {payload.get('patient_id')}")

        # Add to local emergency_alerts list
        emergency_alerts.append(payload)

        # ✅ CRITICAL FIX: Mark as processed immediately to prevent S3 duplicate
        alert_key = f"{payload.get('patient_id')}_{payload.get('type')}_{payload.get('timestamp')}"
        processed_emergency_alert_ids.add(alert_key)
        save_processed_emergency_alert(alert_key)
        logger.info(f"✅ Marked emergency alert as processed: {alert_key}")

        # ✅ Forward to web clients immediately
        socketio.emit('emergency_alert', payload, namespace='/')
        notify_telegram_alert(payload, alert_kind="Emergency Alert")

        logger.warning(f"✅ Emergency alert broadcasted to web clients (will be ignored by S3 polling)")

    except Exception as e:
        logger.error(f"❌ Error handling MQTT emergency alert: {e}")


def handle_mqtt_fall_alert(topic: str, payload: dict):
    """✅ FIXED: Handle fall alerts with proper confidence-based routing

    - <70%: Ignore
    - 70-80%: Send to PATIENT for check-in (fall_check event)
    - ≥80%: Send to DOCTOR immediately (fall_alert event)
    """
    try:
        confidence = payload.get('confidence', 0)
        patient_id = payload.get('patient_id', PATIENT_ID)
        alert_id = payload.get('alert_id', str(int(time.time() * 1000)))
        alert_time = payload.get('datetime', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        logger.warning(f"🚨 ==========================================")
        logger.warning(f"🚨 FALL ALERT VIA MQTT!")
        logger.warning(f"🚨 ==========================================")
        logger.warning(f"   Confidence: {confidence}%")
        logger.warning(f"   Patient: {patient_id}")

        # ✅ TIER 1: <70% = Ignore (too low confidence)
        if confidence < 70:
            logger.info(f"⚪ LOW CONFIDENCE FALL (<70%): Ignored")
            return

        # ✅ TIER 2: 70-80% = Patient Check-In
        elif 70 <= confidence < 80:
            logger.warning(f"🟡 MODERATE FALL (70-80%): Patient check required")

            # Store pending response
            pending_fall_responses[alert_id] = {
                'alert': payload,
                'timestamp': time.time(),
                'patient_responded': False,
                'confidence': confidence,
                'patient_id': patient_id,
                'datetime': alert_time
            }

            # ✅ Send check-in to PATIENT ONLY (not doctor)
            patient_payload = {
                "type": "fall_check",
                "alert_id": alert_id,
                "confidence": confidence,
                "patient_id": patient_id,
                "datetime": alert_time,
                "for_role": "patient"  # ✅ CRITICAL: Only for patient
            }
            socketio.emit('fall_check', patient_payload, namespace='/')
            logger.info(f"✅ Moderate fall {alert_id} - patient check sent (NOT to doctor yet)")

            # ✅ Start timeout thread (only if not already running)
            with timeout_threads_lock:
                if alert_id not in active_timeout_threads:
                    active_timeout_threads.add(alert_id)
                    threading.Thread(
                        target=check_patient_response_timeout,
                        args=(alert_id,),
                        daemon=True
                    ).start()
                    logger.info(f"⏰ Started timeout thread for alert {alert_id}")

        # ✅ TIER 3: ≥80% = Immediate Critical Alert to Doctor
        else:
            logger.warning(f"🔴 CRITICAL FALL (≥80%): Immediate doctor notification")

            # ✅ STANDARDIZED FORMAT for doctor
            fall_alert_payload = {
                'patient_id': patient_id,
                'confidence': confidence,
                'datetime': alert_time,
                'alert_id': alert_id,
                'type': 'fall_detected',
                'for_role': 'doctor'  # ✅ CRITICAL: Only for doctor
            }
            # ✅ Also record as emergency alert for dashboard visibility
            emergency_alerts.append({
                "patient_id": patient_id,
                "patient_name": payload.get("patient_name"),
                "confidence": confidence,
                "datetime": alert_time,
                "alert_id": alert_id,
                "type": "fall_detected"
            })
            socketio.emit('fall_alert', fall_alert_payload, namespace='/')
            notify_telegram_alert(fall_alert_payload, alert_kind="Fall Alert")
            logger.info(f"✅ Critical fall alert sent to doctor")

    except Exception as e:
        logger.error(f"❌ Error handling MQTT fall alert: {e}")


def handle_mqtt_watch_status(topic: str, payload: dict):
    """Handle watch online/offline status updates from MQTT."""
    try:
        payload = payload or {}
        if payload.get("request") == "watch_status":
            logger.debug("⌚ Ignoring watch status request payload")
            return
        if isinstance(topic, str) and "/request/" in topic:
            logger.debug("⌚ Ignoring watch status request topic")
            return
        patient_id = normalize_patient_id(
            payload.get("patient_id") or payload.get("patientId") or payload.get("patient")
        )
        if not patient_id and isinstance(topic, str):
            parts = [p for p in topic.split("/") if p]
            for part in reversed(parts):
                if part.isdigit():
                    candidate = normalize_patient_id(part)
                    if candidate and len(candidate) == 5:
                        patient_id = candidate
                        break
        if not patient_id:
            logger.warning("⚠️ Watch status message missing patient_id")
            return

        connected = payload.get("connected")
        if connected is None:
            status_value = payload.get("status") or payload.get("state")
            if isinstance(status_value, str):
                connected = status_value.strip().lower() in {"online", "connected", "true", "1"}
            else:
                connected = bool(status_value)
        connected = bool(connected)

        timestamp = (
            payload.get("timestamp")
            or payload.get("datetime")
            or payload.get("time")
            or payload.get("time_stamp")
        )
        last_seen = parse_timestamp(timestamp)
        now_local = datetime.now()
        if not last_seen:
            last_seen = now_local

        battery = payload.get("battery")
        logger.info(f"⌚ Watch status payload for {patient_id}: {payload}")

        with watch_status_lock:
            watch_status_by_patient[patient_id] = {
                "connected": connected,
                "last_seen": last_seen,
                "battery": battery,
                "updated_at": now_local
            }

        logger.info(
            f"⌚ Watch status update for {patient_id}: "
            f"{'online' if connected else 'offline'}"
        )
    except Exception as e:
        logger.error(f"❌ Error handling MQTT watch status: {e}")

def initialize_mqtt(patient_id=None):
    """✅ FIXED: Initialize MQTT client with proper connection management"""
    global mqtt_client, mqtt_connection_thread, mqtt_keep_running

    if patient_id is None:
        patient_id = PATIENT_ID

    try:
        # ✅ Check if already initialized and connected
        if mqtt_client is not None:
            if mqtt_client.is_connected:
                logger.info("✅ MQTT already connected")
                return True
            else:
                logger.warning("⚠️ MQTT client exists but not connected - reconnecting...")
                mqtt_client.disconnect()
                mqtt_client = None

        # ✅ Create new MQTT client FIRST
        mqtt_client = MQTTClient(
            client_id=f"web_app_{patient_id}_{int(time.time())}",  # ✅ Unique client ID
            patient_id=patient_id
        )

        # ✅ Connect to broker
        if mqtt_client.connect():
            logger.info("✅ MQTT connected successfully")

            # ✅ NOW subscribe to topics (after client is created and connected)

            # Subscribe to vitals updates (real-time)
            mqtt_client.subscribe(
                MQTTConfig.get_vitals_topic(patient_id),
                handle_mqtt_vitals_update
            )

            # Subscribe to vitals responses (for fresh vitals requests)
            mqtt_client.subscribe(
                MQTTConfig.get_vitals_response_topic(patient_id),
                handle_mqtt_vitals_response
            )
            mqtt_client.subscribe(
                MQTTConfig.get_glucose_response_topic(patient_id),
                handle_mqtt_glucose_response
            )

            # ✅ Subscribe to emergency alerts (immediate)
            mqtt_client.subscribe(
                MQTTConfig.get_emergency_alert_topic(patient_id),
                handle_mqtt_emergency_alert
            )

            # ✅ Subscribe to fall alerts (immediate)
            mqtt_client.subscribe(
                MQTTConfig.get_fall_alert_topic(patient_id),
                handle_mqtt_fall_alert
            )

            # ✅ Subscribe to watch status updates (LWT/heartbeat)
            mqtt_client.subscribe(
                "watch/status/#",
                handle_mqtt_watch_status
            )
            # Also accept device status published on remoni/{patient_id}/status
            mqtt_client.subscribe(
                MQTTConfig.get_status_topic(patient_id),
                handle_mqtt_watch_status
            )

            # ✅ Start connection monitor thread
            start_mqtt_connection_monitor()

            return True
        else:
            logger.error("❌ Failed to connect to MQTT broker")
            mqtt_client = None
            return False

    except Exception as e:
        logger.error(f"❌ MQTT initialization error: {e}")
        mqtt_client = None
        return False
# ✅ Pending vitals requests (for MQTT responses)
pending_mqtt_vitals_requests = {}


def start_mqtt_connection_monitor():
    """✅ NEW: Monitor MQTT connection and reconnect if needed"""
    global mqtt_connection_thread, mqtt_keep_running

    def monitor_loop():
        global mqtt_client, mqtt_keep_running

        while mqtt_keep_running:
            try:
                # Check connection every 30 seconds
                time.sleep(30)

                if mqtt_client is None:
                    logger.warning("⚠️ MQTT client is None - reinitializing...")
                    initialize_mqtt(PATIENT_ID)
                elif not mqtt_client.is_connected:
                    logger.warning("⚠️ MQTT disconnected - attempting reconnect...")

                    # Try to reconnect
                    if not mqtt_client.connect():
                        logger.error("❌ MQTT reconnection failed")
                        # Don't create new client immediately - wait for next cycle
                else:
                    # Connection is healthy
                    logger.debug("✅ MQTT connection healthy")

            except Exception as e:
                logger.error(f"❌ MQTT monitor error: {e}")
                time.sleep(10)  # Wait before retrying

    # Only start if not already running
    if mqtt_connection_thread is None or not mqtt_connection_thread.is_alive():
        mqtt_keep_running = True
        mqtt_connection_thread = threading.Thread(target=monitor_loop, daemon=True)
        mqtt_connection_thread.start()
        logger.info("✅ MQTT connection monitor started")


def stop_mqtt():
    """✅ NEW: Gracefully stop MQTT client"""
    global mqtt_client, mqtt_keep_running

    mqtt_keep_running = False

    if mqtt_client is not None:
        try:
            mqtt_client.disconnect()
        except Exception as e:
            logger.error(f"Error stopping MQTT: {e}")

    mqtt_client = None
    logger.info("MQTT stopped")


def request_watch_status(patient_id: str) -> None:
    """Publish a watch status request if the last request was too old."""
    if not patient_id:
        return
    now_local = datetime.now()
    with watch_status_request_lock:
        last_sent = last_watch_status_request.get(patient_id)
        if last_sent and (now_local - last_sent).total_seconds() < WATCH_STATUS_REQUEST_COOLDOWN_SECONDS:
            return
        last_watch_status_request[patient_id] = now_local
    try:
        if mqtt_client and mqtt_client.is_connected:
            payload = {
                "patient_id": patient_id,
                "request": "watch_status",
                "timestamp": now_local.strftime("%Y-%m-%d %H:%M:%S")
            }
            mqtt_client.publish(f"watch/status/request/{patient_id}", payload)
    except Exception as e:
        logger.error(f"❌ Error requesting watch status: {e}")


# ============================================================================
# ✅ FIXED MQTT MESSAGE HANDLERS
# ============================================================================
def has_valid_vitals_payload(payload):
    if not isinstance(payload, dict):
        return False
    vital_keys = [
        'heart_rate',
        'spo2',
        'oxygen_saturation',
        'systolic_pressure',
        'diastolic_pressure',
        'body_temperature',
        'respiratory_rate',
        'glucose'
    ]
    for key in vital_keys:
        if key in payload and payload.get(key) is not None:
            return True
    return False


def handle_mqtt_vitals_update(topic: str, payload: dict):
    """✅ IMPROVED: Handle real-time vitals from MQTT with receipt time tracking"""
    try:
        patient_id = normalize_patient_id(payload.get('patient_id') or PATIENT_ID)
        if patient_id:
            payload['patient_id'] = patient_id

        if not has_valid_vitals_payload(payload):
            logger.warning("⚠️ MQTT vitals update missing vital values - ignoring")
            return

        # ✅ CRITICAL: Update latest vitals cache IMMEDIATELY
        if patient_id in latest_vitals_by_patient:
            latest_vitals_by_patient[patient_id].update(payload)
            logger.debug(f"✅ Updated vitals cache for patient {patient_id}")
        else:
            latest_vitals_by_patient[patient_id] = payload
            logger.info(f"✅ Created vitals cache for patient {patient_id}")

        if patient_id == PATIENT_ID:
            latest_vitals.update(payload)
            logger.debug(f"✅ Updated global vitals cache")

        # ✅ Threshold-based emergency alerts
        process_threshold_alerts(patient_id)

        # ✅ NEW: Track when we received this MQTT message
        last_mqtt_vitals_received[patient_id] = time.time()
        logger.debug(f"📡 Updated MQTT receipt time for patient {patient_id}")

        # ✅ IMPORTANT: Log vitals age for debugging
        vitals_time_str = payload.get('datetime', 'Unknown')
        if vitals_time_str != 'Unknown':
            try:
                vitals_time = pd.to_datetime(vitals_time_str)
                age_seconds = (datetime.now() - vitals_time).total_seconds()
                logger.debug(f"📊 Vitals received via MQTT - Age: {int(age_seconds)}s")
            except:
                pass

        # ✅ Mark any pending requests as received
        for request_id in list(pending_mqtt_vitals_requests.keys()):
            pending_mqtt_vitals_requests[request_id]['received'] = True
            pending_mqtt_vitals_requests[request_id]['vitals'] = payload
            logger.info(f"✅ Marked request {request_id} as received")

        # Forward to web clients via SocketIO
        socketio.emit("vitals_update", payload, namespace='/')
        logger.debug(f"📡 Forwarded vitals to web clients via SocketIO")

    except Exception as e:
        logger.error(f"❌ Error handling MQTT vitals: {e}")

def handle_mqtt_vitals_response(topic: str, payload: dict):
    """✅ IMPROVED: Handle fresh vitals response from MQTT"""
    try:
        request_id = payload.get('request_id')
        vitals = payload.get('vitals') if isinstance(payload, dict) else {}
        if not vitals and isinstance(payload, dict):
            vitals = {k: v for k, v in payload.items() if k != 'request_id'}

        logger.info(f"📨 Received vitals response via MQTT: {request_id}")

        # Update pending request
        if request_id in pending_mqtt_vitals_requests and has_valid_vitals_payload(vitals):
            pending_mqtt_vitals_requests[request_id]['vitals'] = vitals
            pending_mqtt_vitals_requests[request_id]['received'] = True
            logger.info(f"✅ Updated pending MQTT request {request_id}")

            # ✅ ALSO update the main vitals cache
            patient_id = normalize_patient_id(vitals.get('patient_id') or PATIENT_ID)
            vitals['patient_id'] = patient_id
            if patient_id:
                if patient_id in latest_vitals_by_patient:
                    latest_vitals_by_patient[patient_id].update(vitals)
                else:
                    latest_vitals_by_patient[patient_id] = vitals

                if patient_id == PATIENT_ID:
                    latest_vitals.update(vitals)

                logger.debug(f"✅ Updated vitals cache from response")

                # ✅ Threshold-based emergency alerts
                process_threshold_alerts(patient_id)

    except Exception as e:
        logger.error(f"❌ Error handling MQTT response: {e}")
# ============================================================================
# ✅ IMPROVED VITALS FETCHING WITH MQTT
# ============================================================================
def handle_mqtt_glucose_response(topic: str, payload: dict):
    """✅ FIXED: Handle fresh glucose response from MQTT with proper error handling"""
    try:
        request_id = payload.get('request_id')
        glucose = payload.get('glucose')  # This might be None

        logger.info(f"📨 Received glucose response via MQTT: {request_id}")
        logger.debug(f"📊 Glucose payload: {glucose}")

        # ✅ CRITICAL FIX: Check if glucose data is valid
        if not glucose:
            logger.warning(f"⚠️ Received empty glucose response for request {request_id}")

            # Still mark request as received, but with empty data
            if request_id in pending_mqtt_glucose_requests:
                pending_mqtt_glucose_requests[request_id]['received'] = True
                pending_mqtt_glucose_requests[request_id]['glucose'] = None
                logger.info(f"✅ Marked request {request_id} as received (but empty)")
            return

        # Update pending request
        if request_id in pending_mqtt_glucose_requests:
            pending_mqtt_glucose_requests[request_id]['glucose'] = glucose
            pending_mqtt_glucose_requests[request_id]['received'] = True
            logger.info(f"✅ Updated pending MQTT glucose request {request_id}")

            # ✅ CRITICAL FIX: Safely update cache with validation
            patient_id = normalize_patient_id(glucose.get('patient_id', PATIENT_ID))
            glucose['patient_id'] = patient_id

            # Validate glucose data has required fields
            if glucose.get('value_mgdl') is not None:
                latest_glucose_by_patient[patient_id] = glucose
                if patient_id == PATIENT_ID:
                    latest_glucose.update(glucose)
                glucose_source_by_patient[patient_id] = "mqtt"
                logger.info(f"✅ Updated glucose cache for patient {patient_id}: {glucose.get('value_mgdl')} mg/dL")

                # ✅ Threshold-based emergency alerts
                process_threshold_alerts(patient_id)
            else:
                logger.warning(f"⚠️ Glucose response missing value_mgdl field")
        else:
            logger.warning(f"⚠️ Request ID {request_id} not found in pending requests")

    except Exception as e:
        logger.error(f"❌ Error handling MQTT glucose response: {e}")
        logger.error(f"   Payload: {payload}")

        # Mark request as received even on error to prevent hanging
        if 'request_id' in locals() and request_id in pending_mqtt_glucose_requests:
            pending_mqtt_glucose_requests[request_id]['received'] = True
            pending_mqtt_glucose_requests[request_id]['glucose'] = None


def fetch_current_vitals_via_mqtt(patient_id=None):
    """✅ Request fresh vitals via MQTT"""
    global pending_vitals_requests

    if patient_id is None:
        patient_id = PATIENT_ID

    if mqtt_client is None or not mqtt_client.is_connected:
        logger.warning("⚠️ MQTT not connected - using S3 fallback")
        success = fetch_vitals_from_s3(patient_id)
        return success, "s3_fallback", False

    try:
        import uuid
        request_id = str(uuid.uuid4())

        # Create pending request
        pending_vitals_requests[request_id] = {
            'vitals': None,
            'received': False,
            'timestamp': time.time(),
            'patient_id': patient_id
        }

        # Send request to edge server
        request_payload = {
            'request_id': request_id,
            'patient_id': patient_id,
            'requester': 'web_app',
            'timestamp': int(time.time() * 1000)
        }

        logger.info(f"📤 Requesting fresh vitals via MQTT (request_id: {request_id})")

        # Publish to request topic
        success = mqtt_client.publish(
            MQTTConfig.get_vitals_request_topic(patient_id),
            request_payload
        )

        if not success:
            logger.warning("⚠️ Failed to publish MQTT request")
            del pending_vitals_requests[request_id]
            return False, "publish_failed", False

        # Wait for response (timeout: 10 seconds)
        timeout = 10
        start_time = time.time()

        logger.info(f"⏳ Waiting for fresh vitals response...")

        while (time.time() - start_time) < timeout:
            if request_id in pending_vitals_requests:
                req_data = pending_vitals_requests[request_id]

                if req_data['received'] and req_data['vitals'] is not None:
                    fresh_vitals = req_data['vitals']

                    # Update cache
                    latest_vitals_by_patient[patient_id] = fresh_vitals
                    if patient_id == PATIENT_ID:
                        latest_vitals.update(fresh_vitals)

                    logger.info(f"✅ Fresh vitals received via MQTT")
                    del pending_vitals_requests[request_id]
                    return True, "mqtt_fresh", True

            time.sleep(0.1)

        # Timeout
        logger.warning("⏰ MQTT vitals request timeout")
        if request_id in pending_vitals_requests:
            del pending_vitals_requests[request_id]

        # Fallback to S3
        success = fetch_vitals_from_s3(patient_id)
        return success, "mqtt_timeout", False

    except Exception as e:
        logger.error(f"❌ Error requesting vitals via MQTT: {e}")
        if 'request_id' in locals() and request_id in pending_vitals_requests:
            del pending_vitals_requests[request_id]
        success = fetch_vitals_from_s3(patient_id)
        return success, "mqtt_error", False


# ============================================================================
# ✅ CLEANUP FUNCTION (Call on app shutdown)
# ============================================================================

import atexit


def cleanup_on_exit():
    """Cleanup MQTT connection on exit"""
    logger.info("Cleaning up MQTT connection...")
    stop_mqtt()


atexit.register(cleanup_on_exit)


def handle_mqtt_vitals(topic: str, payload: dict):
    """Handle real-time vitals from edge server via MQTT"""
    try:
        patient_id = normalize_patient_id(payload.get('patient_id') or PATIENT_ID)
        if patient_id:
            payload['patient_id'] = patient_id
        logger.info(f"📨 Received vitals via MQTT for patient {patient_id}")

        # Update latest vitals cache
        if patient_id in latest_vitals_by_patient:
            latest_vitals_by_patient[patient_id].update(payload)
        else:
            latest_vitals_by_patient[patient_id] = payload

        if patient_id == PATIENT_ID:
            latest_vitals.update(payload)

        last_mqtt_vitals_received[patient_id] = time.time()

        # ✅ Mark any pending requests as received
        # We need to match this vitals to any pending request for this patient
        for request_id in list(pending_vitals_requests.keys()):
            req_data = pending_vitals_requests[request_id]
            if req_data['patient_id'] == patient_id and not req_data['received']:
                req_data['vitals'] = payload
                req_data['received'] = True
                logger.info(f"✅ Marked request {request_id} as received")

        # Forward to web clients via SocketIO
        socketio.emit("vitals_update", payload, namespace='/')

    except Exception as e:
        logger.error(f"❌ Error handling MQTT vitals: {e}")

def handle_mqtt_vitals_response(topic: str, payload: dict):
    """Handle fresh vitals response from MQTT"""
    try:
        request_id = payload.get('request_id')
        vitals = payload.get('vitals', {})

        logger.info(f"📨 Received vitals response via MQTT: {request_id}")

        # Update pending request
        if request_id in pending_mqtt_vitals_requests:
            pending_mqtt_vitals_requests[request_id]['vitals'] = vitals
            pending_mqtt_vitals_requests[request_id]['received'] = True
            logger.info(f"✅ Updated pending MQTT request {request_id}")

            patient_id = normalize_patient_id(vitals.get('patient_id') or PATIENT_ID)
            vitals['patient_id'] = patient_id
            if patient_id:
                if patient_id in latest_vitals_by_patient:
                    latest_vitals_by_patient[patient_id].update(vitals)
                else:
                    latest_vitals_by_patient[patient_id] = vitals

                if patient_id == PATIENT_ID:
                    latest_vitals.update(vitals)

                process_threshold_alerts(patient_id)

    except Exception as e:
        logger.error(f"❌ Error handling MQTT response: {e}")


# ============================================================================
# ✅ FIXED: fetch_current_vitals_via_mqtt - Replace in app.py
# ============================================================================

def fetch_current_vitals_via_mqtt(patient_id=None):
    """✅ FIXED: Request fresh vitals via MQTT with proper response checking

    The issue: We were checking pending_mqtt_vitals_requests but vitals come
    via handle_mqtt_vitals_update which marks ALL pending requests as received.
    """
    global latest_vitals, latest_vitals_by_patient

    if patient_id is None:
        patient_id = PATIENT_ID

    # Check if MQTT is connected
    if mqtt_client is None or not mqtt_client.is_connected:
        logger.warning("⚠️ MQTT not connected - using S3 cached data")
        success = fetch_vitals_from_s3(patient_id)
        return success, "s3_fallback", False

    try:
        import uuid
        request_id = str(uuid.uuid4())

        # ✅ CRITICAL FIX: Store initial timestamp to detect new data
        initial_timestamp = latest_vitals_by_patient.get(patient_id, {}).get('timestamp', 0)
        initial_receipt_time = last_mqtt_vitals_received.get(patient_id, 0)

        # Create pending request
        pending_mqtt_vitals_requests[request_id] = {
            'vitals': None,
            'received': False,
            'timestamp': time.time()
        }

        # Send MQTT request
        logger.warning(f"📤 ==========================================")
        logger.warning(f"📤 REQUESTING FRESH VITALS VIA MQTT")
        logger.warning(f"📤 ==========================================")
        logger.warning(f"   Request ID: {request_id}")
        logger.warning(f"   Patient ID: {patient_id}")

        request_payload = {
            "request_id": request_id,
            "patient_id": patient_id,
            "requester": "web_app",
            "timestamp": int(time.time() * 1000),
            "type": "vitals_request"
        }

        success = mqtt_client.publish(
            MQTTConfig.get_vitals_request_topic(patient_id),
            request_payload
        )

        if not success:
            logger.warning("⚠️ Failed to publish MQTT request - using S3 fallback")
            if request_id in pending_mqtt_vitals_requests:
                del pending_mqtt_vitals_requests[request_id]
            success = fetch_vitals_from_s3(patient_id)
            return success, "mqtt_publish_failed", False

        # Wait for response (timeout: 15 seconds)
        timeout = 15
        start_time = time.time()

        logger.info(f"⏳ Waiting for fresh vitals response via MQTT (timeout: {timeout}s)...")

        while (time.time() - start_time) < timeout:
            # ✅ CRITICAL FIX: Check if we received ANY new vitals
            # The pending request might be marked as received, OR
            # we might have received vitals via the general update handler

            req_data = pending_mqtt_vitals_requests.get(request_id, {})

            # Check if request was marked as received
            if req_data.get('received'):
                fresh_vitals = req_data.get('vitals')

                if fresh_vitals and has_valid_vitals_payload(fresh_vitals):
                    # Update cache
                    latest_vitals_by_patient[patient_id] = fresh_vitals
                    if patient_id == PATIENT_ID:
                        latest_vitals.update(fresh_vitals)
                    process_threshold_alerts(patient_id)

                    logger.warning(f"✅ ==========================================")
                    logger.warning(f"✅ FRESH VITALS RECEIVED VIA MQTT!")
                    logger.warning(f"✅ ==========================================")
                    logger.warning(f"   HR: {fresh_vitals.get('heart_rate')} BPM")
                    logger.warning(f"   SpO2: {fresh_vitals.get('spo2')}%")
                    logger.warning(f"   Time: {fresh_vitals.get('datetime')}")

                    del pending_mqtt_vitals_requests[request_id]
                    return True, "mqtt_fresh", True

            # ✅ NEW: ALSO check if latest_vitals_by_patient was updated
            # (This happens when vitals come via handle_mqtt_vitals_update)
            current_vitals = latest_vitals_by_patient.get(patient_id)
            if current_vitals and has_valid_vitals_payload(current_vitals):
                current_timestamp = current_vitals.get('timestamp', 0)
                current_receipt_time = last_mqtt_vitals_received.get(patient_id, 0)

                # If timestamp changed or MQTT receipt time updated, we got new data!
                if current_timestamp > initial_timestamp or current_receipt_time > initial_receipt_time:
                    process_threshold_alerts(patient_id)
                    logger.warning(f"✅ ==========================================")
                    logger.warning(f"✅ FRESH VITALS RECEIVED VIA MQTT!")
                    logger.warning(f"✅ ==========================================")
                    logger.warning(f"   HR: {current_vitals.get('heart_rate')} BPM")
                    logger.warning(f"   SpO2: {current_vitals.get('spo2')}%")
                    logger.warning(f"   Time: {current_vitals.get('datetime')}")

                    if request_id in pending_mqtt_vitals_requests:
                        del pending_mqtt_vitals_requests[request_id]
                    return True, "mqtt_fresh", True

            time.sleep(0.1)

        # Timeout - check if we have ANY vitals in cache (even if not fresh)
        logger.warning("⏰ MQTT vitals request timeout")
        if request_id in pending_mqtt_vitals_requests:
            del pending_mqtt_vitals_requests[request_id]

        # ✅ FALLBACK: If we have vitals in cache (even if old), use them
        cached_vitals = latest_vitals_by_patient.get(patient_id)
        if cached_vitals and cached_vitals.get('heart_rate', 0) > 0:
            logger.info(f"✅ Using cached vitals (MQTT timeout but cache available)")
            return True, "mqtt_timeout_cached", False

        # Last resort: try S3
        success = fetch_vitals_from_s3(patient_id)
        return success, "mqtt_timeout_s3", False

    except Exception as e:
        logger.error(f"❌ Error requesting vitals via MQTT: {e}")

        if 'request_id' in locals() and request_id in pending_mqtt_vitals_requests:
            del pending_mqtt_vitals_requests[request_id]

        # Try to use cached data first
        cached_vitals = latest_vitals_by_patient.get(patient_id)
        if cached_vitals and cached_vitals.get('heart_rate', 0) > 0:
            logger.info(f"✅ Using cached vitals (error but cache available)")
            return True, "mqtt_error_cached", False

        success = fetch_vitals_from_s3(patient_id)
        return success, "mqtt_error_s3", False
def save_processed_emergency_alert(alert_key):
    """Save an emergency alert as processed"""
    try:
        if os.path.exists(PROCESSED_EMERGENCY_FILE):
            with open(PROCESSED_EMERGENCY_FILE, 'r') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {'processed_ids': list(data) if isinstance(data, list) else []}
                if 'processed_ids' not in data:
                    data['processed_ids'] = []
        else:
            data = {'processed_ids': []}

        if alert_key not in data['processed_ids']:
            data['processed_ids'].append(alert_key)

        with open(PROCESSED_EMERGENCY_FILE, 'w') as f:
            json.dump(data, f, indent=2)

        logger.debug(f"✅ Marked emergency alert as processed: {alert_key}")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving processed emergency alert: {e}")
        return False


processed_emergency_alert_ids = load_processed_emergency_alerts()
logger.info(f"📊 System tracking: {len(processed_emergency_alert_ids)} previously processed emergency alerts")


def get_year_months_for_dates(date_list):
    """Get unique YYYY-MM strings from a list of dates"""
    year_months = set()
    for date_str in date_list:
        try:
            year_month = date_str[:7]
            year_months.add(year_month)
        except Exception as e:
            logger.error(f"Error parsing date {date_str}: {e}")
    return sorted(list(year_months))


def load_processed_fall_alerts():
    """Load list of already processed fall alert IDs"""
    if os.path.exists(PROCESSED_FALLS_FILE):
        try:
            with open(PROCESSED_FALLS_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    processed_ids = set(data.get('processed_ids', []))
                elif isinstance(data, list):
                    processed_ids = set(data)
                else:
                    processed_ids = set()
                logger.info(f"📋 Loaded {len(processed_ids)} processed fall alert IDs")
                return processed_ids
        except Exception as e:
            logger.error(f"Error loading processed fall alerts: {e}")
            return set()
    return set()


def save_processed_fall_alert(alert_id, patient_id, confidence, datetime_str):
    """Save a fall alert ID as processed"""
    try:
        if os.path.exists(PROCESSED_FALLS_FILE):
            with open(PROCESSED_FALLS_FILE, 'r') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {'processed_ids': list(data) if isinstance(data, list) else [], 'alerts': {}}
                if 'processed_ids' not in data:
                    data['processed_ids'] = []
                if 'alerts' not in data:
                    data['alerts'] = {}
        else:
            data = {'processed_ids': [], 'alerts': {}}

        if alert_id not in data['processed_ids']:
            data['processed_ids'].append(alert_id)
            alert_key = f"{patient_id}_{alert_id}"
            data['alerts'][alert_key] = {
                'id': alert_id,
                'patient_id': patient_id,
                'confidence': confidence,
                'datetime': datetime_str,
                'processed_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        with open(PROCESSED_FALLS_FILE, 'w') as f:
            json.dump(data, f, indent=2)

        logger.debug(f"✅ Marked fall alert {alert_id} as processed")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving processed fall alert: {e}")
        return False


def fetch_current_glucose_via_mqtt(patient_id=None):
    """✅ FIXED: Request fresh glucose via MQTT with better error handling"""
    global pending_mqtt_glucose_requests

    if patient_id is None:
        patient_id = PATIENT_ID

    if mqtt_client is None or not mqtt_client.is_connected:
        logger.warning("⚠️ MQTT not connected - using S3 fallback")
        success = fetch_glucose_from_s3(patient_id)
        return success, "s3_fallback", False

    try:
        import uuid
        request_id = str(uuid.uuid4())

        # Create pending request
        pending_mqtt_glucose_requests[request_id] = {
            'glucose': None,
            'received': False,
            'timestamp': time.time(),
            'patient_id': patient_id
        }

        # Send request to edge server
        request_payload = {
            'request_id': request_id,
            'patient_id': patient_id,
            'requester': 'web_app',
            'timestamp': int(time.time() * 1000),
            'type': 'glucose_request'
        }

        logger.warning(f"📤 ==========================================")
        logger.warning(f"📤 REQUESTING FRESH GLUCOSE VIA MQTT")
        logger.warning(f"📤 ==========================================")
        logger.warning(f"   Request ID: {request_id}")
        logger.warning(f"   Patient ID: {patient_id}")

        # Publish to glucose request topic
        success = mqtt_client.publish(
            MQTTConfig.get_glucose_request_topic(patient_id),
            request_payload
        )

        if not success:
            logger.warning("⚠️ Failed to publish MQTT glucose request")
            del pending_mqtt_glucose_requests[request_id]
            success = fetch_glucose_from_s3(patient_id)
            return success, "publish_failed", False

        # Wait for response (timeout: 15 seconds - LibreLink API can be slow)
        timeout = 15
        start_time = time.time()

        logger.info(f"⏳ Waiting for fresh glucose response via MQTT (timeout: {timeout}s)...")

        while (time.time() - start_time) < timeout:
            if request_id in pending_mqtt_glucose_requests:
                req_data = pending_mqtt_glucose_requests[request_id]

                if req_data['received']:
                    fresh_glucose = req_data.get('glucose')

                    # ✅ CRITICAL FIX: Check if we got valid glucose data
                    if fresh_glucose and fresh_glucose.get('value_mgdl') is not None:
                        # Update cache
                        latest_glucose_by_patient[patient_id] = fresh_glucose
                        if patient_id == PATIENT_ID:
                            latest_glucose.update(fresh_glucose)

                        logger.warning(f"✅ ==========================================")
                        logger.warning(f"✅ FRESH GLUCOSE RECEIVED VIA MQTT!")
                        logger.warning(f"✅ ==========================================")
                        logger.warning(f"   Glucose: {fresh_glucose.get('value_mgdl')} mg/dL")
                        logger.warning(f"   Time: {fresh_glucose.get('datetime')}")

                        del pending_mqtt_glucose_requests[request_id]
                        return True, "mqtt_fresh", True
                    else:
                        # Received response but no valid data
                        logger.warning("⚠️ Received glucose response but data is empty/invalid")
                        del pending_mqtt_glucose_requests[request_id]
                        success = fetch_glucose_from_s3(patient_id)
                        return success, "mqtt_empty_response", False

            time.sleep(0.1)

        # Timeout - clean up and fall back to S3
        logger.warning("⏰ MQTT glucose request timeout - using S3 cached data")
        if request_id in pending_mqtt_glucose_requests:
            del pending_mqtt_glucose_requests[request_id]

        success = fetch_glucose_from_s3(patient_id)
        return success, "mqtt_timeout", False

    except Exception as e:
        logger.error(f"❌ Error requesting glucose via MQTT: {e}")

        if 'request_id' in locals() and request_id in pending_mqtt_glucose_requests:
            del pending_mqtt_glucose_requests[request_id]

        success = fetch_glucose_from_s3(patient_id)
        return success, "mqtt_error", False


def clear_old_processed_alerts(days_to_keep=7):
    """Clear processed alerts older than specified days"""
    try:
        if not os.path.exists(PROCESSED_FALLS_FILE):
            return

        with open(PROCESSED_FALLS_FILE, 'r') as f:
            data = json.load(f)

        if not isinstance(data, dict):
            logger.warning("⚠️ Invalid format, recreating processed falls file")
            data = {'processed_ids': [], 'alerts': {}}

        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        alerts_to_keep = {}
        ids_to_keep = []

        for key, alert in data.get('alerts', {}).items():
            try:
                processed_at = datetime.strptime(alert['processed_at'], "%Y-%m-%d %H:%M:%S")
                if processed_at >= cutoff_date:
                    alerts_to_keep[key] = alert
                    ids_to_keep.append(alert['id'])
            except:
                alerts_to_keep[key] = alert
                ids_to_keep.append(alert['id'])

        data['alerts'] = alerts_to_keep
        data['processed_ids'] = ids_to_keep

        with open(PROCESSED_FALLS_FILE, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"🧹 Cleaned old processed alerts (kept {len(ids_to_keep)} from last {days_to_keep} days)")

    except Exception as e:
        logger.error(f"Error clearing old processed alerts: {e}")


processed_fall_alert_ids = load_processed_fall_alerts()
logger.info(f"📊 System tracking: {len(processed_fall_alert_ids)} previously processed fall alerts")

DOCTOR_REQUESTS_FILE = os.path.join('static', 'local_data', 'doctor_requests.json')
doctor_requests_lock = threading.Lock()

CHATROOM_MESSAGES_FILE = os.path.join('static', 'local_data', 'chatroom_messages.json')
chatroom_messages_lock = threading.Lock()


def load_doctor_requests():
    if os.path.exists(DOCTOR_REQUESTS_FILE):
        try:
            with open(DOCTOR_REQUESTS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading doctor requests: {e}")
            return {}
    return {}


def save_doctor_requests(data):
    try:
        os.makedirs(os.path.dirname(DOCTOR_REQUESTS_FILE), exist_ok=True)
        with open(DOCTOR_REQUESTS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving doctor requests: {e}")


def load_chatroom_messages():
    if os.path.exists(CHATROOM_MESSAGES_FILE):
        try:
            with open(CHATROOM_MESSAGES_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading chatroom messages: {e}")
            return []
    return []


def save_chatroom_messages(data):
    try:
        os.makedirs(os.path.dirname(CHATROOM_MESSAGES_FILE), exist_ok=True)
        with open(CHATROOM_MESSAGES_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving chatroom messages: {e}")


def normalize_timestamp_to_standard(raw_timestamp):
    """Normalize ANY timestamp format to standard: YYYY-MM-DD HH:MM:SS"""
    try:
        if not raw_timestamp:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        raw_timestamp = str(raw_timestamp).strip()

        # ✅ FIX FOR US DATE FORMAT: "4/1/2025 0:00"
        if '/' in raw_timestamp and ':' in raw_timestamp:
            try:
                # Try parsing US format: "4/1/2025 0:00"
                parts = raw_timestamp.split()
                if len(parts) >= 2:
                    date_part = parts[0]
                    time_part = parts[1]

                    # Parse US date
                    month, day, year = map(int, date_part.split('/'))

                    # Parse time (could be "0:00" or "00:00:00")
                    time_parts = time_part.split(':')
                    if len(time_parts) == 2:
                        hour, minute = map(int, time_parts)
                        second = 0
                    elif len(time_parts) == 3:
                        hour, minute, second = map(int, time_parts)
                    else:
                        hour, minute, second = 0, 0, 0

                    dt = datetime(year, month, day, hour, minute, second)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass  # Fall through to other formats

        if raw_timestamp.isdigit() and len(raw_timestamp) >= 13:
            dt = datetime.fromtimestamp(int(raw_timestamp) / 1000)
            return dt.strftime("%Y-%m-%d %H:%M:%S")

        if raw_timestamp.isdigit() and len(raw_timestamp) == 10:
            dt = datetime.fromtimestamp(int(raw_timestamp))
            return dt.strftime("%Y-%m-%d %H:%M:%S")

        if '/' in raw_timestamp:  # Other / formats
            try:
                # Try with AM/PM indicator
                dt = datetime.strptime(raw_timestamp, "%m/%d/%Y %I:%M:%S %p")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                # Try without AM/PM
                dt = datetime.strptime(raw_timestamp, "%m/%d/%Y %H:%M:%S")
                return dt.strftime("%Y-%m-%d %H:%M:%S")

        # Rest of your existing code...
        if 'T' in raw_timestamp:
            raw_timestamp = raw_timestamp.replace('Z', '+00:00')
            dt = datetime.fromisoformat(raw_timestamp)
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt.strftime("%Y-%m-%d %H:%M:%S")

        if '-' in raw_timestamp and ':' in raw_timestamp:
            try:
                dt = datetime.strptime(raw_timestamp, "%Y-%m-%d %H:%M:%S")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                dt = pd.to_datetime(raw_timestamp)
                try:
                    if getattr(dt, "tzinfo", None) is not None:
                        local_tz = datetime.now().astimezone().tzinfo
                        dt = dt.tz_convert(local_tz).tz_localize(None)
                except Exception:
                    pass
                return dt.strftime("%Y-%m-%d %H:%M:%S")

        dt = pd.to_datetime(raw_timestamp)
        try:
            if getattr(dt, "tzinfo", None) is not None:
                local_tz = datetime.now().astimezone().tzinfo
                dt = dt.tz_convert(local_tz).tz_localize(None)
        except Exception:
            pass
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    except Exception as e:
        logger.error(f"❌ Error parsing timestamp '{raw_timestamp}': {e}")
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
def safe_number(value, default=0):
    """Return a numeric-like value or a default when missing/NaN."""
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        if pd.isna(value):
            return default
        return value
    except Exception:
        return default


def safe_int(value, default=0):
    value = safe_number(value, default)
    try:
        return int(float(value))
    except Exception:
        return default


def safe_float(value, default=0.0):
    value = safe_number(value, default)
    try:
        return float(value)
    except Exception:
        return default


# ✅ Vital threshold rules (aligned with prior app thresholds)
VITAL_THRESHOLDS = {
    "heart_rate": {"low": 45, "high": 120},
    "body_temperature": {"low": 29, "high": 36},
    "glucose": {"low": 75, "high": 175},
    "oxygen_saturation": {"low": 90, "high": 100},
    "systolic_pressure": {"low": 95, "high": 175},
    "respiratory_rate": {"low": 12, "high": 23},
    "diastolic_pressure": {"low": 65, "high": 115}
}
VITAL_LABELS = {
    "heart_rate": "Heart Rate",
    "blood_pressure": "Blood Pressure",
    "glucose": "Blood Glucose",
    "body_temperature": "Body Temperature",
    "respiratory_rate": "Respiratory Rate",
    "oxygen_saturation": "Blood Oxygen"
}

VITAL_UNITS = {
    "heart_rate": "BPM",
    "blood_pressure": "mmHg",
    "glucose": "mg/dL",
    "body_temperature": "°C",
    "respiratory_rate": "breaths/min",
    "oxygen_saturation": "%"
}

CRITICAL_THRESHOLDS = { 
    "heart_rate": {"low": 40, "high": 130}, 
    "body_temperature": {"low": 27, "high": 38}, 
    "glucose": {"low": 70, "high": 180}, 
    "oxygen_saturation": {"low": 88, "high": 100}, 
    "systolic_pressure": {"low": 90, "high": 180}, 
    "respiratory_rate": {"low": 10, "high": 25}, 
    "diastolic_pressure": {"low": 60, "high": 120} 
} 

GLUCOSE_STATUS_FRESH_MINUTES = 7

# Track last known threshold status to avoid duplicate alerts
threshold_status_by_patient = {}
threshold_status_lock = threading.Lock()


def get_patient_name_by_id(patient_id: str) -> str:
    try:
        patient_id = str(patient_id)
        patients = load_patient_meta()
        for row in patients:
            if str(row.get('patient_id', '')).strip() == patient_id:
                name = row.get('name') or row.get('patient_name')
                if name:
                    return name
    except Exception:
        pass
    return f"Patient {patient_id}"


def classify_threshold(value, low, high):
    if value is None or value == 0:
        return None
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    return "normal"


def compute_patient_status(patient_id: str) -> str:
    patient_id = normalize_patient_id(patient_id) or patient_id
    # Prefer emergency alerts for status (last 6 hours)
    try:
        now = datetime.now()
        cutoff = now - timedelta(hours=6)
        recent_alerts = []
        for alert in emergency_alerts:
            if str(alert.get('patient_id') or '') != str(patient_id):
                continue
            dt = parse_timestamp(alert.get('datetime'))
            if not dt:
                ts = alert.get('timestamp') or alert.get('alert_id')
                try:
                    ts_val = float(ts) if ts is not None else None
                    if ts_val:
                        if ts_val > 1e12:
                            dt = datetime.fromtimestamp(ts_val / 1000)
                        elif ts_val > 1e9:
                            dt = datetime.fromtimestamp(ts_val)
                except Exception:
                    dt = None
            if dt and dt >= cutoff:
                recent_alerts.append(alert)

        if recent_alerts:
            critical = False
            for alert in recent_alerts:
                severity = str(alert.get('severity') or '').upper()
                alert_type = str(alert.get('type') or '').lower()
                confidence = alert.get('confidence')
                is_critical = (
                    severity == "CRITICAL"
                    or "critical" in alert_type
                    or alert_type in {"no_response", "patient_needs_help"}
                    or (confidence is not None and float(confidence) >= 99.6)
                )
                if is_critical:
                    critical = True
                    break
            return "Critical" if critical else "Urgent"
    except Exception:
        pass

    # For the real patient, status should follow emergency alerts only
    if str(patient_id) == str(PATIENT_ID):
        return "Stable"

    vitals = latest_vitals_by_patient.get(patient_id, {}) or {}
    glucose = latest_glucose_by_patient.get(patient_id, {}) or {}

    hr = safe_float(vitals.get('heart_rate'))
    spo2 = safe_float(vitals.get('spo2') or vitals.get('oxygen_saturation'))
    temp = safe_float(vitals.get('skin_temperature') or vitals.get('body_temperature'))
    rr = safe_float(vitals.get('respiratory_rate'))
    bp = vitals.get('blood_pressure') or {}
    sys_bp = safe_float(bp.get('systolic') or vitals.get('systolic_pressure'))
    dia_bp = safe_float(bp.get('diastolic') or vitals.get('diastolic_pressure'))
    glucose_val = safe_float(glucose.get('value_mgdl') or glucose.get('glucose'))

    critical = False
    urgent = False

    if hr:
        if hr < CRITICAL_THRESHOLDS["heart_rate"]["low"] or hr > CRITICAL_THRESHOLDS["heart_rate"]["high"]:
            critical = True
        elif hr < VITAL_THRESHOLDS["heart_rate"]["low"] or hr > VITAL_THRESHOLDS["heart_rate"]["high"]:
            urgent = True

    if sys_bp or dia_bp:
        if sys_bp > CRITICAL_THRESHOLDS["systolic_pressure"]["high"] or dia_bp > CRITICAL_THRESHOLDS["diastolic_pressure"]["high"]:
            critical = True
        elif sys_bp > VITAL_THRESHOLDS["systolic_pressure"]["high"] or dia_bp > VITAL_THRESHOLDS["diastolic_pressure"]["high"]:
            urgent = True
        elif (0 < sys_bp < VITAL_THRESHOLDS["systolic_pressure"]["low"]) or (0 < dia_bp < VITAL_THRESHOLDS["diastolic_pressure"]["low"]):
            urgent = True

    if temp:
        if temp < CRITICAL_THRESHOLDS["body_temperature"]["low"] or temp > CRITICAL_THRESHOLDS["body_temperature"]["high"]:
            critical = True
        elif temp < VITAL_THRESHOLDS["body_temperature"]["low"] or temp > VITAL_THRESHOLDS["body_temperature"]["high"]:
            urgent = True

    if rr:
        if rr < CRITICAL_THRESHOLDS["respiratory_rate"]["low"] or rr > CRITICAL_THRESHOLDS["respiratory_rate"]["high"]:
            critical = True
        elif rr < VITAL_THRESHOLDS["respiratory_rate"]["low"] or rr > VITAL_THRESHOLDS["respiratory_rate"]["high"]:
            urgent = True

    if spo2:
        if spo2 < CRITICAL_THRESHOLDS["oxygen_saturation"]["low"]:
            critical = True
        elif spo2 < VITAL_THRESHOLDS["oxygen_saturation"]["low"]:
            urgent = True

    if glucose_val:
        if glucose_val < CRITICAL_THRESHOLDS["glucose"]["low"] or glucose_val > CRITICAL_THRESHOLDS["glucose"]["high"]:
            critical = True
        elif glucose_val < VITAL_THRESHOLDS["glucose"]["low"] or glucose_val > VITAL_THRESHOLDS["glucose"]["high"]:
            urgent = True

    if critical:
        return "Critical"
    if urgent:
        return "Urgent"
    return "Stable"


def process_threshold_alerts(patient_id: str):
    try:
        patient_id = str(patient_id)
        vitals = latest_vitals_by_patient.get(patient_id, {}) or {}
        glucose = latest_glucose_by_patient.get(patient_id, {}) or {}

        # Extract vitals
        hr = safe_float(vitals.get('heart_rate'))
        spo2 = safe_float(vitals.get('spo2') or vitals.get('oxygen_saturation'))
        temp = safe_float(vitals.get('skin_temperature') or vitals.get('body_temperature'))
        rr = safe_float(vitals.get('respiratory_rate'))

        bp = vitals.get('blood_pressure') or {}
        sys_bp = safe_float(bp.get('systolic') or vitals.get('systolic_pressure'))
        dia_bp = safe_float(bp.get('diastolic') or vitals.get('diastolic_pressure'))

        glucose_val = safe_float(glucose.get('value_mgdl') or glucose.get('glucose'))
        glucose_is_high = bool(glucose.get('is_high', False))
        glucose_is_low = bool(glucose.get('is_low', False))

        statuses = {}
        details = {}

        # Heart rate
        hr_status = classify_threshold(
            hr,
            CRITICAL_THRESHOLDS["heart_rate"]["low"],
            CRITICAL_THRESHOLDS["heart_rate"]["high"]
        )
        if hr_status:
            statuses["heart_rate"] = hr_status
            details["heart_rate"] = f"{int(hr)} {VITAL_UNITS['heart_rate']}"

        # Blood pressure (combined)
        if sys_bp > 0 or dia_bp > 0:
            bp_high = sys_bp > CRITICAL_THRESHOLDS["systolic_pressure"]["high"] or dia_bp > CRITICAL_THRESHOLDS["diastolic_pressure"]["high"]
            bp_status = "high" if bp_high else "normal"
            statuses["blood_pressure"] = bp_status
            details["blood_pressure"] = f"{int(sys_bp)}/{int(dia_bp)} {VITAL_UNITS['blood_pressure']}"

        # Glucose
        if glucose_val > 0:
            if glucose_is_high:
                gl_status = "high"
            elif glucose_is_low:
                gl_status = "low"
            else:
                gl_status = classify_threshold(
                    glucose_val,
                    CRITICAL_THRESHOLDS["glucose"]["low"],
                    CRITICAL_THRESHOLDS["glucose"]["high"]
                )
            if gl_status:
                statuses["glucose"] = gl_status
                details["glucose"] = f"{int(glucose_val)} {VITAL_UNITS['glucose']}"

        # Temperature
        temp_status = classify_threshold(
            temp,
            CRITICAL_THRESHOLDS["body_temperature"]["low"],
            CRITICAL_THRESHOLDS["body_temperature"]["high"]
        )
        if temp_status:
            statuses["body_temperature"] = temp_status
            details["body_temperature"] = f"{temp:.1f} {VITAL_UNITS['body_temperature']}"

        # Respiratory rate
        rr_status = classify_threshold(
            rr,
            CRITICAL_THRESHOLDS["respiratory_rate"]["low"],
            CRITICAL_THRESHOLDS["respiratory_rate"]["high"]
        )
        if rr_status:
            statuses["respiratory_rate"] = rr_status
            details["respiratory_rate"] = f"{int(rr)} {VITAL_UNITS['respiratory_rate']}"

        # SpO2
        spo2_status = classify_threshold(spo2, CRITICAL_THRESHOLDS["oxygen_saturation"]["low"], None)
        if spo2_status:
            statuses["oxygen_saturation"] = spo2_status
            details["oxygen_saturation"] = f"{int(spo2)} {VITAL_UNITS['oxygen_saturation']}"

        if not statuses:
            return

        with threshold_status_lock:
            prev = threshold_status_by_patient.get(patient_id, {})
            for vital_key, status in statuses.items():
                prev_status = prev.get(vital_key)
                if status in ("high", "low") and status != prev_status:
                    alert_id = str(int(time.time() * 1000))
                    alert_type = f"threshold_{vital_key}_{status}"
                    reason = f"{VITAL_LABELS.get(vital_key, vital_key.replace('_', ' ').title())} is {status}"
                    payload = {
                        "patient_id": patient_id,
                        "patient_name": get_patient_name_by_id(patient_id),
                        "alert_id": alert_id,
                        "timestamp": alert_id,
                        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "alert_title": reason,
                        "type": alert_type,
                        "reason": reason,
                        "value": details.get(vital_key, "--"),
                        "source": "threshold"
                    }
                    emergency_alerts.append(payload)
                    alert_key = f"{patient_id}_{alert_type}_{alert_id}"
                    processed_emergency_alert_ids.add(alert_key)
                    save_processed_emergency_alert(alert_key)
                    socketio.emit('emergency_alert', payload, namespace='/')
                    notify_telegram_alert(payload, alert_kind="Threshold Alert")
                    logger.warning(f"🚨 Threshold alert: {reason} ({payload['value']})")

                if status != prev_status:
                    prev[vital_key] = status

            threshold_status_by_patient[patient_id] = prev
    except Exception as e:
        logger.error(f"❌ Error processing threshold alerts: {e}")


def safe_timestamp_ms(value):
    """Convert a timestamp-like value to epoch ms, falling back to now."""
    try:
        ts = pd.to_datetime(value, errors='coerce')
        if pd.isna(ts):
            return int(pd.Timestamp.utcnow().timestamp() * 1000)
        return int(ts.timestamp() * 1000)
    except Exception:
        return int(pd.Timestamp.utcnow().timestamp() * 1000)


def build_dummy_vitals_series(period):
    """Return a small dummy series for non-real patients."""
    now = datetime.now()
    series = []

    if period == 'daily':
        points = 8
        for i in range(points):
            ts = now - timedelta(hours=(points - 1 - i) * 3)
            label = ts.strftime("%H:%M")
            series.append({
                "time": label,
                "heartRate": 70 + (i % 5),
                "systolic": 120 + (i % 4),
                "diastolic": 80 + (i % 3),
                "glucose": 100 + (i % 6),
                "temperature": 36.5,
                "respiratory": 16 + (i % 3),
                "oxygen": 97
            })
    elif period == 'weekly':
        for i in range(7):
            ts = now - timedelta(days=6 - i)
            label = ts.strftime("%a")
            series.append({
                "time": label,
                "heartRate": 72 + (i % 4),
                "systolic": 118 + (i % 5),
                "diastolic": 78 + (i % 4),
                "glucose": 98 + (i % 7),
                "temperature": 36.6,
                "respiratory": 15 + (i % 3),
                "oxygen": 97
            })
    elif period == 'monthly':
        points = 10
        for i in range(points):
            ts = now - timedelta(days=(points - 1 - i) * 3)
            label = ts.strftime("%b %d")
            series.append({
                "time": label,
                "heartRate": 71 + (i % 5),
                "systolic": 119 + (i % 4),
                "diastolic": 79 + (i % 4),
                "glucose": 101 + (i % 6),
                "temperature": 36.5,
                "respiratory": 16 + (i % 2),
                "oxygen": 98
            })
    else:
        for i in range(12):
            ts = now - timedelta(days=(11 - i) * 30)
            label = ts.strftime("%b")
            series.append({
                "time": label,
                "heartRate": 70 + (i % 4),
                "systolic": 121 + (i % 3),
                "diastolic": 80 + (i % 3),
                "glucose": 99 + (i % 5),
                "temperature": 36.6,
                "respiratory": 16 + (i % 2),
                "oxygen": 97
            })

    return series


def build_dummy_latest_vitals(patient_id):
    now = datetime.now()
    return {
        'heart_rate': 72,
        'spo2': 97,
        'blood_pressure': {'systolic': 120, 'diastolic': 80},
        'skin_temperature': 36.6,
        'respiratory_rate': 16,
        'timestamp': int(now.timestamp() * 1000),
        'datetime': now.strftime("%Y-%m-%d %H:%M:%S"),
        'patient_id': patient_id
    }


def build_dummy_latest_glucose(patient_id):
    now = datetime.now()
    return {
        'value_mgdl': 102,
        'trend_arrow': 0,
        'is_high': False,
        'is_low': False,
        'datetime': now.strftime("%Y-%m-%d %H:%M:%S"),
        'patient_id': patient_id
    }


def build_dummy_device_status(patient_id):
    now = datetime.now()
    return {
        "edge_device": {
            "status": "online",
            "last_sync": "5 min ago"
        },
        "smart_watch": {
            "status": "connected",
            "last_sync": "4 min ago"
        },
        "glucose_sensor": {
            "status": "active",
            "last_sync": "7 min ago"
        },
        "wifi": {
            "ip_address": "192.168.1.20",
            "ssid": "Home_WiFi"
        },
        "patient_id": patient_id,
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S")
    }


def build_device_status_payload(patient_id): 
    """Build device status payload using S3 WiFi/vitals/glucose + watch status.""" 
    try: 
        fetch_vitals_from_s3(patient_id) 
        fetch_wifi_connection_from_s3() 
    except Exception: 
        pass 

    edge_ip = None
    edge_ssid = None
    edge_dt = None
    if isinstance(latest_wifi_connection, dict):
        edge_ip = latest_wifi_connection.get('ip_address') or latest_wifi_connection.get('ip')
        edge_ssid = latest_wifi_connection.get('ssid') or latest_wifi_connection.get('wifi_ssid')
        edge_dt = parse_timestamp(
            latest_wifi_connection.get('time_stamp')
            or latest_wifi_connection.get('timestamp')
            or latest_wifi_connection.get('datetime')
            or latest_wifi_connection.get('time')
        )

    vitals = latest_vitals_by_patient.get(patient_id, latest_vitals)
    vitals_dt = parse_timestamp(vitals.get('datetime') if isinstance(vitals, dict) else None)

    glucose = latest_librelink_glucose_by_patient.get(patient_id) or latest_glucose_by_patient.get(patient_id, latest_glucose) 
    glucose_origin = "librelink" if latest_librelink_glucose_by_patient.get(patient_id) else glucose_source_by_patient.get(patient_id) 
    glucose_dt = parse_timestamp(glucose.get('datetime') if isinstance(glucose, dict) else None) 
    glucose_value = None 
    if isinstance(glucose, dict): 
        glucose_value = safe_float(glucose.get('value_mgdl') or glucose.get('glucose')) 

    now = datetime.now() 

    wifi_recent = edge_dt and (now - edge_dt) <= timedelta(minutes=10) 
    glucose_recent = False 
    if glucose_dt and glucose_value: 
        glucose_recent = (now - glucose_dt) <= timedelta(minutes=GLUCOSE_STATUS_FRESH_MINUTES) 
        if glucose_recent and glucose_origin != "librelink": 
            glucose_origin = "librelink" 
    if glucose_origin != "librelink": 
        glucose_dt = None 
        glucose_recent = False 

    edge_connected = bool(wifi_recent)
    watch_last_seen = None
    watch_connected = False
    with watch_status_lock:
        watch_entry = watch_status_by_patient.get(patient_id)
    if isinstance(watch_entry, dict):
        watch_last_seen = watch_entry.get("last_seen")
        if isinstance(watch_last_seen, str):
            watch_last_seen = parse_timestamp(watch_last_seen)
        updated_at = watch_entry.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = parse_timestamp(updated_at)
        if updated_at and (not watch_last_seen or updated_at > watch_last_seen):
            watch_last_seen = updated_at
        if watch_last_seen:
            watch_recent = (now - watch_last_seen) <= timedelta(minutes=WATCH_STATUS_MAX_AGE_MINUTES)
            watch_connected = bool(watch_entry.get("connected")) and watch_recent
        else:
            watch_connected = bool(watch_entry.get("connected"))
        if not watch_connected:
            request_watch_status(patient_id)
    else:
        request_watch_status(patient_id)

    if not wifi_recent:
        edge_ip = None
        edge_ssid = None

    return { 
        "edge_device": { 
            "status": "online" if edge_connected else "offline", 
            "last_sync": format_age(edge_dt)
        },
        "smart_watch": {
            "status": "connected" if watch_connected else "offline",
            "last_sync": format_age(watch_last_seen)
        },
        "glucose_sensor": {
            "status": "active" if glucose_recent else "offline",
            "last_sync": format_age(glucose_dt)
        },
        "wifi": {
            "ip_address": edge_ip,
            "ssid": edge_ssid
        },
        "patient_id": patient_id,
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S")
    }


def build_dashboard_preload(patient_id, use_dummy=False):
    """Build initial dashboard payload to avoid first-load delays."""
    if use_dummy:
        return {
            "latestVitals": build_dummy_latest_vitals(patient_id),
            "latestGlucose": build_dummy_latest_glucose(patient_id),
            "deviceStatus": build_dummy_device_status(patient_id),
            "vitalsSeries": {
                "daily": build_dummy_vitals_series("daily")
            },
            "dailyUsage": build_dummy_daily_usage(days=7),
            "emergencyAlerts": []
        }

    vitals_payload = latest_vitals_by_patient.get(patient_id, latest_vitals)
    glucose_payload = latest_glucose_by_patient.get(patient_id, latest_glucose)
    device_status = build_device_status_payload(patient_id)

    try:
        daily_usage = load_daily_usage_from_s3(patient_id, days=7)
    except Exception:
        daily_usage = []

    try:
        daily_series = build_vitals_series(patient_id, 'daily')
    except Exception:
        daily_series = []

    return {
        "latestVitals": vitals_payload,
        "latestGlucose": glucose_payload,
        "deviceStatus": device_status,
        "vitalsSeries": {
            "daily": daily_series
        },
        "dailyUsage": daily_usage,
        "emergencyAlerts": list(emergency_alerts)
    }


def parse_periods(periods):
    parsed = []
    if not periods:
        return parsed
    for period in periods:
        if not isinstance(period, dict):
            continue
        start_val = (
            period.get('start')
            or period.get('start_time')
            or period.get('startTime')
            or period.get('start_timestamp')
            or period.get('startTimestamp')
        )
        end_val = (
            period.get('end')
            or period.get('end_time')
            or period.get('endTime')
            or period.get('end_timestamp')
            or period.get('endTimestamp')
        )
        if isinstance(start_val, (int, float)):
            start_ts = datetime.fromtimestamp(start_val / 1000 if start_val > 1e12 else start_val)
        else:
            start_ts = parse_timestamp(start_val)
        if isinstance(end_val, (int, float)):
            end_ts = datetime.fromtimestamp(end_val / 1000 if end_val > 1e12 else end_val)
        else:
            end_ts = parse_timestamp(end_val)
        if not start_ts or not end_ts:
            continue
        parsed.append((start_ts, end_ts))
    return parsed


def calc_period_stats(periods):
    if not periods:
        return 0.0, 0.0, 0.0
    total_hours = 0.0
    start_min = None
    end_max = None
    for start, end in periods:
        if end < start:
            end = end + timedelta(days=1)
        total_hours += (end - start).total_seconds() / 3600.0
        start_hour = start.hour + start.minute / 60.0
        end_hour = end.hour + end.minute / 60.0
        start_min = start_hour if start_min is None else min(start_min, start_hour)
        end_max = end_hour if end_max is None else max(end_max, end_hour)

    start_min = max(0.0, min(start_min or 0.0, 24.0))
    end_max = max(0.0, min(end_max or 0.0, 24.0))
    total_hours = max(0.0, min(total_hours, 24.0))
    return start_min, end_max, total_hours


def clip_periods_to_day(periods, day_start):
    clipped = []
    if not periods:
        return clipped
    day_end = day_start + timedelta(days=1)
    for start, end in periods:
        if end < start:
            end = end + timedelta(days=1)
        if end <= day_start or start >= day_end:
            continue
        start_clip = max(start, day_start)
        end_clip = min(end, day_end)
        if end_clip > start_clip:
            clipped.append((start_clip, end_clip))
    return clipped


def calc_period_stats_for_day(periods, day_start):
    clipped = clip_periods_to_day(periods, day_start)
    if not clipped:
        return 0.0, 0.0, 0.0
    total_hours = 0.0
    start_min = None
    end_max = None
    for start, end in clipped:
        total_hours += (end - start).total_seconds() / 3600.0
        start_hour = start.hour + start.minute / 60.0
        if end == day_start + timedelta(days=1):
            end_hour = 24.0
        else:
            end_hour = end.hour + end.minute / 60.0
        start_min = start_hour if start_min is None else min(start_min, start_hour)
        end_max = end_hour if end_max is None else max(end_max, end_hour)
    start_min = max(0.0, min(start_min or 0.0, 24.0))
    end_max = max(0.0, min(end_max or 0.0, 24.0))
    total_hours = max(0.0, min(total_hours, 24.0))
    return start_min, end_max, total_hours


def build_activity_entry_from_periods(date_obj, sleep_periods, worn_periods):
    day_start = datetime.combine(date_obj.date(), datetime.min.time())
    sleep_start, sleep_end, sleep_duration = calc_period_stats_for_day(sleep_periods, day_start)
    watch_start, watch_end, watch_duration = calc_period_stats_for_day(worn_periods, day_start)

    def format_hour_12(hour_value):
        try:
            hour_int = int(round(hour_value)) % 24
        except Exception:
            hour_int = 0
        suffix = "AM" if hour_int < 12 else "PM"
        hour_12 = hour_int % 12
        if hour_12 == 0:
            hour_12 = 12
        return f"{hour_12}:00 {suffix}"

    return {
        "date": date_obj.strftime("%Y-%m-%d"),
        "day": date_obj.strftime("%a"),
        "sleepOffset": sleep_start,
        "sleepDuration": sleep_duration,
        "watchOffset": watch_start,
        "watchDuration": watch_duration,
        "sleepStart": int(round(sleep_start)),
        "sleepEnd": int(round(sleep_end)),
        "watchStart": int(round(watch_start)),
        "watchEnd": int(round(watch_end)),
        "sleepLabel": f"{int(round(sleep_start))}:00-{int(round(sleep_end))}:00",
        "watchLabel": f"{format_hour_12(watch_start)} - {format_hour_12(watch_end)}"
    }


def build_activity_entry(date_obj, summary):
    sleep_periods = parse_periods(summary.get('sleepPeriods') or summary.get('sleep_periods'))
    worn_periods = parse_periods(summary.get('wornPeriods') or summary.get('worn_periods'))
    return build_activity_entry_from_periods(date_obj, sleep_periods, worn_periods)


def load_daily_usage_from_s3(patient_id, days=7):
    if not s3_client:
        return []
    results = []
    payloads = {}
    date_objs = []
    for offset in range(days - 1, -1, -1):
        date_obj = datetime.now().date() - timedelta(days=offset)
        date_str = date_obj.strftime("%Y-%m-%d")
        date_objs.append(date_obj)
        s3_key = f"{patient_id}/daily_usage/{date_str}.json"
        try:
            obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
            payloads[date_str] = json.loads(obj['Body'].read().decode('utf-8'))
        except Exception:
            continue

    for date_obj in date_objs:
        date_str = date_obj.strftime("%Y-%m-%d")
        payload = payloads.get(date_str)
        prev_date_str = (date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
        prev_payload = payloads.get(prev_date_str) or {}

        sleep_periods = parse_periods((payload or {}).get('sleepPeriods') or (payload or {}).get('sleep_periods'))
        worn_periods = parse_periods((payload or {}).get('wornPeriods') or (payload or {}).get('worn_periods'))
        prev_sleep = parse_periods(prev_payload.get('sleepPeriods') or prev_payload.get('sleep_periods'))
        prev_worn = parse_periods(prev_payload.get('wornPeriods') or prev_payload.get('worn_periods'))

        if not sleep_periods and not worn_periods and not prev_sleep and not prev_worn:
            continue

        combined_sleep = {}
        combined_worn = {}
        for start, end in (sleep_periods + prev_sleep):
            combined_sleep[(start, end)] = (start, end)
        for start, end in (worn_periods + prev_worn):
            combined_worn[(start, end)] = (start, end)

        entry = build_activity_entry_from_periods(
            datetime.combine(date_obj, datetime.min.time()),
            list(combined_sleep.values()),
            list(combined_worn.values())
        )
        results.append(entry)
    return results


def build_dummy_daily_usage(days=7):
    results = []
    for offset in range(days - 1, -1, -1):
        date_obj = datetime.now().date() - timedelta(days=offset)
        entry = {
            "date": date_obj.strftime("%Y-%m-%d"),
            "day": date_obj.strftime("%a"),
            "sleepOffset": 22.0,
            "sleepDuration": 7.5,
            "watchOffset": 8.0,
            "watchDuration": 12.0,
            "sleepStart": 22,
            "sleepEnd": 6,
            "watchStart": 8,
            "watchEnd": 20,
            "sleepLabel": "22:00-6:00",
            "watchLabel": "8:00 AM - 8:00 PM"
        }
        results.append(entry)
    return results

def parse_timestamp(value):
    """Return a naive datetime or None from a timestamp-like value."""
    try:
        if value is None:
            return None
        # Handle numeric epoch values (seconds or milliseconds)
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            try:
                num = float(value)
                # Heuristic: >= 1e12 -> milliseconds, >= 1e9 -> seconds
                if num >= 1e12:
                    ts = datetime.fromtimestamp(num / 1000.0)
                elif num >= 1e9:
                    ts = datetime.fromtimestamp(num)
                else:
                    ts = pd.to_datetime(value, errors='coerce')
            except Exception:
                ts = pd.to_datetime(value, errors='coerce')
        else:
            ts = pd.to_datetime(value, errors='coerce')
        if pd.isna(ts):
            return None
        if getattr(ts, "tzinfo", None) is not None:
            try:
                local_tz = datetime.now().astimezone().tzinfo
                ts = ts.tz_convert(local_tz).tz_localize(None)
            except Exception:
                try:
                    ts = ts.tz_convert("UTC").tz_localize(None)
                except Exception:
                    ts = ts.tz_localize(None)
        if hasattr(ts, "floor"):
            ts = ts.floor("s")
        dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        try:
            dt = dt.replace(microsecond=0)
        except Exception:
            pass
        # Guard against bogus/ancient timestamps
        now = datetime.now()
        if dt.year < 2000 or dt > now + timedelta(days=1):
            return None
        return dt
    except Exception:
        return None


def format_age(dt):
    """Return a human-friendly age string like '5 min ago'."""
    if not dt:
        return "Never"
    try:
        now = datetime.now()
        delta = now - dt
        if delta.total_seconds() < 0:
            return "Just now"
        minutes = max(0, int(delta.total_seconds() / 60))
        if minutes < 1:
            return "Just now"
        if minutes < 60:
            return f"{minutes} min ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hr ago"
        days = hours // 24
        if days <= 7:
            return f"{days} d ago"
        return "Never"
    except Exception:
        return "Unknown"


def check_response_id_age():
    """
    Check if response_id is too old (> 1.5 hours) and clear it
    Call this before using response_id
    """
    if 'response_id_timestamp' not in session:
        session['response_id_timestamp'] = time.time()
    
    age_seconds = time.time() - session.get('response_id_timestamp', 0)
    
    # Clear if older than 1.5 hours (5400 seconds)
    if age_seconds > 5400:
        logger.warning(f"⚠️ Response ID expired ({int(age_seconds/60)} minutes old) - clearing")
        session['response_id'] = None
        session['response_id_timestamp'] = time.time()
        return None
    
    return session.get('response_id')

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            return {}
    return {}


def save_users():
    try:
        with open(USERS_FILE, 'wb') as f:
            pickle.dump(USERS, f)
        logger.info("Users saved to database")
    except Exception as e:
        logger.error(f"Error saving users: {e}")


USERS = load_users()


def _default_doctor_profile(user_record=None):
    user_record = user_record or {}
    return {
        "name": user_record.get("name", ""),
        "email": user_record.get("email", ""),
        "phone_number": user_record.get("phone_number", ""),
        "whatsapp_number": user_record.get("whatsapp_number", ""),
        "home_address": user_record.get("home_address", ""),
        "profile_picture": user_record.get("profile_picture", "")
    }


def get_doctor_profile(username):
    user_record = USERS.get(username, {})
    profile = _default_doctor_profile(user_record)
    stored = user_record.get("doctor_profile")
    if isinstance(stored, dict):
        profile.update({k: stored.get(k, profile.get(k, "")) for k in profile.keys()})
    return profile


def save_doctor_profile(username, profile_updates):
    if username not in USERS:
        raise KeyError("Doctor account not found")

    current = get_doctor_profile(username)
    for key in current.keys():
        if key in profile_updates:
            current[key] = (profile_updates.get(key) or "").strip()

    USERS[username]["doctor_profile"] = current
    if current.get("name"):
        USERS[username]["name"] = current["name"]
    if current.get("email"):
        USERS[username]["email"] = current["email"]
    USERS[username]["phone_number"] = current.get("phone_number", "")
    USERS[username]["whatsapp_number"] = current.get("whatsapp_number", "")
    USERS[username]["home_address"] = current.get("home_address", "")
    USERS[username]["profile_picture"] = current.get("profile_picture", "")
    save_users()
    return current


def load_weekly_analysis_data():
    if not os.path.exists(WEEKLY_ANALYSIS_FILE):
        return {}
    try:
        with open(WEEKLY_ANALYSIS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.error(f"Error loading weekly analysis data: {e}")
        return {}


def save_weekly_analysis_data(data):
    try:
        os.makedirs(os.path.dirname(WEEKLY_ANALYSIS_FILE), exist_ok=True)
        with open(WEEKLY_ANALYSIS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving weekly analysis data: {e}")


def get_weekly_patient_store(patient_id):
    data = load_weekly_analysis_data()
    patient_store = data.setdefault(str(patient_id), {})
    patient_store.setdefault("reports", [])
    patient_store.setdefault("action_plans", [])
    patient_store.setdefault("doctor_reviews", [])
    return data, patient_store


def _parse_any_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%b %d, %Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f"
    ):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    try:
        parsed = pd.to_datetime(text, errors='coerce')
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()
    except Exception:
        return None


def _within_last_days(value, days=7):
    dt = _parse_any_datetime(value)
    if not dt:
        return False
    return dt >= (datetime.now() - timedelta(days=days))


def _format_week_event_date(value):
    dt = _parse_any_datetime(value) or datetime.now()
    return {
        "date": dt.strftime("%a, %b %d"),
        "time": dt.strftime("%I:%M %p")
    }


def _weekly_reports_static_relpath(patient_id, filename):
    return f"local_data/weekly_reports/{patient_id}/{filename}".replace("\\", "/")


def _load_weekly_emergency_events(patient_id, days=7):
    cutoff = datetime.now() - timedelta(days=days)
    events = []

    def _normalize_alert(alert):
        alert_patient_id = str(alert.get("patient_id") or "")
        if alert_patient_id != str(patient_id):
            return None
        dt = (
            _parse_any_datetime(alert.get("datetime"))
            or _parse_any_datetime(alert.get("timestamp"))
            or _parse_any_datetime(alert.get("date"))
        )
        if not dt or dt < cutoff:
            return None
        formatted = _format_week_event_date(dt)
        reason = alert.get("reason") or alert.get("alert_title") or alert.get("type") or "Emergency alert"
        value = alert.get("value") or "--"
        severity = "CRITICAL"
        reason_lower = str(reason).lower()
        if "urgent" in reason_lower:
            severity = "URGENT"
        return {
            "id": str(alert.get("alert_id") or alert.get("id") or int(dt.timestamp() * 1000)),
            "patientName": alert.get("patient_name") or get_patient_name_by_id(patient_id),
            "patientId": str(patient_id),
            "date": formatted["date"],
            "time": formatted["time"],
            "severity": severity,
            "reason": str(reason),
            "value": str(value),
            "_sort_ts": dt.timestamp()
        }

    for alert in emergency_alerts:
        normalized = _normalize_alert(alert)
        if normalized:
            events.append(normalized)

    if s3_client:
        for offset in range(days):
            day = (datetime.now() - timedelta(days=offset)).strftime("%Y-%m-%d")
            s3_key = f"{patient_id}/emergency_alerts/{day}.json"
            try:
                obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
                payload = json.loads(obj["Body"].read().decode("utf-8"))
                if isinstance(payload, list):
                    for alert in payload:
                        normalized = _normalize_alert(alert if isinstance(alert, dict) else {})
                        if normalized:
                            events.append(normalized)
            except Exception:
                continue

    deduped = {}
    for event in events:
        deduped[event["id"]] = event
    sorted_events = sorted(
        deduped.values(),
        key=lambda item: item.get("_sort_ts", 0),
        reverse=True
    )
    for event in sorted_events:
        event.pop("_sort_ts", None)
    return sorted_events


def get_weekly_analysis_payload(patient_id):
    patient_id = str(patient_id or PATIENT_ID)
    _, patient_store = get_weekly_patient_store(patient_id)
    reports = []
    for item in patient_store.get("reports", []):
        report = dict(item)
        if report.get("path") and not report.get("url"):
            report["url"] = url_for('static', filename=report["path"])
        reports.append(report)
    action_plans = list(patient_store.get("action_plans", []))
    doctor_reviews = list(patient_store.get("doctor_reviews", []))
    advices = []
    with advice_lock:
        for item in load_advices().get(patient_id, []):
            advice_dt = _parse_any_datetime(item.get("approved_at") or item.get("date"))
            if advice_dt and advice_dt >= datetime.now() - timedelta(days=7):
                advices.append({
                    "id": item.get("id"),
                    "text": item.get("text", ""),
                    "date": advice_dt.strftime("%Y-%m-%d"),
                    "time": advice_dt.strftime("%I:%M %p"),
                    "source": item.get("source", "Doctor")
                })
    return {
        "patient_id": patient_id,
        "reports": reports,
        "action_plans": action_plans,
        "doctor_reviews": doctor_reviews,
        "emergency_events": _load_weekly_emergency_events(patient_id, days=7),
        "advices": sorted(advices, key=lambda item: f"{item.get('date', '')} {item.get('time', '')}", reverse=True)
    }


def _build_weekly_pdf_pages(lines, title="Weekly Analysis Report"):
    page_width, page_height = 1240, 1754
    margin_x, margin_y = 80, 80
    line_height = 32
    max_lines = max(1, int((page_height - 2 * margin_y - 90) / line_height))
    try:
        title_font = ImageFont.truetype("arial.ttf", 36)
        body_font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    chunks = []
    current = []
    for line in lines:
        wrapped = textwrap.wrap(str(line), width=90) or [""]
        for sub_line in wrapped:
            if len(current) >= max_lines:
                chunks.append(current)
                current = []
            current.append(sub_line)
    if current or not chunks:
        chunks.append(current)

    pages = []
    for index, chunk in enumerate(chunks, start=1):
        image = Image.new("RGB", (page_width, page_height), "white")
        draw = ImageDraw.Draw(image)
        draw.text((margin_x, margin_y), title, fill="black", font=title_font)
        draw.text((page_width - margin_x - 120, margin_y + 8), f"Page {index}", fill="gray", font=body_font)
        y = margin_y + 90
        for line in chunk:
            draw.text((margin_x, y), line, fill="black", font=body_font)
            y += line_height
        pages.append(image.convert("RGB"))
    return pages


def generate_weekly_summary_pdf(patient_id, patient_name, doctor_name):
    payload = get_weekly_analysis_payload(patient_id)
    start_date = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"Patient: {patient_name} ({patient_id})",
        f"Prepared for: {doctor_name}",
        f"Week Range: {start_date} to {end_date}",
        "",
        "Emergency Alerts",
    ]
    if payload["emergency_events"]:
        for event in payload["emergency_events"]:
            lines.append(f"- {event['date']} {event['time']}: {event['severity']} - {event['reason']} ({event['value']})")
    else:
        lines.append("- No emergency alerts recorded in the past 7 days.")

    lines.extend(["", "Doctor Reviews"])
    if payload["doctor_reviews"]:
        for review in payload["doctor_reviews"]:
            lines.append(f"- {review.get('date', '')}: {review.get('content', '')}")
    else:
        lines.append("- No doctor reviews recorded.")

    lines.extend(["", "Action Plans"])
    if payload["action_plans"]:
        for plan in payload["action_plans"]:
            lines.append(f"- V{plan.get('version', '')} ({plan.get('createdDate', '')}): {plan.get('content', '')}")
    else:
        lines.append("- No action plans recorded.")

    lines.extend(["", "Advice / Notes"])
    if payload["advices"]:
        for advice in payload["advices"]:
            lines.append(f"- {advice.get('date', '')} {advice.get('time', '')}: {advice.get('text', '')}")
    else:
        lines.append("- No doctor advice notes recorded.")

    lines.extend(["", "Uploaded Reports"])
    if payload["reports"]:
        for report in payload["reports"]:
            lines.append(
                f"- {report.get('uploadDate', '')}: {report.get('name', '')} [{report.get('category', 'other')}] {report.get('size', '')}"
            )
    else:
        lines.append("- No uploaded reports attached in the system.")

    pages = _build_weekly_pdf_pages(lines, title="Weekly Patient Summary")
    temp_dir = tempfile.mkdtemp(prefix="weekly-report-")
    output_path = os.path.join(temp_dir, f"weekly_summary_{patient_id}.pdf")
    pages[0].save(output_path, save_all=True, append_images=pages[1:])
    return output_path, payload


def send_weekly_email(to_email, subject, body, attachments):
    if not (SMTP_HOST and SMTP_FROM_EMAIL):
        return False, "SMTP is not configured. Add SMTP_HOST and SMTP_FROM_EMAIL in the environment."

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = to_email
    message.set_content(body)

    for attachment_path in attachments:
        if not attachment_path or not os.path.exists(attachment_path):
            continue
        mime_type, _ = mimetypes.guess_type(attachment_path)
        maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
        with open(attachment_path, "rb") as f:
            message.add_attachment(
                f.read(),
                maintype=maintype,
                subtype=subtype,
                filename=os.path.basename(attachment_path)
            )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            if SMTP_USE_TLS:
                smtp.starttls()
                smtp.ehlo()
            if SMTP_USERNAME:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
        return True, "Email sent"
    except Exception as e:
        logger.error(f"Error sending weekly email: {e}")
        return False, str(e)

# Initialize S3
s3_client = None
try:
    if S3_KEY_ID and S3_SECRET_KEY:
        s3_client = boto3.client(
            service_name='s3',
            region_name=AWS_REGION,
            aws_access_key_id=S3_KEY_ID,
            aws_secret_access_key=S3_SECRET_KEY
        )
        logger.info("✅ S3 initialized successfully")
    else:
        logger.warning("⚠️ S3 credentials not provided")
except Exception as e:
    logger.error(f"❌ S3 initialization failed: {e}")
    s3_client = None


class EdgeDeviceClient:
    """✅ ONLY used for LibreLink setup (requires same WiFi temporarily)

    NOT USED for fetching vitals - vitals always come from S3 via API keys
    This allows the web application to work even when on different WiFi than Pi
    """

    def __init__(self, edge_device_ip=None, port=5000):
        self.edge_device_ip = edge_device_ip
        self.port = port
        self.base_url = f"http://{edge_device_ip}:{port}" if edge_device_ip else None
        self.timeout = 5

    def set_edge_device_ip(self, ip_address):
        self.edge_device_ip = ip_address
        self.base_url = f"http://{ip_address}:{self.port}"
        logger.info(f"Edge device IP set to: {ip_address}")

    def get_realtime_vitals(self):
        """Fetch real-time vitals directly from edge device"""
        if not self.base_url:
            return None
        try:
            logger.info(f"🔄 Fetching real-time vitals from edge device at {self.base_url}")
            response = requests.get(f"{self.base_url}/api/realtime_vitals?fresh=true", timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    logger.info(f"✅ Got real-time vitals from edge device")
                    return data.get('vitals')
        except Exception as e:
            logger.error(f"❌ Error fetching from edge device: {e}")
        return None

    def setup_librelink(self, email, password):
        if not self.base_url:
            return False, "Edge device not connected"
        try:
            logger.info(f"📧 Sending LibreLink credentials to edge device...")
            response = requests.post(
                f"{self.base_url}/setup_librelink",
                json={"email": email, "password": password},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    logger.info("✅ LibreLink configured on edge server")
                    return True, data.get('message', 'LibreLink connected')
                else:
                    return False, data.get('message', 'Setup failed')
            else:
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            logger.error(f"Error setting up LibreLink: {e}")
            return False, str(e)

    def delete_librelink(self, patient_id):
        if not self.base_url:
            return False, "Edge device not connected"
        try:
            logger.info(f"🗑️ Deleting LibreLink credentials from edge device...")
            response = requests.post(
                f"{self.base_url}/delete_librelink",
                json={"patient_id": patient_id},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    logger.info("✅ LibreLink credentials deleted from edge device")
                    return True, data.get('message', 'Credentials deleted')
                else:
                    return False, data.get('message', 'Deletion failed')
            else:
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            logger.warning(f"⚠️ Could not delete from edge device: {e}")
            return False, str(e)


edge_device_client = EdgeDeviceClient()

# Data storage
latest_vitals_by_patient = {} 
latest_glucose_by_patient = {} 
latest_librelink_glucose_by_patient = {} 

latest_vitals = {
    'heart_rate': 0,
    'spo2': 0,
    'blood_pressure': {'systolic': 0, 'diastolic': 0},
    'skin_temperature': 0,
    'respiratory_rate': 0,

    'timestamp': 0,
    'datetime': 'Never',
    'patient_id': PATIENT_ID
}

latest_glucose = {
    'value_mgdl': 0,
    'trend_arrow': 0,
    'is_high': False,
    'is_low': False,
    'datetime': 'Never',
    'patient_id': PATIENT_ID
}

latest_vitals_by_patient[PATIENT_ID] = latest_vitals.copy()
latest_glucose_by_patient[PATIENT_ID] = latest_glucose.copy() 
latest_librelink_glucose_by_patient[PATIENT_ID] = latest_glucose.copy() 

latest_wifi_connection = {}
fall_alerts = []
vitals_df = pd.DataFrame()
glucose_df = pd.DataFrame()
pending_fall_responses = {}

setup_state = {
    'setup_completed': False,
    'current_step': None,
    'edge_device_connected': False,
    'watch_connected': False,
    'libre_setup_completed': False
}

PLOT_FOLDER = './static/local_data/show_data/'
os.makedirs(PLOT_FOLDER, exist_ok=True)
os.makedirs('./static/images', exist_ok=True)
os.makedirs('./static/local_data', exist_ok=True)

# Initialize NLP Engine
nlp = nlp_engine()


def request_fresh_vitals_via_s3(patient_id):
    """Write request file to S3"""
    if not s3_client:
        return None

    try:
        request_id = f"{int(time.time() * 1000)}"
        request_data = {
            "request_id": request_id,
            "patient_id": patient_id,
            "type": "fresh_vitals_request",
            "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": int(time.time() * 1000),
            "status": "pending"
        }

        s3_key = f"{patient_id}/vitals_requests/{request_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(request_data, indent=2).encode('utf-8'),
            ContentType='application/json'
        )

        logger.info(f"📤 Requested fresh vitals via S3: {request_id}")
        return request_id

    except Exception as e:
        logger.error(f"❌ Error requesting fresh vitals: {e}")
        return None


def wait_for_vitals_response_from_s3(patient_id, request_id, timeout=10):
    """Wait for edge device response"""
    if not s3_client or not request_id:
        return None

    start_time = time.time()
    response_key = f"{patient_id}/vitals_responses/{request_id}.json"

    logger.info(f"⏳ Waiting for response from edge device (timeout: {timeout}s)...")

    while (time.time() - start_time) < timeout:
        try:
            obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=response_key)
            response_data = json.loads(obj['Body'].read().decode('utf-8'))

            if response_data.get('status') == 'completed':
                logger.info(f"✅ Got fresh vitals response from edge device!")
                return response_data.get('vitals')

        except s3_client.exceptions.NoSuchKey:
            pass
        except Exception as e:
            logger.error(f"❌ Error checking for response: {e}")
            return None

        time.sleep(0.5)

    logger.warning(f"⏰ Timeout waiting for fresh vitals response")
    return None


def load_librelink_credentials_from_s3(patient_id):
    """Load LibreLink credentials from S3 if present."""
    if not s3_client:
        return None
    s3_key = f"{patient_id}/librelink_credentials.json"
    try:
        obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        creds = json.loads(obj['Body'].read().decode('utf-8'))
        email = creds.get('email')
        password = creds.get('password')
        if not email or not password:
            return None
        return {"email": email, "password": password}
    except s3_client.exceptions.NoSuchKey:
        return None
    except Exception as e:
        logger.error(f"❌ Error loading LibreLink credentials: {e}")
        return None


def can_check_librelink(patient_id):
    now = datetime.now()
    with librelink_status_lock:
        last_check = librelink_last_check.get(patient_id)
        if last_check and (now - last_check).total_seconds() < LIBRELINK_CHECK_COOLDOWN_SECONDS:
            return False
        librelink_last_check[patient_id] = now
    return True


def fetch_current_glucose_via_librelink(patient_id): 
    """Fetch fresh glucose directly from LibreLinkUp (no MQTT).""" 
    creds = load_librelink_credentials_from_s3(patient_id)
    if not creds:
        return False, "LibreLink credentials missing", False

    if not can_check_librelink(patient_id):
        return False, "LibreLink cooldown", False

    base_url = "https://api.libreview.io"
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'product': 'llu.android',
        'version': '4.16.0'
    }
    try:
        login_url = f"{base_url}/llu/auth/login"
        login_data = {"email": creds["email"], "password": creds["password"]}
        response = requests.post(login_url, headers=headers, json=login_data, timeout=10)
        data = response.json()

        if data.get("status") == 0 and data.get("data", {}).get("redirect"):
            region = data["data"].get("region")
            base_url = f"https://api-{region}.libreview.io"
            login_url = f"{base_url}/llu/auth/login"
            response = requests.post(login_url, headers=headers, json=login_data, timeout=10)
            data = response.json()

        if data.get("status") != 0:
            return False, "LibreLink login failed", False

        token = data.get('data', {}).get('authTicket', {}).get('token')
        user_id = data.get('data', {}).get('user', {}).get('id')
        if not token or not user_id:
            return False, "LibreLink auth missing", False

        account_id = hashlib.sha256(user_id.encode('utf-8')).hexdigest().lower()
        auth_headers = headers.copy()
        auth_headers['Authorization'] = f"Bearer {token}"
        auth_headers['Account-Id'] = account_id

        connections_url = f"{base_url}/llu/connections"
        connections_resp = requests.get(connections_url, headers=auth_headers, timeout=10)
        if connections_resp.status_code != 200:
            return False, "LibreLink connections failed", False
        connections_data = connections_resp.json()
        if connections_data.get("status") != 0:
            return False, "LibreLink connections invalid", False
        connections = connections_data.get("data") or []
        if not connections:
            return False, "LibreLink no connections", False

        connection = connections[0]
        connection_patient_id = connection.get('patientId')
        if not connection_patient_id:
            return False, "LibreLink missing patientId", False

        graph_url = f"{base_url}/llu/connections/{connection_patient_id}/graph"
        graph_resp = requests.get(graph_url, headers=auth_headers, timeout=10)
        if graph_resp.status_code != 200:
            return False, "LibreLink graph failed", False
        graph_data = graph_resp.json()
        if graph_data.get("status") != 0:
            return False, "LibreLink graph invalid", False

        measurement = graph_data.get("data", {}).get("connection", {}).get("glucoseMeasurement", {})
        if not measurement:
            return False, "LibreLink no measurement", False

        raw_timestamp = measurement.get("Timestamp") 
        dt = pd.to_datetime(raw_timestamp, errors="coerce") 
        if dt is not pd.NaT: 
            local_tz = datetime.now().astimezone().tzinfo 
            if getattr(dt, "tzinfo", None) is None: 
                # LibreLink timestamps appear to be local; avoid shifting hours.
                dt = dt.replace(tzinfo=local_tz).replace(tzinfo=None) 
            else: 
                dt = dt.tz_convert(local_tz).tz_localize(None) 
            formatted_timestamp = dt.strftime("%Y-%m-%d %H:%M:%S") 
        else: 
            formatted_timestamp = normalize_timestamp_to_standard(raw_timestamp) 
        glucose_reading = {
            'patient_id': patient_id,
            'value_mgdl': measurement.get("ValueInMgPerDl"),
            'trend_arrow': measurement.get("TrendArrow"),
            'is_high': measurement.get("isHigh", False),
            'is_low': measurement.get("isLow", False),
            'datetime': formatted_timestamp,
            'timestamp': int(datetime.now().timestamp() * 1000)
        }

        if glucose_reading.get('value_mgdl') is not None:
            glucose_dt = parse_timestamp(glucose_reading.get('datetime'))
            glucose_age_minutes = None
            is_fresh = False
            if glucose_dt:
                glucose_age_minutes = (datetime.now() - glucose_dt).total_seconds() / 60.0
                is_fresh = glucose_age_minutes <= 35
            logger.info(
                f"🩸 LibreLink glucose time={glucose_reading.get('datetime')} "
                f"age_min={glucose_age_minutes:.1f}" if glucose_age_minutes is not None
                else f"🩸 LibreLink glucose time={glucose_reading.get('datetime')} age_min=unknown"
            )
            latest_glucose_by_patient[patient_id] = glucose_reading 
            latest_librelink_glucose_by_patient[patient_id] = glucose_reading 
            if patient_id == PATIENT_ID: 
                latest_glucose.update(glucose_reading) 
            glucose_source_by_patient[patient_id] = "librelink"
            return True, "LibreLink", is_fresh
        return False, "LibreLink missing glucose value", False

    except Exception as e:
        logger.error(f"❌ LibreLink fetch error: {e}")
        return False, "LibreLink error", False 
 
 
glucose_sensor_monitor_running = False 
glucose_sensor_monitor_lock = threading.Lock() 
 
 
def start_glucose_sensor_monitoring(interval_minutes=10):  
    """Poll LibreLink periodically to update glucose sensor status."""  
    global glucose_sensor_monitor_running 
 
    with glucose_sensor_monitor_lock: 
        if glucose_sensor_monitor_running: 
            return 
        glucose_sensor_monitor_running = True 
 
    def _monitor_loop(): 
        while True: 
            try: 
                success, source, is_fresh = fetch_current_glucose_via_librelink(PATIENT_ID) 
                if success: 
                    logger.info(f"LibreLink monitor update: fresh={is_fresh}") 
                else: 
                    logger.warning(f"LibreLink monitor update failed: {source}") 
            except Exception as e: 
                logger.error(f"LibreLink monitor error: {e}") 
 
            now = datetime.now() 
            next_minute_mark = ((now.minute // interval_minutes) + 1) * interval_minutes 
            if next_minute_mark >= 60: 
                next_time = (now + timedelta(hours=1)).replace( 
                    minute=0, second=0, microsecond=0 
                ) 
            else: 
                next_time = now.replace( 
                    minute=next_minute_mark, second=0, microsecond=0 
                ) 
 
            sleep_seconds = max(5, (next_time - datetime.now()).total_seconds()) 
            time.sleep(sleep_seconds) 
 
    threading.Thread(target=_monitor_loop, daemon=True).start()  


def maybe_refresh_librelink_glucose(patient_id, freshness_minutes=GLUCOSE_STATUS_FRESH_MINUTES):  
    """Kick off a LibreLink refresh if the cached reading is stale or missing."""  
    patient_id = normalize_patient_id(patient_id) or patient_id  
    glucose = latest_librelink_glucose_by_patient.get(patient_id)  
    glucose_dt = parse_timestamp(glucose.get('datetime') if isinstance(glucose, dict) else None)  
    if not glucose_dt or (datetime.now() - glucose_dt) > timedelta(minutes=freshness_minutes):  
        threading.Thread(  
            target=fetch_current_glucose_via_librelink,  
            args=(patient_id,),  
            daemon=True  
        ).start()  


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                return redirect(url_for('login'))
            if session.get('role') != role:
                return redirect(url_for('index'))
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def check_s3_patient_data_exists(patient_id):
    """Check if patient data exists in S3"""
    if not s3_client:
        return False
    try:
        year_month = datetime.now().strftime("%Y-%m")
        s3_key = f"{patient_id}/time_series/{year_month}.csv"
        s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        return True
    except:
        return False


def get_authorized_patient_id(session_role, session_patient_id, requested_patient_id):

    # ✅ CRITICAL FIX: Map ALL self-reference words to the current user
    self_reference_words = [
        'my', 'me', 'i', 'myself',  # First person
        'his', 'her', 'their', 'them',  # Third person pronouns
        'the patient', 'patient',  # Generic references
        'him', 'she', 'he',  # More pronouns
        'self', 'user', 'unknown','current','now','today'  # System references
    ]

    # Normalize numeric patient IDs to 5-digit form when provided
    normalized_requested_id = normalize_patient_id(requested_patient_id) if requested_patient_id else None
    if normalized_requested_id:
        requested_patient_id = normalized_requested_id

    # Convert to lowercase for comparison
    if requested_patient_id:
        requested_patient_id_lower = str(requested_patient_id).lower()
    else:
        requested_patient_id_lower = None

    # ============================================================================
    # PATIENT ROLE
    # ============================================================================
    if session_role == 'patient':
        # ✅ Ensure a default patient ID for patient sessions without one
        if not session_patient_id:
            session_patient_id = PATIENT_ID
        # ✅ FIX 1: Any self-reference word → use patient's own ID
        if requested_patient_id_lower in self_reference_words:
            logger.info(
                f"✅ Patient used self-reference '{requested_patient_id}' - mapping to their own ID: {session_patient_id}")
            return session_patient_id, None

        # ✅ FIX 2: No patient specified → use patient's own ID
        if not requested_patient_id or requested_patient_id_lower == 'unknown':
            logger.info(f"✅ Patient {session_patient_id} - no patient specified, using their own ID")
            return session_patient_id, None

        # ✅ FIX 3: Trying to access different patient ID → DENY
        if requested_patient_id != session_patient_id:
            logger.warning(f"🚫 DENIED: Patient {session_patient_id} tried to access Patient {requested_patient_id}")
            return None, "⛔ Access Denied: You can only view your own health data."

        # ✅ Requesting their own ID explicitly → ALLOW
        return session_patient_id, None

    # ============================================================================
    # DOCTOR ROLE
    # ============================================================================
    elif session_role == 'doctor':
        # ✅ For doctors, map self-references to current/default patient
        if requested_patient_id_lower in self_reference_words:
            # Use the last viewed patient if available, otherwise default
            target_id = session_patient_id if session_patient_id else PATIENT_ID
            logger.info(f"✅ Doctor used self-reference '{requested_patient_id}' - mapping to patient: {target_id}")
            return target_id, None

        # ✅ No patient specified → use default
        if not requested_patient_id or requested_patient_id_lower == 'unknown':
            target_id = session_patient_id if session_patient_id else PATIENT_ID
            logger.info(f"✅ Doctor - no patient specified, using: {target_id}")
            return target_id, None

        # ✅ Specific patient ID requested → ALLOW (doctors can access any patient)
        if requested_patient_id and requested_patient_id not in self_reference_words:
            logger.info(f"✅ DOCTOR accessing Patient {requested_patient_id}")
            return requested_patient_id, None

        # ✅ Fallback to default
        return session_patient_id if session_patient_id else PATIENT_ID, None

    # ✅ Unknown role → DENY
    return None, "⛔ Unauthorized access"


def load_patient_vitals_from_s3(patient_id, date_list=None):
    """Load vitals from S3 for specific dates"""
    if not s3_client:
        return pd.DataFrame()

    if date_list and len(date_list) > 0:
        year_months = get_year_months_for_dates(date_list)
    else:
        year_months = [datetime.now().strftime("%Y-%m")]

    all_dataframes = []

    for year_month in year_months:
        try:
            s3_key = f"{patient_id}/time_series/{year_month}.csv"
            obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
            csv_data = obj['Body'].read().decode('utf-8')
            df = pd.read_csv(StringIO(csv_data))

            if 'time_stamp' in df.columns:
                df['time_stamp'] = df['time_stamp'].apply(normalize_timestamp_to_standard)
                df['time_stamp'] = pd.to_datetime(df['time_stamp'], errors='coerce')
                df = df.dropna(subset=['time_stamp'])

            # Normalize column names to expected schema where needed
            if 'systolic_pressure' in df.columns and 'blood_pressure_systolic' not in df.columns:
                df['blood_pressure_systolic'] = df['systolic_pressure']
            if 'diastolic_pressure' in df.columns and 'blood_pressure_diastolic' not in df.columns:
                df['blood_pressure_diastolic'] = df['diastolic_pressure']
            if 'oxygen_saturation' in df.columns and 'spo2' not in df.columns:
                df['spo2'] = df['oxygen_saturation']
            if 'body_temperature' in df.columns and 'skin_temperature' not in df.columns:
                df['skin_temperature'] = df['body_temperature']

            all_dataframes.append(df)
        except Exception as e:
            logger.warning(f"Could not load {year_month}.csv: {e}")
            continue

    if all_dataframes:
        combined_df = pd.concat(all_dataframes, ignore_index=True)
        combined_df = combined_df.sort_values('time_stamp')
        return combined_df
    else:
        return pd.DataFrame()


def load_patient_glucose_from_s3(patient_id, date_list=None):
    """✅ FIXED: Load glucose from S3 CSV files (same format as vitals)"""
    if not s3_client:
        return pd.DataFrame()

    if date_list and len(date_list) > 0:
        year_months = get_year_months_for_dates(date_list)
    else:
        year_months = [datetime.now().strftime("%Y-%m")]

    all_dataframes = []

    for year_month in year_months:
        try:
            s3_key = f"{patient_id}/glucose/{year_month}.csv"  # ✅ Changed to .csv
            obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
            csv_data = obj['Body'].read().decode('utf-8')
            df = pd.read_csv(StringIO(csv_data))

            if 'time_stamp' in df.columns:
                df['time_stamp'] = df['time_stamp'].apply(normalize_timestamp_to_standard)
                df['time_stamp'] = pd.to_datetime(df['time_stamp'], errors='coerce')
                df = df.dropna(subset=['time_stamp'])

            all_dataframes.append(df)
        except s3_client.exceptions.NoSuchKey:
            # Try fallback without leading zeros if patient_id is zero-padded
            try:
                alt_patient_id = str(int(patient_id))
            except Exception:
                alt_patient_id = None
            if alt_patient_id and alt_patient_id != str(patient_id):
                try:
                    alt_key = f"{alt_patient_id}/glucose/{year_month}.csv"
                    obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=alt_key)
                    csv_data = obj['Body'].read().decode('utf-8')
                    df = pd.read_csv(StringIO(csv_data))
                    if 'time_stamp' in df.columns:
                        df['time_stamp'] = df['time_stamp'].apply(normalize_timestamp_to_standard)
                        df['time_stamp'] = pd.to_datetime(df['time_stamp'], errors='coerce')
                        df = df.dropna(subset=['time_stamp'])
                    all_dataframes.append(df)
                    continue
                except s3_client.exceptions.NoSuchKey:
                    pass
                except Exception as e:
                    logger.warning(f"Could not load glucose {year_month}.csv (alt id): {e}")
            # Final fallback: always try 00001 path for dashboard glucose
            if str(patient_id) != "00001":
                try:
                    fallback_key = f"00001/glucose/{year_month}.csv"
                    obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=fallback_key)
                    csv_data = obj['Body'].read().decode('utf-8')
                    df = pd.read_csv(StringIO(csv_data))
                    if 'time_stamp' in df.columns:
                        df['time_stamp'] = df['time_stamp'].apply(normalize_timestamp_to_standard)
                        df['time_stamp'] = pd.to_datetime(df['time_stamp'], errors='coerce')
                        df = df.dropna(subset=['time_stamp'])
                    all_dataframes.append(df)
                    continue
                except s3_client.exceptions.NoSuchKey:
                    pass
                except Exception as e:
                    logger.warning(f"Could not load glucose {year_month}.csv (fallback 00001): {e}")
            # Missing month is normal; keep glucose empty without warning
            continue
        except Exception as e:
            logger.warning(f"Could not load glucose {year_month}.csv: {e}")
            continue

    if all_dataframes:
        combined_df = pd.concat(all_dataframes, ignore_index=True)
        combined_df = combined_df.sort_values('time_stamp')
        return combined_df
    else:
        return pd.DataFrame()


def fetch_vitals_from_s3(patient_id=None):
    """Fetch current vitals from S3 (fallback when MQTT unavailable)"""
    global vitals_df, latest_vitals, latest_vitals_by_patient

    if not s3_client:
        return False

    if patient_id is None:
        patient_id = PATIENT_ID

    try:
        year_month = datetime.now().strftime("%Y-%m")
        s3_key = f"{patient_id}/time_series/{year_month}.csv"
        obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        csv_data = obj['Body'].read().decode('utf-8')
        df = pd.read_csv(StringIO(csv_data))

        if not df.empty:
            if 'time_stamp' in df.columns:
                df['time_stamp'] = df['time_stamp'].apply(normalize_timestamp_to_standard)

            if patient_id == PATIENT_ID:
                vitals_df = df

            latest_row = df.iloc[-1]
            systolic = latest_row.get('systolic_pressure', latest_row.get('blood_pressure_systolic', 0))
            diastolic = latest_row.get('diastolic_pressure', latest_row.get('blood_pressure_diastolic', 0))
            spo2 = latest_row.get('oxygen_saturation', latest_row.get('spo2', 0))
            skin_temp = latest_row.get('body_temperature', latest_row.get('skin_temperature', 0))
            vitals_data = {
                'heart_rate': safe_int(latest_row.get('heart_rate', 0)),
                'spo2': safe_int(spo2, 0),
                'blood_pressure': {
                    'systolic': safe_int(systolic, 0),
                    'diastolic': safe_int(diastolic, 0)
                },
                'skin_temperature': safe_float(skin_temp, 0.0),
                'respiratory_rate': safe_float(latest_row.get('respiratory_rate', 0), 0.0),
                'timestamp': safe_timestamp_ms(latest_row.get('time_stamp')),
                'datetime': str(latest_row.get('time_stamp', 'Never')),
                'patient_id': patient_id
            }

            latest_vitals_by_patient[patient_id] = vitals_data
            if patient_id == PATIENT_ID:
                latest_vitals.update(vitals_data)

            # ✅ Threshold-based emergency alerts
            process_threshold_alerts(patient_id)

            return True
    except Exception as e:
        logger.debug(f"No vitals data for patient {patient_id}: {e}")
        return False


def fetch_current_vitals(patient_id=None):
    """✅ FIXED: Fetch current vitals using MQTT (NOT S3 request system)

    This function now:
    1. ALWAYS tries MQTT first for fresh vitals
    2. Falls back to S3 cached data if MQTT fails
    3. Works across different WiFi networks
    """
    global latest_vitals, latest_vitals_by_patient

    if patient_id is None:
        patient_id = PATIENT_ID

    # ✅ PRIORITY 1: Try MQTT for fresh vitals
    logger.info(f"📡 Requesting fresh vitals via MQTT...")

    success, source, is_fresh = fetch_current_vitals_via_mqtt(patient_id)

    if success:
        logger.info(f"✅ Vitals fetched via {source} (fresh: {is_fresh})")

        # Check age of data
        patient_vitals = latest_vitals_by_patient.get(patient_id)
        if patient_vitals:
            try:
                vitals_time = pd.to_datetime(patient_vitals.get('datetime'))
                time_diff = datetime.now() - vitals_time
                age_seconds = time_diff.total_seconds()

                if age_seconds < 60:
                    logger.info(f"✅ Data is fresh ({int(age_seconds)}s old)")
                elif age_seconds < 1800:  # Less than 30 minutes
                    logger.info(f"⚠️ Data is {int(age_seconds / 60)} minutes old")
                else:
                    logger.warning(f"⚠️ Data is {int(age_seconds / 60)} minutes old - may be stale")
            except:
                pass
    else:
        logger.warning(f"⚠️ Could not fetch vitals")

    return success, source, is_fresh


def fetch_glucose_from_s3(patient_id=None):
    """✅ FIXED: Fetch glucose from S3 CSV"""
    global glucose_df, latest_glucose, latest_glucose_by_patient

    if not s3_client:
        return False

    if patient_id is None:
        patient_id = PATIENT_ID

    try:
        year_month = datetime.now().strftime("%Y-%m")
        s3_key = f"{patient_id}/glucose/{year_month}.csv"  # ✅ Changed to .csv
        obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        csv_data = obj['Body'].read().decode('utf-8')
        df = pd.read_csv(StringIO(csv_data))

        if not df.empty:
            if 'time_stamp' in df.columns:
                df['time_stamp'] = df['time_stamp'].apply(normalize_timestamp_to_standard)
                df['time_stamp'] = pd.to_datetime(df['time_stamp'], errors='coerce')
                df = df.dropna(subset=['time_stamp'])
                df = df.sort_values('time_stamp')

            if patient_id == PATIENT_ID:
                glucose_df = df

            latest_row = df.iloc[-1]
            glucose_reading = {
                'value_mgdl': safe_int(latest_row.get('glucose', 0)),
                'trend_arrow': safe_int(latest_row.get('trend_arrow', 0)),
                'is_high': bool(latest_row.get('is_high', False)),
                'is_low': bool(latest_row.get('is_low', False)),
                'datetime': str(latest_row.get('time_stamp', 'Never')),
                'patient_id': patient_id
            }

            latest_glucose_by_patient[patient_id] = glucose_reading
            if patient_id == PATIENT_ID:
                latest_glucose.update(glucose_reading)
            glucose_source_by_patient[patient_id] = "s3"

            # ✅ Threshold-based emergency alerts
            process_threshold_alerts(patient_id)

            return True
    except Exception as e:
        logger.debug(f"No glucose data for patient {patient_id}: {e}")
        return False

def fetch_wifi_connection_from_s3():
    """Fetch WiFi info from S3"""
    global latest_wifi_connection
    if not s3_client:
        return False
    try:
        s3_key = f"{PATIENT_ID}/wifi_connection.json"
        obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        wifi_data = json.loads(obj['Body'].read().decode('utf-8'))
        latest_wifi_connection = wifi_data

        if not setup_state['edge_device_connected']:
            setup_state['edge_device_connected'] = True
            edge_device_ip = wifi_data.get('ip_address')
            if edge_device_ip:
                edge_device_client.set_edge_device_ip(edge_device_ip)
        return True
    except Exception as e:
        logger.debug(f"No wifi data for patient {PATIENT_ID}: {e}")
        return False


def build_vitals_series(patient_id, period):
    """Build aggregated vitals series for dashboard charts from S3 data."""
    now = pd.Timestamp.now()
    if period == 'daily':
        start_time = now - pd.Timedelta(hours=24)
        rule = '1h'
        label = 'hour'
    elif period == 'weekly':
        start_time = now - pd.Timedelta(days=7)
        rule = '1D'
        label = 'weekday'
    elif period == 'monthly':
        start_time = now - pd.Timedelta(days=30)
        rule = '1D'
        label = 'date'
    else:
        start_time = now - pd.Timedelta(days=365)
        rule = '1ME'
        label = 'month'

    # Build month list spanning the requested range so S3 lookup covers cross-month data
    def months_between(start_dt, end_dt):
        start = start_dt.to_pydatetime() if hasattr(start_dt, "to_pydatetime") else start_dt
        end = end_dt.to_pydatetime() if hasattr(end_dt, "to_pydatetime") else end_dt
        y, m = start.year, start.month
        end_y, end_m = end.year, end.month
        months = []
        while (y, m) <= (end_y, end_m):
            months.append(f"{y:04d}-{m:02d}-01")
            m += 1
            if m > 12:
                m = 1
                y += 1
        return months

    date_list = months_between(start_time, now)

    vitals_df = load_patient_vitals_from_s3(patient_id, date_list=date_list)
    glucose_df = load_patient_glucose_from_s3(patient_id, date_list=date_list)

    if vitals_df.empty and glucose_df.empty:
        return []

    # Normalize column names if needed
    if 'systolic_pressure' in vitals_df.columns and 'blood_pressure_systolic' not in vitals_df.columns:
        vitals_df['blood_pressure_systolic'] = vitals_df['systolic_pressure']
    if 'diastolic_pressure' in vitals_df.columns and 'blood_pressure_diastolic' not in vitals_df.columns:
        vitals_df['blood_pressure_diastolic'] = vitals_df['diastolic_pressure']
    if 'oxygen_saturation' in vitals_df.columns and 'spo2' not in vitals_df.columns:
        vitals_df['spo2'] = vitals_df['oxygen_saturation']
    if 'body_temperature' in vitals_df.columns and 'skin_temperature' not in vitals_df.columns:
        vitals_df['skin_temperature'] = vitals_df['body_temperature']

    vitals_df['time_stamp'] = pd.to_datetime(vitals_df['time_stamp'], errors='coerce')
    try:
        if getattr(vitals_df['time_stamp'].dt, "tz", None) is not None:
            vitals_df['time_stamp'] = vitals_df['time_stamp'].dt.tz_convert(None)
    except Exception:
        pass
    vitals_df = vitals_df.dropna(subset=['time_stamp'])
    if vitals_df.empty:
        return []

    if not glucose_df.empty and 'time_stamp' in glucose_df.columns:
        # Filter glucose rows to the requested patient if the column exists
        if 'patient_id' in glucose_df.columns:
            try:
                pid_str = str(patient_id)
                pid_alt = str(int(patient_id)) if str(patient_id).isdigit() else None
                glucose_df = glucose_df[
                    glucose_df['patient_id'].astype(str).isin(
                        [pid_str] + ([pid_alt] if pid_alt else [])
                    )
                ]
            except Exception:
                pass
        glucose_df['time_stamp'] = pd.to_datetime(glucose_df['time_stamp'], errors='coerce')
        try:
            if getattr(glucose_df['time_stamp'].dt, "tz", None) is not None:
                glucose_df['time_stamp'] = glucose_df['time_stamp'].dt.tz_convert(None)
        except Exception:
            pass
        glucose_df = glucose_df.dropna(subset=['time_stamp'])

    if not vitals_df.empty:
        vitals_df = vitals_df[vitals_df['time_stamp'] >= start_time]
        if vitals_df.empty:
            vitals_df = pd.DataFrame()

    agg = None
    if not vitals_df.empty:
        vitals_df = vitals_df.set_index('time_stamp')
        agg = vitals_df.resample(rule).mean(numeric_only=True)

    if agg is None and not glucose_df.empty:
        glucose_df = glucose_df[glucose_df['time_stamp'] >= start_time]
        if not glucose_df.empty:
            glucose_df = glucose_df.set_index('time_stamp')
            glucose_agg = glucose_df.resample(rule).mean(numeric_only=True)
            agg = glucose_agg.copy()
    if agg is None or agg.empty:
        return []

    has_glucose = not glucose_df.empty

    if has_glucose:
        # align glucose to the same time window and aggregation
        glucose_df = glucose_df[glucose_df['time_stamp'] >= start_time]
        if not glucose_df.empty:
            glucose_df = glucose_df.set_index('time_stamp')
            glucose_agg = glucose_df.resample(rule).mean(numeric_only=True)
            if agg is None or agg.empty:
                agg = glucose_agg.copy()
            else:
                agg['glucose'] = glucose_agg['glucose']
    else:
        # Keep glucose empty when no data so plots don't show a flat 0 line
        if agg is not None and 'glucose' not in agg.columns:
            agg['glucose'] = None

    series = []
    for ts, row in agg.iterrows():
        if label == 'hour':
            time_label = ts.strftime("%H:%M")
        elif label == 'weekday':
            time_label = ts.strftime("%a")
        elif label == 'month':
            time_label = ts.strftime("%b")
        else:
            time_label = ts.strftime("%b %d")

        series.append({
            "time": time_label,
            "heartRate": safe_int(row.get('heart_rate', 0)),
            "systolic": safe_int(row.get('blood_pressure_systolic', 0)),
            "diastolic": safe_int(row.get('blood_pressure_diastolic', 0)),
            "glucose": safe_int(row.get('glucose', 0)),
            "temperature": safe_float(row.get('skin_temperature', 0), 0.0),
            "respiratory": safe_float(row.get('respiratory_rate', 0), 0.0),
            "oxygen": safe_int(row.get('spo2', 0))
        })

    return series


def fetch_fall_alerts_from_s3():
    """Fetch fall alerts from S3 with tiered response system

    ✅ UPDATED: 70-95% = patient check first, ≥95% = immediate doctor alert
    """
    global fall_alerts, processed_fall_alert_ids
    if not s3_client:
        return False
    try:
        date_str = datetime.now().strftime("%Y-%m-%d")
        s3_key = f"{PATIENT_ID}/fall_alerts/{date_str}.json"
        obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        alerts = json.loads(obj['Body'].read().decode('utf-8'))

        new_alerts = [alert for alert in alerts if alert['id'] not in processed_fall_alert_ids]

        if new_alerts:
            logger.info(f"📥 Found {len(new_alerts)} NEW alerts")
            fall_alerts.extend(new_alerts)

            for alert in new_alerts:
                alert_id = alert.get('id')
                confidence = alert.get('confidence', 0)
                patient_id = alert.get('patient_id', PATIENT_ID)
                alert_time = alert.get('datetime')

                logger.info(f"🚨 Processing NEW alert: ID={alert_id}, Confidence={confidence}%")

                # ✅ CHANGED: 95% threshold for immediate critical alert
                if confidence >= 80:
                    logger.warning(f"🔴 CRITICAL FALL (≥95%): Immediate doctor notification")

                    # ✅ STANDARDIZED FORMAT
                    fall_alert_payload = {
                        'patient_id': patient_id,
                        'confidence': confidence,
                        'datetime': alert_time,
                        'alert_id': alert_id,
                        'type': 'fall_detected',
                        'for_role': 'doctor'
                    }
                    socketio.emit('fall_alert', fall_alert_payload, namespace='/')
                    notify_telegram_alert(fall_alert_payload, alert_kind="Fall Alert")

                    processed_fall_alert_ids.add(alert_id)
                    save_processed_fall_alert(alert_id, patient_id, confidence, alert_time)
                    logger.info(f"✅ Critical alert {alert_id} sent & marked processed")

                # ✅ CHANGED: 70-95% = patient check-in first
                elif 70 <= confidence < 80:
                    logger.warning(f"🟡 MODERATE FALL (70-95%): Patient check required")

                    pending_fall_responses[alert_id] = {
                        'alert': alert,
                        'timestamp': time.time(),
                        'patient_responded': False,
                        'confidence': confidence
                    }

                    patient_payload = {
                        "type": "fall_check",
                        "alert_id": alert_id,
                        "confidence": confidence,
                        "patient_id": patient_id,
                        "datetime": alert_time,
                        "for_role": "patient"
                    }
                    socketio.emit('fall_check', patient_payload, namespace='/')

                    processed_fall_alert_ids.add(alert_id)
                    save_processed_fall_alert(alert_id, patient_id, confidence, alert_time)
                    logger.info(f"✅ Moderate fall {alert_id} - patient check sent")

                    # ✅ FIX: Only start timeout thread if not already running for this alert
                    with timeout_threads_lock:
                        if alert_id not in active_timeout_threads:
                            active_timeout_threads.add(alert_id)
                            threading.Thread(
                                target=check_patient_response_timeout,
                                args=(alert_id,),
                                daemon=True
                            ).start()
                            logger.info(f"⏰ Started timeout thread for alert {alert_id}")
                        else:
                            logger.info(f"⏭️ Timeout thread already running for alert {alert_id}, skipping")

                else:
                    logger.info(f"⚪ LOW CONFIDENCE FALL (<70%): Ignored")
                    processed_fall_alert_ids.add(alert_id)
                    save_processed_fall_alert(alert_id, patient_id, confidence, alert_time)
                    continue

            logger.info(f"✅ Processed {len(new_alerts)} new fall alerts")
        return True
    except Exception as e:
        if "NoSuchKey" not in str(e):
            logger.error(f"Error fetching fall alerts: {e}")
        return False


def fetch_emergency_alerts_from_s3():
    """✅ FIXED: Fetch emergency alerts from S3 with tiered fall response system"""
    global emergency_alerts, processed_emergency_alert_ids, pending_fall_responses
    if not s3_client:
        return False
    try:
        date_str = datetime.now().strftime("%Y-%m-%d")
        s3_key = f"{PATIENT_ID}/emergency_alerts/{date_str}.json"
        obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        alerts = json.loads(obj['Body'].read().decode('utf-8'))

        new_alerts = []
        for alert in alerts:
            alert_key = f"{alert.get('patient_id')}_{alert.get('type')}_{alert.get('timestamp')}"
            
            # ✅ Skip if already processed (by MQTT or previous S3 poll)
            if alert_key not in processed_emergency_alert_ids:
                new_alerts.append(alert)
                processed_emergency_alert_ids.add(alert_key)
                save_processed_emergency_alert(alert_key)
                logger.debug(f"✅ New alert from S3: {alert_key}")
            else:
                logger.debug(f"⏭️ Skipping duplicate alert: {alert_key}")

        if new_alerts:
            logger.info(f"🚨 Found {len(new_alerts)} NEW emergency alerts from S3")
            emergency_alerts.extend(new_alerts)

            for alert in new_alerts:
                alert_type = alert.get('type', '')

                # ✅ SPECIAL HANDLING FOR FALL DETECTION ALERTS
                if alert_type == 'fall_detected':
                    # Extract confidence from details (e.g., "Fall detected with 70.49% confidence")
                    details = alert.get('details', '')
                    confidence = 0

                    # Try to extract confidence percentage
                    import re
                    match = re.search(r'(\d+\.?\d*)%', details)
                    if match:
                        confidence = float(match.group(1))

                    patient_id = alert.get('patient_id', PATIENT_ID)
                    alert_time = alert.get('datetime', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    alert_id = alert.get('timestamp', str(int(time.time() * 1000)))

                    logger.info(f"🚨 Processing FALL ALERT: Confidence={confidence}%")

                    # ✅ TIER 1: <70% = Ignore
                    if confidence < 70:
                        logger.info(f"⚪ LOW CONFIDENCE FALL (<70%): Ignored")
                        continue

                    # ✅ TIER 2: 70-80% = Patient Check-In
                    elif 70 <= confidence < 80:
                        logger.warning(f"🟡 MODERATE FALL (70-80%): Patient check required")

                        # Store pending response
                        pending_fall_responses[alert_id] = {
                            'alert': alert,
                            'timestamp': time.time(),
                            'patient_responded': False,
                            'confidence': confidence,
                            'patient_id': patient_id,
                            'datetime': alert_time
                        }

                        # Send check-in to PATIENT
                        patient_payload = {
                            "type": "fall_check",
                            "alert_id": alert_id,
                            "confidence": confidence,
                            "patient_id": patient_id,
                            "datetime": alert_time,
                            "for_role": "patient"
                        }
                        socketio.emit('fall_check', patient_payload, namespace='/')
                        logger.info(f"✅ Moderate fall {alert_id} - patient check sent")

                        # ✅ FIX: Only start timeout thread if not already running for this alert
                        with timeout_threads_lock:
                            if alert_id not in active_timeout_threads:
                                active_timeout_threads.add(alert_id)
                                threading.Thread(
                                    target=check_patient_response_timeout,
                                    args=(alert_id,),
                                    daemon=True
                                ).start()
                                logger.info(f"⏰ Started timeout thread for alert {alert_id}")
                            else:
                                logger.info(f"⏭️ Timeout thread already running for alert {alert_id}, skipping")

                        # Don't send to doctor yet - wait for patient response
                        continue

                    # ✅ TIER 3: ≥80% = Immediate Critical Alert to Doctor
                    else:
                        logger.warning(f"🔴 CRITICAL FALL (≥80%): Immediate doctor notification")

                        # Send as fall_alert for critical falls
                        fall_alert_payload = {
                            'patient_id': patient_id,
                            'confidence': confidence,
                            'datetime': alert_time,
                            'alert_id': alert_id,
                            'type': 'fall_detected',
                            'for_role': 'doctor'
                        }
                        socketio.emit('fall_alert', fall_alert_payload, namespace='/')
                        notify_telegram_alert(fall_alert_payload, alert_kind="Fall Alert")
                        logger.info(f"✅ Critical fall alert sent to doctor")
                        continue

                # ✅ FOR NON-FALL EMERGENCY ALERTS: Send normally
                # ✅ FOR NON-FALL EMERGENCY ALERTS: STANDARDIZED FORMAT
                patient_id = alert.get('patient_id', PATIENT_ID)
                alert_time = alert.get('datetime', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                alert_title = alert.get('alert_title', 'ALERT')

                # Extract vital sign value from details
                details = alert.get('details', '')
                value = ''

                # Extract value based on alert type
                if 'temperature' in alert_type.lower():
                    match = re.search(r'(\d+\.?\d*)\s*°?C', details)
                    if match:
                        value = f"{match.group(1)}°C"
                elif 'heart_rate' in alert_type.lower():
                    match = re.search(r'(\d+)\s*BPM', details, re.IGNORECASE)
                    if match:
                        value = f"{match.group(1)} BPM"
                elif 'glucose' in alert_type.lower():
                    match = re.search(r'(\d+)\s*mg/dL', details, re.IGNORECASE)
                    if match:
                        value = f"{match.group(1)} mg/dL"
                elif 'spo2' in alert_type.lower() or 'oxygen' in alert_type.lower():
                    match = re.search(r'(\d+)%', details)
                    if match:
                        value = f"{match.group(1)}%"
                elif 'blood_pressure' in alert_type.lower() or 'bp' in alert_type.lower():
                    match = re.search(r'(\d+/\d+)\s*mmHg', details, re.IGNORECASE)
                    if match:
                        value = f"{match.group(1)} mmHg"

                # ✅ STANDARDIZED FORMAT FOR ALL NON-FALL EMERGENCIES
                standardized_payload = {
                    'patient_id': patient_id,
                    'datetime': alert_time,
                    'alert_title': alert_title,
                    'type': alert_type,
                    'value': value,
                    'for_role': 'doctor'
                }

                logger.warning(f"🚨 EMERGENCY: {alert_title} - {details}")
                socketio.emit('emergency_alert', standardized_payload, namespace='/')
                notify_telegram_alert(standardized_payload, alert_kind="Emergency Alert")
            logger.info(f"✅ Processed {len(new_alerts)} emergency alerts")

        return True
    except s3_client.exceptions.NoSuchKey:
        logger.debug(f"No emergency alerts file for today")
        return False
    except Exception as e:
        logger.error(f"Error fetching emergency alerts: {e}")
        return False


def check_patient_response_timeout(alert_id):
    """Check patient response after 10 seconds"""
    time.sleep(10)

    if alert_id in pending_fall_responses:
        response_data = pending_fall_responses[alert_id]
        if not response_data['patient_responded']:
            confidence = response_data.get('confidence', 0)
            alert_time = response_data.get('datetime', 'Unknown')
            patient_id = response_data.get('patient_id', PATIENT_ID)

            emergency_alerts.append({
                "patient_id": patient_id,
                "patient_name": response_data.get("patient_name"),
                "confidence": confidence,
                "datetime": alert_time,
                "alert_id": alert_id,
                "type": "fall_detected"
            })

            fall_alert_payload = {
                'patient_id': patient_id,
                'confidence': confidence,
                'datetime': alert_time,
                'alert_id': alert_id,
                'type': 'no_response',
                'for_role': 'doctor'
            }
            socketio.emit('fall_alert', fall_alert_payload, namespace='/')
            notify_telegram_alert(fall_alert_payload, alert_kind="Fall Alert")

            del pending_fall_responses[alert_id]

    with timeout_threads_lock:
        if alert_id in active_timeout_threads:
            active_timeout_threads.remove(alert_id)

def s3_polling_loop():
    """Background S3 polling"""
    while True:
        try:
            fetch_vitals_from_s3(PATIENT_ID)
            fetch_glucose_from_s3(PATIENT_ID)
            fetch_wifi_connection_from_s3()
            fetch_fall_alerts_from_s3()
            fetch_emergency_alerts_from_s3()
            time.sleep(S3_POLL_INTERVAL)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(S3_POLL_INTERVAL)


@socketio.on('connect')
def handle_connect():
    logger.info(f"🔌 Client connected: {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"🔌 Client disconnected: {request.sid}")


@socketio.on('emergency_alert')
def handle_emergency_alert(data):
    """Handle emergency alerts from edge server"""
    try:
        data = data or {}
        patient_id = data.get('patient_id') or PATIENT_ID

        if str(patient_id) != str(PATIENT_ID):
            logger.info(f"⚠️ Ignoring emergency alert for patient {patient_id} (active: {PATIENT_ID})")
            return

        data['patient_id'] = str(patient_id)

        logger.warning(f"🚨 EMERGENCY ALERT RECEIVED: {data.get('alert_title')}")
        emergency_alerts.append(data)
        alert_key = f"{data.get('patient_id')}_{data.get('type')}_{data.get('timestamp')}"
        processed_emergency_alert_ids.add(alert_key)
        save_processed_emergency_alert(alert_key)
        socketio.emit('emergency_alert', data, namespace='/')
        notify_telegram_alert(data, alert_kind="Emergency Alert")
        logger.info(f"✅ Emergency alert broadcasted to clients")
    except Exception as e:
        logger.error(f"❌ Error handling emergency alert: {e}")


@app.before_request
def make_session_permanent():
    session.permanent = True


@app.route("/")
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    if session.get('role') == 'doctor':
        return redirect(url_for('doctor_dashboard'))
    return redirect(url_for('patient_dashboard'))


@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            data = request.get_json()
            username = data.get('username', '').strip()
            name = data.get('name', '').strip()
            role = data.get('role', '').strip()
            password = data.get('password', '')
            patient_id_input = data.get('patient_id', '').strip()

            if not username or not name or not role or not password:
                return jsonify({'success': False, 'message': 'All fields required'})

            if len(username) < 3:
                return jsonify({'success': False, 'message': 'Username min 3 characters'})

            if len(password) < 6:
                return jsonify({'success': False, 'message': 'Password min 6 characters'})

            if username in USERS:
                return jsonify({'success': False, 'message': 'Username exists'})

            if role not in ['patient', 'doctor']:
                return jsonify({'success': False, 'message': 'Invalid role'})

            assigned_patient_id = None
            if role == 'patient':
                if patient_id_input:
                    if not check_s3_patient_data_exists(patient_id_input):
                        return jsonify(
                            {'success': False, 'message': f'Patient ID {patient_id_input} not found in system'})
                    assigned_patient_id = patient_id_input
                else:
                    assigned_patient_id = PATIENT_ID

            USERS[username] = {
                'password': password,
                'role': role,
                'name': name,
                'patient_id': assigned_patient_id
            }

            save_users()
            logger.info(f"New {role} registered: {username} (Patient ID: {assigned_patient_id})")
            return jsonify({'success': True, 'message': 'Account created!'})
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return jsonify({'success': False, 'message': 'Registration failed'})

    return render_template('register.html')


@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            data = request.get_json()
            username = data.get('username', '').strip()
            password = data.get('password', '')

            if username in USERS and USERS[username]['password'] == password:
                session['username'] = username
                session['role'] = USERS[username]['role']
                session['name'] = USERS[username]['name']

                if USERS[username]['role'] == 'patient': 
                    session['patient_id'] = USERS[username].get('patient_id', PATIENT_ID) 
                    logger.info(f"✅ Patient logged in: {username} (ID: {session['patient_id']})") 
                    maybe_refresh_librelink_glucose(session['patient_id']) 
                else: 
                    session['patient_id'] = None 
                    logger.info(f"✅ Doctor logged in: {username}") 

                return jsonify({'success': True, 'role': USERS[username]['role']})

            return jsonify({'success': False, 'message': 'Invalid credentials'})
        except Exception as e:
            logger.error(f"Login error: {e}")
            return jsonify({'success': False, 'message': 'Login failed'})

    return render_template('login.html')


@app.route("/logout")
def logout():
    username = session.get('username', 'Unknown')
    session.clear()
    logger.info(f"User logged out: {username}")
    return redirect(url_for('login'))


# ============================================================================
# ✅ FIXED DELETE ACCOUNT ENDPOINT - Replace in app.py
# ============================================================================

@app.route("/delete_account", methods=['POST'])
@login_required
def delete_account():
    """✅ FIXED: Delete user account with verified LibreLink credential removal"""
    try:
        # ✅ STEP 1: Get password and validate user FIRST
        data = request.get_json()
        password = data.get('password', '')
        username = session.get('username')

        if not username:
            return jsonify({'success': False, 'message': 'Not logged in'}), 401

        if username not in USERS or USERS[username]['password'] != password:
            return jsonify({'success': False, 'message': 'Invalid password'}), 403

        # ✅ STEP 2: Get user info AFTER validation
        user_role = USERS[username]['role']
        patient_id = USERS[username].get('patient_id')

        logger.info(f"🗑️ Deleting account: {username} ({user_role})")

        # ✅ STEP 3: Delete LibreLink credentials from S3 with VERIFICATION
        credentials_deleted = False
        credentials_cleanup_warnings = []

        if user_role == 'patient' and patient_id and s3_client:
            try:
                s3_key = f"{patient_id}/librelink_credentials.json"

                # First, verify credentials exist
                try:
                    s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
                    credentials_exist = True
                    logger.info(f"📋 LibreLink credentials found in S3: {s3_key}")
                except s3_client.exceptions.NoSuchKey:
                    credentials_exist = False
                    credentials_deleted = True  # Nothing to delete
                    logger.info(f"⚠️ No LibreLink credentials found in S3 for patient {patient_id}")

                # Delete if they exist
                if credentials_exist:
                    logger.info(f"🗑️ Deleting LibreLink credentials from S3...")
                    s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key)

                    # ✅ CRITICAL: Verify deletion succeeded
                    time.sleep(0.5)  # Brief delay for S3 consistency
                    try:
                        s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
                        # If we get here, file still exists!
                        logger.error(f"❌ CRITICAL: Credentials still exist after deletion!")
                        credentials_deleted = False
                        credentials_cleanup_warnings.append(
                            "LibreLink credentials may still exist in S3"
                        )
                    except s3_client.exceptions.NoSuchKey:
                        # File is gone - success!
                        logger.info(f"✅ Verified: LibreLink credentials deleted from S3")
                        credentials_deleted = True

            except Exception as e:
                logger.error(f"❌ Error deleting LibreLink credentials from S3: {e}")
                credentials_deleted = False
                credentials_cleanup_warnings.append(
                    f"Error removing LibreLink credentials: {str(e)}"
                )
        elif user_role == 'patient' and patient_id:
            if not s3_client:
                credentials_cleanup_warnings.append("S3 not available - could not verify credential removal")
            credentials_deleted = True  # Can't verify, but continue

        # ✅ STEP 4: Notify edge device via MQTT to stop glucose monitoring
        mqtt_notification_sent = False
        if user_role == 'patient' and patient_id and mqtt_client and mqtt_client.is_connected:
            try:
                notification_payload = {
                    'patient_id': patient_id,
                    'action': 'account_deleted',
                    'timestamp': int(time.time() * 1000),
                    'datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                success = mqtt_client.publish(
                    MQTTConfig.get_account_status_topic(patient_id),
                    notification_payload
                )

                if success:
                    logger.info(f"✅ Notified edge device: Account {patient_id} deleted")
                    mqtt_notification_sent = True
                else:
                    logger.warning(f"⚠️ Failed to notify edge device via MQTT")
                    credentials_cleanup_warnings.append(
                        "Edge device not notified (may need manual restart)"
                    )

            except Exception as e:
                logger.error(f"❌ Error notifying edge device: {e}")
                credentials_cleanup_warnings.append(
                    "Could not notify edge device"
                )

        # ✅ STEP 5: Try to delete from edge device directly (optional - may fail if different WiFi)
        if user_role == 'patient' and patient_id and edge_device_client.base_url:
            try:
                success, message = edge_device_client.delete_librelink(patient_id)
                if success:
                    logger.info(f"✅ LibreLink credentials cleared from edge device")
                else:
                    logger.warning(f"⚠️ Could not clear edge device credentials: {message}")
                    # Don't add warning - MQTT notification is more reliable
            except Exception as e:
                logger.warning(f"⚠️ Edge device deletion error (may be on different WiFi): {e}")
                # Don't add warning - MQTT notification is more reliable

        # ✅ STEP 6: Delete user from database
        del USERS[username]
        save_users()

        # ✅ STEP 7: Clear session
        session.clear()

        # ✅ STEP 8: Prepare response with warnings if any
        response_message = 'Account deleted successfully'
        if credentials_cleanup_warnings:
            response_message += '\n\nWarnings:\n- ' + '\n- '.join(credentials_cleanup_warnings)
            logger.warning(f"⚠️ Account deleted with warnings: {credentials_cleanup_warnings}")
        else:
            logger.info(f"✅ Account deleted successfully: {username}")

        return jsonify({
            'success': True,
            'message': response_message,
            'warnings': credentials_cleanup_warnings if credentials_cleanup_warnings else None
        })

    except Exception as e:
        logger.error(f"❌ Error deleting account: {e}")
        return jsonify({'success': False, 'message': 'Account deletion failed'}), 500
@app.route("/doctor")
@role_required('doctor')
def doctor_dashboard():
    patients = load_patient_meta()
    try:
        fetch_vitals_from_s3(PATIENT_ID)
        fetch_glucose_from_s3(PATIENT_ID)
    except Exception:
        pass
    conditions = [
        "Hypertension", "Diabetes", "Heart Condition", "Asthma",
        "High Cholesterol", "Arthritis", "Thyroid", "COPD"
    ]
    statuses = ["Stable", "Urgent", "Critical"]
    patient_cards = []
    patient_details = {}

    for idx, patient in enumerate(patients):
        patient_id = normalize_patient_id(patient.get('patient_id', '') or '') or str(patient.get('patient_id', '')).strip()
        name = patient.get('name', f"Patient {patient_id}")
        sex = patient.get('sex', 'N/A')
        age = patient.get('age') or patient.get('Age') or "0"
        phone = patient.get('phone', 'N/A')
        condition = conditions[idx % len(conditions)]
        if str(patient_id) == str(PATIENT_ID):
            status = compute_patient_status(patient_id)
        else:
            status = statuses[idx % len(statuses)]
        last_visit = (datetime.now() - timedelta(days=(idx % 14) + 1)).strftime("%Y-%m-%d")

        patient_cards.append({
            "id": patient_id,
            "name": name,
            "age": int(age) if str(age).isdigit() else 0,
            "condition": condition,
            "lastVisit": last_visit,
            "status": status
        })

        patient_details[patient_id] = {
            "id": patient_id,
            "name": name,
            "age": int(age) if str(age).isdigit() else 0,
            "sex": "Female" if str(sex).upper().startswith("F") else "Male" if str(sex).upper().startswith("M") else "N/A",
            "tel": phone,
            "condition": condition
        }

    preload = build_dashboard_preload(PATIENT_ID, use_dummy=False)

    return render_template(
        'doctor_dashboard.html',
        user_name=session.get('name', 'Doctor'),
        patients=patient_cards,
        patient_details=patient_details,
        preload=preload
    )


@app.route("/doctor/profile")
@role_required('doctor')
def doctor_profile_page():
    username = session.get('username')
    profile = get_doctor_profile(username)
    return render_template(
        'doctor_profile.html',
        profile=profile,
        user_name=profile.get("name") or session.get('name', 'Doctor')
    )


@app.route("/weekly-analysis")
@app.route("/weekly-analysis/")
@role_required('doctor')
def weekly_analysis():
    weekly_dir = os.path.join(app.static_folder, "weekly_analysis")
    return send_from_directory(weekly_dir, "index.html")


@app.route("/weekly-analysis/<path:path>")
@role_required('doctor')
def weekly_analysis_assets(path):
    weekly_dir = os.path.join(app.static_folder, "weekly_analysis")
    return send_from_directory(weekly_dir, path)


@app.route("/doctor/patient/<patient_id>")
@role_required('doctor')
def doctor_patient_dashboard(patient_id):
    return doctor_dashboard()


@app.route("/doctor/chat")
@role_required('doctor')
def doctor_chat():
    return render_template('doctor.html', user_name=session.get('name', 'Doctor'))


@app.route("/api/doctor/profile", methods=['GET', 'POST'])
@role_required('doctor')
def doctor_profile_api():
    username = session.get('username')
    if request.method == 'GET':
        return jsonify({"success": True, "profile": get_doctor_profile(username)})

    form = request.form if request.form else (request.get_json(silent=True) or {})
    updates = {
        "name": form.get("name", ""),
        "email": form.get("email", ""),
        "phone_number": form.get("phone_number", ""),
        "whatsapp_number": form.get("whatsapp_number", ""),
        "home_address": form.get("home_address", "")
    }

    profile_picture = request.files.get("profile_picture")
    if profile_picture and profile_picture.filename:
        os.makedirs(DOCTOR_PROFILE_UPLOAD_DIR, exist_ok=True)
        filename = secure_filename(profile_picture.filename)
        ext = os.path.splitext(filename)[1].lower() or ".png"
        stored_name = f"{secure_filename(username)}{ext}"
        file_path = os.path.join(DOCTOR_PROFILE_UPLOAD_DIR, stored_name)
        profile_picture.save(file_path)
        updates["profile_picture"] = f"local_data/doctor_profiles/{stored_name}".replace("\\", "/")

    profile = save_doctor_profile(username, updates)
    session['name'] = profile.get("name") or session.get('name', 'Doctor')
    return jsonify({"success": True, "profile": profile})


@app.route("/api/weekly-analysis", methods=['GET'])
@role_required('doctor')
def weekly_analysis_api():
    patient_id = normalize_patient_id(request.args.get('patient_id') or PATIENT_ID) or PATIENT_ID
    payload = get_weekly_analysis_payload(patient_id)
    return jsonify({"success": True, **payload})


@app.route("/api/weekly-analysis/reports", methods=['POST'])
@role_required('doctor')
def weekly_analysis_upload_report():
    patient_id = normalize_patient_id(request.form.get('patient_id') or PATIENT_ID) or PATIENT_ID
    category = (request.form.get('category') or 'other').strip().lower()
    if category not in {'lab', 'ecg', 'prescription', 'other'}:
        category = 'other'

    uploaded_file = request.files.get('file')
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"success": False, "message": "PDF file required"}), 400

    filename = secure_filename(uploaded_file.filename)
    if not filename.lower().endswith('.pdf'):
        return jsonify({"success": False, "message": "Only PDF files are supported"}), 400

    patient_dir = os.path.join(WEEKLY_REPORTS_DIR, patient_id)
    os.makedirs(patient_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(patient_dir, stored_name)
    uploaded_file.save(file_path)
    size_mb = os.path.getsize(file_path) / (1024 * 1024)

    report = {
        "id": uuid.uuid4().hex,
        "name": filename,
        "uploadDate": datetime.now().strftime("%Y-%m-%d"),
        "size": f"{size_mb:.2f} MB",
        "category": category,
        "stored_name": stored_name,
        "path": _weekly_reports_static_relpath(patient_id, stored_name),
        "url": url_for('static', filename=_weekly_reports_static_relpath(patient_id, stored_name))
    }

    data, patient_store = get_weekly_patient_store(patient_id)
    patient_store["reports"].insert(0, report)
    save_weekly_analysis_data(data)
    return jsonify({"success": True, "report": report})


@app.route("/api/weekly-analysis/reports/<report_id>", methods=['DELETE'])
@role_required('doctor')
def weekly_analysis_delete_report(report_id):
    patient_id = normalize_patient_id(request.args.get('patient_id') or PATIENT_ID) or PATIENT_ID
    data, patient_store = get_weekly_patient_store(patient_id)
    reports = patient_store.get("reports", [])
    removed = None
    kept = []
    for report in reports:
        if str(report.get("id")) == str(report_id) and removed is None:
            removed = report
        else:
            kept.append(report)
    if not removed:
        return jsonify({"success": False, "message": "Report not found"}), 404
    patient_store["reports"] = kept
    save_weekly_analysis_data(data)
    file_path = os.path.join(app.static_folder, removed.get("path", "").replace("/", os.sep))
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass
    return jsonify({"success": True, "deleted": report_id})


@app.route("/api/weekly-analysis/action-plans", methods=['POST'])
@role_required('doctor')
def weekly_analysis_add_action_plan():
    payload = request.get_json(silent=True) or {}
    patient_id = normalize_patient_id(payload.get('patient_id') or PATIENT_ID) or PATIENT_ID
    content = str(payload.get('content') or '').strip()
    if not content:
        return jsonify({"success": False, "message": "Content required"}), 400

    data, patient_store = get_weekly_patient_store(patient_id)
    next_version = max([int(item.get("version", 0) or 0) for item in patient_store.get("action_plans", [])] + [0]) + 1
    item = {
        "id": uuid.uuid4().hex,
        "version": next_version,
        "createdDate": datetime.now().strftime("%Y-%m-%d"),
        "content": content
    }
    patient_store["action_plans"].insert(0, item)
    save_weekly_analysis_data(data)
    return jsonify({"success": True, "action_plan": item})


@app.route("/api/weekly-analysis/action-plans/<plan_id>", methods=['DELETE'])
@role_required('doctor')
def weekly_analysis_delete_action_plan(plan_id):
    patient_id = normalize_patient_id(request.args.get('patient_id') or PATIENT_ID) or PATIENT_ID
    data, patient_store = get_weekly_patient_store(patient_id)
    original = patient_store.get("action_plans", [])
    patient_store["action_plans"] = [item for item in original if str(item.get("id")) != str(plan_id)]
    if len(original) == len(patient_store["action_plans"]):
        return jsonify({"success": False, "message": "Action plan not found"}), 404
    save_weekly_analysis_data(data)
    return jsonify({"success": True, "deleted": plan_id})


@app.route("/api/weekly-analysis/reviews", methods=['POST'])
@role_required('doctor')
def weekly_analysis_add_review():
    payload = request.get_json(silent=True) or {}
    patient_id = normalize_patient_id(payload.get('patient_id') or PATIENT_ID) or PATIENT_ID
    content = str(payload.get('content') or '').strip()
    if not content:
        return jsonify({"success": False, "message": "Content required"}), 400

    data, patient_store = get_weekly_patient_store(patient_id)
    item = {
        "id": uuid.uuid4().hex,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "content": content
    }
    patient_store["doctor_reviews"].insert(0, item)
    save_weekly_analysis_data(data)
    return jsonify({"success": True, "doctor_review": item})


@app.route("/api/weekly-analysis/reviews/<review_id>", methods=['DELETE'])
@role_required('doctor')
def weekly_analysis_delete_review(review_id):
    patient_id = normalize_patient_id(request.args.get('patient_id') or PATIENT_ID) or PATIENT_ID
    data, patient_store = get_weekly_patient_store(patient_id)
    original = patient_store.get("doctor_reviews", [])
    patient_store["doctor_reviews"] = [item for item in original if str(item.get("id")) != str(review_id)]
    if len(original) == len(patient_store["doctor_reviews"]):
        return jsonify({"success": False, "message": "Review not found"}), 404
    save_weekly_analysis_data(data)
    return jsonify({"success": True, "deleted": review_id})


@app.route("/api/weekly-analysis/send-email", methods=['POST'])
@role_required('doctor')
def weekly_analysis_send_email():
    payload = request.get_json(silent=True) or {}
    patient_id = normalize_patient_id(payload.get('patient_id') or PATIENT_ID) or PATIENT_ID
    patient_name = str(payload.get('patient_name') or get_patient_name_by_id(patient_id) or f"Patient {patient_id}")
    username = session.get('username')
    doctor_profile = get_doctor_profile(username)
    doctor_email = (doctor_profile.get("email") or "").strip()
    doctor_name = doctor_profile.get("name") or session.get("name") or "Doctor"

    if not doctor_email:
        return jsonify({
            "success": False,
            "message": "Doctor email is missing. Add it in the doctor profile first."
        }), 400

    pdf_path = None
    temp_dir = None
    try:
        pdf_path, summary_payload = generate_weekly_summary_pdf(patient_id, patient_name, doctor_name)
        temp_dir = os.path.dirname(pdf_path)
        attachment_paths = [pdf_path]
        for report in summary_payload.get("reports", []):
            report_path = os.path.join(app.static_folder, report.get("path", "").replace("/", os.sep))
            if os.path.exists(report_path):
                attachment_paths.append(report_path)

        subject = f"Weekly patient report - {patient_name} ({patient_id})"
        body = (
            f"Weekly patient summary for {patient_name} ({patient_id}) is attached.\n\n"
            "Included:\n"
            "- Summary PDF\n"
            "- Uploaded weekly report PDFs (attached separately when available)\n"
            "- Emergency alerts, doctor reviews, action plans, and recent advice notes inside the summary PDF\n"
        )
        sent, message = send_weekly_email(doctor_email, subject, body, attachment_paths)
        status = 200 if sent else 500
        return jsonify({"success": sent, "message": message}), status
    finally:
        if temp_dir and os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@app.route("/patient")
@role_required('patient')
def patient_dashboard():
    patient_id = session.get('patient_id', PATIENT_ID)
    patients = load_patient_meta()
    patient_record = next((p for p in patients if str(p.get('patient_id')) == str(patient_id)), None)
    if not patient_record:
        patient_record = {
            "patient_id": patient_id,
            "name": "Tammy Hale" if str(patient_id) == str(PATIENT_ID) else f"Patient {patient_id}",
            "sex": "N/A",
            "age": "0",
            "phone": "N/A"
        }
    elif str(patient_id) == str(PATIENT_ID):
        patient_record["name"] = "Tammy Hale"
    patient_view = {
        "id": str(patient_record.get('patient_id', patient_id)),
        "name": patient_record.get('name', f"Patient {patient_id}"),
        "age": int(patient_record.get('age', 0)) if str(patient_record.get('age', 0)).isdigit() else 0,
        "sex": "Female" if str(patient_record.get('sex', '')).upper().startswith("F") else "Male" if str(patient_record.get('sex', '')).upper().startswith("M") else "N/A",
        "phone": patient_record.get('phone', 'N/A')
    }
    patient_details = {
        patient_view["id"]: {
            "id": patient_view["id"],
            "name": patient_view["name"],
            "age": patient_view["age"],
            "sex": patient_view["sex"],
            "tel": patient_view["phone"],
            "condition": "Hypertension"
        }
    }

    preload = build_dashboard_preload(patient_id, use_dummy=(str(patient_id) != str(PATIENT_ID)))

    return render_template(
        'patient_dashboard.html',
        user_name=session.get('name', 'Patient'),
        patient_id=patient_id,
        patient=patient_view,
        patient_details=patient_details,
        preload=preload
    )


@app.route("/patient/chat")
@role_required('patient')
def patient_chat():
    patient_id = session.get('patient_id', PATIENT_ID)
    return render_template('patient.html',
                           user_name=session.get('name', 'Patient'),
                           patient_id=patient_id)


@app.route("/chatroom")
@login_required
def chatroom():
    """Serve the shared doctor-patient-REMONI chatroom app."""
    chatroom_build = os.path.join(os.path.dirname(__file__), 'chatroom', 'build')
    return send_from_directory(chatroom_build, 'index.html')


@app.route("/chatroom/<path:path>")
@login_required
def chatroom_assets(path):
    chatroom_build = os.path.join(os.path.dirname(__file__), 'chatroom', 'build')
    return send_from_directory(chatroom_build, path)


@app.route("/doctor/chats")
@role_required('doctor')
def doctor_chat_list():
    return render_template("doctor_chat_list.html")


@app.route("/patient/chats")
@role_required('patient')
def patient_chat_list():
    return render_template("patient_chat_list.html")


@app.route("/direct-chat/<patient_id>")
@login_required
def direct_chat(patient_id):
    user_role = session.get('role')
    user_patient_id = session.get('patient_id')

    if user_role == 'patient' and str(patient_id) != str(user_patient_id):
        return redirect(url_for('patient_chat_list'))

    back_url = '/doctor/chats' if user_role == 'doctor' else '/patient/chats'
    return render_template(
        "direct_chat.html",
        role=user_role,
        patient_id=patient_id,
        back_url=back_url
    )


@app.route("/api/direct_chat/messages", methods=['GET', 'POST'])
@login_required
def direct_chat_messages():
    user_role = session.get('role')
    user_patient_id = session.get('patient_id')
    patient_id = request.args.get('patient_id') or (request.get_json(silent=True) or {}).get('patient_id') or PATIENT_ID

    if user_role == 'patient' and str(patient_id) != str(user_patient_id):
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    file_path = os.path.join('static', 'local_data', 'direct_chat_messages.json')
    lock = threading.Lock()

    def load_msgs():
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_msgs(data):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)

    if request.method == 'GET':
        with lock:
            all_msgs = load_msgs()
        msgs = [m for m in all_msgs if str(m.get('patient_id')) == str(patient_id)]
        return jsonify({"success": True, "messages": msgs[-200:]})

    payload = request.get_json(silent=True) or {}
    text = str(payload.get('text') or '').strip()
    if not text:
        return jsonify({"success": False, "message": "Empty message"}), 400

    sender = user_role if user_role in ['doctor', 'patient'] else 'patient'
    now = datetime.now()
    msg = {
        "id": str(int(time.time() * 1000)),
        "sender": sender,
        "text": text,
        "timestamp": now.strftime("%I:%M %p"),
        "date": now.strftime("%Y-%m-%d"),
        "senderName": session.get('name') or sender.capitalize(),
        "patient_id": patient_id
    }

    with lock:
        all_msgs = load_msgs()
        all_msgs.append(msg)
        save_msgs(all_msgs)

    return jsonify({"success": True, "message": msg})


@app.route("/socket.io/socket.io.js")
def socketio_client_proxy():
    """Serve Socket.IO client from CDN to avoid 400s on local server."""
    return redirect("https://cdn.socket.io/4.4.1/socket.io.min.js")


@app.route("/api/emergency_alerts", methods=['GET'])
@login_required
def get_emergency_alerts():
    """Get emergency alerts for authorized users"""
    try:
        user_role = session.get('role')
        user_patient_id = session.get('patient_id')

        now = datetime.now()
        cutoff = now - timedelta(hours=6)

        def _alert_dt(alert):
            dt = parse_timestamp(alert.get('datetime'))
            if dt:
                return dt
            ts = alert.get('timestamp') or alert.get('alert_id')
            if ts:
                try:
                    ts_val = float(ts)
                    if ts_val > 1e12:
                        return datetime.fromtimestamp(ts_val / 1000)
                    if ts_val > 1e9:
                        return datetime.fromtimestamp(ts_val)
                except Exception:
                    return None
            return None

        def _is_recent(alert):
            dt = _alert_dt(alert)
            return bool(dt and dt >= cutoff)

        # Prune global list to last 6 hours to avoid growth
        try:
            global emergency_alerts
            emergency_alerts = [a for a in emergency_alerts if _is_recent(a)]
        except Exception:
            pass

        if user_role == 'patient':
            filtered_alerts = [a for a in emergency_alerts if a.get('patient_id') == user_patient_id and _is_recent(a)]
        else:
            filtered_alerts = [a for a in emergency_alerts if _is_recent(a)]

        recent_alerts = filtered_alerts[-50:] if len(filtered_alerts) > 50 else filtered_alerts

        normalized_alerts = []
        for alert in recent_alerts:
            item = dict(alert or {})
            alert_type = str(item.get('type') or '').lower()
            reason = str(item.get('reason') or item.get('alert_title') or '').strip()
            confidence = item.get('confidence')
            pid = item.get('patient_id') or user_patient_id or PATIENT_ID
            if str(pid) == str(PATIENT_ID):
                item['patient_name'] = "Tammy Hale"
            elif not item.get('patient_name'):
                item['patient_name'] = get_patient_name_by_id(pid)

            # Severity rules for fall alerts
            if alert_type in {"fall_detected", "no_response", "patient_needs_help"}:
                if alert_type in {"no_response", "patient_needs_help"}:
                    item["severity"] = "CRITICAL"
                else:
                    try:
                        conf_val = float(confidence) if confidence is not None else None
                    except Exception:
                        conf_val = None
                    if conf_val is not None and conf_val >= 80:
                        item["severity"] = "CRITICAL"
                    elif conf_val is not None and conf_val >= 70:
                        item["severity"] = "URGENT"
                    else:
                        item["severity"] = item.get("severity") or "URGENT"

            if not reason or reason.lower() in {"emergency alert", "alert"} or reason.lower().startswith("emergency"):
                inferred = None
                if alert_type.startswith("threshold_"):
                    parts = alert_type.split("_")
                    if len(parts) >= 3:
                        vital_key = "_".join(parts[1:-1])
                        status = parts[-1]
                        label = VITAL_LABELS.get(vital_key, vital_key.replace('_', ' ').title())
                        inferred = f"{label} is {status}"
                else:
                    status = "high" if "high" in alert_type else "low" if "low" in alert_type else None
                    if status:
                        for vital_key, label in VITAL_LABELS.items():
                            if vital_key in alert_type:
                                inferred = f"{label} is {status}"
                                break
                if inferred:
                    item['reason'] = inferred
                    item['alert_title'] = item.get('alert_title') or inferred
                elif "respiratory_rate" in alert_type or "respiratory" in alert_type:
                    item['reason'] = "Respiratory Rate is low" if "low" in alert_type else "Respiratory Rate is high" if "high" in alert_type else "Respiratory Rate alert"
                    item['alert_title'] = item.get('alert_title') or item['reason']

            if ("respiratory_rate" in alert_type or "respiratory" in alert_type) and (not item.get('value') or item.get('value') == "--"):
                rr_val = item.get('respiratory_rate') or item.get('rr')
                if rr_val:
                    try:
                        item['value'] = f"{int(float(rr_val))} {VITAL_UNITS['respiratory_rate']}"
                    except Exception:
                        item['value'] = f"{rr_val} {VITAL_UNITS['respiratory_rate']}"

            normalized_alerts.append(item)

        return jsonify({
            'success': True,
            'alerts': normalized_alerts,
            'total': len(filtered_alerts)
        })
    except s3_client.exceptions.NoSuchKey:  # 404 = Success! ✅
        logger.info("✅ Verified: Credentials deleted")
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route("/api/emergency_alerts/delete", methods=['POST'])
@login_required
def delete_emergency_alert():
    """Delete a single emergency alert by id."""
    try:
        data = request.get_json(silent=True) or {}
        alert_id = str(data.get("alert_id") or data.get("id") or "").strip()
        patient_id = str(data.get("patient_id") or "").strip()
        datetime_val = str(data.get("datetime") or "").strip()
        alert_type = str(data.get("type") or "").strip()

        global emergency_alerts
        removed = False
        updated = []
        for alert in emergency_alerts:
            if removed:
                updated.append(alert)
                continue

            if alert_id and str(alert.get("alert_id") or alert.get("id") or "") == alert_id:
                removed = True
                continue

            if patient_id and datetime_val:
                if str(alert.get("patient_id") or "") == patient_id and str(alert.get("datetime") or "") == datetime_val:
                    if not alert_type or str(alert.get("type") or "") == alert_type:
                        removed = True
                        continue

            updated.append(alert)

        emergency_alerts = updated
        return jsonify({"success": True, "removed": removed})
    except Exception as e:
        logger.error(f"Error deleting emergency alert: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route("/api/doctor_requests", methods=['GET', 'POST'])
@login_required
def doctor_requests_api():
    user_role = session.get('role')
    user_patient_id = session.get('patient_id')

    if request.method == 'GET':
        patient_id = request.args.get('patient_id', '').strip() or user_patient_id or PATIENT_ID
        if user_role == 'patient' and str(patient_id) != str(user_patient_id):
            return jsonify({"success": False, "message": "Unauthorized"}), 403
        with doctor_requests_lock:
            data = load_doctor_requests()
            requests = data.get(str(patient_id), [])
        # return only pending (unseen/unreplied)
        pending = [r for r in requests if r.get('status') == 'pending']
        return jsonify({"success": True, "requests": pending})

    # POST
    if user_role != 'doctor':
        return jsonify({"success": False, "message": "Only doctors can send requests"}), 403

    payload = request.get_json(silent=True) or {}
    patient_id = str(payload.get('patient_id') or PATIENT_ID)
    message = str(payload.get('message') or 'Are you okay? Please respond.').strip()

    now = datetime.now()
    request_item = {
        "id": str(int(time.time() * 1000)),
        "patient_id": patient_id,
        "message": message,
        "status": "pending",
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M")
    }

    with doctor_requests_lock:
        data = load_doctor_requests()
        data.setdefault(patient_id, [])
        data[patient_id].insert(0, request_item)
        save_doctor_requests(data)

    socketio.emit('doctor_request', request_item, namespace='/')
    return jsonify({"success": True, "request": request_item})


@app.route("/api/doctor_requests/reply", methods=['POST'])
@login_required
def doctor_requests_reply():
    user_role = session.get('role')
    user_patient_id = session.get('patient_id')
    if user_role != 'patient':
        return jsonify({"success": False, "message": "Only patients can reply"}), 403

    payload = request.get_json(silent=True) or {}
    request_id = str(payload.get('request_id') or '').strip()
    patient_id = str(payload.get('patient_id') or user_patient_id or PATIENT_ID)
    reply = str(payload.get('message') or '').strip()
    if not request_id or not reply:
        return jsonify({"success": False, "message": "Missing request_id or message"}), 400

    updated = None
    with doctor_requests_lock:
        data = load_doctor_requests()
        requests = data.get(patient_id, [])
        for req in requests:
            if str(req.get('id')) == request_id:
                req['status'] = 'replied'
                req['reply'] = reply
                req['replied_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                updated = req
                break
        if updated:
            save_doctor_requests(data)

    if not updated:
        return jsonify({"success": False, "message": "Request not found"}), 404

    socketio.emit('doctor_request_reply', {
        "patient_id": patient_id,
        "request_id": request_id,
        "reply": reply
    }, namespace='/')

    return jsonify({"success": True})


@app.route("/api/doctor_requests/seen", methods=['POST'])
@login_required
def doctor_requests_seen():
    """Mark a doctor request as seen by the patient."""
    user_role = session.get('role')
    user_patient_id = session.get('patient_id')
    if user_role != 'patient':
        return jsonify({"success": False, "message": "Only patients can mark seen"}), 403

    payload = request.get_json(silent=True) or {}
    request_id = str(payload.get('request_id') or '').strip()
    patient_id = str(payload.get('patient_id') or user_patient_id or PATIENT_ID)
    if not request_id:
        return jsonify({"success": False, "message": "Missing request_id"}), 400

    updated = False
    with doctor_requests_lock:
        data = load_doctor_requests()
        requests = data.get(patient_id, [])
        for req in requests:
            if str(req.get('id')) == request_id and req.get('status') == 'pending':
                req['status'] = 'seen'
                req['seen_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                updated = True
                break
        if updated:
            save_doctor_requests(data)

    return jsonify({"success": True, "updated": updated})


@app.route("/api/chatroom/session", methods=['GET'])
@login_required
def chatroom_session():
    """Return session details for chatroom."""
    return jsonify({
        "success": True,
        "role": session.get('role'),
        "name": session.get('name') or ("Doctor" if session.get('role') == 'doctor' else "Patient"),
        "patient_id": session.get('patient_id') or PATIENT_ID
    })


@app.route("/api/chatroom/messages", methods=['GET', 'POST'])
@login_required
def chatroom_messages():
    """Shared chatroom messages for doctor + patient + REMONI."""
    user_role = session.get('role')
    user_patient_id = session.get('patient_id') or PATIENT_ID
    requested_patient_id = request.args.get('patient_id') or user_patient_id
    target_patient_id = requested_patient_id if user_role == 'doctor' else user_patient_id

    if request.method == 'GET':
        with chatroom_messages_lock:
            all_msgs = load_chatroom_messages()
        # Only show messages for the current patient
        msgs = [m for m in all_msgs if str(m.get('patient_id')) == str(target_patient_id)]
        return jsonify({"success": True, "messages": msgs[-200:]})

    payload = request.get_json(silent=True) or {}
    text = str(payload.get('text') or '').strip()
    sender = str(payload.get('sender') or '').strip()

    if not text:
        return jsonify({"success": False, "message": "Empty message"}), 400

    # Enforce sender by role for doctor/patient; allow remoni from same session
    if sender not in ['doctor', 'patient', 'remoni']:
        return jsonify({"success": False, "message": "Invalid sender"}), 400
    if sender in ['doctor', 'patient'] and sender != user_role:
        return jsonify({"success": False, "message": "Sender mismatch"}), 403

    now = datetime.now()
    msg = {
        "id": str(int(time.time() * 1000)),
        "sender": sender,
        "text": text,
        "timestamp": now.strftime("%I:%M %p"),
        "date": now.strftime("%Y-%m-%d"),
        "senderName": payload.get('senderName') or session.get('name') or sender.capitalize(),
        "patient_id": target_patient_id
    }
    reply_to = payload.get('replyTo')
    if isinstance(reply_to, dict):
        msg['replyTo'] = {
            "id": reply_to.get('id'),
            "senderName": reply_to.get('senderName'),
            "text": reply_to.get('text')
        }

    with chatroom_messages_lock:
        all_msgs = load_chatroom_messages()
        all_msgs.append(msg)
        save_chatroom_messages(all_msgs)

    notify_telegram_chat_message(
        {
            "senderName": msg.get("senderName"),
            "text": msg.get("text"),
            "patient_id": msg.get("patient_id")
        },
        patient_id=target_patient_id
    )

    return jsonify({"success": True, "message": msg})


@app.route("/api/telegram/webhook", methods=['POST'])
def telegram_webhook():
    """Capture Telegram chat id from webhook updates."""
    data = request.get_json(silent=True) or {}
    logger.info(f"Telegram webhook received: {data}")
    message = (
        data.get("message")
        or data.get("edited_message")
        or data.get("channel_post")
        or {}
    )
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is not None:
        _save_telegram_chat_id(chat_id, chat.get("title") or chat.get("username"))
    sender = message.get("from") or {}
    is_bot = bool(sender.get("is_bot"))
    text = message.get("text") or ""
    if text and not is_bot and chat_id is not None:
        base_url = request.url_root.rstrip("/")
        threading.Thread(
            target=_handle_telegram_chat_message,
            args=(chat_id, text, base_url),
            daemon=True
        ).start()
    return jsonify({"ok": True, "chat_id": chat_id})


@app.route("/api/telegram/test", methods=['GET'])
def telegram_test():
    """Send a test message to the configured Telegram chat."""
    text = request.args.get("text") or "RemoniChatBot test message."
    sent = send_telegram_message(text)
    return jsonify({"ok": bool(sent), "sent": bool(sent)})


@app.route("/api/doctor_request_replies", methods=['GET'])
@login_required
def doctor_request_replies():
    """Return replied doctor requests for doctor chatbox history."""
    user_role = session.get('role')
    if user_role != 'doctor':
        return jsonify({"success": False, "message": "Only doctors can access"}), 403

    try:
        with doctor_requests_lock:
            data = load_doctor_requests()

        replies = []
        for patient_id, requests in data.items():
            for req in requests:
                if req.get('status') == 'replied' and req.get('reply'):
                    replies.append({
                        "id": req.get('id'),
                        "patient_id": patient_id,
                        "reply": req.get('reply'),
                        "replied_at": req.get('replied_at') or req.get('datetime')
                    })

        replies = sorted(replies, key=lambda x: x.get('replied_at', ''), reverse=True)[:50]
        return jsonify({"success": True, "replies": replies})
    except Exception as e:
        logger.error(f"Error loading doctor request replies: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/advice", methods=['GET', 'POST', 'DELETE'])
@login_required
def advice_api():
    """Get or add doctor advices for a patient."""
    user_role = session.get('role')
    user_patient_id = session.get('patient_id')

    if request.method == 'GET':
        patient_id = request.args.get('patient_id', '').strip() or PATIENT_ID
        if user_role == 'patient' and str(patient_id) != str(user_patient_id):
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        with advice_lock:
            data = load_advices()
            advices = data.get(str(patient_id), [])
            if user_role == 'patient':
                advices = [
                    a for a in advices
                    if str(a.get("source", "")).lower() != "remoni" or a.get("approved") is True
                ]
            elif str(patient_id) != str(PATIENT_ID):
                advices = [
                    a for a in advices
                    if str(a.get("source", "")).lower() != "remoni"
                ]
        polished = []
        for item in advices:
            updated = dict(item)
            updated["text"] = _polite_advice_text(updated.get("text"))
            polished.append(updated)
        return jsonify({"success": True, "advices": polished})

    if request.method == 'DELETE':
        if user_role != 'doctor':
            return jsonify({"success": False, "message": "Only doctors can delete advice"}), 403

        payload = request.get_json(silent=True) or {}
        patient_id = str(payload.get('patient_id') or PATIENT_ID)
        advice_id = str(payload.get('advice_id') or '').strip()
        if not advice_id:
            return jsonify({"success": False, "message": "Advice id required"}), 400

        with advice_lock:
            data = load_advices()
            advices = data.get(patient_id, [])
            new_advices = [a for a in advices if str(a.get('id')) != advice_id]
            data[patient_id] = new_advices
            save_advices(data)

        return jsonify({"success": True, "deleted": advice_id})

    if user_role != 'doctor':
        return jsonify({"success": False, "message": "Only doctors can add advice"}), 403

    payload = request.get_json(silent=True) or {}
    patient_id = str(payload.get('patient_id') or PATIENT_ID)
    text = _polite_advice_text((payload.get('text') or '').strip())
    if not text:
        return jsonify({"success": False, "message": "Advice text required"}), 400

    now = datetime.now()
    advice_item = {
        "id": str(uuid.uuid4()),
        "text": text,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%I:%M %p"),
        "source": "Doctor",
        "approved": True,
        "approved_by": session.get("name") or session.get("username") or "doctor",
        "approved_at": now.strftime("%Y-%m-%d %H:%M:%S")
    }

    with advice_lock:
        data = load_advices()
        data.setdefault(patient_id, [])
        data[patient_id].insert(0, advice_item)
        save_advices(data)

    return jsonify({"success": True, "advice": advice_item})


@app.route("/api/advice/approve", methods=['POST'])
@login_required
def approve_remoni_advice():
    """Approve a Remoni advice so it shows on patient dashboards."""
    user_role = session.get('role')
    if user_role != 'doctor':
        return jsonify({"success": False, "message": "Only doctors can approve advice"}), 403

    payload = request.get_json(silent=True) or {}
    patient_id = str(payload.get('patient_id') or PATIENT_ID)
    advice_id = str(payload.get('advice_id') or '').strip()
    if not advice_id:
        return jsonify({"success": False, "message": "Advice id required"}), 400

    approved_item = None
    now = datetime.now()
    with advice_lock:
        data = load_advices()
        advices = data.get(patient_id, [])
        for item in advices:
            if str(item.get("id")) == advice_id:
                item["approved"] = True
                item["approved_by"] = session.get("name") or session.get("username") or "doctor"
                item["approved_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
                approved_item = item
                break
        data[patient_id] = advices
        save_advices(data)

    if not approved_item:
        return jsonify({"success": False, "message": "Advice not found"}), 404

    return jsonify({"success": True, "advice": approved_item})


@app.route("/api/vitals_series", methods=['GET'])
@login_required
def get_vitals_series():
    """Return aggregated vitals series for dashboard charts."""
    user_role = session.get('role')
    user_patient_id = session.get('patient_id')
    requested_patient_id = request.args.get('patient_id') or PATIENT_ID
    period = request.args.get('period', 'daily').lower()

    authorized_patient_id, error_msg = get_authorized_patient_id(
        user_role,
        user_patient_id,
        requested_patient_id
    )
    if error_msg:
        return jsonify({'error': error_msg}), 403

    if authorized_patient_id != PATIENT_ID:
        if check_s3_patient_data_exists(authorized_patient_id):
            try:
                series = build_vitals_series(authorized_patient_id, period)
                return jsonify({"success": True, "series": series})
            except Exception as e:
                logger.error(f"Error building vitals series for {authorized_patient_id}: {e}")
        series = build_dummy_vitals_series(period)
        return jsonify({"success": True, "series": series})

    try:
        series = build_vitals_series(authorized_patient_id, period)
        return jsonify({"success": True, "series": series})
    except Exception as e:
        logger.error(f"Error building vitals series: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/device_status", methods=["GET"])
@login_required
def get_device_status():
    """Return device connection status inferred from edge + vitals + glucose."""
    user_role = session.get('role')
    user_patient_id = session.get('patient_id')
    requested_patient_id = request.args.get('patient_id') or PATIENT_ID

    authorized_patient_id, error_msg = get_authorized_patient_id(
        user_role,
        user_patient_id,
        requested_patient_id
    )
    if error_msg:
        return jsonify({'error': error_msg}), 403
    authorized_patient_id = normalize_patient_id(authorized_patient_id) or authorized_patient_id

    if authorized_patient_id != PATIENT_ID:
        return jsonify(build_dummy_device_status(authorized_patient_id))

    maybe_refresh_librelink_glucose(authorized_patient_id) 
    status = build_device_status_payload(authorized_patient_id) 
    return jsonify(status) 


@app.route("/api/daily_usage", methods=["GET"])
@login_required
def get_daily_usage():
    user_role = session.get('role')
    user_patient_id = session.get('patient_id')
    requested_patient_id = request.args.get('patient_id') or PATIENT_ID
    days = int(request.args.get('days', 7))

    authorized_patient_id, error_msg = get_authorized_patient_id(
        user_role,
        user_patient_id,
        requested_patient_id
    )
    if error_msg:
        return jsonify({'error': error_msg}), 403

    if authorized_patient_id != PATIENT_ID:
        return jsonify({"data": build_dummy_daily_usage(days)})

    data = load_daily_usage_from_s3(authorized_patient_id, days=days)
    return jsonify({"data": data})


SETUP_INSTRUCTIONS = {
    'welcome': """Hello! I'm REMONI, your virtual nurse.
I'll help you set up your health monitoring system.
Type 'start' to begin or 'skip' if already set up.""",

    'step1_power': """<b>Step 1: Plug in Your Device</b>
1. Take the device from the box
2. Use the Type-C cable
3. Plug into wall outlet
4. You should see lights turn on
Type 'next' when ready""",

    'step2_wifi_setup': """<b>Step 2: Connect to Setup WiFi</b>
1. Go to WiFi Settings on your phone
2. Find "REMONI-Setup"
3. Connect (password: remoni2024)
Type 'next' when connected""",

    'step3_wifi_config': """<b>Step 3: Configure Home WiFi</b>
1. Open browser
2. Go to: 10.42.0.1
3. Tap "SCAN FOR NETWORKS"
4. Select your WiFi
5. Enter password
6. Tap "Connect"
Type 'next' when connected""",

    'step4_libre_app': """<b>Step 4: Install FreeStyle Libre App</b>
Important: Remember your email and password!
1. App Store / Play Store
2. Search "FreeStyle Libre"
3. Download and install
4. Create account
Type 'next' when done or 'skip' to skip glucose""",

    'step5_librelinkup': """<b>Step 5: Install LibreLinkUp App</b>
Use SAME email and password!
1. App Store / Play Store
2. Search "LibreLinkUp"
3. Download and install
Type 'next' when done""",

    'step6_connect_apps': """<b>Step 6: Connect Apps</b>
1. Open FreeStyle Libre app
2. Menu → Connected Apps
3. Select LibreLinkUp
4. Add Connection
5. Enter your email
Type 'next' when done""",

    'step7_accept': """<b>Step 7: Accept Connection</b>
1. Open LibreLinkUp app
2. Accept notification
3. Verify you see glucose
Type 'next' when done""",

    'step8_credentials': """<b>Step 8: Enter LibreLink Login</b>
Type your credentials like this:
email: your_email@example.com
password: your_password
This will be sent securely to your home device.""",

    'step9_watch': """<b>Step 9: Connect Watch</b>
1. Open REMONI app on watch
2. Enter IP: {edge_ip}
3. Tap Connect
Type 'next' when connected""",

    'step10_complete': """All Done! 🎉

✅ Home Device - Connected
✅ Glucose
✅ Watch

I'm monitoring your health 24/7!"""
}


@app.route("/api/setup_status", methods=['GET'])
@login_required
def get_setup_status():
    if session.get('role') != 'patient':
        return jsonify({'error': 'Not authorized'}), 403
    return jsonify({'setup_completed': setup_state['setup_completed']})


@app.route("/api/latest_vitals", methods=['GET'])
@login_required
def get_latest_vitals():
    """Get latest vitals with S3 request system for fresh data"""
    user_role = session.get('role')
    user_patient_id = session.get('patient_id')
    requested_patient_id = request.args.get('patient_id')
    fresh = request.args.get('fresh', 'false').lower() == 'true'  # NEW

    authorized_patient_id, error_msg = get_authorized_patient_id(
        user_role,
        user_patient_id,
        requested_patient_id
    )

    if error_msg:
        return jsonify({'error': error_msg}), 403

    if authorized_patient_id != PATIENT_ID:
        return jsonify(build_dummy_latest_vitals(authorized_patient_id))

    # Use S3 request system for fresh data
    if fresh:
        fetch_current_vitals_via_mqtt(authorized_patient_id)
    else:
        fetch_vitals_from_s3(authorized_patient_id)

    vitals = latest_vitals_by_patient.get(authorized_patient_id, latest_vitals)
    return jsonify(vitals)

@app.route("/api/latest_glucose", methods=['GET'])
@login_required
def get_latest_glucose():
    """✅ FIXED: Get latest glucose with MQTT immediate fetch support"""
    user_role = session.get('role')
    user_patient_id = session.get('patient_id')
    requested_patient_id = request.args.get('patient_id')
    fresh = request.args.get('fresh', 'false').lower() == 'true'  # ✅ NEW

    authorized_patient_id, error_msg = get_authorized_patient_id(
        user_role,
        user_patient_id,
        requested_patient_id
    )

    if error_msg:
        return jsonify({'error': error_msg}), 403

    if authorized_patient_id != PATIENT_ID:
        return jsonify(build_dummy_latest_glucose(authorized_patient_id))

    # ✅ If fresh is requested, fetch via MQTT (edge device) 
    if fresh: 
        success, source, is_fresh = fetch_current_glucose_via_mqtt(authorized_patient_id) 
        logger.info(f"✅ Fresh glucose request: success={success}, source={source}, fresh={is_fresh}") 
    else: 
        fetch_glucose_from_s3(authorized_patient_id) 

    glucose = latest_glucose_by_patient.get(authorized_patient_id, latest_glucose) 
    if fresh and not is_fresh: 
        glucose = {} 
    return jsonify(glucose) 


@app.route("/api/edge_device_ip", methods=['GET'])
@login_required
def get_edge_device_ip():
    """✅ NEW APPROACH: Check connection based on MQTT receipt time, not data age"""
    if session.get('role') != 'patient':
        return jsonify({'error': 'Not authorized'}), 403

    try:
        patient_id = session.get('patient_id', PATIENT_ID)

        if not s3_client:
            return jsonify({
                'ip_address': None,
                'connected': False,
                'message': 'S3 not configured'
            })

        # ✅ Get WiFi info from S3
        s3_key = f"{patient_id}/wifi_connection.json"

        try:
            obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
            wifi_data = json.loads(obj['Body'].read().decode('utf-8'))
        except s3_client.exceptions.NoSuchKey:
            return jsonify({
                'ip_address': None,
                'connected': False,
                'message': 'No device connected yet'
            })
        except Exception as e:
            logger.error(f"Error reading WiFi data: {e}")
            return jsonify({
                'ip_address': None,
                'connected': False,
                'error': str(e)
            })

        ip_address = wifi_data.get('ip_address')
        ssid = wifi_data.get('ssid', 'Unknown')
        wifi_datetime = wifi_data.get('datetime')

        if not ip_address:
            return jsonify({
                'ip_address': None,
                'connected': False,
                'message': 'No IP address in WiFi data'
            })

        # ✅ WiFi-only freshness check for edge device connection
        is_connected = False
        if wifi_datetime:
            try:
                wifi_time = pd.to_datetime(wifi_datetime)
                wifi_age = (datetime.now() - wifi_time).total_seconds()
                is_connected = wifi_age < 480  # 8 minutes
            except Exception:
                is_connected = False

        # ✅ Rate limit status change logging
        current_time = time.time()

        if not hasattr(get_edge_device_ip, 'last_logged_status'):
            get_edge_device_ip.last_logged_status = None
            get_edge_device_ip.last_log_time = 0

        time_since_last_log = current_time - get_edge_device_ip.last_log_time
        status_changed = get_edge_device_ip.last_logged_status != is_connected

        # Log if status changed AND it's been at least 10 seconds
        if status_changed and (get_edge_device_ip.last_log_time == 0 or time_since_last_log >= 10):
            status_str = "CONNECTED" if is_connected else "DISCONNECTED"
            logger.warning(f"🔌 Edge device status: {status_str} (Patient {patient_id})")

            get_edge_device_ip.last_logged_status = is_connected
            get_edge_device_ip.last_log_time = current_time

        # ✅ Return response
        return jsonify({
            'ip_address': ip_address,
            'ssid': ssid,
            'connected': is_connected,
            'wifi_datetime': wifi_datetime,
            'patient_id': patient_id
        })

    except Exception as e:
        logger.error(f"Error in get_edge_device_ip: {e}")
        return jsonify({
            'ip_address': None,
            'connected': False,
            'error': str(e)
        }), 500


@app.route("/patient_fall_response", methods=['POST'])
@login_required
def patient_fall_response():
    """Handle patient response to fall check-in"""
    try:
        data = request.get_json()
        alert_id = data.get('alert_id')
        response = data.get('response')

        if not alert_id or not response:
            return jsonify({"status": "error", "message": "Missing data"}), 400

        if alert_id in pending_fall_responses:
            response_data = pending_fall_responses[alert_id]

            if response == 'ok':
                response_data['patient_responded'] = True
                logger.info(f"✅ Patient responded OK to fall check (Alert ID: {alert_id})")

                # ✅ FIX: Remove from active timeout threads when patient responds
                with timeout_threads_lock:
                    if alert_id in active_timeout_threads:
                        active_timeout_threads.remove(alert_id)
                        logger.info(f"✅ Removed alert {alert_id} from active threads (patient responded OK)")

                patient_id = response_data.get('patient_id', PATIENT_ID)
                doctor_notification = {
                    "type": "status",
                    "message": f"✅ Patient Check-In: OK\n\nPatient responded after fall detection\nConfidence: {response_data.get('confidence', 0)}%\nTime: {response_data.get('datetime', 'Unknown')}\nStatus: Patient reports they are okay",
                    "for_role": "doctor"
                }
                socketio.emit('chat_message', doctor_notification, namespace='/')
                notify_telegram_chat_message(doctor_notification, patient_id=patient_id)

                del pending_fall_responses[alert_id]

                return jsonify({
                    "status": "ok",
                    "message": "Thank you for letting me know you're okay. I've informed your doctor."
                })

            elif response == 'help':
                response_data['patient_responded'] = True
                logger.warning(f"🚨 Patient needs help! (Alert ID: {alert_id})")

                # ✅ FIX: Remove from active timeout threads when patient requests help
                with timeout_threads_lock:
                    if alert_id in active_timeout_threads:
                        active_timeout_threads.remove(alert_id)
                        logger.info(f"✅ Removed alert {alert_id} from active threads (patient needs help)")

                confidence = response_data.get('confidence', 0)
                alert_time = response_data.get('datetime', 'Unknown')
                patient_id = response_data.get('patient_id', PATIENT_ID)

                emergency_alerts.append({
                    "patient_id": patient_id,
                    "patient_name": response_data.get("patient_name"),
                    "confidence": confidence,
                    "datetime": alert_time,
                    "alert_id": alert_id,
                    "type": "fall_detected"
                })

                # ✅ ONLY send via chat_message (no fall_alert to avoid duplicates)
                fall_alert_payload = {
                    'patient_id': patient_id,
                    'confidence': confidence,
                    'datetime': alert_time,
                    'alert_id': alert_id,
                    'type': 'patient_needs_help',
                    'for_role': 'doctor'
                }
                socketio.emit('fall_alert', fall_alert_payload, namespace='/')
                notify_telegram_alert(fall_alert_payload, alert_kind="Fall Alert")

                del pending_fall_responses[alert_id]

                return jsonify({
                    "status": "ok",
                    "message": "🚨 I've notified your doctor immediately. Help is coming. Please stay where you are if it's safe to do so."
                })

        return jsonify({"status": "error", "message": "Alert not found"}), 404

    except Exception as e:
        logger.error(f"Error handling patient response: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/pending_fall_check", methods=['GET'])
@login_required
def get_pending_fall_check():
    """Return latest pending fall check for the logged-in patient."""
    user_role = session.get('role')
    user_patient_id = session.get('patient_id')

    if user_role != 'patient':
        return jsonify({"success": False, "message": "Not authorized"}), 403

    if not user_patient_id:
        return jsonify({"success": False, "message": "Missing patient_id"}), 400

    try:
        pending = [
            data for data in pending_fall_responses.values()
            if str(data.get('patient_id')) == str(user_patient_id)
            and not data.get('patient_responded')
        ]
        if not pending:
            return jsonify({"success": True, "pending": None})

        latest = sorted(pending, key=lambda x: x.get('timestamp', 0), reverse=True)[0]
        alert = latest.get('alert', {}) or {}
        return jsonify({
            "success": True,
            "pending": {
                "alert_id": alert.get('alert_id') or alert.get('id'),
                "confidence": alert.get('confidence', latest.get('confidence', 0)),
                "patient_id": latest.get('patient_id'),
                "datetime": latest.get('datetime')
            }
        })
    except Exception as e:
        logger.error(f"Error getting pending fall check: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ============================================================================
# ✅ FIXED CHAT ROUTE - Replace the chat() function in app.py
# ============================================================================
# ============================================================================
# ✅ COMPLETE FIXED /chat ROUTE - REPLACE IN YOUR app.py
# ============================================================================

def get_data_freshness_status(datetime_str: str) -> dict:
    """✅ FIXED: Check if data is fresh and return status

    Returns:
        dict: {
            'is_fresh': bool,
            'age_seconds': int,
            'status': str,  # 'fresh', 'recent', 'stale', 'very_old'
            'warning': str
        }
    """
    try:
        # ✅ CRITICAL FIX: Handle None or invalid datetime
        if not datetime_str or datetime_str == 'Never' or datetime_str == 'None':
            return {
                'is_fresh': False,
                'age_seconds': None,
                'age_minutes': None,
                'status': 'no_data',
                'warning': '⚠️ No timestamp available - data may not be synchronized'
            }

        data_time = pd.to_datetime(datetime_str)
        age = (datetime.now() - data_time).total_seconds()

        # Define freshness thresholds
        if age < 300:  # < 5 minutes
            return {
                'is_fresh': True,
                'age_seconds': int(age),
                'age_minutes': int(age / 60),
                'status': 'fresh',
                'warning': None
            }
        elif age < 900:  # 5-15 minutes
            return {
                'is_fresh': True,
                'age_seconds': int(age),
                'age_minutes': int(age / 60),
                'status': 'recent',
                'warning': f"⚠️ Data is {int(age / 60)} minutes old"
            }
        elif age < 1800:  # 15-30 minutes
            return {
                'is_fresh': False,
                'age_seconds': int(age),
                'age_minutes': int(age / 60),
                'status': 'stale',
                'warning': f"⚠️ Data is {int(age / 60)} minutes old - may not reflect current state"
            }
        else:  # > 30 minutes
            hours = int(age / 3600)
            minutes = int((age % 3600) / 60)
            time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes} minutes"

            return {
                'is_fresh': False,
                'age_seconds': int(age),
                'age_minutes': int(age / 60),
                'age_hours': hours,
                'status': 'very_old',
                'warning': f"🔴 STALE DATA: Last reading was {time_str} ago. Device may be disconnected."
            }

    except Exception as e:
        logger.error(f"Error checking data freshness: {e}")
        return {
            'is_fresh': False,
            'age_seconds': None,
            'age_minutes': None,
            'status': 'unknown',
            'warning': '⚠️ Unable to determine data age'
        }

@app.route("/chat", methods=['POST'])
@login_required
def chat():
    try:
        payload = request.get_json(silent=True) or {}
        if payload.get("new_chat") or payload.get("reset_conversation"):
            session['response_id'] = None
            session['response_id_timestamp'] = time.time()
            session['chat_history'] = []
            session['conversation_mode'] = None
            session.modified = True
        question = payload.get("message", "").strip()
        if not question:
            return jsonify({"answer": "Please enter a message."})
        
        question_lower = question.lower()
        user_role = session.get('role')
        user_patient_id = session.get('patient_id')
        MAX_AGE_FOR_CURRENT_VITALS = 600



        if 'response_id' not in session:
            session['response_id'] = None
            logger.info("🆕 Initialized new conversation tracking")
        




        # ✅ SETUP PROCESS FOR PATIENTS (keeping existing setup code)
        if user_role == 'patient':
            if not session.get('setup_completed', False):
                if question_lower in ['start', 'begin', 'setup']:
                    session['setup_step'] = 'step1_power'
                    return jsonify({"answer": SETUP_INSTRUCTIONS['step1_power']})

                current_step = session.get('setup_step')

                if current_step and question_lower == 'next':
                    step_order = ['step1_power', 'step2_wifi_setup', 'step3_wifi_config',
                                  'step4_libre_app', 'step5_librelinkup', 'step6_connect_apps',
                                  'step7_accept', 'step8_credentials', 'step9_watch', 'step10_complete']

                    current_index = step_order.index(current_step)
                    if current_index < len(step_order) - 1:
                        next_step = step_order[current_index + 1]
                        session['setup_step'] = next_step

                        if next_step == 'step8_credentials':
                            return jsonify({"answer": SETUP_INSTRUCTIONS['step8_credentials']})

                        return jsonify({"answer": SETUP_INSTRUCTIONS[next_step]})

                if current_step == 'step8_credentials':
                    if 'email:' in question_lower and 'password:' in question_lower:
                        try:
                            lines = question.split('\n')
                            email = None
                            password = None

                            for line in lines:
                                if 'email:' in line.lower():
                                    email = line.split(':', 1)[1].strip()
                                elif 'password:' in line.lower():
                                    password = line.split(':', 1)[1].strip()

                            if not email or not password:
                                email_match = re.search(r'email:\s*([^\s]+)', question, re.IGNORECASE)
                                password_match = re.search(r'password:\s*([^\s]+)', question, re.IGNORECASE)
                                if email_match:
                                    email = email_match.group(1).strip()
                                if password_match:
                                    password = password_match.group(1).strip()

                            if email and password:
                                if mqtt_client and mqtt_client.is_connected:
                                    credentials_payload = {
                                        'patient_id': user_patient_id,
                                        'email': email,
                                        'password': password,
                                        'timestamp': int(time.time() * 1000),
                                        'datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    }

                                    success = mqtt_client.publish(
                                        MQTTConfig.get_librelink_credentials_topic(user_patient_id),
                                        credentials_payload
                                    )

                                    if success:
                                        session['setup_step'] = 'step9_watch'
                                        session['libre_setup_completed'] = True

                                        try:
                                            s3_key = f"{user_patient_id}/wifi_connection.json"
                                            obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
                                            wifi_data = json.loads(obj['Body'].read().decode('utf-8'))
                                            edge_ip = wifi_data.get('ip_address', 'Unknown')
                                        except:
                                            edge_ip = 'Unknown'

                                        return jsonify({
                                            "answer": SETUP_INSTRUCTIONS['step9_watch'].format(edge_ip=edge_ip)
                                        })
                                    else:
                                        return jsonify({
                                            "answer": "❌ Failed to send credentials to edge device. Please check connection and try again."
                                        })
                                else:
                                    return jsonify({
                                        "answer": "❌ Edge device not connected. Please ensure your edge device is online."
                                    })
                            else:
                                return jsonify({
                                    "answer": "❌ Invalid format. Please use:\nemail: your_email@example.com\npassword: your_password"
                                })

                        except Exception as e:
                            logger.error(f"Error parsing credentials: {e}")
                            return jsonify({
                                "answer": "❌ Error processing credentials. Please try again."
                            })

                if current_step == 'step9_watch' and question_lower == 'next':
                    session['setup_completed'] = True
                    session.pop('setup_step', None)

                    glucose_status = "Connected ✅" if session.get('libre_setup_completed') else "Skipped"
                    watch_status = "Connected ✅"

                    return jsonify({
                        "answer": SETUP_INSTRUCTIONS['step10_complete'].format(
                            glucose_status=glucose_status,
                            watch_status=watch_status
                        )
                    })

                if current_step in ['step4_libre_app', 'step5_librelinkup', 'step6_connect_apps',
                                    'step7_accept', 'step8_credentials'] and question_lower == 'skip':
                    session['setup_step'] = 'step9_watch'

                    try:
                        s3_key = f"{user_patient_id}/wifi_connection.json"
                        obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
                        wifi_data = json.loads(obj['Body'].read().decode('utf-8'))
                        edge_ip = wifi_data.get('ip_address', 'Unknown')
                    except:
                        edge_ip = 'Unknown'

                    return jsonify({
                        "answer": SETUP_INSTRUCTIONS['step9_watch'].format(edge_ip=edge_ip)
                    })

        # Handle fall responses
        if user_role == 'patient' and len(pending_fall_responses) > 0:
            if any(word in question_lower for word in ['yes', 'ok', 'okay', 'fine', "i'm ok", "im ok", "i am ok"]):
                for alert_id, data in list(pending_fall_responses.items()):
                    if not data['patient_responded']:
                        data['patient_responded'] = True
                        confidence = data.get('confidence', 0)

                        with timeout_threads_lock:
                            if alert_id in active_timeout_threads:
                                active_timeout_threads.remove(alert_id)

                        doctor_notification = {
                            "type": "status",
                            "message": f"✅ Patient Check-In: OK\n\nPatient responded after fall detection\nConfidence: {confidence}%\nTime: {data.get('datetime', 'Unknown')}\nStatus: Patient reports they are okay",
                            "for_role": "doctor"
                        }
                        socketio.emit('chat_message', doctor_notification, namespace='/')
                        notify_telegram_chat_message(doctor_notification, patient_id=data.get('patient_id', PATIENT_ID))
                        del pending_fall_responses[alert_id]

                        return jsonify(
                            {"answer": "Thank you for letting me know you're okay. I've informed your doctor."})

            elif any(word in question_lower for word in ['help', 'not ok', 'emergency', 'need help', 'hurt', 'pain']):
                for alert_id, data in list(pending_fall_responses.items()):
                    if not data['patient_responded']:
                        data['patient_responded'] = True
                        confidence = data.get('confidence', 0)
                        patient_id = data.get('patient_id', PATIENT_ID)
                        alert_time = data.get('datetime', 'Unknown')

                        with timeout_threads_lock:
                            if alert_id in active_timeout_threads:
                                active_timeout_threads.remove(alert_id)

                        fall_alert_payload = {
                            'patient_id': patient_id,
                            'confidence': confidence,
                            'datetime': alert_time,
                            'alert_id': alert_id,
                            'type': 'patient_needs_help',
                            'for_role': 'doctor'
                        }
                        socketio.emit('fall_alert', fall_alert_payload, namespace='/')
                        notify_telegram_alert(fall_alert_payload, alert_kind="Fall Alert")
                        del pending_fall_responses[alert_id]

                        return jsonify({
                            "answer": "🚨 I've notified your doctor immediately. Help is coming. Please stay where you are if it's safe to do so."
                        })

        # ========================================================================
        # NLP PROCESSING WITH RESPONSES API
        # ========================================================================

        try:
            logger.info(f"🔍 NLP Query from {user_role}: {question}")

            # ✅ Get previous_response_id from session
            previous_response_id = session.get('response_id')
            
            # ✅ For fallback mode, get conversation history
            conversation_history = session.get('chat_history', [])
            current_mode = session.get('conversation_mode')
            
            logger.info(f"📡 Using previous_response_id: {previous_response_id}")
            previous_response_id = check_response_id_age()

            # Call intent detection with conversation context
            if not nlp.intent_detection(
                question, 
                previous_response_id=previous_response_id
            ):
                return jsonify({"answer": "I couldn't understand. Please try rephrasing."})

            logger.info(f"📋 Detected Intent: {nlp.intent_dict}")

            nlp.vital_signs_text = 'None'
            nlp.image_description = 'None'

            if nlp.intent_dict.get('vital_sign'):
                vital_signs = ['glucose' if v == 'glucose_level' else v for v in nlp.intent_dict['vital_sign']]
                nlp.intent_dict['vital_sign'] = vital_signs

            requested_patient_id = nlp.intent_dict.get('patient_id')
            authorized_patient_id, error_msg = get_authorized_patient_id(
                user_role,
                user_patient_id,
                requested_patient_id
            )

            if error_msg:
                logger.warning(f"🚫 Unauthorized: {user_role} tried to access {requested_patient_id}")
                return jsonify({"answer": error_msg})

            if not authorized_patient_id:
                return jsonify({"answer": "Unable to determine patient data access."})

            nlp.intent_dict['patient_id'] = authorized_patient_id
            nlp.patient_id = authorized_patient_id

            logger.info(f"✅ Authorized: {user_role} → Patient {authorized_patient_id}")

            nlp.check_and_update_patient_id()
            nlp.process_special_historical_data_retrieval()

            if nlp.intent_dict.get('is_image') or nlp.intent_dict.get('recognition'):
                nlp.image_description = "IMPORTANT: The camera system is NOT CONNECTED and NO images are available. Do not tell the user to check below. Instead, inform them that the camera system is currently unavailable and cannot provide images."

                if not nlp.intent_dict.get('vital_sign') or len(nlp.intent_dict.get('vital_sign', [])) == 0:
                    try:
                        patient_id_numeric = int(nlp.patient_id)
                    except (ValueError, TypeError):
                        return jsonify({"answer": f"Error: Invalid patient ID '{nlp.patient_id}'."})

                    patient_info = nlp.patient_meta_df[nlp.patient_meta_df['patient_id'] == patient_id_numeric]
                    if patient_info.empty:
                        patient_info = pd.DataFrame([{
                            'patient_id': patient_id_numeric,
                            'name': f'Patient {nlp.patient_id}',
                            'sex': 'Unknown',
                            'address': 'Not specified',
                            'phone': 'Not specified',
                            'birth': 'Not specified',
                            'age': 'Unknown'
                        }])

                    output, response_id = nlp.endpoint_llm(
                        patient_info, 
                        question,
                        previous_response_id=previous_response_id,
                        conversation_history=conversation_history if not previous_response_id else None
                    )
                    
                    # ✅ Store the response_id for continuity
                    if response_id:
                        session['response_id'] = response_id
                        logger.info(f"✅ Stored new response_id for intent endpoint: {response_id}")
                    elif not previous_response_id:
                        # If using fallback mode, update conversation history
                        conversation_history.append({"role": "user", "content": question})
                        conversation_history.append({"role": "assistant", "content": output})
                        
                        # Keep only last 10 messages (5 exchanges)
                        if len(conversation_history) > 10:
                            conversation_history = conversation_history[-10:]
                        
                        session['chat_history'] = conversation_history
                        logger.info(f"✅ Updated conversation history with {len(conversation_history)} messages")
                    
                    session.modified = True
                    
                    output = re.sub(r'!\[([^\]]*)\]\([^\)]*\)', '', output)
                    output = re.sub(r'\n\s*\n\s*\n', '\n\n', output).strip()
                    return jsonify({"answer": output})

            try:
                patient_id_numeric = int(nlp.patient_id)
            except (ValueError, TypeError):
                return jsonify({"answer": f"Error: Invalid patient ID format '{nlp.patient_id}'."})

            patient_info = nlp.patient_meta_df[nlp.patient_meta_df['patient_id'] == patient_id_numeric]
            if patient_info.empty:
                patient_info = pd.DataFrame([{
                    'patient_id': patient_id_numeric,
                    'name': f'Patient {nlp.patient_id}',
                    'sex': 'Unknown',
                    'address': 'Not specified',
                    'phone': 'Not specified',
                    'birth': 'Not specified',
                    'age': 'Unknown'
                }])

            # ========================================================================
            # DATA RETRIEVAL
            # ========================================================================

            show_list = []
            nlp.vital_signs_text = 'None'

            if len(nlp.intent_dict.get('vital_sign', [])) > 0:
                vital_signs = nlp.intent_dict.get('vital_sign', [])
                has_glucose = 'glucose' in vital_signs
                other_vitals = [v for v in vital_signs if v != 'glucose']

                has_dates = len(nlp.intent_dict.get('list_date', [])) > 0
                has_times = len(nlp.intent_dict.get('list_time', [])) > 0
                is_current = not has_dates and not has_times

                # ============================================================
                # HANDLE REGULAR VITALS
                # ============================================================
                if other_vitals:
                    if is_current:
                        logger.info("📡 Fetching CURRENT vitals...")
                        success, source, is_fresh = fetch_current_vitals_via_mqtt(nlp.patient_id)

                        if success:
                            patient_vitals = latest_vitals_by_patient.get(nlp.patient_id)
                            if patient_vitals:
                                freshness = get_data_freshness_status(patient_vitals.get('datetime'))

                                if freshness.get('age_seconds') and freshness['age_seconds'] > MAX_AGE_FOR_CURRENT_VITALS:
                                    age_minutes = freshness.get('age_minutes', 0)
                                    age_hours = freshness.get('age_hours', 0)
                                    
                                    if age_hours > 0:
                                        time_str = f"{age_hours}h {age_minutes % 60}m"
                                    else:
                                        time_str = f"{age_minutes} minutes"

                                    logger.warning(f"⚠️ Data too old ({time_str}) - rejecting as 'current'")

                                    nlp.vital_signs_text = f"""{'=' * 70}
⚠️ CURRENT VITALS NOT AVAILABLE
{'=' * 70}
The most recent vital signs data is {time_str} old (from {patient_vitals.get('datetime')}).

This data is too stale to be considered "current" vitals.

Possible reasons:
- Watch is not connected or powered off
- Patient is not wearing the watch
- Connection issue between watch and system
- Watch battery is depleted

Please ensure:
✅ Watch is powered on and charged
✅ Watch is being worn by the patient
✅ Watch is connected to the system

Try again in a few minutes after checking the watch connection.
{'=' * 70}
"""
                                else:
                                    vital_text = f"{'=' * 50}\n"
                                    vital_text += f"VITAL SIGNS (Patient {nlp.patient_id}):\n"
                                    vital_text += f"{'=' * 50}\n"
                                    vital_text += f"Reading Time: {patient_vitals.get('datetime')}\n"

                                    if freshness['is_fresh']:
                                        if freshness['status'] == 'fresh':
                                            vital_text += f"Status: ✅ FRESH ({freshness['age_minutes']} min old)\n"
                                        else:
                                            vital_text += f"Status: ⚠️ RECENT ({freshness['age_minutes']} min old)\n"
                                    else:
                                        vital_text += f"Status: ⚠️ {freshness['age_minutes']} min old\n"

                                    vital_text += f"Data Source: {'Live (MQTT)' if is_fresh else 'Cached (S3)'}\n"
                                    vital_text += f"{'=' * 50}\n\n"
                                    has_simulated_values = False

                                    bp = patient_vitals.get('blood_pressure', {})

                                    hr = patient_vitals.get('heart_rate', 0)
                                    if hr and hr > 0:
                                        vital_text += f"Heart Rate: {hr} BPM\n"

                                    systolic = bp.get('systolic', 0)
                                    diastolic = bp.get('diastolic', 0)
                                    if systolic and systolic > 0:
                                        vital_text += f"Systolic Blood Pressure: {systolic} mmHg\n"
                                        has_simulated_values = True
                                    if diastolic and diastolic > 0:
                                        vital_text += f"Diastolic Blood Pressure: {diastolic} mmHg\n"

                                    spo2 = patient_vitals.get('spo2', 0)
                                    if spo2 and spo2 > 0:
                                        vital_text += f"Oxygen Saturation (SpO2): {spo2}%\n"
                                        has_simulated_values = True

                                    temp = patient_vitals.get('skin_temperature', 0)
                                    if temp and temp > 0:
                                        vital_text += f"Body Temperature: {temp}°C\n"
                                        has_simulated_values = True

                                    rr = patient_vitals.get('respiratory_rate', 0)
                                    if rr and rr > 0:
                                        vital_text += f"Respiratory Rate: {rr} breaths/min\n"
                                        has_simulated_values = True

                                    if has_simulated_values:
                                        vital_text += f"\n(*) - These values are simulated due to Samsung Galaxy Watch hardware limitations.\n"

                                    nlp.vital_signs_text = vital_text

                            else:
                                logger.error(f"❌ No vitals found in cache for patient {nlp.patient_id}")
                                nlp.vital_signs_text = f"⚠️ Vitals data not available for Patient {nlp.patient_id}."
                        else:
                            logger.error(f"❌ Failed to fetch vitals")
                            nlp.vital_signs_text = f"⚠️ Unable to retrieve current vital signs for Patient {nlp.patient_id}."

                    else:
                        # ============================================================
                        # ✅ HISTORICAL DATA WITH SMART AGGREGATION
                        # ============================================================
                        logger.info(f"📊 Fetching HISTORICAL vitals for patient {nlp.patient_id}")

                        patient_vitals_df = load_patient_vitals_from_s3(
                            nlp.patient_id,
                            date_list=nlp.intent_dict.get('list_date', [])
                        )

                        if not patient_vitals_df.empty:
                            from utils import filter_raw_df, plot_vital_sign
                            from config_nlp_engine import vital_sign_var_to_text, SIMULATED_VITALS

                            filtered_df = filter_raw_df(
                                patient_vitals_df,
                                nlp.intent_dict,
                                is_current=False
                            )

                            logger.info(f"📊 Filtered data: {len(filtered_df)} rows")

                            if not filtered_df.empty:
                                # ✅ Use LLM-detected data format preference
                                data_format = nlp.intent_dict.get('data_format', 'raw')
                                
                                logger.info(f"📊 Data format requested: {data_format}")
                                
                                # ============================================================
                                # PRIORITY 1: Plot-only requests
                                # ============================================================
                                if data_format == 'plot_only':
                                    logger.info(f"📊 Plot-only request detected - skipping text data")
                                    
                                    plot_results = []
                                    for vital in other_vitals:
                                        plot_result = plot_vital_sign(filtered_df, vital)
                                        if plot_result:
                                            plot_results.append(plot_result)
                                            show_list.append(plot_result['path'])
                                            logger.info(f"✅ Plot created: {plot_result['path']}")
                                    
                                    if show_list:
                                        # Build response with proper vital names
                                        vital_labels = []
                                        for vital in other_vitals:
                                            label = vital_sign_var_to_text.get(vital, vital.replace('_', ' ').title())
                                            vital_labels.append(label)
                                        
                                        # Join with proper grammar
                                        if len(vital_labels) == 1:
                                            vital_names = vital_labels[0]
                                        elif len(vital_labels) == 2:
                                            vital_names = f"{vital_labels[0]} and {vital_labels[1]}"
                                        else:
                                            vital_names = ', '.join(vital_labels[:-1]) + f", and {vital_labels[-1]}"
                                        
                                        # Format date range
                                        if len(nlp.intent_dict.get('list_date', [])) > 1:
                                            date_range = f"{nlp.intent_dict['list_date'][0]} to {nlp.intent_dict['list_date'][-1]}"
                                        else:
                                            date_range = nlp.intent_dict.get('list_date', [''])[0]
                                        
                                        # Build response with disclaimer if needed
                                        if len(show_list) == 1:
                                            simple_response = f"Here is the {vital_names} plot for {date_range}:"
                                        else:
                                            simple_response = f"Here are the {vital_names} plots for {date_range}:"
                                        
                                        # Add disclaimer if any simulated vitals
                                        simulated_vitals_in_plots = [p for p in plot_results if p['is_simulated']]
                                        if simulated_vitals_in_plots:
                                            simulated_vital_names = [vital_sign_var_to_text.get(p['vital_sign'], p['vital_sign']) 
                                                                    for p in simulated_vitals_in_plots]
                                            disclaimer = f"\n\n(*) {', '.join(simulated_vital_names)} values are simulated due to Samsung Galaxy Watch hardware limitations."
                                            simple_response += disclaimer
                                        
                                        logger.info(f"✅ Returning {len(show_list)} plots WITHOUT text data")
                                        return jsonify({"answer": simple_response, "plots": show_list})
                                
                                # ============================================================
                                # ALWAYS use smart aggregation for historical vitals
                                # ============================================================
                                logger.info("📊 Using smart aggregation for historical vitals (all formats)")
                                
                                vitals_intent = nlp.intent_dict.copy()
                                vitals_intent['vital_sign'] = other_vitals
                                
                                logger.info(f"📊 Processing {len(filtered_df)} samples with smart aggregation...")
                                
                                nlp.vital_signs_text, aggregation_level = vitals_aggregator.process_data_for_llm(
                                    filtered_df, 
                                    other_vitals
                                )
                                
                                logger.info(f"📝 Data processed using '{aggregation_level}' aggregation")
                                logger.info(f"   Output size: {len(nlp.vital_signs_text)} characters")

                                # Generate plots if requested
                                if nlp.intent_dict.get('is_plot'):
                                    logger.info("📊 Also generating plots as requested")
                                    for vital in other_vitals:
                                        plot_result = plot_vital_sign(filtered_df, vital)
                                        if plot_result:
                                            show_list.append(plot_result['path'])
                                            logger.info(f"✅ Plot created: {plot_result['path']}")
                            else:
                                nlp.vital_signs_text = f"No {', '.join(other_vitals)} data found for the specified time period."

                        else:
                            nlp.vital_signs_text = f"No vital signs data available for Patient {nlp.patient_id}."

                # ============================================================
                # HANDLE GLUCOSE
                # ============================================================
                if has_glucose: 
                    if is_current: 
                        logger.info("📡 Fetching CURRENT glucose via MQTT...") 
                        glucose_success, glucose_source, glucose_is_fresh = fetch_current_glucose_via_mqtt( 
                            nlp.patient_id) 

                        glucose_origin = glucose_source_by_patient.get(nlp.patient_id) 
                        patient_glucose = latest_glucose_by_patient.get(nlp.patient_id, latest_glucose) 
                        if not glucose_is_fresh: 
                            patient_glucose = None 

                        if patient_glucose and patient_glucose.get('value_mgdl', 0) > 0:
                            freshness = get_data_freshness_status(patient_glucose.get('datetime'))

                            glucose_text = f"\n{'=' * 50}\n"
                            glucose_text += f"GLUCOSE DATA:\n"
                            glucose_text += f"{'=' * 50}\n"
                            glucose_text += f"Level: {patient_glucose.get('value_mgdl')} mg/dL\n"
                            glucose_text += f"Reading Time: {patient_glucose.get('datetime')}\n"

                            if freshness['is_fresh']:
                                if freshness['status'] == 'fresh':
                                    glucose_text += f"Status: ✅ FRESH ({freshness.get('age_minutes', 0)} min old)\n"
                                else:
                                    glucose_text += f"Status: ⚠️ RECENT ({freshness.get('age_minutes', 0)} min old)\n"
                            else:
                                glucose_text += f"Status: 🔴 STALE ({freshness.get('age_minutes', 0)} min old)\n"
                                if freshness.get('warning'):
                                    glucose_text += f"\n{freshness['warning']}\n"

                            source_label = "MQTT (edge)" if glucose_origin == "mqtt" else "Cached (S3)" 
                            glucose_text += f"Data Source: {source_label}\n" 
                            glucose_text += f"{'=' * 50}\n" 

                            if nlp.vital_signs_text and nlp.vital_signs_text != 'None':
                                nlp.vital_signs_text += "\n" + glucose_text
                            else:
                                nlp.vital_signs_text = glucose_text

                        else:
                            glucose_note = f"\n{'=' * 50}\n"
                            glucose_note += f"GLUCOSE DATA:\n"
                            glucose_note += f"{'=' * 50}\n"
                            glucose_note += f"Status: Not currently available\n"
                            glucose_note += f"Note: MQTT data is stale or unavailable\n" 
                            glucose_note += f"{'=' * 50}\n" 

                            if nlp.vital_signs_text and nlp.vital_signs_text != 'None':
                                nlp.vital_signs_text += "\n" + glucose_note
                            else:
                                nlp.vital_signs_text = glucose_note

                    else:
                        # ============================================================
                        # ✅ HISTORICAL GLUCOSE WITH SMART AGGREGATION
                        # ============================================================
                        patient_glucose_df = load_patient_glucose_from_s3(
                            nlp.patient_id,
                            date_list=nlp.intent_dict.get('list_date', [])
                        )

                        if not patient_glucose_df.empty:
                            from utils import filter_raw_df, plot_vital_sign

                            glucose_intent = nlp.intent_dict.copy()
                            glucose_intent['vital_sign'] = ['glucose']

                            filtered_glucose = filter_raw_df(
                                patient_glucose_df,
                                glucose_intent,
                                is_current=False
                            )

                            if not filtered_glucose.empty:
                                # ✅ ALWAYS use smart aggregation for historical glucose
                                logger.info(f"📊 Processing {len(filtered_glucose)} glucose samples with smart aggregation...")
                                glucose_text, glucose_agg_level = vitals_aggregator.process_data_for_llm(
                                    filtered_glucose,
                                    ['glucose']
                                )
                                logger.info(f"📝 Glucose data processed using '{glucose_agg_level}' aggregation")

                                if nlp.vital_signs_text and nlp.vital_signs_text != 'None':
                                    nlp.vital_signs_text += "\n\n" + glucose_text
                                else:
                                    nlp.vital_signs_text = glucose_text

                                if nlp.intent_dict.get('is_plot'):
                                    plot_result = plot_vital_sign(filtered_glucose, 'glucose')
                                    if plot_result:
                                        show_list.append(plot_result['path'])

            # ========================================================================
            # Call OpenAI endpoint with Responses API
            # ========================================================================

            # ✅ Fallback: reuse last vitals text for follow-up analysis questions
            if (not nlp.vital_signs_text or nlp.vital_signs_text == 'None') and any(
                word in question.lower() for word in ['analyze', 'analyse', 'assess', 'interpret', 'evaluate', 'them']
            ):
                last_vitals_text = session.get('last_vitals_text')
                last_vitals_patient = session.get('last_vitals_patient')
                last_vitals_ts = session.get('last_vitals_timestamp', 0)
                age_seconds = time.time() - last_vitals_ts if last_vitals_ts else None

                if last_vitals_text and last_vitals_patient == nlp.patient_id and age_seconds is not None and age_seconds <= 6 * 3600:
                    nlp.vital_signs_text = last_vitals_text
                    logger.info("✅ Reusing recent vitals text for follow-up analysis")

            # ✅ Cache latest vitals text for follow-ups
            if nlp.vital_signs_text and nlp.vital_signs_text != 'None':
                session['last_vitals_text'] = nlp.vital_signs_text
                session['last_vitals_patient'] = nlp.patient_id
                session['last_vitals_timestamp'] = time.time()

            logger.info(f"📤 Sending to OpenAI with {len(nlp.vital_signs_text)} chars of data")

            # ✅ Add context hints for better responses
            if len(nlp.intent_dict.get('list_date', [])) > 1:
                question = question + "\n\nIMPORTANT: add their SI units"

            if any(word in question.lower() for word in ['age', 'how old', 'years old', 'born']):
                birth_date = patient_info['birth'].values[0]
                birth_dt = pd.to_datetime(birth_date)
                today = datetime.now()
                calculated_age = today.year - birth_dt.year - ((today.month, today.day) < (birth_dt.month, birth_dt.day))
                question = question + f"\n\nIMPORTANT: The patient's current age is {calculated_age} years (calculated from birth date {birth_date})."

            if len(nlp.intent_dict.get('list_date', [])) == 1 and len(nlp.intent_dict.get('list_time', [])) == 4:
                question = question + "\n\nIMPORTANT: show timestamps.and list the values with standard units."

            if any(word in question.lower() for word in ['analyze', 'analyse', 'assess', 'interpret', 'evaluate']):
                question = question + "\n\nIMPORTANT: The vital signs data IS PROVIDED in the context above. Use this data for your analysis. Do NOT list individual timestamps or raw data points in your response. Instead, provide medical interpretation, trends, patterns, and clinical insights based on the comprehensive statistics and metrics provided."

            # ✅ NEW: Add aggregation context for LLM
            if hasattr(vitals_aggregator, 'last_aggregation_level'):
                aggregation_level = vitals_aggregator.last_aggregation_level
                
                if aggregation_level == 'daily':
                    question = question + "\n\nIMPORTANT: The data has been aggregated to daily averages. Each day shows mean/min/max/std values. Focus on overall patterns and trends rather than individual readings."
                
                elif aggregation_level == 'metrics':
                    question = question + "\n\nIMPORTANT: The data has been summarized using comprehensive statistical metrics covering baseline, variability, extreme values, abnormal burden, trends, and circadian patterns. Provide medical interpretation of these metrics rather than listing individual readings."

            # ✅ UPDATED: Use endpoint_llm with Responses API support
            output, response_id = nlp.endpoint_llm(
                patient_info, 
                question,
                previous_response_id=previous_response_id if current_mode == 'responses_api' else None,
                conversation_history=conversation_history if current_mode == 'fallback' else None
            )

            # ✅ Store the new response_id for continuity
            if response_id is not None:
                # Responses API worked - store response_id
                session['conversation_mode'] = 'responses_api'
                session['response_id'] = response_id
                session['chat_history'] = []  # Clear history when using Responses API
                logger.info(f"✅ Updated session - Mode: responses_api, ID: {response_id[:20]}...")
            else:
                # Fallback mode - store chat history for continuity
                session['conversation_mode'] = 'fallback'
                conversation_history.append({"role": "user", "content": question})
                conversation_history.append({"role": "assistant", "content": output})
                if len(conversation_history) > 10:
                    conversation_history = conversation_history[-10:]
                session['chat_history'] = conversation_history
                logger.info(f"✅ Updated conversation history with {len(conversation_history)} messages")


            # ✅ CRITICAL: Mark session as modified
            session.modified = True
            
            # Clean up output and return
            output = re.sub(r'!\[([^\]]*)\]\([^\)]*\)', '', output)
            output = re.sub(r'\n\s*\n\s*\n', '\n\n', output).strip()
            output = re.sub(r'(?:Please see the graph below:?\s*){2,}', 'Please see the graph below: ', output, flags=re.IGNORECASE)
            # Keep the model response when plots are included.
            
            if show_list:
                logger.info(f"✅ Returning response with {len(show_list)} plots")
                return jsonify({"answer": output, "plots": show_list})
            else:
                logger.info(f"✅ Returning response (no plots)")
                return jsonify({"answer": output})
                
        except Exception as e:
            logger.error(f"NLP processing error: {e}", exc_info=True)
            return jsonify({"answer": "Error processing your request. Please try again."})
            
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        return jsonify({"answer": "An error occurred. Please try again."})

@app.route("/api/clear_conversation", methods=['POST'])
@login_required
def clear_conversation():
    """Clear conversation memory completely"""
    try:
        username = session.get('username')
        
        # ✅ SIMPLIFIED: Only clear response_id
        session['response_id'] = None
        session['response_id_timestamp'] = time.time()
        session['chat_history'] = []
        session['conversation_mode'] = None
        session.modified = True
        
        logger.info(f"🗑️ Cleared conversation for {username}")
        
        return jsonify({
            'success': True, 
            'message': 'Conversation cleared successfully'
        })
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/api/conversation_status", methods=['GET'])
@login_required
def conversation_status():
    """Get current conversation status"""
    try:
        response_id = session.get('response_id')
        
        return jsonify({
            'success': True,
            'using_responses_api': True,  # Always true now
            'response_id': response_id[:20] + '...' if response_id else None,
            'has_active_conversation': response_id is not None
        })
    except Exception as e:
        logger.error(f"Error getting conversation status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    

@app.route("/api/test_responses_api", methods=['GET'])
@login_required
def test_responses_api():
    """Test if Responses API is available"""
    try:
        from request_to_openai import client
        
        # Try to create a simple response
        test_response = client.responses.create(
            model="gpt-4",
            input=[{"type": "text", "text": "Hello"}],
            instructions="You are a helpful assistant.",
            temperature=0.1
        )
        
        return jsonify({
            'success': True,
            'available': True,
            'response_id': test_response.id,
            'output': test_response.output_text,
            'message': 'Responses API is available and working'
        })
        
    except Exception as e:
        logger.warning(f"Responses API not available: {e}")
        return jsonify({
            'success': True,
            'available': False,
            'message': f'Responses API not available: {str(e)}',
            'fallback': 'Using Chat Completions API with conversation history'
        })


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("REMONI - REAL-TIME HEALTH MONITORING")
    print("=" * 70)
    print(f"S3 Bucket: {S3_BUCKET_NAME}")
    print(f"Patient ID: {PATIENT_ID}")
    print("=" * 70)

    # ✅ Initialize MQTT with improved connection handling
    mqtt_initialized = False
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries and not mqtt_initialized:
        try:
            if initialize_mqtt(PATIENT_ID):
                logger.info("✅ MQTT client ready for fresh vitals requests")
                mqtt_initialized = True
            else:
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"⚠️ MQTT initialization failed - retry {retry_count}/{max_retries}")
                    time.sleep(2)
        except Exception as e:
            logger.error(f"❌ MQTT initialization error: {e}")
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(2)

    if not mqtt_initialized:
        logger.warning("⚠️ MQTT not available - will use S3 fallback only")

    # Start S3 polling for historical data 
    if s3_client: 
        threading.Thread(target=s3_polling_loop, daemon=True).start() 
        logger.info("✅ S3 polling started") 
        start_glucose_sensor_monitoring(interval_minutes=5) 
        logger.info("✅ LibreLink glucose monitor started") 
        start_remoni_advice_scheduler()
        logger.info("✅ Remoni advice scheduler started")

    print("=" * 70 + "\n")
    print("Starting server on http://0.0.0.0:5002\n")

    try:
        socketio.run(app, host='0.0.0.0', port=5002, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down gracefully...")
        stop_mqtt()
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        stop_mqtt()
