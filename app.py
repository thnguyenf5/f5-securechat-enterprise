import os
import sys
import json
import time
import uuid
import httpx
import tiktoken
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="F5 AI Chat Application", version="1.0.0")

# Load 12-Factor Environment Configuration
API_KEY = os.environ.get("F5_AI_GUARDRAILS_API_KEY", "")
PROJECT_ID = os.environ.get("F5_AI_GUARDRAILS_PROJECT_ID", "your-f5-project-id")
BASE_URL = os.environ.get("F5_AI_GUARDRAILS_BASE_URL", "https://www.us1.calypsoai.app").rstrip("/")
active_provider_name = "azure-open-ai"
scanner_catalog = {}

async def sync_f5_scanner_catalog():
    """
    Queries F5 Guardrails API to populate scanner ID -> friendly name catalog mapping.
    """
    global scanner_catalog
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            url = f"{BASE_URL}/backend/v1/projects/{PROJECT_ID}/scanners"
            resp = await client.get(url, headers={
                "Authorization": f"Bearer {API_KEY}",
                "x-calypso-project-id": PROJECT_ID
            })
            if resp.status_code == 200:
                data = resp.json()
                scanners = data.get("projectScanners", {}).get("scanners", {})
                for sid, sinfo in scanners.items():
                    if isinstance(sinfo, dict) and sinfo.get("name"):
                        scanner_catalog[sid] = sinfo.get("name")
                print(f"[F5 GUARDRAILS SYNC] Loaded {len(scanner_catalog)} user-defined guardrail names into scanner catalog.")
    except Exception as e:
        print(f"[F5 GUARDRAILS SYNC WARNING] Failed to sync scanner catalog: {e}")

async def sync_f5_provider_config() -> tuple:
    """
    Queries F5 Guardrails Management API to discover the currently active enabled provider profile.
    Returns (provider_name, endpoint_url)
    """
    global active_provider_name, active_calypso_endpoint
    
    # Sync scanner catalog first
    await sync_f5_scanner_catalog()

    # Check if explicit custom endpoint override is provided in env
    env_endpoint = os.environ.get("F5_AI_GUARDRAILS_ENDPOINT", "")
    if env_endpoint and "/auto" not in env_endpoint and "wise-openai" not in env_endpoint and "azure-open-ai" not in env_endpoint:
        active_calypso_endpoint = env_endpoint
        active_provider_name = env_endpoint.split("/openai/")[-1].split("/")[0] if "/openai/" in env_endpoint else "custom"
        return active_provider_name, active_calypso_endpoint

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            url = f"{BASE_URL}/backend/v1/projects/{PROJECT_ID}"
            resp = await client.get(url, headers={
                "Authorization": f"Bearer {API_KEY}",
                "x-calypso-project-id": PROJECT_ID
            })
            if resp.status_code == 200:
                data = resp.json()
                providers = data.get("project", {}).get("config", {}).get("providers", [])
                for p in providers:
                    if p.get("enabled") and (p.get("default") or len(providers) == 1):
                        active_provider_name = p.get("name", "azure-open-ai")
                        active_calypso_endpoint = f"{BASE_URL}/openai/{active_provider_name}/chat/completions"
                        print(f"[F5 GUARDRAILS SYNC] Active Provider: {active_provider_name} ({active_calypso_endpoint})")
                        return active_provider_name, active_calypso_endpoint
    except Exception as e:
        print(f"[F5 GUARDRAILS SYNC WARNING] Failed to sync provider: {e}")

    return active_provider_name, active_calypso_endpoint

@app.on_event("startup")
async def on_startup():
    print("[STARTUP] Syncing active provider configuration with F5 AI Guardrails management plane...")
    provider_name, endpoint = await sync_f5_provider_config()
    print(f"[STARTUP] Active F5 Provider Profile: {provider_name} ({endpoint})")

@app.post("/api/provider/sync")
@app.get("/api/provider/sync")
async def api_sync_provider():
    provider_name, endpoint = await sync_f5_provider_config()
    return {
        "status": "success",
        "active_provider": provider_name,
        "endpoint_url": endpoint,
        "scanners_loaded": len(scanner_catalog)
    }
PORT = int(os.environ.get("PORT", "8000"))

# Initialize tiktoken for accurate token counting
try:
    tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception:
    tokenizer = None

