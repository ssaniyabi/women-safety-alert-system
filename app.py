import os
import sys
import time
import wave
import json
import sqlite3
import pickle
import threading
import webbrowser
import urllib.request
import urllib.parse
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import matplotlib
matplotlib.use("TkAgg") # Set backend for Tkinter embedding
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

# ----------------- 🛠️ SETUP AUDIO RECORDING & SIREN -----------------
AUDIO_RECORDING_SUPPORTED = False
try:
    import sounddevice as sd
    import scipy.io.wavfile as wav
    import numpy as np
    AUDIO_RECORDING_SUPPORTED = True
except ImportError:
    pass

import winsound

MEDIA_DIR = "alerts_media"
os.makedirs(MEDIA_DIR, exist_ok=True)

# Session tracking file
SESSION_FILE = "session.json"

# ----------------- 🎨 COLOR THEME CONSTANTS (LIGHT PINK) -----------------
BG_COLOR = "#FFF0F5"         # Lavender Blush (Soft light pink window background)
CARD_BG = "#FFFFFF"          # Pure White cards for contrast
TEXT_COLOR = "#4A1525"       # Deep Rose/Burgundy for text
ACCENT_COLOR = "#FF6B81"     # Sweet Rose Pink for primary buttons
SOS_COLOR = "#FF3366"        # Cherry Red/Pink for SOS alarm
SECONDARY_BG = "#FFE4E1"     # Misty Rose for text input background and dividers
GREEN_COLOR = "#2ecc71"      # Green badge for safe
YELLOW_COLOR = "#f1c40f"     # Yellow badge for warning

# ----------------- 💾 DATABASE OPERATIONS (SQLite) -----------------
DB_FILE = "safety_system_v2.db"

def init_db():
    """Initializes SQLite database tables for Users, Contacts, and Alerts."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password TEXT,
            name TEXT,
            phone TEXT
        )
    """)
    
    # Emergency Contacts Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            name TEXT,
            phone TEXT,
            FOREIGN KEY(user_email) REFERENCES users(email) ON DELETE CASCADE
        )
    """)
    
    # Alerts Table
    cursor.execute("""
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
    """)
    
    conn.commit()
    conn.close()

# Database Helper Functions
def register_user(email, password, name, phone):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (email, password, name, phone) VALUES (?, ?, ?, ?)",
                       (email, password, name, phone))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def authenticate_user(email, password):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name, phone FROM users WHERE email = ? AND password = ?", (email, password))
    row = cursor.fetchone()
    conn.close()
    return row # Returns (name, phone) or None

def get_user_details(email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name, phone FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    return row

def add_emergency_contact(user_email, name, phone):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO emergency_contacts (user_email, name, phone) VALUES (?, ?, ?)",
                   (user_email, name, phone))
    conn.commit()
    conn.close()

def delete_emergency_contact(contact_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM emergency_contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()

def get_emergency_contacts(user_email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, phone FROM emergency_contacts WHERE user_email = ?", (user_email,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def log_alert(user_email, timestamp, location, message, image_path, audio_path, threat_level):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO alerts (user_email, timestamp, location, message, image_path, audio_path, threat_level)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_email, timestamp, location, message, image_path, audio_path, threat_level))
    conn.commit()
    conn.close()

def fetch_user_alerts(user_email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, location, message, threat_level, image_path, audio_path 
        FROM alerts WHERE user_email = ? ORDER BY id DESC
    """, (user_email,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# ----------------- 📍 NATIVE GEOLOCATION API LOOKUP -----------------
def get_device_location():
    """Queries Windows native GeoCoordinateWatcher API via PowerShell subprocess."""
    ps_script = """
    Add-Type -AssemblyName System.Device
    $watcher = New-Object System.Device.Location.GeoCoordinateWatcher
    $watcher.Start()
    $timeout = 0
    while (($watcher.Status -ne 'Ready') -and ($timeout -lt 25)) {
        Start-Sleep -Milliseconds 100
        $timeout++
    }
    $pos = $watcher.Position.Location
    if ($pos.IsUnknown) {
        Write-Output "UNKNOWN"
    } else {
        Write-Output "$($pos.Latitude),$($pos.Longitude)"
    }
    """
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        process = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", ps_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo
        )
        stdout, stderr = process.communicate()
        result = stdout.strip()
        if result and result != "UNKNOWN" and not result.startswith("ERROR"):
            lat, lon = result.split(",")
            return float(lat), float(lon)
    except Exception:
        pass
    return None

# ----------------- 🧠 MACHINE LEARNING CLASSIFIER -----------------
model = None
vectorizer = None
try:
    with open("model.pkl", "rb") as f:
        model = pickle.load(f)
    with open("vectorizer.pkl", "rb") as f:
        vectorizer = pickle.load(f)
except Exception as e:
    print(f"Warning: model.pkl or vectorizer.pkl not loaded. Rule-based fallback activated: {e}")

def get_threat_level(text):
    if not text.strip():
        return "Safe", 0

    if model is None or vectorizer is None:
        text_lower = text.lower()
        if any(w in text_lower for w in ["help", "attack", "kill", "danger", "police", "chase", "kidnap", "harass", "grab", "stop"]):
            return "Emergency", 2
        elif any(w in text_lower for w in ["follow", "suspicious", "dark", "cab", "wrong route", "drunk", "uncomfortable", "stare"]):
            return "Warning", 1
        return "Safe", 0

    features = vectorizer.transform([text])
    pred = model.predict(features)[0]
    
    mapping = {0: "Safe", 1: "Warning", 2: "Emergency"}
    return mapping.get(pred, "Safe"), pred

