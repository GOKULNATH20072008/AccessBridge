# AccessBridge

> Accessibility-focused desktop assistant enabling hands-free computer interaction through voice commands, Morse code input, and intelligent accessibility tools.

## 🏆 Hackathon Submission

**Agents League Hackathon 2026**

### Submission Information

* **Project Name:** AccessBridge
* **Category:** Accessibility / Creative Apps
* **Team:** Solo
* **Status:** MVP / Prototype

### Key Innovation

AccessBridge combines voice control, Morse code interaction, and accessibility-focused assistance into a single desktop application, enabling users with limited mobility or accessibility needs to interact with computers more effectively.

---

## 🚀 Overview

AccessBridge is an accessibility-first desktop assistant designed to provide alternative computer interaction methods beyond traditional keyboard and mouse input.

The application offers:

* 🎤 Voice Command Control
* 📡 Morse Code Input System
* ♿ Accessibility-Focused Interaction
* 💡 Intelligent Suggestions
* 🖥️ Hands-Free Operation

### 🌐 Web Widget (v2)

Alongside the desktop app, AccessBridge now ships a self-contained **web widget**
that brings the same switch-access philosophy to any web page. A single switch
key (or two switches) can drive every interactive element on a page, with
auto-scan and step-scan modes, one-press select handling, screen-reader
announcements, and a high-contrast highlight.

See [`accessbridge/web_widget/`](accessbridge/web_widget/) for details and a runnable demo.

---

## ✨ Features

### 🎤 Voice Commands

Control applications and system functions using natural speech.

### 📡 Morse Code Input

Allows users to interact with the system using one or two buttons through Morse code.

### 💡 Smart Suggestions

Provides helpful recommendations based on user interaction.

### ♿ Accessibility First

Designed with inclusivity and ease of use as core principles.

### ⚡ Lightweight Desktop Application

Simple architecture with minimal system requirements.

---

## 🛠️ Tech Stack

| Technology         | Purpose            |
| ------------------ | ------------------ |
| Python             | Core Application   |
| Tkinter            | User Interface     |
| Speech Recognition | Voice Input        |
| Accessibility APIs | System Interaction |
| Git & GitHub       | Version Control    |

---

## 📂 Project Structure

```text
accessbridge/
│
├── ai/
│   ├── __init__.py
│   ├── backend.py
│   ├── foundry.py
│   └── providers.py
│
├── core/
│   ├── __init__.py
│   ├── state.py
│   └── utils.py
│
├── input/
│   └── handler.py
│
├── morse/
│   ├── __init__.py
│   └── decoder.py
│
├── ui/
│   ├── __init__.py
│   └── dashboard.py
│
├── __init__.py
├── config.json
├── main.py
├── requirements.txt
└── README.md
```

---

## 📦 Installation

### Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/AccessBridge.git
cd AccessBridge
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Application

```bash
python main.py
```

---

## 🎥 Demo Video

Watch the project demonstration here:

[Demo Video](https://youtu.be/LMUee8vj2Ew)

---

## 🎯 Problem Statement

Many individuals face challenges using traditional keyboard and mouse interfaces due to mobility limitations, accessibility requirements, or situational constraints.

AccessBridge provides alternative interaction methods that help make computing more accessible and inclusive.

---

## 🔮 Future Improvements

* AI-powered assistance
* Improved speech recognition
* Multi-language support
* Personalized accessibility profiles
* Cloud synchronization
* Cross-platform support

---

## 👨‍💻 Developer

**Gokulnath**

Built for accessibility, inclusion, and innovative human-computer interaction.

---

## ⭐ Support

If you find this project useful, please consider starring the repository.
