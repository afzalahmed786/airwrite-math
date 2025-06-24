Here's a complete `README.md` for your **AirWrite Math** project, designed to help others understand, set up, and use your system:

---

# ✍️ AirWrite Math: Gesture-Based Math Learning with IMU and AI

**AirWrite Math** is a gesture-driven, interactive math learning platform powered by a wrist-worn ESP32 + MPU6050 sensor and a Flask server. It dynamically generates math questions using Google's Gemini API and evaluates answers from real-time air-written digit recognition using TensorFlow Lite on ESP32.

---

## 🔧 Features

* 👋 **Gesture-Based Interaction**: Air-writing digits using wrist motions
* 📶 **ESP32 + MPU6050**: Sensor-based motion capture (6-axis IMU)
* 🧠 **On-Device ML**: Lightweight TFLite model for digit classification
* 🧮 **Dynamic Question Generation**: Via Google Gemini API
* 🧠 **Adaptive Difficulty**: Level adjusts based on user performance
* 🛑 **Gesture-Based Emergency Stop and Reboot**
* 🌐 **HTTPS Communication** between ESP32 and Flask backend

---

## 📁 Project Structure

```
AirWrite-Math/
│
├── arduino_code/             # Code for ESP32
│   ├── model_1.h             # TFLite model header
│   ├── main.ino              # Core Arduino logic
│   └── ...
│
├── flask_server/             # Flask backend
│   ├── app.py                # Flask API endpoints
│   ├── .env_template         # Template for env vars (e.g., API keys)
│   ├── requirements.txt      # Python dependencies
│   └── ...
│
├── model_training/           # Optional: Training code for digit classifier
│
└── README.md                 # This file
```

---

## 🚀 Getting Started

### 🧠 Prerequisites

* ESP32 board with MPU6050 sensor
* Arduino IDE with libraries:

  * `tflm_esp32`
  * `EloquentTinyML`
  * `Adafruit MPU6050`
  * `Adafruit GFX`, `ST7735`
  * `ArduinoJson`
* Python 3.8+ for Flask server
* Google Gemini API key

---

### 1️⃣ Arduino Setup

* Open `arduino_code/main.ino`
* Update the following:

  * Your **Wi-Fi SSID & password**
  * Your **Flask server endpoint**
* Upload to your ESP32
* Required Arduino Libraries:

  * See `arduino_code/README.md` or Arduino Library Manager

---

### 2️⃣ Flask Server Setup

```bash
cd flask_server
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

#### 🔐 Create `.env` from Template

```bash
cp .env_template .env
```

Fill in your `.env` file:

```
GEMINI_API_KEY=your_google_gemini_api_key
```

#### 🏃‍♂️ Run Flask Server (Dev)

```bash
python app.py
```

---

## 📡 Communication Flow

1. **ESP32 selects difficulty** via gesture and sends HTTPS request
2. **Flask generates questions** with Gemini API and returns JSON
3. **User performs gestures**, digits are recognized by TFLite model
4. **"!" gesture** submits answer
5. Every 5 questions: ESP32 POSTs results back to Flask
6. Flask **evaluates**, tracks score, and adjusts difficulty
7. Special **"\$" gesture** for emergency stop

---

## 🔐 Security Notes

* API keys and Wi-Fi credentials are stored in:

  * `.env` for Flask
  * Defined constants in Arduino code (consider refactoring)
* NEVER commit real `.env` or sensitive keys to GitHub.

---

## 📦 Deployment Notes

* Consider deploying the Flask app with **Gunicorn + Nginx**
* Host on **Render, Railway, Heroku**, or **your own VPS**
* Secure the ESP32–Flask link with **HTTPS**

---

## 🤝 Contributing

Fork this repo and feel free to contribute! Ideas welcome:

* Improving the model
* UI/UX for question feedback
* New gesture additions
* Better adaptive logic

---

## 📜 License

This project is licensed under the MIT License.

---

## 🙌 Acknowledgements

* [Adafruit](https://www.adafruit.com/) for IMU sensor libraries
* [Google Gemini API](https://ai.google.dev/)
* [EloquentTinyML](https://github.com/eloquentarduino/EloquentTinyML)
* [TensorFlow Lite for Microcontrollers](https://www.tensorflow.org/lite/microcontrollers)

---
