import time
import random
import requests
import jdatetime
from datetime import datetime


# ==================== تنظیمات ====================
BOT_TOKEN = "BALE_BOT_TOKEN"
API_BASE = f"https://tapi.bale.ai/bot{BOT_TOKEN}"

# حافظه‌ی موقت (فقط تا وقتی برنامه روشنه نگه داشته می‌شه)
user_sessions = {}        # {chat_id: {"name":..., "lat":..., "lon":...}}
pending_mode = {}         # {chat_id: "today" | "week"}  -> فقط وقتی هنوز شهر انتخاب نشده
last_mode = {}            # {chat_id: "today" | "week"}  -> آخرین حالتی که کاربر دیده

WEEKDAY_FA = ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه', 'شنبه', 'یکشنبه']
JALALI_MONTHS_FA = [
    'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
]


def jalali_str(gregorian_dt) -> str:
    """تبدیل تاریخ میلادی به رشته‌ی تاریخ هجری شمسی، مثل '21 تیر'"""
    jd = jdatetime.date.fromgregorian(date=gregorian_dt.date())
    return f"{jd.day} {JALALI_MONTHS_FA[jd.month - 1]}"

# کد وضعیت آب و هوا (WMO) -> (ایموجی، توضیح کوتاه، جمله‌های باحال)
WEATHER_INFO = {
    0: ("☀️", "آسمون کاملا صافه", [
        "امروز آسمون یه‌پارچه آبیه، عینک آفتابیتو یادت نره!",
        "هوا آفتابی و دلبازه، وقت خوبیه برای یه پیاده‌روی کوتاه.",
    ]),
    1: ("🌤️", "کمی ابری", ["امروز آسمون یه‌کم ابر داره ولی آفتاب هم می‌تابه."]),
    2: ("⛅", "نیمه ابری", ["آسمون بین آفتاب و ابر مردده، هوای نسبتا دلپذیریه."]),
    3: ("☁️", "ابری", ["امروز ابرها میزبان آسمونن، هوا یکم گرفته‌ست."]),
    45: ("🌫️", "مه‌آلود", ["مه غلیظی همه‌جا رو گرفته، توی رانندگی مراقب باش."]),
    48: ("🌫️", "مه و یخ‌زدگی", ["مه همراه با سرمای یخ‌زننده، لباس گرم بپوش."]),
    51: ("🌦️", "نم‌نم باران", ["بارون ریزی توی راهه، یه چتر تاشو کافیه."]),
    53: ("🌦️", "باران ملایم", ["یه بارون ملایم امروز میزبانمونه."]),
    55: ("🌧️", "باران نسبتا شدید", ["بارون امروز جدی‌تره، چترتو حتما بردار."]),
    56: ("🌧️", "باران یخ‌زده سبک", ["مراقب لغزندگی معابر باش."]),
    57: ("🌧️", "باران یخ‌زده", ["سطح‌ها لیز میشن، احتیاط کن."]),
    61: ("🌧️", "بارانی", ["امروز روز بارونیه، چتر همراهت باشه."]),
    63: ("🌧️", "باران متوسط", ["بارون خوبی می‌باره، لباس ضدآب بپوش."]),
    65: ("🌧️", "باران شدید", ["بارون شدیدیه، بهتره کمتر بیرون بمونی."]),
    66: ("🌧️", "باران یخ‌زده", ["جاده‌ها می‌تونن لیز باشن، احتیاط."]),
    67: ("🌧️", "باران یخ‌زده شدید", ["احتیاط زیاد لازمه امروز."]),
    71: ("❄️", "برف سبک", ["دونه‌های نازک برف میبارن، لذت ببر از منظره."]),
    73: ("❄️", "برف متوسط", ["امروز برف میاد، لباس گرم فراموش نشه."]),
    75: ("❄️", "برف سنگین", ["برف سنگینی در راهه، اگه میشه بیرون نرو."]),
    77: ("🌨️", "دانه‌های برف", ["دونه‌های ریز برف توی هوا پخشن."]),
    80: ("🌦️", "رگبار پراکنده", ["رگبارهای کوتاه و پراکنده داریم."]),
    81: ("🌧️", "رگبار", ["رگبار باران، احتمالا هوا زود عوض میشه."]),
    82: ("⛈️", "رگبار شدید", ["رگبار شدیدی در راهه، مراقب باش."]),
    85: ("🌨️", "رگبار برف سبک", ["رگبار برف سبکی داریم."]),
    86: ("🌨️", "رگبار برف شدید", ["رگبار برف شدید، جاده‌ها لغزنده میشن."]),
    95: ("⛈️", "رعد و برق", ["توفان رعد و برق در راهه، مراقب باش."]),
    96: ("⛈️", "رعد و برق با تگرگ", ["احتمال تگرگ هست، وسیله نقلیه‌ات رو جای امن پارک کن."]),
    99: ("⛈️", "رعد و برق شدید با تگرگ", ["توفان شدیدیه، در خونه بمون اگه میشه."]),
}

