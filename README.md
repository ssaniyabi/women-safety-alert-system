# Women Safety Alert System (with Machine Learning)

An interactive, desktop-based Women Safety SOS Application designed as a **4th-semester engineering mini-project**. It combines Python GUI development, database logging, external web APIs, audio/image handling, and natural language processing (NLP) to detect and dispatch alert telemetries in real-time.

---

## 🌟 Core Features

1. **🚨 One-Click SOS Trigger**: Triggers a sequence of emergency actions (plays siren warning sound, logs details to database, and initiates contact alerts).
2. **📱 Instant WhatsApp Redirection**: Automates message sending by compiling emergency details (user name, phone number, location, and Google Maps URL) and launching the browser to WhatsApp with the contact number and message pre-filled.
3. **👤 Local User Profile**: Saves personal details and emergency contacts locally in a secure SQLite database.
4. **📍 Automated Location Fetching**: Utilizes a live IP Geo-location API (`ip-api.com`) to extract current coordinates, city, and region automatically. Works offline by falling back to a simulated location.
5. **🎙️ Voice Recording & Image Attachments**: Logs suspect images and records 5-second voice memos to a local media folder (`alerts_media/`).
6. **🧠 Smart Threat Level Analysis (AI/ML)**: Analyzes the custom message using a trained Machine Learning model to categorize the risk level into **Safe 🟢**, **Warning 🟡**, or **Emergency 🔴** in real-time.
7. **📊 Log History & Analytics**: Displays past alerts in a table list and presents an embedded dark-themed Matplotlib bar chart of historical alert counts.

---

## 🛠️ Tech Stack & Requirements

- **Programming Language**: Python 3.8+
- **GUI Framework**: Tkinter (built-in)
- **Database**: SQLite3 (built-in)
- **ML / Data Processing**: `pandas`, `scikit-learn`
- **Visualization**: `matplotlib`
- **Multimedia (Optional)**: `sounddevice`, `scipy` (mic recording - falls back to silent simulation if missing)

---

## 📦 Installation & Setup

Before running the application, make sure you install the required Python libraries. Open your VS Code terminal and execute the commands below.

### 1. Install Required Core Libraries:
```bash
pip install pandas scikit-learn matplotlib
```

### 2. Install Optional Audio Recording Libraries (Microphone support):
*Note: If these fail to install, the app will degrade gracefully to simulated voice notes.*
```bash
pip install sounddevice scipy numpy
```

---

## 🚀 How to Run the Project (Step-by-Step)

Follow these steps in **VS Code** to run the complete workflow:

### **Step 1: Generate the Training Dataset**
Run the generator script. This will programmatically build a clean CSV dataset (`dataset.csv`) with 150 rows containing sample emergency, warning, and safe phrases:
```bash
python dataset_generator.py
```
*Expected Output: `Dataset successfully created and saved to dataset.csv!`*

### **Step 2: Train the Machine Learning Model**
Run the training script to build and serialize your TF-IDF vectorizer and Logistic Regression classifier:
```bash
python train_model.py
```
*Expected Output:*
- Prints the model accuracy on test data (approx 85-90%).
- Prints a classification report and confusion matrix.
- Generates `dataset_distribution.png` (a plot of training data frequencies).
- Exports `model.pkl` and `vectorizer.pkl`.

### **Step 3: Launch the GUI Application**
Run the main Tkinter desktop dashboard:
```bash
python app.py
```

### **Step 4: Configure & Use the App**
1. Click the **Profile Settings** tab and enter your name, phone number, and emergency contact's WhatsApp phone number (make sure to include the country code prefix, e.g., `+919876543210`). Click **Save Profiles**.
2. Go back to the **SOS Alert** tab. Type a threat description in the box (e.g., *"Help me, a stranger is grabbing my wrist!*").
3. Notice that the **Live Threat badge** changes to `🔴 EMERGENCY` based on the ML prediction.
4. Try attaching an image or recording a voice note using the side-panel buttons.
5. Click **ACTIVATE SOS**. A siren will beep, the details are logged to your database, and your web browser will launch a prefilled WhatsApp link directing you to send the coordinates and details to your emergency contact.
6. Check the **History Logs** tab to view your past alerts and examine the Matplotlib analytical chart.

---

## 🎓 Viva-Voce Study Guide (ML Explanation)

Be prepared to answer these questions if asked during your mini-project evaluation:

### 1. What Machine Learning concepts are used here?
We used a **TF-IDF Vectorizer** for feature extraction and a **Logistic Regression** classifier for text categorization.

### 2. What is TF-IDF and why is it used?
* **TF-IDF** stands for **Term Frequency-Inverse Document Frequency**.
* Since machine learning models cannot understand raw English text, we use TF-IDF to convert words into numbers.
* It assigns higher values to unique keywords (like *"kidnap"*, *"attack"*) and discounts common, non-informative words (like *"is"*, *"the"*, *"am"*).

### 3. Why did you choose Logistic Regression instead of Deep Learning?
* **Logistic Regression** is simple, fast, highly explainable, and works exceptionally well with sparse text features.
* It fits the scale of our student dataset (~150 rows) without suffering from overfitting, unlike complex neural networks which require thousands of samples.

### 4. How does the WhatsApp alert automation work without paid APIs?
We used Python's `webbrowser` library to direct to WhatsApp's API link (`https://api.whatsapp.com/send?phone=...&text=...`). This leverages WhatsApp Web/Desktop directly on the operating system, bypassing the need for paid subscription keys like Twilio.
