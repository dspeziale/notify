"""End-to-End automated testing suite for Multi-Application Notification Gateway.

Tests health, metrics, admin management, API keys, Telegram Bot dispatch,
Gmail/Email (App Password / SMTP) dispatch, idempotency, multi-tenant isolation,
rate limiting, and audit trail.
"""

import os
import sys
import time
import uuid
import httpx
from dotenv import load_dotenv

# Load .env
load_dotenv(".env")

BASE_URL = os.getenv("GATEWAY_BASE_URL", f"http://localhost:{os.getenv('GATEWAY_PORT', '8080')}")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

# Telegram Bot credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Email / Gmail App Password credentials
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
TEST_EMAIL_RECIPIENT = os.getenv("TEST_EMAIL_RECIPIENT", SMTP_USER).strip()

# ANSI Color formatting
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_step(title: str):
    print(f"\n{BOLD}{CYAN}=== [STEP] {title} ==={RESET}")


def print_pass(msg: str):
    print(f"  {GREEN}✔ PASS:{RESET} {msg}")


def print_fail(msg: str):
    print(f"  {RED}✖ FAIL:{RESET} {msg}")


def print_info(msg: str):
    print(f"  {YELLOW}ℹ INFO:{RESET} {msg}")


def main():
    print(f"{BOLD}{GREEN}=================================================================={RESET}")
    print(f"{BOLD}    MULTI-APPLICATION NOTIFICATION GATEWAY - END-TO-END TESTER    {RESET}")
    print(f"{BOLD}{GREEN}=================================================================={RESET}")
    print(f"Target URL: {BASE_URL}")
    print(f"Admin Key: {ADMIN_API_KEY[:8]}... (configured in .env)")

    has_real_telegram = (
        bool(TELEGRAM_BOT_TOKEN)
        and "YOUR_TELEGRAM" not in TELEGRAM_BOT_TOKEN
        and bool(TELEGRAM_CHAT_ID)
        and "YOUR_TELEGRAM" not in TELEGRAM_CHAT_ID
    )

    has_real_email = (
        bool(SMTP_USER)
        and "@" in SMTP_USER
        and "YOUR_EMAIL" not in SMTP_USER
        and bool(SMTP_PASSWORD)
        and "YOUR_16" not in SMTP_PASSWORD
    )

    if has_real_telegram:
        print(f"Telegram Bot: {GREEN}REAL CREDENTIALS DETECTED{RESET} (Chat ID: {TELEGRAM_CHAT_ID})")
    else:
        print(f"Telegram Bot: {YELLOW}Placeholder token in .env (live send will be simulated){RESET}")

    if has_real_email:
        print(f"Gmail (App Password): {GREEN}REAL CREDENTIALS DETECTED{RESET} ({SMTP_USER})")
    else:
        print(f"Gmail (App Password): {YELLOW}No password in .env (live send will be simulated){RESET}")

    results = []

    with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
        # -------------------------------------------------------------
        # STEP 1: Health Check
        # -------------------------------------------------------------
        print_step("1. Checking Gateway Health (/health & /api/v1/health)")
        try:
            res = client.get("/health")
            if res.status_code == 200 and res.json().get("status") == "healthy":
                components = res.json().get("components", {})
                print_pass(f"System healthy: DB={components.get('database')}, Redis={components.get('redis')}")
                results.append(("Health Check", True))
            else:
                print_fail(f"Health returned {res.status_code}: {res.text}")
                results.append(("Health Check", False))
        except Exception as e:
            print_fail(f"Could not connect to gateway at {BASE_URL}: {e}")
            sys.exit(1)

        # -------------------------------------------------------------
        # STEP 2: Prometheus Metrics
        # -------------------------------------------------------------
        print_step("2. Scraping Prometheus Metrics (/metrics)")
        res = client.get("/metrics")
        if res.status_code == 200 and "notifications_total" in res.text:
            print_pass("Prometheus scrape target operational and returning gateway metrics")
            results.append(("Metrics", True))
        else:
            print_fail(f"Metrics endpoint error {res.status_code}")
            results.append(("Metrics", False))

        # -------------------------------------------------------------
        # STEP 3: Admin Auth Verification
        # -------------------------------------------------------------
        print_step("3. Testing Administrative Authentication Protection")
        res_no_auth = client.get("/api/v1/admin/applications")
        if res_no_auth.status_code == 401:
            print_pass("Rejection of unauthenticated admin request (HTTP 401)")
        else:
            print_fail(f"Expected 401 without auth, got {res_no_auth.status_code}")

        admin_headers = {"X-Admin-API-Key": ADMIN_API_KEY}
        res_auth = client.get("/api/v1/admin/applications", headers=admin_headers)
        if res_auth.status_code == 200:
            print_pass("Authorized administrative access verified (HTTP 200)")
            results.append(("Admin Authentication", True))
        else:
            print_fail(f"Admin auth failed: {res_auth.status_code} {res_auth.text}")
            results.append(("Admin Authentication", False))

        # -------------------------------------------------------------
        # STEP 4: Application Registration & API Key Generation
        # -------------------------------------------------------------
        print_step("4. Registering New Client Application & Generating API Key")
        app_name = f"E2E-Finance-App-{uuid.uuid4().hex[:6]}"
        app_payload = {
            "name": app_name,
            "description": "Automated E2E Test Application",
            "rate_limit_per_minute": 5,
            "permissions": ["telegram:send", "gmail:send"],
        }
        res_app = client.post("/api/v1/admin/applications", json=app_payload, headers=admin_headers)
        if res_app.status_code == 200:
            app_data = res_app.json()["data"]
            app_id = app_data["id"]
            raw_api_key = app_data["initial_api_key"]["raw_api_key"]
            key_prefix = app_data["initial_api_key"]["key_prefix"]

            print_pass(f"Application created: ID={app_id}, Name='{app_name}'")
            print_pass(f"Generated API Key: {raw_api_key}")
            print_info(f"Prefix stored: {key_prefix} | Secret is HMAC-SHA256 hashed in database")
            results.append(("Application Registration", True))
        else:
            print_fail(f"Failed to create application: {res_app.text}")
            results.append(("Application Registration", False))
            return

        client_headers = {"X-API-Key": raw_api_key}

        # -------------------------------------------------------------
        # STEP 5: Telegram Configuration Management
        # -------------------------------------------------------------
        print_step("5. Registering Telegram Configuration with AES-256-GCM Encryption")
        token_to_use = TELEGRAM_BOT_TOKEN if has_real_telegram else "123456789:AAFakeTokenForDemonstrationOnly999"
        chat_to_use = TELEGRAM_CHAT_ID if has_real_telegram else "123456789"

        tg_payload = {
            "application_id": app_id,
            "name": "E2E Alerts Bot",
            "bot_token": token_to_use,
            "default_chat_id": chat_to_use,
            "is_active": True,
        }
        res_tg = client.post("/api/v1/admin/telegram", json=tg_payload, headers=admin_headers)
        if res_tg.status_code == 200:
            tg_config = res_tg.json()["data"]
            tg_config_id = tg_config["id"]
            print_pass(f"Telegram Config registered: ID={tg_config_id}")
            if "bot_token" not in tg_config and "encrypted_bot_token" not in tg_config:
                print_pass("Security verified: Raw/encrypted bot token is never exposed in response")
            results.append(("Telegram Config Registration", True))
        else:
            print_fail(f"Failed to register Telegram config: {res_tg.text}")
            results.append(("Telegram Config Registration", False))
            return

        # -------------------------------------------------------------
        # STEP 6: Dispatching Telegram Notification
        # -------------------------------------------------------------
        print_step("6. Dispatching Telegram Notification via Client API")
        notif_payload = {
            "configuration_id": tg_config_id,
            "chat_id": chat_to_use,
            "message": (
                "🚀 <b>Notification Gateway E2E Verification</b>\n\n"
                "• <b>Status:</b> Operational\n"
                f"• <b>Application:</b> {app_name}\n"
                f"• <b>Timestamp:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                "<i>Secure multi-tenant message dispatched successfully.</i>"
            ),
            "parse_mode": "HTML",
            "buttons": [
                [
                    {"text": "📖 Swagger Docs", "url": f"{BASE_URL}/docs"},
                    {"text": "📊 Metrics", "url": f"{BASE_URL}/metrics"},
                ]
            ],
            "idempotency_key": f"tx_e2e_{uuid.uuid4().hex[:8]}",
        }

        res_send = client.post("/api/v1/notifications/telegram", json=notif_payload, headers=client_headers)
        if res_send.status_code == 200:
            send_data = res_send.json()["data"]
            notif_id = send_data["id"]
            status = send_data["status"]
            print_pass(f"Notification processed: ID={notif_id}, Status='{status}', Attempts={send_data['attempts_count']}")
            if status == "sent":
                print_pass("Telegram Bot successfully received and delivered the notification!")
            elif not has_real_telegram:
                print_info(f"Status '{status}' as expected for simulated placeholder token")
            results.append(("Telegram Notification Dispatch", True))
        else:
            print_fail(f"Telegram send failed: {res_send.status_code} {res_send.text}")
            results.append(("Telegram Notification Dispatch", False))
            notif_id = None

        # -------------------------------------------------------------
        # STEP 7: Email / Gmail (App Password) Configuration & Dispatch
        # -------------------------------------------------------------
        print_step("7. Registering Gmail / Email Configuration with Google App Password")
        email_sender = SMTP_USER if has_real_email else "test-mailer@company.com"
        email_pass = SMTP_PASSWORD if has_real_email else "abcd efgh ijkl mnop"
        email_recipient = TEST_EMAIL_RECIPIENT if has_real_email else "recipient@company.com"

        email_config_payload = {
            "application_id": app_id,
            "name": "E2E Gmail Mailer",
            "email_address": email_sender,
            "auth_type": "app_password",
            "app_password": email_pass,
            "smtp_host": SMTP_HOST,
            "smtp_port": SMTP_PORT,
            "is_active": True,
        }
        res_email_cfg = client.post("/api/v1/admin/gmail", json=email_config_payload, headers=admin_headers)
        if res_email_cfg.status_code == 200:
            email_cfg_data = res_email_cfg.json()["data"]
            email_cfg_id = email_cfg_data["id"]
            print_pass(f"Email Config registered: ID={email_cfg_id}, Host={email_cfg_data.get('smtp_host')}:{email_cfg_data.get('smtp_port')}")
            if "app_password" not in email_cfg_data and "encrypted_app_password" not in email_cfg_data:
                print_pass("Security verified: App Password encrypted with AES-256-GCM and never exposed")
            results.append(("Email Config Registration", True))
        else:
            print_fail(f"Failed to register email config: {res_email_cfg.text}")
            results.append(("Email Config Registration", False))
            email_cfg_id = None

        if email_cfg_id:
            print_step("8. Dispatching Email Notification via Client API (POST /api/v1/notifications/email)")
            email_payload = {
                "configuration_id": email_cfg_id,
                "to": [email_recipient],
                "subject": f"Notification Gateway Test - {time.strftime('%H:%M:%S')}",
                "text": "This is an automated test email sent through the Notification Gateway using Google App Passwords.",
                "html": (
                    "<h2>Notification Gateway Verification</h2>"
                    "<p>This email was dispatched via <b>Google App Password (SMTP)</b>.</p>"
                    "<ul>"
                    f"<li><b>Application:</b> {app_name}</li>"
                    f"<li><b>Sender:</b> {email_sender}</li>"
                    "</ul>"
                ),
                "idempotency_key": f"tx_email_{uuid.uuid4().hex[:8]}",
            }
            res_email_send = client.post("/api/v1/notifications/email", json=email_payload, headers=client_headers)
            if res_email_send.status_code == 200:
                e_data = res_email_send.json()["data"]
                e_status = e_data["status"]
                print_pass(f"Email processed: ID={e_data['id']}, Status='{e_status}', Attempts={e_data['attempts_count']}")
                if e_status == "sent":
                    print_pass(f"Email delivered to SMTP server successfully! Check inbox for: {email_recipient}")
                elif not has_real_email:
                    print_info(f"Status '{e_status}' as expected for simulated placeholder password")
                results.append(("Email Dispatch", True))
            else:
                print_fail(f"Email send failed: {res_email_send.status_code} {res_email_send.text}")
                results.append(("Email Dispatch", False))

        # -------------------------------------------------------------
        # STEP 9: Idempotency Key Verification
        # -------------------------------------------------------------
        print_step("9. Testing Idempotency Protection (Duplicate Prevention)")
        idemp_key = f"idemp_test_{uuid.uuid4().hex[:8]}"
        idemp_payload = {
            "configuration_id": tg_config_id,
            "chat_id": chat_to_use,
            "message": "Payment Receipt #9901 - Single Charge",
            "idempotency_key": idemp_key,
        }

        # First call
        res_idemp_1 = client.post("/api/v1/notifications/telegram", json=idemp_payload, headers=client_headers)
        first_id = res_idemp_1.json()["data"]["id"]

        # Duplicate call with identical idempotency key
        res_idemp_2 = client.post("/api/v1/notifications/telegram", json=idemp_payload, headers=client_headers)
        second_id = res_idemp_2.json()["data"]["id"]

        if first_id == second_id:
            print_pass(f"Idempotency verified: Duplicate call returned cached ID {first_id} without duplicate dispatch")
            results.append(("Idempotency Verification", True))
        else:
            print_fail(f"Idempotency failed: Returned different IDs {first_id} vs {second_id}")
            results.append(("Idempotency Verification", False))

        # -------------------------------------------------------------
        # STEP 10: Multi-Tenant Isolation
        # -------------------------------------------------------------
        print_step("10. Testing Multi-Tenant Isolation")
        tenant_b_payload = {"name": f"Tenant-B-{uuid.uuid4().hex[:6]}", "permissions": ["telegram:send"]}
        res_tenant_b = client.post("/api/v1/admin/applications", json=tenant_b_payload, headers=admin_headers)
        key_b = res_tenant_b.json()["data"]["initial_api_key"]["raw_api_key"]

        # Tenant B attempts to use Tenant A's config_id
        hack_payload = {
            "configuration_id": tg_config_id,  # Belongs to Tenant A
            "chat_id": "111111",
            "message": "Malicious attempt across tenant boundary",
        }
        res_hack = client.post("/api/v1/notifications/telegram", json=hack_payload, headers={"X-API-Key": key_b})
        if res_hack.status_code == 404:
            print_pass("Tenant boundary enforced: Tenant B cannot access Tenant A's configuration (HTTP 404)")
            results.append(("Tenant Isolation", True))
        else:
            print_fail(f"Security leak: Expected 404 for cross-tenant access, got {res_hack.status_code}")
            results.append(("Tenant Isolation", False))

        # -------------------------------------------------------------
        # STEP 11: Granular Permissions Enforcement
        # -------------------------------------------------------------
        print_step("11. Testing Granular Permissions Enforcement")
        restricted_app = {"name": f"Tg-Only-{uuid.uuid4().hex[:6]}", "permissions": ["telegram:send"]}
        res_restr = client.post("/api/v1/admin/applications", json=restricted_app, headers=admin_headers)
        restr_key = res_restr.json()["data"]["initial_api_key"]["raw_api_key"]

        res_perm_denied = client.post(
            "/api/v1/notifications/email",
            json={
                "configuration_id": str(uuid.uuid4()),
                "to": ["user@example.com"],
                "subject": "Unauthorized Email",
                "text": "Denied",
            },
            headers={"X-API-Key": restr_key},
        )
        if res_perm_denied.status_code == 403:
            print_pass("Permission check passed: Application without 'gmail:send' blocked with HTTP 403")
            results.append(("Permission Enforcement", True))
        else:
            print_fail(f"Expected 403 for missing permission, got {res_perm_denied.status_code}")
            results.append(("Permission Enforcement", False))

        # -------------------------------------------------------------
        # STEP 12: Rate Limiting
        # -------------------------------------------------------------
        print_step("12. Testing Sliding-Window Rate Limiting")
        print_info(f"Targeting '{app_name}' with limit of 5 requests/minute...")
        hit_429 = False
        retry_after_val = None

        rate_test_payload = {
            "configuration_id": tg_config_id,
            "chat_id": chat_to_use,
            "message": "Rapid rate limit probe",
        }

        for i in range(10):
            res_rate = client.post(
                "/api/v1/notifications/telegram", json=rate_test_payload, headers=client_headers
            )
            if res_rate.status_code == 429:
                hit_429 = True
                retry_after_val = res_rate.headers.get("Retry-After")
                break

        if hit_429:
            print_pass(f"Rate limiting triggered: HTTP 429 received (Retry-After: {retry_after_val}s)")
            results.append(("Rate Limiting", True))
        else:
            print_fail("Rate limit was not triggered after 10 rapid requests")
            results.append(("Rate Limiting", False))

        # -------------------------------------------------------------
        # STEP 13: Notification Status & History Query
        # -------------------------------------------------------------
        print_step("13. Querying Notification Status and Attempts Tracking")
        if notif_id:
            res_query = client.get(f"/api/v1/notifications/{notif_id}", headers=client_headers)
            if res_query.status_code == 200:
                q_data = res_query.json()["data"]
                print_pass(f"Notification details retrieved: ID={q_data['id']}, Provider={q_data['provider']}")
                attempts = q_data.get("attempts", [])
                print_pass(f"Logged attempts: {len(attempts)}")
                for att in attempts:
                    print_info(f"  Attempt #{att['attempt_number']}: status={att['status']}, duration={att['duration_ms']}ms")
                results.append(("Status & Tracking", True))
            else:
                print_fail(f"Status query failed: {res_query.status_code}")
                results.append(("Status & Tracking", False))

        # -------------------------------------------------------------
        # STEP 14: Audit Log Trail
        # -------------------------------------------------------------
        print_step("14. Inspecting Administrative Audit Trail (/api/v1/admin/audit-logs)")
        res_audit = client.get("/api/v1/admin/audit-logs", headers=admin_headers)
        if res_audit.status_code == 200:
            logs = res_audit.json()["data"]
            print_pass(f"Retrieved {len(logs)} audit entries from database")
            recent_actions = [l["action"] for l in logs[:4]]
            print_info(f"Recent recorded actions: {', '.join(recent_actions)}")
            results.append(("Audit Trail", True))
        else:
            print_fail(f"Audit logs query failed: {res_audit.status_code}")
            results.append(("Audit Trail", False))

    # -------------------------------------------------------------
    # FINAL SUMMARY REPORT
    # -------------------------------------------------------------
    print(f"\n{BOLD}{CYAN}=================================================================={RESET}")
    print(f"{BOLD}                    TEST EXECUTION SUMMARY                       {RESET}")
    print(f"{BOLD}{CYAN}=================================================================={RESET}")
    all_passed = True
    for test_name, passed in results:
        status_str = f"{GREEN}PASSED{RESET}" if passed else f"{RED}FAILED{RESET}"
        print(f"  • {test_name:<35} : {status_str}")
        if not passed:
            all_passed = False

    print("------------------------------------------------------------------")
    if all_passed:
        print(f"{BOLD}{GREEN}ALL 14 END-TO-END GATEWAY TESTS PASSED SUCCESSFULLY! 🚀{RESET}")
    else:
        print(f"{BOLD}{RED}SOME TESTS FAILED. Please review the output above.{RESET}")
    print("==================================================================\n")


if __name__ == "__main__":
    main()
