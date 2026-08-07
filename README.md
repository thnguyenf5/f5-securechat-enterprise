# F5 SecureChat Enterprise 🛡️🤖

**F5 SecureChat Enterprise** is a modern, enterprise-grade AI Chat Application workspace protected by **F5 AI Security Guardrails**. Built with FastAPI, asynchronous Server-Sent Events (SSE) streaming, and Vanilla CSS, it provides real-time threat detection, PII/SSN data loss prevention, prompt injection blocking, and interactive security telemetry analysis.

---

## 🌟 Key Features

* **🛡️ Real-Time F5 Guardrails Protection**: Automatically inspects user prompts and LLM completions for Prompt Injection, PII/SSN Leakage, API Key Leaks, Financial Data (PCI-DSS), and Malware Instructions.
* **📊 Live Security Telemetry & Inspection**: Every message bubble in chat history is interactive—click any message to inspect its exact risk score, triggered scanner, confidence rating, incident ID, and latency.
* **⚡ Token Savings Analytics**: Displays real-time estimated token savings (`~Est. Tokens Saved`) to quantify cost avoidance from blocked malicious or excessive responses.
* **🔄 Zero-Restart Provider Auto-Discovery**: Automatically queries the F5 Guardrails Management Plane to resolve active model providers (`Azure OpenAI`, `OpenAI`, `Bedrock`, `OpenRouter`). Includes a manual **`🔄 Sync Provider`** control button in the left-hand toolbar.
* **🎨 Modern Responsive UI System**: Features split-view Guardrails Analysis panel, blue transparent response cards for allowed completions, red transparent security block cards for policy violations, and a custom **☀️ / 🌙 theme switch pill**.
* **💬 Chat History Management**: Local storage session persistence with one-click trash can deletion and immediate new session thread creation.

---

## 📸 Application Screenshots

*(Replace image links below with your uploaded screenshot assets)*

| Dark Mode Split-View Workspace | Light Mode Theme Switch |
| :---: | :---: |
| ![Dark Mode Workspace](static/screenshots/dark_mode_workspace.png) | ![Light Mode Workspace](static/screenshots/light_mode_workspace.png) |

| F5 Guardrail Security Policy Block (Red Card) | Interactive Message Telemetry Analysis |
| :---: | :---: |
| ![Security Block Card](static/screenshots/security_block.png) | ![Telemetry Analysis](static/screenshots/telemetry_analysis.png) |

---

## 📋 Prerequisites

1. **Docker & Docker Compose** (Recommended) OR **Python 3.11+**.
2. An active **F5 AI Security Guardrails** account / tenant (`https://www.us1.calypsoai.app/`).

---

## 🛠️ How to Create a Project & API Key in F5 AI Guardrails GUI

Follow these step-by-step instructions to set up your security project in the F5 Management Console:

### Step 1: Log Into the F5 Guardrails Portal
Navigate to **[https://www.us1.calypsoai.app/](https://www.us1.calypsoai.app/)** and sign in with your enterprise credentials.

### Step 2: Create a New Security Project
1. In the left navigation sidebar, click **Projects**.
2. Click **+ New Project** in the top right.
3. Enter a project name (e.g., `f5-securechat-enterprise`) and optional description.
4. Click **Create**.

### Step 3: Enable Security Scanners
1. Inside your newly created project, navigate to **Scanner Settings**.
2. Enable the desired security scanners:
   * **Prompt Injection & Jailbreak Detector**: Blocks system override & "DAN mode" jailbreaks.
   * **PII & SSN Data Scanner**: Prevents social security numbers and personal data leakage.
   * **Secret & API Key Leakage Scanner**: Detects exposed API keys, private keys, and passwords.
   * **Financial & PCI-DSS Data Scanner**: Blocks credit card numbers and banking data.
   * **Malware & Harmful Instruction Scanner**: Filters malicious script creation requests.

### Step 4: Configure Upstream Model Provider Profiles
1. Navigate to **Provider Profiles** under Project Settings.
2. Click **Add Provider** and select your model deployment (e.g. `Azure OpenAI`, `OpenAI`, or `AWS Bedrock`).
3. Enter your provider API credentials and deployment details.
4. Mark the provider as **Default** and ensure it is **Enabled**.

### Step 5: Generate Credentials
1. Under Project Settings, click **API Keys**.
2. Click **Generate API Key**.
3. Copy both values immediately:
   * **Project ID** (e.g. `019f91fd-c09f-70ed-81f6-f27c2ee905dd`)
   * **API Key** (e.g. `MDE5ZmQyYjkt...`)

---

## 🚀 Quickstart (1-Command Docker Startup)

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/f5-securechat-enterprise.git
cd f5-securechat-enterprise
```

### 2. Configure Environment Variables
Copy the template `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` with your F5 Guardrails credentials:
```env
F5_AI_GUARDRAILS_API_KEY="your_f5_guardrails_api_key_here"
F5_AI_GUARDRAILS_PROJECT_ID="your_f5_guardrails_project_id_here"
PORT=8000
```

### 3. Launch the Application
```bash
docker-compose up -d
```
Open **`http://localhost:8000`** in your browser!

---

## ⚙️ Environment Variables Reference

| Variable Name | Description | Required | Default / Example |
| :--- | :--- | :---: | :--- |
| `F5_AI_GUARDRAILS_API_KEY` | API Key generated in F5 Guardrails Console | Yes | `MDE5ZmQ2...` |
| `F5_AI_GUARDRAILS_PROJECT_ID` | Project UUID from F5 Guardrails Console | Yes | `019f91fd-...` |
| `F5_AI_GUARDRAILS_ENDPOINT` | Custom proxy URL override | No | *Auto-discovered via API* |
| `PORT` | Web application listening port | No | `8000` |

---

## 🔒 Security & Privacy Notice

* **Zero Hardcoded Secrets**: This codebase contains zero hardcoded API keys or project IDs. All credentials are supplied via environment variables or local `.env` files (which are git-ignored).
* **Local Session Storage**: Chat history and telemetry logs are stored in the user's browser `localStorage` and never transmitted to third-party tracking services.

---

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.
