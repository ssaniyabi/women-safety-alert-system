import datetime as dt
import os
import pickle
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "safety_system_v2.db"
MEDIA_DIR = BASE_DIR / "alerts_media"
MODEL_FILE = BASE_DIR / "model.pkl"
VECTORIZER_FILE = BASE_DIR / "vectorizer.pkl"

MEDIA_DIR.mkdir(exist_ok=True)


st.set_page_config(
    page_title="Women Safety Alert System",
    page_icon="SOS",
    layout="wide",
)


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password TEXT,
            name TEXT,
            phone TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            name TEXT,
            phone TEXT,
            FOREIGN KEY(user_email) REFERENCES users(email) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            timestamp TEXT,
            location TEXT,
            message TEXT,
            image_path TEXT,
            audio_path TEXT,
            threat_level TEXT,
            FOREIGN KEY(user_email) REFERENCES users(email) ON DELETE CASCADE
        )
        """
    )
    conn.commit()
    conn.close()


def execute_query(query, params=(), fetch=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = None
    if fetch == "one":
        result = cursor.fetchone()
    elif fetch == "all":
        result = cursor.fetchall()
    conn.commit()
    conn.close()
    return result


def register_user(email, password, name, phone):
    try:
        execute_query(
            "INSERT INTO users (email, password, name, phone) VALUES (?, ?, ?, ?)",
            (email, password, name, phone),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def authenticate_user(email, password):
    return execute_query(
        "SELECT name, phone FROM users WHERE email = ? AND password = ?",
        (email, password),
        fetch="one",
    )


def get_emergency_contacts(user_email):
    return execute_query(
        "SELECT id, name, phone FROM emergency_contacts WHERE user_email = ? ORDER BY id DESC",
        (user_email,),
        fetch="all",
    )


def add_emergency_contact(user_email, name, phone):
    execute_query(
        "INSERT INTO emergency_contacts (user_email, name, phone) VALUES (?, ?, ?)",
        (user_email, name, phone),
    )


def delete_emergency_contact(contact_id, user_email):
    execute_query(
        "DELETE FROM emergency_contacts WHERE id = ? AND user_email = ?",
        (contact_id, user_email),
    )


def log_alert(user_email, timestamp, location, message, image_path, audio_path, threat_level):
    execute_query(
        """
        INSERT INTO alerts (user_email, timestamp, location, message, image_path, audio_path, threat_level)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_email, timestamp, location, message, image_path, audio_path, threat_level),
    )


def fetch_user_alerts(user_email):
    return execute_query(
        """
        SELECT id, timestamp, location, message, threat_level, image_path, audio_path
        FROM alerts
        WHERE user_email = ?
        ORDER BY id DESC
        """,
        (user_email,),
        fetch="all",
    )


@st.cache_resource
def load_classifier():
    try:
        with MODEL_FILE.open("rb") as model_file:
            model = pickle.load(model_file)
        with VECTORIZER_FILE.open("rb") as vectorizer_file:
            vectorizer = pickle.load(vectorizer_file)
        return model, vectorizer
    except Exception:
        return None, None


def get_threat_level(text):
    if not text.strip():
        return "Safe", 0

    model, vectorizer = load_classifier()
    if model is None or vectorizer is None:
        text_lower = text.lower()
        if any(
            word in text_lower
            for word in ["help", "attack", "kill", "danger", "police", "chase", "kidnap", "harass", "grab", "stop"]
        ):
            return "Emergency", 2
        if any(
            word in text_lower
            for word in ["follow", "suspicious", "dark", "cab", "wrong route", "drunk", "uncomfortable", "stare"]
        ):
            return "Warning", 1
        return "Safe", 0

    prediction = int(model.predict(vectorizer.transform([text]))[0])
    return {0: "Safe", 1: "Warning", 2: "Emergency"}.get(prediction, "Safe"), prediction


def get_location():
    fallback = {
        "city": "Chennai",
        "region": "Tamil Nadu",
        "lat": 13.0827,
        "lon": 80.2707,
        "full_name": "Chennai, Tamil Nadu, India (Simulated)",
    }
    try:
        with urllib.request.urlopen("http://ip-api.com/json/", timeout=4) as response:
            data = pd.read_json(response, typ="series").to_dict()
        if data.get("status") == "success":
            city = data.get("city", "Unknown City")
            region = data.get("regionName", "Unknown Region")
            country = data.get("country", "")
            return {
                "city": city,
                "region": region,
                "lat": data.get("lat", fallback["lat"]),
                "lon": data.get("lon", fallback["lon"]),
                "full_name": f"{city}, {region}, {country}".strip(", "),
            }
    except Exception:
        pass
    return fallback


def save_upload(uploaded_file, prefix):
    if uploaded_file is None:
        return ""

    suffix = Path(uploaded_file.name).suffix or ".bin"
    filename = f"{prefix}_{int(dt.datetime.now().timestamp())}{suffix}"
    path = MEDIA_DIR / filename
    path.write_bytes(uploaded_file.getbuffer())
    return str(path)


def make_whatsapp_link(phone, message):
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    encoded_message = urllib.parse.quote(message)
    return f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_message}"