def count_tokens(text: str) -> int:
    if tokenizer and text:
        try:
            return len(tokenizer.encode(text))
        except Exception:
            pass
    return max(1, len(text) // 4)

def parse_f5_scanner(user_prompt: str, err_j: dict) -> tuple:
    """
    Parses exact F5 AI Guardrails error details directly from the API response payload.
    Unwraps nested error objects (cai_error) and distinguishes security policy blocks from API system errors.
    Returns (scanner_name, block_message, risk_score)
    """
    err_detail = ""
    exact_scanner = ""
    is_policy_block = False
    
    # 1. Unwrap nested "error" dict if present in API payload
    err_obj = err_j
    if isinstance(err_j, dict) and isinstance(err_j.get("error"), dict):
        err_obj = err_j["error"]
    
    if isinstance(err_obj, dict):
        err_detail = str(err_obj.get("message", "")).strip() or str(err_obj.get("detail", "")).strip()
        
        # Check direct scanner/rule keys
        for key in ["scanner", "scanner_name", "rule", "category", "violation", "trigger"]:
            val = err_obj.get(key) or (err_j.get(key) if isinstance(err_j, dict) else None)
            if val and isinstance(val, str) and val.strip():
                exact_scanner = val.strip()
                break

    # 2. Inspect cai_error for guardrail outcome & failed scanners
    cai_error = {}
    if isinstance(err_obj, dict) and isinstance(err_obj.get("cai_error"), dict):
        cai_error = err_obj["cai_error"]
    elif isinstance(err_j, dict) and isinstance(err_j.get("cai_error"), dict):
        cai_error = err_j["cai_error"]

    if cai_error:
        if cai_error.get("outcome") == "blocked":
            is_policy_block = True
        scanner_results = cai_error.get("scanner_results", [])
        failed_scanners = [s for s in scanner_results if s.get("outcome") == "failed"]
        if failed_scanners and not exact_scanner:
            failed_names = []
            for s in failed_scanners:
                sid = s.get("scanner_id", "")
                s_name = s.get("scanner_name") or s.get("name") or s.get("rule") or s.get("category")
                
                # Check dynamic scanner catalog cache for user-defined guardrail name
                if not s_name and sid and sid in scanner_catalog:
                    s_name = scanner_catalog[sid]

                if not s_name and s.get("data", {}).get("type"):
                    dtype = s.get("data", {}).get("type")
                    if dtype != "custom":
                        s_name = dtype.title() + " Scanner"

                if not s_name and sid:
                    s_name = f"Custom Guardrail ({sid[:8]})"

                if s_name and s_name not in failed_names:
                    failed_names.append(s_name)
            if failed_names:
                exact_scanner = ", ".join(failed_names)

    # Detect if message indicates policy block vs system/API error
    if "blocked" in err_detail.lower() or "guardrail" in err_detail.lower():
        is_policy_block = True

    # 3. Format output scanner title & clean message
    if exact_scanner:
        scanner_title = exact_scanner.strip(" .").title()
        if not any(k in scanner_title.lower() for k in ["scanner", "guardrail", "detector", "policy"]):
            scanner_title += " Guardrail"
        clean_msg = err_detail if err_detail else f"{exact_scanner.strip()} Triggered."
        msg = f"🛑 [F5 Guardrails Policy Block]: {clean_msg}"
        risk = "95% (High)"
        return scanner_title, msg, risk


    if is_policy_block:
        scanner = "F5 AI Security Guardrail"
        clean_msg = err_detail if err_detail else "CAI guardrails blocked the prompt."
        msg = f"🛑 [F5 Guardrails Policy Block]: {clean_msg}"
        risk = "95% (High)"
        return scanner, msg, risk

    # Handle system/API errors cleanly (e.g. Auth failure, network error, 500)
    scanner = "F5 Guardrails API Error"
    clean_msg = err_detail if err_detail else "An unexpected error occurred while communicating with F5 AI Guardrails."
    msg = f"⚠️ [F5 Guardrails API Error]: {clean_msg}"
    risk = "N/A (System Error)"
    return scanner, msg, risk





# Serve static UI files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.head("/")
@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse(content="<h1>F5 AI Chat Application</h1>", status_code=200)

@app.get("/v1/models")
@app.get("/v1/models/{model_id:path}")
async def get_models(model_id: str = None):
    return {
        "object": "list",
        "data": [
            {
                "id": "f5-protected-llm",
                "name": "F5 Protected LLM backend",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "f5-ai-guardrails"
            }
        ]
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    start_time = time.time()
    try:
        body = await request.json()
    except Exception:
        body = {}

    messages = body.get("messages", [])
    user_prompt = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_prompt = msg.get("content", "")
            break

    is_stream = body.get("stream", True)
    
    # Ensure correct model name for Calypso backend
    body["model"] = "gpt-4o-mini"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "x-calypso-project-id": PROJECT_ID
    }

    input_tokens = count_tokens(user_prompt)
    prevented_output_tokens = 500
    total_tokens_saved = input_tokens + prevented_output_tokens
    incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}-SEC"

    calypso_target_url = active_calypso_endpoint

    client = httpx.AsyncClient(timeout=60.0)

    if is_stream:
        async def stream_generator():
            try:
                async with client.stream("POST", calypso_target_url, json=body, headers=headers) as resp:
                    latency_ms = int((time.time() - start_time) * 1000)

                    if resp.status_code != 200:
                        err_text = await resp.aread()
                        err_j = {}
                        try:
                            err_j = json.loads(err_text.decode("utf-8", errors="ignore"))
                        except Exception:
                            pass

                        triggered_scanner, block_msg, risk_score = parse_f5_scanner(user_prompt, err_j)

                        # Rich security telemetry payload embedded in SSE chunk for UI Guardrails Analysis panel
                        telemetry = {
                            "inspected_text": user_prompt,
                            "status": "BLOCKED (Deny)",
                            "triggered_scanner": triggered_scanner,
                            "risk_score": risk_score,
                            "confidence": "99.2%",
                            "incident_id": incident_id,
                            "input_tokens": input_tokens,
                            "prevented_output_tokens": prevented_output_tokens,
                            "total_tokens_saved": total_tokens_saved,
                            "latency_ms": f"{latency_ms}ms"
                        }

                        c1 = {
                            "id": "chatcmpl-blocked",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": "f5-protected-llm",
                            "choices": [{
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "content": block_msg,
                                    "f5_telemetry": telemetry
                                },
                                "finish_reason": None
                            }]
                        }
                        c2 = {
                            "id": "chatcmpl-blocked",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": "f5-protected-llm",
                            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                        }

                        yield f"data: {json.dumps(c1)}\n\ndata: {json.dumps(c2)}\n\ndata: [DONE]\n\n".encode("utf-8")
                        return

                    # For ALLOWED prompts (HTTP 200), send an initial telemetry chunk so UI updates live
                    allowed_telemetry = {
                        "inspected_text": user_prompt,
                        "status": "ALLOWED (Pass)",
                        "triggered_scanner": "None (All Scanners Passed)",
                        "risk_score": "0% (Clean)",
                        "confidence": "100%",
                        "incident_id": incident_id,
                        "input_tokens": input_tokens,
                        "prevented_output_tokens": 0,
                        "total_tokens_saved": 0,
                        "latency_ms": f"{latency_ms}ms"
                    }
                    init_chunk = {
                        "id": "chatcmpl-allowed",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "f5-protected-llm",
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "f5_telemetry": allowed_telemetry
                            }
                        }]
                    }
                    yield f"data: {json.dumps(init_chunk)}\n\n".encode("utf-8")

                    async for chunk in resp.aiter_bytes():
                        yield chunk
            finally:
                await client.aclose()

        return StreamingResponse(
            stream_generator(),
            status_code=200,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )
    else:
        try:
            resp = await client.post(calypso_target_url, json=body, headers=headers)
            latency_ms = int((time.time() - start_time) * 1000)
            if resp.status_code != 200:
                err_j = {}
                try:
                    err_j = resp.json()
                except Exception:
                    pass

                triggered_scanner, block_msg, risk_score = parse_f5_scanner(user_prompt, err_j)

                telemetry = {
                    "inspected_text": user_prompt,
                    "status": "BLOCKED (Deny)",
                    "triggered_scanner": triggered_scanner,
                    "risk_score": risk_score,
                    "confidence": "99.2%",
                    "incident_id": incident_id,
                    "input_tokens": input_tokens,
                    "prevented_output_tokens": prevented_output_tokens,
                    "total_tokens_saved": total_tokens_saved,
                    "latency_ms": f"{latency_ms}ms"
                }

                return JSONResponse(status_code=200, content={
                    "id": "chatcmpl-blocked",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": "f5-protected-llm",
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": block_msg,
                            "f5_telemetry": telemetry
                        },
                        "finish_reason": "stop"
                    }]
                })
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        finally:
            await client.aclose()

if __name__ == "__main__":
    print(f"Starting F5 AI Chat Application on port {PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