DEFAULT_INFO = ("🌡️", "نامشخص", ["هوا امروز یکم غیرقابل پیش‌بینیه!"])

# نسخه‌ی شبانه‌ی ایموجی و جمله‌های باحال، فقط برای وضعیت‌های مرتبط با آفتاب/ابر
# (چون شب پیشنهاد «عینک آفتابی» یا «پیاده‌روی زیر آفتاب» بی‌معنیه)
NIGHT_EMOJI_OVERRIDE = {0: "🌙", 1: "🌙", 2: "🌙"}
NIGHT_FUNS_OVERRIDE = {
    0: [
        "آسمون امشب صاف و پرستاره‌ست، اگه بیرونی یه نگاه به آسمون بنداز 🌌",
        "هوای امشب آرومه، وقت خوبیه برای یه پیاده‌روی خنک شبونه 🌙",
    ],
    1: ["امشب آسمون کمی ابر داره ولی جای ماه رو خالی نذاشته 🌙"],
    2: ["امشب آسمون نیمه‌ابریه، دیدت به ماه و ستاره‌ها متوسطه ☁️🌙"],
    3: ["امشب هم مثل امروز ابریه، شب آرومی رو تجربه کن ☁️"],
}


def wind_desc(speed_kmh: float) -> str:
    if speed_kmh < 5:
        return "آرامش کامل 🍃"
    if speed_kmh < 20:
        return "نسیم ملایم 🍃"
    if speed_kmh < 40:
        return "باد نسبتا شدید 💨"
    if speed_kmh < 60:
        return "باد شدید 🌬️"
    return "باد بسیار شدید، مراقب باش 🌪️"


def pop_desc(pop: float) -> str:
    if pop < 20:
        return "بعیده بارونی بیاد"
    if pop < 50:
        return "امکانش هست، چتر همراهت باشه"
    if pop < 80:
        return "به احتمال زیاد می‌باره"
    return "تقریبا مطمئنیم که می‌باره ☔"


def clothing_suggestion(temp: float, wind: float, pop: float) -> str:
    """پیشنهاد پوشش لباس بر اساس دما، باد و احتمال بارش"""
    if temp < 0:
        base = "🧥 کاپشن ضخیم، شال‌گردن و دستکش یادت نره، هوا خیلی سرده!"
    elif temp < 10:
        base = "🧥 کاپشن یا پالتوی گرم بپوش."
    elif temp < 18:
        base = "🧶 یه ژاکت یا سویشرت کافیه."
    elif temp < 28:
        base = "👕 لباس معمولی و راحت بپوش."
    else:
        base = "🩳 لباس نازک و سبک بپوش و آب زیاد بخور."

    extra = []
    if pop >= 50:
        extra.append("☔ چتر یا بارونی همراهت باشه.")
    if wind >= 40:
        extra.append("🌬️ به‌خاطر باد شدید، لباس محکم‌تری انتخاب کن.")

    if extra:
        return base + " " + " ".join(extra)
    return base


def aqi_desc(aqi):
    """توضیح شاخص کیفیت هوا (US AQI)"""
    if aqi is None:
        return ("❔", "نامشخص")
    if aqi <= 50:
        return ("🟢", "پاک و سالم")
    if aqi <= 100:
        return ("🟡", "متوسط")
    if aqi <= 150:
        return ("🟠", "برای گروه‌های حساس ناسالم")
    if aqi <= 200:
        return ("🔴", "ناسالم")
    if aqi <= 300:
        return ("🟣", "بسیار ناسالم")
    return ("⚫", "خطرناک")


# ==================== Open-Meteo ====================
def geocode_city(name: str):
    """پیدا کردن بهترین تطبیق برای اسم شهر (فقط یک نتیجه برمی‌گردونه)"""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    try:
        r = requests.get(url, params={"name": name, "count": 6, "language": "fa"}, timeout=10)
        data = r.json()
    except Exception:
        return None
    results = data.get("results", []) or []
    if not results:
        return None
    iran = [c for c in results if c.get("country_code") == "IR"]
    return (iran or results)[0]