def render_header():
    st.markdown(
        """
        <style>
        .stApp { background: #fff7fa; }
        [data-testid="stSidebar"] { background: #fff0f5; }
        .metric-card {
            padding: 1rem;
            border: 1px solid #ffd2dc;
            border-radius: 8px;
            background: #ffffff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Women Safety Alert System")
    st.caption("Machine-learning assisted SOS logging and WhatsApp alert dispatch.")


def auth_view():
    render_header()
    login_tab, register_tab = st.tabs(["Login", "Create account"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", type="primary")

        if submitted:
            user = authenticate_user(email.strip(), password)
            if user:
                st.session_state.user_email = email.strip()
                st.session_state.user_name = user[0]
                st.session_state.user_phone = user[1]
                st.rerun()
            st.error("Invalid email or password.")

    with register_tab:
        with st.form("register_form"):
            name = st.text_input("Full name")
            phone = st.text_input("Phone number")
            email = st.text_input("Email", key="register_email")
            password = st.text_input("Password", type="password", key="register_password")
            submitted = st.form_submit_button("Create account", type="primary")

        if submitted:
            if not all([name.strip(), phone.strip(), email.strip(), password]):
                st.warning("Please fill in all fields.")
            elif register_user(email.strip(), password, name.strip(), phone.strip()):
                st.success("Account created. You can log in now.")
            else:
                st.error("An account with this email already exists.")


def sos_view(user_email):
    st.subheader("SOS Alert")
    location = get_location()
    message = st.text_area("Threat description", height=140, placeholder="Describe what is happening...")
    threat_level, score = get_threat_level(message)

    color = {"Safe": "green", "Warning": "orange", "Emergency": "red"}[threat_level]
    st.markdown(f"**Live threat level:** :{color}[{threat_level}]")

    image = st.file_uploader("Attach suspect/location photo", type=["png", "jpg", "jpeg"])
    audio = st.file_uploader("Attach voice note", type=["wav", "mp3", "m4a"])

    contacts = get_emergency_contacts(user_email)
    contact_labels = {f"{name} ({phone})": (name, phone) for _, name, phone in contacts}
    selected_contact = st.selectbox("Emergency contact", list(contact_labels.keys()) if contact_labels else [])

    st.info(f"Detected location: {location['full_name']}")

    if st.button("Activate SOS", type="primary", use_container_width=True):
        if not message.strip():
            st.warning("Please enter a threat description first.")
            return
        if not selected_contact:
            st.warning("Please add an emergency contact first.")
            return

        image_path = save_upload(image, "img")
        audio_path = save_upload(audio, "voice")
        timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        maps_url = f"https://www.google.com/maps?q={location['lat']},{location['lon']}"
        location_text = f"{location['full_name']} | {maps_url}"

        log_alert(user_email, timestamp, location_text, message, image_path, audio_path, threat_level)

        contact_name, contact_phone = contact_labels[selected_contact]
        alert_message = (
            f"SOS Alert from {st.session_state.user_name}\n"
            f"Threat Level: {threat_level}\n"
            f"Message: {message}\n"
            f"Location: {location_text}"
        )
        whatsapp_link = make_whatsapp_link(contact_phone, alert_message)
        st.success(f"SOS logged for {contact_name}. Open WhatsApp to send the alert.")
        st.link_button("Open WhatsApp alert", whatsapp_link, use_container_width=True)


def contacts_view(user_email):
    st.subheader("Emergency Contacts")
    with st.form("contact_form", clear_on_submit=True):
        name = st.text_input("Contact name")
        phone = st.text_input("WhatsApp phone with country code")
        submitted = st.form_submit_button("Add contact", type="primary")

    if submitted:
        if name.strip() and phone.strip():
            add_emergency_contact(user_email, name.strip(), phone.strip())
            st.success("Contact added.")
            st.rerun()
        else:
            st.warning("Please enter both name and phone.")

    contacts = get_emergency_contacts(user_email)
    if not contacts:
        st.info("No emergency contacts yet.")
        return

    for contact_id, name, phone in contacts:
        cols = st.columns([3, 3, 1])
        cols[0].write(name)
        cols[1].write(phone)
        if cols[2].button("Delete", key=f"delete_{contact_id}"):
            delete_emergency_contact(contact_id, user_email)
            st.rerun()


def history_view(user_email):
    st.subheader("History Logs")
    rows = fetch_user_alerts(user_email)
    if not rows:
        st.info("No alerts logged yet.")
        return

    df = pd.DataFrame(
        rows,
        columns=["ID", "Timestamp", "Location", "Message", "Threat Level", "Image", "Audio"],
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    counts = df["Threat Level"].value_counts().reindex(["Safe", "Warning", "Emergency"], fill_value=0)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(counts.index, counts.values, color=["#2ecc71", "#f1c40f", "#ff3366"])
    ax.set_title("Logged Threat Distribution")
    ax.set_ylabel("Alerts")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    st.pyplot(fig)


def main():
    init_db()
    if "user_email" not in st.session_state:
        auth_view()
        return

    render_header()
    st.sidebar.write(f"Signed in as **{st.session_state.user_name}**")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    page = st.sidebar.radio("Navigation", ["SOS Alert", "Emergency Contacts", "History Logs"])
    if page == "SOS Alert":
        sos_view(st.session_state.user_email)
    elif page == "Emergency Contacts":
        contacts_view(st.session_state.user_email)
    else:
        history_view(st.session_state.user_email)


if __name__ == "__main__":
    main()
