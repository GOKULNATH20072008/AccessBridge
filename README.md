# AccessBridge

> Accessibility-first, hands-free computer interaction — voice commands, Morse code input, and a switch-driven web widget for any page.

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

AccessBridge is an accessibility-first assistant that provides alternative computer interaction methods beyond traditional keyboard and mouse input — on the desktop and on the web.

* 🎤 Voice Command Control
* 📡 Morse Code Input System
* 🌐 Switch-Access Web Widget (v2)
* ♿ Accessibility-Focused Interaction
* 💡 Intelligent Suggestions
* 🖥️ Hands-Free Operation

---

## 🌐 Web Widget (v2)

The **AccessBridge Web Widget** brings switch-access to any web page. A person using a single switch key (Space by default) — or two switches — can navigate and activate every interactive element, with an adjustable scan speed and a high-contrast highlight.

One self-contained file, vanilla JS, no dependencies, no build step:

```html
<script src="accessbridge/web_widget/access-widget.js" async></script>
```

**What it does**

* **Auto mode** — the highlight auto-advances at Slow / Medium / Fast; the switch key activates the highlighted item.
* **Step mode** (two switches) — `Space` moves the highlight, `Enter` activates it; no timer runs.
* **One-press selects** — a `<select>` opens its native dropdown on activation; scanning pauses until you pick an option.
* **Text fields** — enter a paused editing state on activation (the switch key is released to the field); `Esc` returns to scanning.
* **Screen-reader support** — `aria-live` announcements for start/stop, editing, and activations; the target receives real focus with the native ring suppressed.
* **Status pill** — live mode, speed, and position (e.g. `Scanning · medium · 5/24`).
* **Key-mash proof** — presses within 250 ms and OS repeat keys are ignored; a debounced `MutationObserver` tracks page changes.
* Settings persist in a cookie (`accessbridge_settings`).

Try the runnable demo: [`accessbridge/web_widget/`](accessbridge/web_widget/)

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
| Vanilla JS         | Web Widget (v2)    |
| Shadow DOM         | Widget Isolation   |
| Git & GitHub       | Version Control    |

---

## 📂 Project Structure

```text
accessbridge/
│
├── web_widget/              # Web Widget (v2)
│   ├── access-widget.js     #   entire widget, single file
│   ├── demo/index.html      #   runnable demo + self-test checklist
│   └── README.md
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