def fetch_weather(lat: float, lon: float):
    """
    اطلاعات آب و هوا رو از دیروز (past_days=1) تا ۶ روز آینده (forecast_days=7) می‌گیره.
    ایندکس آرایه‌ی daily: 0=دیروز، 1=امروز، 2=فردا، 3=پس‌فردا، ... تا 7
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,weathercode,windspeed_10m,relative_humidity_2m",
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,windspeed_10m_max",
        "timezone": "auto",
        "past_days": 1,
        "forecast_days": 7,
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def fetch_air_quality(lat: float, lon: float):
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {"latitude": lat, "longitude": lon, "current": "us_aqi,pm2_5,pm10"}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("current", {})

# ==================== قالب‌بندی متن پاسخ ====================
def day_title_for(offset, weekday, dt, is_night_now):
    if offset == -1:
        return "دیروز"
    if offset == 0:
        return "امشب" if is_night_now else "امروز"
    if offset == 1:
        return "فردا"
    if offset == 2:
        return "پس‌فردا"
    return f"{weekday}، {jalali_str(dt)}"


def format_day(data, city_name, offset, aqi_value=None):
    """
    گزارش یک روز مشخص (از دیروز offset=-1 تا ۶ روز بعد offset=6).
    برای امروز (offset=0) از داده‌ی لحظه‌ای (current) استفاده می‌شه که دقیق‌تره،
    برای بقیه‌ی روزها از میانگین/بیشینه‌ی روزانه (daily).
    """
    daily = data["daily"]
    idx = offset + 1  # چون ایندکس ۰ آرایه مربوط به دیروزه (offset=-1)
    dt = datetime.strptime(daily["time"][idx], "%Y-%m-%d")
    weekday = WEEKDAY_FA[dt.weekday()]

    is_night_now = False
    if offset == 0:
        cur_time_str = data.get("current", {}).get("time", "")
        if "T" in cur_time_str:
            hour = int(cur_time_str.split("T")[1][:2])
            is_night_now = hour >= 19 or hour < 5

    day_title = day_title_for(offset, weekday, dt, is_night_now)

    pop = daily["precipitation_probability_max"][idx]
    if pop is not None:
        precip_line = f"☔ احتمال بارش: {pop}% — {pop_desc(pop)}"
    else:
        psum_list = daily.get("precipitation_sum", [None] * len(daily["time"]))
        psum = psum_list[idx]
        precip_line = f"☔ میزان بارش: {psum} mm" if psum is not None else "☔ اطلاعات بارش موجود نیست"

    pop_for_clothing = pop if pop is not None else 0

    if offset == 0:
        cur = data["current"]
        code = cur["weathercode"]
        temp = cur["temperature_2m"]
        wind = cur["windspeed_10m"]

        if is_night_now and code in NIGHT_FUNS_OVERRIDE:
            _, label, _ = WEATHER_INFO.get(code, DEFAULT_INFO)
            emoji = NIGHT_EMOJI_OVERRIDE.get(code, "🌙")
            funs = NIGHT_FUNS_OVERRIDE[code]
        else:
            emoji, label, funs = WEATHER_INFO.get(code, DEFAULT_INFO)

        lines = [
            f"{emoji}  آب و هوای «{city_name}» — {day_title}",
            "―――――――――――――",
            f"وضعیت: {label}",
            f"🌡️ دما: {round(temp)}°C  (احساس واقعی {round(cur['apparent_temperature'])}°C)",
            f"💧 رطوبت: {cur['relative_humidity_2m']}%",
            f"💨 باد: {round(wind)} km/h — {wind_desc(wind)}",
            precip_line,
        ]

        aqi_emoji, aqi_label = aqi_desc(aqi_value)
        if aqi_value is not None:
            lines.append(f"{aqi_emoji} کیفیت هوا: {aqi_label} (شاخص AQI: {aqi_value})")

        lines.append("")
        lines.append(f"👔 پیشنهاد پوشش: {clothing_suggestion(temp, wind, pop_for_clothing)}")
        lines.append("")
        lines.append(f"💬 {random.choice(funs)}")
    else:
        emoji, label, funs = WEATHER_INFO.get(daily["weathercode"][idx], DEFAULT_INFO)
        tmax = daily["temperature_2m_max"][idx]
        tmin = daily["temperature_2m_min"][idx]
        wind = daily["windspeed_10m_max"][idx]
        avg_temp = (tmax + tmin) / 2

        lines = [
            f"{emoji}  آب و هوای «{city_name}» — {day_title}",
            "―――――――――――――",
            f"وضعیت: {label}",
            f"🌡️ دما: بین {round(tmin)}°C تا {round(tmax)}°C",
            f"💨 باد: {round(wind)} km/h — {wind_desc(wind)}",
            precip_line,
            "",
            f"👔 پیشنهاد پوشش: {clothing_suggestion(avg_temp, wind, pop_for_clothing)}",
            "",
            f"💬 {random.choice(funs)}",
        ]

    return "\n".join(lines)


def format_week(data, city_name):
    daily = data["daily"]
    lines = [f"📅  پیش‌بینی هفتگی «{city_name}» (خلاصه)", "―――――――――――――"]
    # ایندکس ۰ آرایه مربوط به دیروزه، پس هفته‌ی پیش‌رو از ایندکس ۱ (امروز) شروع می‌شه
    for i in range(1, len(daily["time"])):
        dt = datetime.strptime(daily["time"][i], "%Y-%m-%d")
        weekday = WEEKDAY_FA[dt.weekday()]
        emoji, _, _ = WEATHER_INFO.get(daily["weathercode"][i], DEFAULT_INFO)
        tmax = round(daily["temperature_2m_max"][i])
        tmin = round(daily["temperature_2m_min"][i])
        pop = daily["precipitation_probability_max"][i]
        pop_text = f"{pop}%" if pop is not None else "نامشخص"
        lines.append(f"{emoji} {weekday} {jalali_str(dt)}: {tmax}°/{tmin}°  |  بارش {pop_text}")
    return "\n".join(lines)


# ==================== کیبوردهای شیشه‌ای (Inline) ====================
def mode_select_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🌤 آب و هوای امروز", "callback_data": "mode:today"}],
            [{"text": "📅 هفته آینده (خلاصه)", "callback_data": "mode:week"}],
        ]
    }


def day_nav_keyboard(offset):
    """
    کیبورد ناوبری بین روزها: روز قبل / امروز / روز بعد
    offset از -1 (دیروز) تا 6 (شش روز بعد) مجازه.
    """
    nav_row = []
    if offset > -1:
        nav_row.append({"text": "◀️ روز قبل", "callback_data": f"day:{offset - 1}"})
    if offset != 0:
        nav_row.append({"text": "🔄 امروز", "callback_data": "day:0"})
    if offset < 6:
        nav_row.append({"text": "روز بعد ▶️", "callback_data": f"day:{offset + 1}"})

    rows = [nav_row] if nav_row else []
    rows.append([
        {"text": "🏙️ تغییر شهر", "callback_data": "changecity"},
        {"text": "🏠 منوی اصلی", "callback_data": "mainmenu"},
    ])
    return {"inline_keyboard": rows}


def simple_result_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🏙️ تغییر شهر", "callback_data": "changecity"},
             {"text": "🏠 منوی اصلی", "callback_data": "mainmenu"}],
        ]
    }


# ==================== توابع ارتباط با API بله ====================
def api_post(method, payload):
    try:
        requests.post(f"{API_BASE}/{method}", json=payload, timeout=10)
    except Exception as e:
        print("خطای ارسال:", e)


def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    api_post("sendMessage", payload)


def edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    api_post("editMessageText", payload)


def answer_callback(callback_id, text=None):
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    api_post("answerCallbackQuery", payload)


# ==================== منطق اصلی ربات ====================
WELCOME_TEXT = (
    "سلام! 👋 به ربات آب و هوا خوش اومدی 🌦️\n\n"
    "اول یکی از گزینه‌های زیر رو انتخاب کن، بعد اسم شهرت رو برام بفرست 🏙️"
)


def deliver_day(chat_id, offset, message_id=None):
    """نمایش گزارش یک روز مشخص (دیروز تا ۶ روز بعد) با کیبورد ناوبری"""
    session = user_sessions.get(chat_id)
    if not session:
        text = "اول اسم یه شهر رو برام بفرست 🙂"
        if message_id:
            edit_message(chat_id, message_id, text)
        else:
            send_message(chat_id, text)
        return

    try:
        weather = fetch_weather(session["lat"], session["lon"])
    except Exception:
        text = "⚠️ مشکلی توی دریافت اطلاعات آب و هوا پیش اومد، دوباره امتحان کن."
        if message_id:
            edit_message(chat_id, message_id, text)
        else:
            send_message(chat_id, text)
        return

    aqi_value = None
    if offset == 0:
        try:
            aq = fetch_air_quality(session["lat"], session["lon"])
            aqi_value = aq.get("us_aqi")
        except Exception:
            pass

    text = format_day(weather, session["name"], offset, aqi_value)
    keyboard = day_nav_keyboard(offset)

    if message_id:
        edit_message(chat_id, message_id, text, reply_markup=keyboard)
    else:
        send_message(chat_id, text, reply_markup=keyboard)
def deliver_week(chat_id, message_id=None):
    """نمایش خلاصه‌ی هفت روز آینده"""
    session = user_sessions.get(chat_id)
    if not session:
        text = "اول اسم یه شهر رو برام بفرست 🙂"
        if message_id:
            edit_message(chat_id, message_id, text)
        else:
            send_message(chat_id, text)
        return

    try:
        weather = fetch_weather(session["lat"], session["lon"])
    except Exception:
        text = "⚠️ مشکلی توی دریافت اطلاعات آب و هوا پیش اومد، دوباره امتحان کن."
        if message_id:
            edit_message(chat_id, message_id, text)
        else:
            send_message(chat_id, text)
        return

    text = format_week(weather, session["name"])
    keyboard = simple_result_keyboard()

    if message_id:
        edit_message(chat_id, message_id, text, reply_markup=keyboard)
    else:
        send_message(chat_id, text, reply_markup=keyboard)


def handle_message(msg):
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()

    if text in ("/start", "start", "شروع"):
        send_message(chat_id, WELCOME_TEXT, reply_markup=mode_select_keyboard())
        return

    # اگر کاربر تا حالا هیچ حالتی (امروز/هفته) رو انتخاب نکرده، اول باید انتخاب کنه
    if chat_id not in pending_mode and chat_id not in last_mode:
        send_message(chat_id, "اول یکی از گزینه‌های زیر رو انتخاب کن 👇", reply_markup=mode_select_keyboard())
        return

    # هر متنی که برسه به‌عنوان اسم شهر در نظر گرفته می‌شه
    city = geocode_city(text)
    if not city:
        send_message(chat_id, f"😕 شهر «{text}» رو پیدا نکردم. لطفا اسمشو دقیق‌تر بنویس.")
        return

    user_sessions[chat_id] = {"name": city.get("name"), "lat": city["latitude"], "lon": city["longitude"]}

    mode = pending_mode.pop(chat_id, None) or last_mode.get(chat_id, "today")
    last_mode[chat_id] = mode

    if mode == "today":
        deliver_day(chat_id, 0)
    else:
        deliver_week(chat_id)


def handle_callback(cq):
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]
    data = cq.get("data", "")
    answer_callback(cq["id"])

    if data.startswith("mode:"):
        mode = data.split(":", 1)[1]
        if chat_id in user_sessions:
            # شهر از قبل مشخصه، دیگه لازم نیست دوباره ازش بپرسیم
            pending_mode.pop(chat_id, None)
            last_mode[chat_id] = mode
            if mode == "today":
                deliver_day(chat_id, 0, message_id=message_id)
            else:
                deliver_week(chat_id, message_id=message_id)
        else:
            pending_mode[chat_id] = mode
            edit_message(chat_id, message_id, "اسم شهر مورد نظرت رو برام بفرست 🏙️")
        return

    if data.startswith("day:"):
        offset = int(data.split(":", 1)[1])
        offset = max(-1, min(6, offset))
        last_mode[chat_id] = "today"
        deliver_day(chat_id, offset, message_id=message_id)
        return

    if data == "changecity":
        edit_message(chat_id, message_id, "باشه! اسم شهر جدید رو برام بفرست 🏙️")
        return

    if data == "mainmenu":
        pending_mode.pop(chat_id, None)
        edit_message(chat_id, message_id, WELCOME_TEXT, reply_markup=mode_select_keyboard())
        return


def handle_update(update):
    if "message" in update:
        handle_message(update["message"])
    elif "callback_query" in update:
        handle_callback(update["callback_query"])


def main():
    print("cilick Ctrl + C for stop bot")
    offset = None
    while True:
        try:
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset
            r = requests.get(f"{API_BASE}/getUpdates", params=params, timeout=35)
            resp = r.json()
            if not resp.get("ok"):
                time.sleep(1)
                continue
            for update in resp.get("result", []):
                offset = update["update_id"] + 1
                handle_update(update)
        except KeyboardInterrupt:
            print("\n🛑 ربات خاموش شد.")
            break
        except Exception as e:
            print("خطا در حلقه اصلی:", e)
            time.sleep(2)


if __name__ == "__main__":
    main()