# ----------------- 📱 TKINTER GUI APPLICATION -----------------
class SafetyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🛡️ Women Safety Alert System")
        self.root.geometry("900x670")
        self.root.configure(bg=BG_COLOR)
        
        # States
        self.logged_in_email = ""
        self.logged_in_name = ""
        self.logged_in_phone = ""
        
        self.current_location = {
            "city": "Chennai",
            "region": "Tamil Nadu",
            "lat": 13.0827,
            "lon": 80.2707,
            "full_name": "Chennai, Tamil Nadu, India (Simulated)"
        }
        self.attached_image_path = ""
        self.attached_audio_path = ""
        
        # Setup tables
        init_db()
        self.setup_styles()
        
        # Main Container
        self.main_container = tk.Frame(self.root, bg=BG_COLOR)
        self.main_container.pack(fill="both", expand=True)
        
        # Check Session
        self.check_active_session()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Treeview (History)
        style.configure("Treeview", 
                        background=CARD_BG, 
                        foreground=TEXT_COLOR, 
                        fieldbackground=CARD_BG, 
                        rowheight=28,
                        font=('Segoe UI', 10))
        
        style.map("Treeview", 
                  background=[('selected', ACCENT_COLOR)],
                  foreground=[('selected', 'white')])
                  
        style.configure("Treeview.Heading", 
                        background=SECONDARY_BG, 
                        foreground=TEXT_COLOR, 
                        font=('Segoe UI', 10, 'bold'))

    # Session Management
    def check_active_session(self):
        """Bypasses login if email is saved in session.json."""
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r") as f:
                    data = json.load(f)
                    email = data.get("email", "")
                    if email:
                        details = get_user_details(email)
                        if details:
                            self.logged_in_email = email
                            self.logged_in_name, self.logged_in_phone = details
                            self.load_main_app()
                            return
            except Exception:
                pass
        self.load_auth_screens()

    def save_session(self, email):
        with open(SESSION_FILE, "w") as f:
            json.dump({"email": email}, f)

    def clear_session(self):
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)

    # ----------------- 🔐 LOGIN / REGISTRATION VIEWS -----------------
    def load_auth_screens(self):
        """Builds registration and login display frames."""
        for widget in self.main_container.winfo_children():
            widget.destroy()
            
        self.auth_frame = tk.Frame(self.main_container, bg=BG_COLOR)
        self.auth_frame.pack(fill="both", expand=True)
        
        self.show_login_frame()

    def show_login_frame(self):
        for widget in self.auth_frame.winfo_children():
            widget.destroy()
            
        card = tk.Frame(self.auth_frame, bg=CARD_BG, padx=40, pady=40, highlightbackground=SECONDARY_BG, highlightthickness=2)
        card.place(relx=0.5, rely=0.5, anchor="center", width=420, height=450)
        
        lbl_title = tk.Label(card, text="🛡️ Login to Safety App", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 16, "bold"))
        lbl_title.pack(pady=(0, 25))
        
        # Email
        tk.Label(card, text="Email Address:", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 2))
        ent_email = tk.Entry(card, bg=BG_COLOR, fg=TEXT_COLOR, bd=0, insertbackground=TEXT_COLOR, font=("Segoe UI", 11))
        ent_email.pack(fill="x", ipady=8, pady=(0, 10))
        
        # Password
        tk.Label(card, text="Password:", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 2))
        ent_pass = tk.Entry(card, show="*", bg=BG_COLOR, fg=TEXT_COLOR, bd=0, insertbackground=TEXT_COLOR, font=("Segoe UI", 11))
        ent_pass.pack(fill="x", ipady=8, pady=(0, 20))
        
        # Login Button
        btn_login = tk.Button(card, text="Sign In", bg=ACCENT_COLOR, fg="white", font=("Segoe UI", 11, "bold"),
                              bd=0, cursor="hand2", activebackground=TEXT_COLOR, activeforeground="white",
                              command=lambda: self.process_login(ent_email.get().strip(), ent_pass.get()))
        btn_login.pack(fill="x", ipady=8, pady=10)
        
        # Register redirect
        btn_go_reg = tk.Button(card, text="Don't have an account? Sign Up Here", bg=CARD_BG, fg=ACCENT_COLOR,
                               font=("Segoe UI", 9, "underline"), bd=0, cursor="hand2", activebackground=CARD_BG,
                               activeforeground=TEXT_COLOR, command=self.show_register_frame)
        btn_go_reg.pack(pady=10)

    def process_login(self, email, password):
        if not email or not password:
            messagebox.showerror("Error", "Please fill in all details!")
            return
            
        auth = authenticate_user(email, password)
        if auth:
            self.logged_in_email = email
            self.logged_in_name, self.logged_in_phone = auth
            self.save_session(email)
            self.load_main_app()
        else:
            messagebox.showerror("Invalid Credentials", "Incorrect email or password!")

    def show_register_frame(self):
        for widget in self.auth_frame.winfo_children():
            widget.destroy()
            
        card = tk.Frame(self.auth_frame, bg=CARD_BG, padx=40, pady=30, highlightbackground=SECONDARY_BG, highlightthickness=2)
        card.place(relx=0.5, rely=0.5, anchor="center", width=420, height=540)
        
        lbl_title = tk.Label(card, text="👤 Register Account", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 16, "bold"))
        lbl_title.pack(pady=(0, 20))
        
        # Name
        tk.Label(card, text="Full Name:", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 2))
        ent_name = tk.Entry(card, bg=BG_COLOR, fg=TEXT_COLOR, bd=0, insertbackground=TEXT_COLOR, font=("Segoe UI", 10))
        ent_name.pack(fill="x", ipady=6, pady=(0, 10))
        
        # Phone
        tk.Label(card, text="Your Phone Number:", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 2))
        ent_phone = tk.Entry(card, bg=BG_COLOR, fg=TEXT_COLOR, bd=0, insertbackground=TEXT_COLOR, font=("Segoe UI", 10))
        ent_phone.pack(fill="x", ipady=6, pady=(0, 10))
        
        # Email
        tk.Label(card, text="Email Address:", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 2))
        ent_email = tk.Entry(card, bg=BG_COLOR, fg=TEXT_COLOR, bd=0, insertbackground=TEXT_COLOR, font=("Segoe UI", 10))
        ent_email.pack(fill="x", ipady=6, pady=(0, 10))
        
        # Password
        tk.Label(card, text="Set Password:", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 2))
        ent_pass = tk.Entry(card, show="*", bg=BG_COLOR, fg=TEXT_COLOR, bd=0, insertbackground=TEXT_COLOR, font=("Segoe UI", 10))
        ent_pass.pack(fill="x", ipady=6, pady=(0, 15))
        
        # Register Button
        btn_reg = tk.Button(card, text="Sign Up", bg=ACCENT_COLOR, fg="white", font=("Segoe UI", 11, "bold"),
                            bd=0, cursor="hand2", activebackground=TEXT_COLOR, activeforeground="white",
                            command=lambda: self.process_register(ent_email.get().strip(), ent_pass.get(), ent_name.get().strip(), ent_phone.get().strip()))
        btn_reg.pack(fill="x", ipady=8, pady=10)
        
        # Login Redirect
        btn_go_log = tk.Button(card, text="Already have an account? Login Here", bg=CARD_BG, fg=ACCENT_COLOR,
                               font=("Segoe UI", 9, "underline"), bd=0, cursor="hand2", activebackground=CARD_BG,
                               activeforeground=TEXT_COLOR, command=self.show_login_frame)
        btn_go_log.pack(pady=5)

    def process_register(self, email, password, name, phone):
        if not email or not password or not name or not phone:
            messagebox.showerror("Error", "All registration fields are required!")
            return
            
        success = register_user(email, password, name, phone)
        if success:
            messagebox.showinfo("Success", "Account created successfully! Please log in.")
            self.show_login_frame()
        else:
            messagebox.showerror("Conflict", "An account with this email already exists!")

    # ----------------- 🛡️ MAIN CORE APPLICATION VIEWS -----------------
    def load_main_app(self):
        """Loads tabs once the user successfully logged in."""
        for widget in self.main_container.winfo_children():
            widget.destroy()
            
        # Top Header frame
        header = tk.Frame(self.main_container, bg=CARD_BG, height=55, highlightbackground=SECONDARY_BG, highlightthickness=1)
        header.pack(fill="x", side="top")
        
        app_title = tk.Label(header, text="🛡️ WOMEN SAFETY SYSTEM", bg=CARD_BG, fg=SOS_COLOR, font=("Segoe UI", 12, "bold"))
        app_title.pack(side="left", padx=20, pady=12)
        
        # User Tag
        lbl_welcome = tk.Label(header, text=f"👤 Welcome, {self.logged_in_name}", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 9, "bold"))
        lbl_welcome.pack(side="left", padx=10)
        
        # Logout
        btn_logout = tk.Button(header, text="Logout", bg=SECONDARY_BG, fg=TEXT_COLOR, font=("Segoe UI", 9, "bold"),
                               bd=0, cursor="hand2", padx=12, activebackground=ACCENT_COLOR, activeforeground="white",
                               command=self.process_logout)
        btn_logout.pack(side="right", padx=15, pady=10)
        
        # Navigation page links
        self.btn_sos = tk.Button(header, text="🚨 SOS Alert", bg=SOS_COLOR, fg="white", font=("Segoe UI", 10, "bold"),
                                 bd=0, cursor="hand2", padx=15, activebackground=TEXT_COLOR, command=lambda: self.show_page("sos"))
        self.btn_sos.pack(side="right", padx=5, pady=10)
        
        self.btn_history = tk.Button(header, text="📊 History Logs", bg=SECONDARY_BG, fg=TEXT_COLOR, font=("Segoe UI", 10),
                                     bd=0, cursor="hand2", padx=15, activebackground=TEXT_COLOR, command=lambda: self.show_page("history"))
        self.btn_history.pack(side="right", padx=5, pady=10)

        self.btn_profile = tk.Button(header, text="👥 Contacts Settings", bg=SECONDARY_BG, fg=TEXT_COLOR, font=("Segoe UI", 10),
                                     bd=0, cursor="hand2", padx=15, activebackground=TEXT_COLOR, command=lambda: self.show_page("profile"))
        self.btn_profile.pack(side="right", padx=5, pady=10)
        
        # Display Body
        self.app_body = tk.Frame(self.main_container, bg=BG_COLOR)
        self.app_body.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Build layout frames
        self.build_sos_frame()
        self.build_profile_frame()
        self.build_history_frame()
        
        # Switch to default SOS Dashboard
        self.show_page("sos")
        threading.Thread(target=self.fetch_location_details, daemon=True).start()

    def process_logout(self):
        self.clear_session()
        self.logged_in_email = ""
        self.logged_in_name = ""
        self.logged_in_phone = ""
        self.load_auth_screens()

    def show_page(self, page_name):
        self.sos_frame.pack_forget()
        self.profile_frame.pack_forget()
        self.history_frame.pack_forget()
        
        # Color styles updates on headers
        self.btn_sos.config(bg=SOS_COLOR if page_name == "sos" else SECONDARY_BG, fg="white" if page_name == "sos" else TEXT_COLOR, font=("Segoe UI", 10, "bold" if page_name == "sos" else "normal"))
        self.btn_profile.config(bg=SOS_COLOR if page_name == "profile" else SECONDARY_BG, fg="white" if page_name == "profile" else TEXT_COLOR, font=("Segoe UI", 10, "bold" if page_name == "profile" else "normal"))
        self.btn_history.config(bg=SOS_COLOR if page_name == "history" else SECONDARY_BG, fg="white" if page_name == "history" else TEXT_COLOR, font=("Segoe UI", 10, "bold" if page_name == "history" else "normal"))
        
        if page_name == "sos":
            self.sos_frame.pack(fill="both", expand=True)
        elif page_name == "profile":
            self.profile_frame.pack(fill="both", expand=True)
            self.load_contacts_table()
        elif page_name == "history":
            self.history_frame.pack(fill="both", expand=True)
            self.load_history_table()
            self.render_stats_chart()

    # ----------------- 🚨 TAB 1: SOS DASHBOARD PAGE -----------------
    def build_sos_frame(self):
        self.sos_frame = tk.Frame(self.app_body, bg=BG_COLOR)
        self.sos_frame.grid_columnconfigure(0, weight=3)
        self.sos_frame.grid_columnconfigure(1, weight=2)
        
        # Left Panel (Input / Activate button)
        left_card = tk.Frame(self.sos_frame, bg=CARD_BG, padx=20, pady=20, highlightbackground=SECONDARY_BG, highlightthickness=1)
        left_card.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Editable Location/Landmark Box (For 100% Accuracy Override)
        loc_frame = tk.Frame(left_card, bg=CARD_BG)
        loc_frame.pack(fill="x", pady=(0, 5))
        
        tk.Label(loc_frame, text="📍 Current Location / Exact Landmark:", bg=CARD_BG, fg=TEXT_COLOR,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        
        self.ent_location = tk.Entry(loc_frame, bg=BG_COLOR, fg=TEXT_COLOR, bd=0, insertbackground=TEXT_COLOR, font=("Segoe UI", 10))
        self.ent_location.pack(fill="x", ipady=6, pady=2)
        self.ent_location.insert(0, "Fetching location...")

        # Geolocation settings tip label
        self.lbl_loc_tip = tk.Label(loc_frame, text="💡 Tip: For live GPS, turn ON 'Location Services' in Windows Settings!", 
                                    bg=CARD_BG, fg="#8e8e93", font=("Segoe UI", 8, "italic"))
        self.lbl_loc_tip.pack(anchor="w", pady=(0, 5))
        
        # Text input description
        lbl_msg = tk.Label(left_card, text="Describe the Situation / Threat:", bg=CARD_BG, fg=TEXT_COLOR,
                           font=("Segoe UI", 11, "bold"))
        lbl_msg.pack(anchor="w", pady=(5, 5))
        
        self.txt_message = tk.Text(left_card, height=4, bg=BG_COLOR, fg=TEXT_COLOR, bd=0,
                                   font=("Segoe UI", 10), insertbackground=TEXT_COLOR, padx=10, pady=10)
        self.txt_message.pack(fill="x", pady=5)
        self.txt_message.bind("<KeyRelease>", self.on_message_keyup)
        
        # Dynamic AI Badge prediction indicator
        threat_indicator_frame = tk.Frame(left_card, bg=CARD_BG)
        threat_indicator_frame.pack(fill="x", pady=5)
        
        lbl_threat_title = tk.Label(threat_indicator_frame, text="Analyzed Threat Level (AI Model):", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 9))
        lbl_threat_title.pack(side="left")
        
        self.lbl_threat_badge = tk.Label(threat_indicator_frame, text="🟢 SAFE", bg=CARD_BG, fg=GREEN_COLOR, font=("Segoe UI", 10, "bold"), padx=10)
        self.lbl_threat_badge.pack(side="left")
        
        # SOS Trigger Action button
        self.sos_button = tk.Button(left_card, text="🚨 ACTIVATE SOS", bg=SOS_COLOR, fg="white",
                                    font=("Segoe UI", 16, "bold"), bd=0, height=3, cursor="hand2",
                                    activebackground="#ff6b81", activeforeground="white",
                                    command=self.trigger_sos)
        self.sos_button.pack(fill="x", pady=25)
        
        # Right Panel (Attachments)
        right_card = tk.Frame(self.sos_frame, bg=CARD_BG, padx=20, pady=20, highlightbackground=SECONDARY_BG, highlightthickness=1)
        right_card.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        lbl_attachments = tk.Label(right_card, text="Multimedia Attachments", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 11, "bold"))
        lbl_attachments.pack(anchor="w", pady=(0, 15))
        
        # Sound Recorder Frame
        audio_frame = tk.LabelFrame(right_card, text="Voice Recorder", bg=CARD_BG, fg=SOS_COLOR, font=("Segoe UI", 9, "bold"), padx=10, pady=10)
        audio_frame.pack(fill="x", pady=10)
        
        self.btn_record = tk.Button(audio_frame, text="🎙️ Record Voice Memo (5s)", bg=SECONDARY_BG, fg=TEXT_COLOR, bd=0, pady=8,
                                    activebackground=ACCENT_COLOR, activeforeground="white", command=self.start_audio_thread)
        self.btn_record.pack(fill="x")
        
        self.lbl_audio_status = tk.Label(audio_frame, text="No voice note recorded", bg=CARD_BG, fg=TEXT_COLOR,
                                         font=("Segoe UI", 9, "italic"), pady=5)
        self.lbl_audio_status.pack()
        
        # Image attachment Frame
        img_frame = tk.LabelFrame(right_card, text="Image Upload", bg=CARD_BG, fg=SOS_COLOR, font=("Segoe UI", 9, "bold"), padx=10, pady=10)
        img_frame.pack(fill="x", pady=10)
        
        btn_attach_img = tk.Button(img_frame, text="📸 Attach Scene/Suspect Photo", bg=SECONDARY_BG, fg=TEXT_COLOR, bd=0, pady=8,
                                    activebackground=ACCENT_COLOR, activeforeground="white", command=self.attach_image_file)
        btn_attach_img.pack(fill="x")
        
        self.lbl_image_status = tk.Label(img_frame, text="No image attached", bg=CARD_BG, fg=TEXT_COLOR,
                                         font=("Segoe UI", 9, "italic"), pady=5)
        self.lbl_image_status.pack()

    def fetch_location_details(self):
        """Attempts Windows native coordinatesWatcher API first, then falls back to IP geo lookup."""
        self.lbl_loc_tip.config(text="📍 Accessing live device coordinates...", fg=ACCENT_COLOR)
        coords = get_device_location()
        
        if coords:
            lat, lon = coords
            self.current_location = {
                "city": "Exact Device Location",
                "region": "Windows GPS/WiFi",
                "lat": lat,
                "lon": lon,
                "full_name": f"Device Coordinates (Lat: {lat:.6f}, Lon: {lon:.6f})"
            }
            # Update location tip
            self.root.after(0, lambda: self.lbl_loc_tip.config(text="✅ Live device coordinates accessed successfully!", fg=GREEN_COLOR))
        else:
            # Fallback to IP-based estimation if Windows GPS is off
            try:
                url = "http://ip-api.com/json/"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    res_data = json.loads(response.read().decode())
                    if res_data.get("status") == "success":
                        self.current_location = {
                            "city": res_data.get("city", "Chennai"),
                            "region": res_data.get("regionName", "Tamil Nadu"),
                            "lat": res_data.get("lat", 13.0827),
                            "lon": res_data.get("lon", 80.2707),
                            "full_name": f"{res_data.get('city')}, {res_data.get('regionName')}, India"
                        }
            except Exception:
                pass
            # Update location tip warning
            self.root.after(0, lambda: self.lbl_loc_tip.config(text="⚠️ Device GPS blocked. Enable 'Location Services' in Windows Settings for exact coordinate mapping.", fg=YELLOW_COLOR))
            
        self.root.after(0, self.update_location_ui)

    def update_location_ui(self):
        self.ent_location.delete(0, tk.END)
        self.ent_location.insert(0, self.current_location['full_name'])

    def on_message_keyup(self, event):
        text = self.txt_message.get("1.0", "end-1c")
        level, _ = get_threat_level(text)
        
        if level == "Safe":
            self.lbl_threat_badge.config(text="🟢 SAFE", fg=GREEN_COLOR)
        elif level == "Warning":
            self.lbl_threat_badge.config(text="🟡 WARNING", fg=YELLOW_COLOR)
        else:
            self.lbl_threat_badge.config(text="🔴 EMERGENCY", fg=SOS_COLOR)

    def attach_image_file(self):
        file_path = filedialog.askopenfilename(
            title="Attach Threat Image",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif *.bmp")]
        )
        if file_path:
            ext = os.path.splitext(file_path)[1]
            new_filename = f"img_{int(time.time())}{ext}"
            dest = os.path.join(MEDIA_DIR, new_filename)
            try:
                shutil.copy(file_path, dest)
                self.attached_image_path = dest
                self.lbl_image_status.config(text=f"✅ Attached: {new_filename}", fg=GREEN_COLOR)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to attach image: {e}")

    def start_audio_thread(self):
        self.btn_record.config(state="disabled")
        threading.Thread(target=self.record_audio_logic, daemon=True).start()

    def record_audio_logic(self):
        filename = os.path.join(MEDIA_DIR, f"voice_{int(time.time())}.wav")
        duration = 5
        
        if AUDIO_RECORDING_SUPPORTED:
            fs = 44100
            self.lbl_audio_status.config(text="🎙️ Recording... Speak now!", fg=SOS_COLOR)
            try:
                recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
                sd.wait()
                wav.write(filename, fs, recording)
                self.attached_audio_path = filename
                self.lbl_audio_status.config(text=f"✅ Voice note: {os.path.basename(filename)}", fg=GREEN_COLOR)
            except Exception as e:
                self.record_audio_simulation(filename, msg=f"Mic failed, simulating: {e}")
        else:
            self.record_audio_simulation(filename)
            
        self.btn_record.config(state="normal")

    def record_audio_simulation(self, filepath, msg=""):
        self.lbl_audio_status.config(text=f"🎙️ Simulating capture (5s)...", fg=TEXT_COLOR)
        for i in range(5, 0, -1):
            time.sleep(1)
        try:
            with wave.open(filepath, 'wb') as obj:
                obj.setnchannels(1)
                obj.setsampwidth(2)
                obj.setframerate(44100)
                obj.writeframesraw(b'\x00' * (44100 * 5 * 2))
                
            self.attached_audio_path = filepath
            self.lbl_audio_status.config(text=f"✅ Voice simulated: {os.path.basename(filepath)}", fg=GREEN_COLOR)
        except Exception as e:
            self.lbl_audio_status.config(text=f"❌ Failed simulation: {e}", fg=SOS_COLOR)

    def trigger_sos(self):
        """SOS sequence logging incident and sending messages to all contacts via WhatsApp tabs."""
        try:
            # Grab Emergency contacts
            contacts = get_emergency_contacts(self.logged_in_email)
            if not contacts:
                messagebox.showwarning("No Contacts", "⚠️ You have not saved any Emergency Contacts! Please add them in the Settings tab first.")
                self.show_page("profile")
                return
                
            msg_text = self.txt_message.get("1.0", "end-1c")
            if not msg_text.strip():
                msg_text = "Emergency! I am in danger, please send help!"
                
            # Read exact user entered/edited location landmark for 100% precision
            loc_str = self.ent_location.get().strip()
            if not loc_str or loc_str == "Fetching location...":
                loc_str = f"Coordinates (Lat: {self.current_location['lat']}, Lon: {self.current_location['lon']})"
                
            threat_level, _ = get_threat_level(msg_text)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            maps_link = f"https://www.google.com/maps/search/?api=1&query={self.current_location['lat']},{self.current_location['lon']}"
            
            # Start sound thread
            threading.Thread(target=self.play_siren_audio, daemon=True).start()
            
            # Write Log to database
            log_alert(self.logged_in_email, timestamp, loc_str, msg_text, self.attached_image_path, self.attached_audio_path, threat_level)
            
            # Construct message content
            sms_text = (
                f"🚨 EMERGENCY ALERT! 🚨\n\n"
                f"👤 Sent By: {self.logged_in_name} (Ph: {self.logged_in_phone})\n"
                f"📍 Location / Landmark: {loc_str}\n"
                f"🗺️ Maps Link: {maps_link}\n"
                f"⚠️ Threat Analyzed: {threat_level}\n"
                f"💬 Message: \"{msg_text}\"\n"
            )
            if self.attached_image_path:
                sms_text += f"📸 Attached Photo logged: {os.path.basename(self.attached_image_path)}\n"
            if self.attached_audio_path:
                sms_text += f"🎙️ Voice Note logged: {os.path.basename(self.attached_audio_path)}\n"
            sms_text += "\n[Sent via Women Safety App (Device Live Location Geotag)]"
            
            # Encode URL
            encoded_message = urllib.parse.quote(sms_text)
            
            # Open WhatsApp for EVERY contact in browser tabs
            for contact_row in contacts:
                c_name, c_phone = contact_row[1], contact_row[2]
                
                # Clean phone number (leave digits and optional leading plus)
                c_phone_clean = "".join(char for char in c_phone if char.isdigit() or char == '+')
                
                # Format WhatsApp Link URL with correct encoded text, phone number, and location
                whatsapp_url = f"https://api.whatsapp.com/send?phone={c_phone_clean}&text={encoded_message}"
                
                print(f"Opening WhatsApp tab for {c_name} ({c_phone_clean})")
                webbrowser.open(whatsapp_url)
                time.sleep(1.0) # Pause to allow tabs to spawn cleanly
                
            success_info = f"SOS Logged Successfully!\n\nLocation: {loc_str}\nContacts Alerts triggered: {len(contacts)} contacts.\n\nOpening WhatsApp redirection web tabs..."
            messagebox.showinfo("🚨 SOS Alerts Triggered", success_info)
            
            # Reset attachments in GUI
            self.attached_image_path = ""
            self.attached_audio_path = ""
            self.lbl_image_status.config(text="No image attached", fg=TEXT_COLOR)
            self.lbl_audio_status.config(text="No voice note recorded", fg=TEXT_COLOR)
            self.txt_message.delete("1.0", tk.END)
            self.lbl_threat_badge.config(text="🟢 SAFE", fg=GREEN_COLOR)
            
        except Exception as e:
            messagebox.showerror("SOS Error", f"An error occurred while triggering SOS: {e}")

    def play_siren_audio(self):
        for _ in range(4):
            winsound.Beep(900, 250)
            winsound.Beep(1400, 250)

    # ----------------- 👤 TAB 2: PROFILE & EMERGENCY CONTACTS PAGE -----------------
    def build_profile_frame(self):
        self.profile_frame = tk.Frame(self.app_body, bg=BG_COLOR)
        self.profile_frame.grid_columnconfigure(0, weight=1)
        self.profile_frame.grid_columnconfigure(1, weight=1)
        
        # Left Frame: User Profile Info (Read Only)
        left_card = tk.Frame(self.profile_frame, bg=CARD_BG, padx=25, pady=25, highlightbackground=SECONDARY_BG, highlightthickness=1)
        left_card.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        tk.Label(left_card, text="👤 Your Profile Profile Info", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 20))
        
        profile_form = tk.Frame(left_card, bg=CARD_BG)
        profile_form.pack(fill="x")
        
        tk.Label(profile_form, text="Name:", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=5)
        self.lbl_prof_name = tk.Label(profile_form, text=self.logged_in_name, bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10))
        self.lbl_prof_name.grid(row=0, column=1, sticky="w", pady=5, padx=15)
        
        tk.Label(profile_form, text="Phone:", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=5)
        self.lbl_prof_phone = tk.Label(profile_form, text=self.logged_in_phone, bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10))
        self.lbl_prof_phone.grid(row=1, column=1, sticky="w", pady=5, padx=15)
        
        tk.Label(profile_form, text="Email:", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=5)
        self.lbl_prof_email = tk.Label(profile_form, text=self.logged_in_email, bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10))
        self.lbl_prof_email.grid(row=2, column=1, sticky="w", pady=5, padx=15)
        
        # Right Frame: Multiple Emergency Contacts Manager
        right_card = tk.Frame(self.profile_frame, bg=CARD_BG, padx=25, pady=25, highlightbackground=SECONDARY_BG, highlightthickness=1)
        right_card.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        tk.Label(right_card, text="👥 Manage Emergency Contacts", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 10))
        
        # Add Contact Fields
        add_frame = tk.Frame(right_card, bg=CARD_BG)
        add_frame.pack(fill="x", pady=10)
        
        tk.Label(add_frame, text="Contact Name:", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=2)
        self.ent_contact_name = tk.Entry(add_frame, bg=BG_COLOR, fg=TEXT_COLOR, bd=0, insertbackground=TEXT_COLOR, font=("Segoe UI", 9))
        self.ent_contact_name.grid(row=0, column=1, sticky="ew", pady=2, padx=10, ipady=4)
        
        tk.Label(add_frame, text="WhatsApp Number:", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=2)
        self.ent_contact_phone = tk.Entry(add_frame, bg=BG_COLOR, fg=TEXT_COLOR, bd=0, insertbackground=TEXT_COLOR, font=("Segoe UI", 9))
        self.ent_contact_phone.grid(row=1, column=1, sticky="ew", pady=2, padx=10, ipady=4)
        
        add_frame.columnconfigure(1, weight=1)
        
        # Hint label
        tk.Label(right_card, text="Prefix phone with country code (e.g. +919876543210)", bg=CARD_BG, fg="#8e8e93",
                 font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=(0, 10))
        
        # Add Button
        btn_add_contact = tk.Button(right_card, text="➕ Add Contact", bg=ACCENT_COLOR, fg="white", font=("Segoe UI", 9, "bold"),
                                    bd=0, cursor="hand2", activebackground=TEXT_COLOR, activeforeground="white", command=self.save_contact)
        btn_add_contact.pack(fill="x", pady=5)
        
        # List display
        lbl_sub = tk.Label(right_card, text="Saved Contacts List:", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10, "bold"))
        lbl_sub.pack(anchor="w", pady=(10, 5))
        
        # Contacts List Treeview
        scroll = tk.Scrollbar(right_card)
        self.contact_tree = ttk.Treeview(right_card, columns=("ID", "Name", "Phone"), show="headings", height=5, yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        scroll.config(command=self.contact_tree.yview)
        self.contact_tree.pack(fill="both", expand=True)
        
        self.contact_tree.heading("ID", text="ID")
        self.contact_tree.heading("Name", text="Contact Name")
        self.contact_tree.heading("Phone", text="WhatsApp Phone")
        
        self.contact_tree.column("ID", width=30, anchor="center")
        self.contact_tree.column("Name", width=120, anchor="w")
        self.contact_tree.column("Phone", width=130, anchor="w")
        
        # Delete Button
        btn_del_contact = tk.Button(right_card, text="🗑️ Delete Selected Contact", bg=SOS_COLOR, fg="white", font=("Segoe UI", 9, "bold"),
                                    bd=0, cursor="hand2", activebackground=TEXT_COLOR, activeforeground="white", command=self.remove_contact)
        btn_del_contact.pack(fill="x", pady=(10, 0))

    def save_contact(self):
        c_name = self.ent_contact_name.get().strip()
        c_phone = self.ent_contact_phone.get().strip()
        
        if not c_name or not c_phone:
            messagebox.showerror("Error", "Please fill in contact Name and Phone!")
            return
            
        add_emergency_contact(self.logged_in_email, c_name, c_phone)
        messagebox.showinfo("Success", "Emergency contact added successfully!")
        
        # Reset fields
        self.ent_contact_name.delete(0, tk.END)
        self.ent_contact_phone.delete(0, tk.END)
        
        # Reload List view
        self.load_contacts_table()

    def remove_contact(self):
        selected = self.contact_tree.focus()
        if not selected:
            messagebox.showwarning("Select Contact", "Please select a contact from the list first!")
            return
            
        contact_id = self.contact_tree.item(selected)["values"][0]
        delete_emergency_contact(contact_id)
        messagebox.showinfo("Success", "Contact deleted.")
        self.load_contacts_table()

    def load_contacts_table(self):
        # Update read-only details card labels
        self.lbl_prof_name.config(text=self.logged_in_name)
        self.lbl_prof_phone.config(text=self.logged_in_phone)
        self.lbl_prof_email.config(text=self.logged_in_email)
        
        # Clear items in table list
        for item in self.contact_tree.get_children():
            self.contact_tree.delete(item)
            
        rows = get_emergency_contacts(self.logged_in_email)
        for r in rows:
            self.contact_tree.insert("", "end", values=(r[0], r[1], r[2]))

    # ----------------- 📊 TAB 3: HISTORY LOGS & ANALYTICS -----------------
    def build_history_frame(self):
        self.history_frame = tk.Frame(self.app_body, bg=BG_COLOR)
        self.history_frame.grid_columnconfigure(0, weight=4)
        self.history_frame.grid_columnconfigure(1, weight=3)
        self.history_frame.grid_rowconfigure(0, weight=1)
        
        # Left Panel (Treeview logs list)
        table_card = tk.Frame(self.history_frame, bg=CARD_BG, padx=15, pady=15, highlightbackground=SECONDARY_BG, highlightthickness=1)
        table_card.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        lbl_title = tk.Label(table_card, text="📜 SOS Incident Logs", bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 11, "bold"))
        lbl_title.pack(anchor="w", pady=(0, 10))
        
        scroll_y = tk.Scrollbar(table_card, orient="vertical")
        scroll_x = tk.Scrollbar(table_card, orient="horizontal")
        
        self.tree = ttk.Treeview(
            table_card, 
            columns=("ID", "Timestamp", "Location", "Message", "Threat"), 
            show="headings",
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set
        )
        
        scroll_y.pack(side="right", fill="y")
        scroll_y.config(command=self.tree.yview)
        scroll_x.pack(side="bottom", fill="x")
        scroll_x.config(command=self.tree.xview)
        self.tree.pack(fill="both", expand=True)
        
        self.tree.heading("ID", text="ID")
        self.tree.heading("Timestamp", text="Date & Time")
        self.tree.heading("Location", text="Location Coordinates")
        self.tree.heading("Message", text="User Alert Message")
        self.tree.heading("Threat", text="Threat Level")
        
        self.tree.column("ID", width=40, anchor="center")
        self.tree.column("Timestamp", width=120, anchor="center")
        self.tree.column("Location", width=150, anchor="w")
        self.tree.column("Message", width=160, anchor="w")
        self.tree.column("Threat", width=80, anchor="center")
        
        # Attachment handlers action buttons
        action_frame = tk.Frame(table_card, bg=CARD_BG, pady=10)
        action_frame.pack(fill="x")
        
        btn_open_img = tk.Button(action_frame, text="📸 View Attached Photo", bg=SECONDARY_BG, fg=TEXT_COLOR, bd=0, padx=10, pady=5,
                                command=self.open_selected_image)
        btn_open_img.pack(side="left", padx=5)
        
        btn_play_audio = tk.Button(action_frame, text="🎙️ Play Voice Memo", bg=SECONDARY_BG, fg=TEXT_COLOR, bd=0, padx=10, pady=5,
                                  command=self.play_selected_audio)
        btn_play_audio.pack(side="left", padx=5)
        
        # Right Panel (Embedded Matplotlib Canvas chart)
        self.chart_card = tk.Frame(self.history_frame, bg=CARD_BG, padx=15, pady=15, highlightbackground=SECONDARY_BG, highlightthickness=1)
        self.chart_card.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

    def load_history_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        rows = fetch_user_alerts(self.logged_in_email)
        for r in rows:
            self.tree.insert("", "end", values=(r[0], r[1], r[2], r[3], r[4]))

    def open_selected_image(self):
        selected = self.tree.focus()
        if not selected:
            messagebox.showwarning("Select Item", "Please select a log from the table first!")
            return
            
        row_id = self.tree.item(selected)["values"][0]
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT image_path FROM alerts WHERE id = ?", (row_id,))
        img_path = cursor.fetchone()[0]
        conn.close()
        
        if img_path and os.path.exists(img_path):
            try:
                os.startfile(img_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open image file: {e}")
        else:
            messagebox.showinfo("No Attachment", "No photos were attached to this SOS alert.")

    def play_selected_audio(self):
        selected = self.tree.focus()
        if not selected:
            messagebox.showwarning("Select Item", "Please select a log from the table first!")
            return
            
        row_id = self.tree.item(selected)["values"][0]
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT audio_path FROM alerts WHERE id = ?", (row_id,))
        audio_path = cursor.fetchone()[0]
        conn.close()
        
        if audio_path and os.path.exists(audio_path):
            try:
                winsound.PlaySound(audio_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception as e:
                try:
                    os.startfile(audio_path)
                except Exception:
                    messagebox.showerror("Error", f"Failed to play audio file: {e}")
        else:
            messagebox.showinfo("No Attachment", "No voice notes were recorded for this SOS alert.")

    def render_stats_chart(self):
        alerts = fetch_user_alerts(self.logged_in_email)
        
        counts = {"Safe": 0, "Warning": 0, "Emergency": 0}
        for r in alerts:
            threat = r[4]
            if threat in counts:
                counts[threat] += 1
                
        for widget in self.chart_card.winfo_children():
            widget.destroy()
            
        fig, ax = plt.subplots(figsize=(4, 4), facecolor=CARD_BG)
        ax.set_facecolor(CARD_BG)
        
        categories = list(counts.keys())
        frequencies = list(counts.values())
        palette = [GREEN_COLOR, YELLOW_COLOR, SOS_COLOR]
        
        bars = ax.bar(categories, frequencies, color=palette, edgecolor=TEXT_COLOR, width=0.55)
        
        ax.tick_params(colors=TEXT_COLOR, labelsize=9)
        ax.spines['bottom'].set_color(TEXT_COLOR)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(TEXT_COLOR)
        ax.yaxis.grid(True, linestyle='--', alpha=0.3, color=TEXT_COLOR)
        ax.set_axisbelow(True)
        
        for b in bars:
            height = b.get_height()
            ax.annotate(f'{height}',
                        xy=(b.get_x() + b.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', color=TEXT_COLOR, fontweight='bold', fontsize=9)
                        
        ax.set_title("Logged Threat Distribution", color=TEXT_COLOR, fontsize=11, fontweight='bold', pad=15)
        plt.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, master=self.chart_card)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill="both", expand=True)
        canvas.draw()
        plt.close(fig)

# ----------------- 🚀 MAIN RUN BLOCK -----------------
if __name__ == "__main__":
    root = tk.Tk()
    app = SafetyApp(root)
    root.mainloop()
