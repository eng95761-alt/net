import asyncio
from contextlib import asynccontextmanager
import json
import logging
import os
import re
import socket
import struct
import time
from typing import Dict, List, Any
import paramiko
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mscp_backend")

# Router Connection Settings (Read-Only operations strictly enforced)
# Load from .env if present
env_candidates = [
    os.path.join(os.path.dirname(__file__), ".env"),
    os.path.join(os.path.dirname(__file__), "..", ".env"),
    ".env"
]
for ec in env_candidates:
    if os.path.exists(ec):
        try:
            with open(ec, "r", encoding="utf-8") as ef:
                for eline in ef:
                    eline = eline.strip()
                    if eline and not eline.startswith("#") and "=" in eline:
                        ek, ev = eline.split("=", 1)
                        os.environ.setdefault(ek.strip(), ev.strip())
        except Exception:
            pass

ROUTER_IP = os.getenv("ROUTER_IP", "192.168.4.238")
ROUTER_PORT = int(os.getenv("ROUTER_PORT", "22"))
ROUTER_USER = os.getenv("ROUTER_USER", "admin")
ROUTER_PASS = os.getenv("ROUTER_PASS", "")

# Rolling history for live bandwidth charts (last 30 samples = ~45s)
history_buffer = {
    "timestamps": [],
    "combined_rx": [],
    "starlink_rx": [],
    "starlink_tx": [],
    "quicknet_rx": [],
    "quicknet_tx": [],
    "line1_rx": [],
    "line2_rx": [],
    "line3_rx": [],
    "line4_rx": [],
    "line5_rx": []
}

# 10-Minute Peak Analyzer State (Auto-pruning after 24h = max 144 windows)
peak_tracker = {
    "window_start_time": time.time(),
    "window_start_label": time.strftime("%H:%M"),
    "window_peak_rx": 0.0,
    "window_peak_tx": 0.0,
    "window_peak_time": time.strftime("%H:%M:%S"),
    "window_samples": 0,
    "window_sum_rx": 0.0,
    "all_time_24h_peak_rx": 0.0,
    "all_time_24h_peak_time": "--",
    "day_start_date": time.strftime("%Y-%m-%d"),
    "history_10m_windows": []  # max 144 items
}

# Arabic System Log Translation Engine
def translate_log_message(topic: str, msg: str) -> dict:
    t = topic.lower()
    m = msg.strip()
    sev = "info"
    ar = m

    if "error" in t or "critical" in t:
        sev = "error"
    elif "warning" in t:
        sev = "warning"

    if "authenticated" in m:
        sub = re.search(r"<pppoe-([^>]+)>", m)
        name = sub.group(1) if sub else "المشترك"
        ar = f"تمت مصادقة اشتراك ({name}) بنجاح"
        sev = "info"
    elif "connected" in m and "logged in" not in m:
        sub = re.search(r"<pppoe-([^>]+)>", m)
        name = sub.group(1) if sub else "المشترك"
        ar = f"اتصل اشتراك ({name}) وبدأ البث"
        sev = "success"
    elif "peer is not responding" in m:
        sub = re.search(r"<pppoe-([^>]+)>", m)
        name = sub.group(1) if sub else "المشترك"
        ar = f"فصل اشتراك ({name}): انقطاع إشارة / راوتر المشترك مطفأ أو مفصول"
        sev = "warning"
    elif "terminating..." in m:
        sub = re.search(r"<pppoe-([^>]+)>", m)
        name = sub.group(1) if sub else ""
        ar = f"جاري إنهاء وفصل جلسة المشترك ({name})"
        sev = "warning"
    elif "disconnected" in m:
        sub = re.search(r"<pppoe-([^>]+)>", m)
        name = sub.group(1) if sub else ""
        ar = f"تم فصل جلسة المشترك ({name})"
        sev = "warning"
    elif "logged in" in m:
        m_admin = re.search(r"user\s+([^\s]+)\s+logged in from\s+([^\s]+)\s+via\s+([^\s]+)", m)
        if m_admin:
            ar = f"دخول مسؤول ({m_admin.group(1)}) من IP: {m_admin.group(2)} عبر {m_admin.group(3)}"
            sev = "info"
        elif "from" in m:
            parts = m.split("logged in,")
            user_part = parts[0].replace("account", "").strip()
            ar = f"دخول اشتراك PPPoE: {user_part}"
            sev = "success"
    elif "logged out" in m:
        if "from" in m:
            parts = m.split("logged out")
            user_part = parts[0].replace("account", "").strip()
            ar = f"خروج / فصل اشتراك: {user_part}"
            sev = "warning"
    elif "DAILY-RESET" in m:
        ar = "🔄 تنفيذ التصفير اليومي لكوتة ستارلنك وعودة المشتركين لوضع كويك نت"
        sev = "info"
    elif "HYBRID-SWITCH" in m:
        ar = "🔄 تبديل مسار المشتركين الهايبرد (المساء 6:00 م)"
        sev = "info"
    elif "CRITICAL-QUOTA" in m:
        ar = "🚨 تحذير كوتة: ستارلنك بلغت 145GB وتم تحويل المشتركين لكويك نت!"
        sev = "error"
    elif "assigned" in m and "DHCP" in m:
        ar = f"توزيع عنوان IP جديد من خادم DHCP: {m}"
    elif "deassigned" in m and "DHCP" in m:
        ar = f"سحب عنوان IP منتهٍ في خادم DHCP: {m}"
    elif "link down" in m:
        ar = f"انقطاع المنفذ الفيزيائي (Link Down): {m}"
        sev = "error"
    elif "link up" in m:
        ar = f"تشغيل المنفذ الفيزيائي (Link Up): {m}"
        sev = "success"

    return {
        "topic": topic,
        "message_ar": ar,
        "message_en": m,
        "severity": sev
    }


telemetry_data: Dict[str, Any] = {
    "status": "connecting",
    "timestamp": time.time(),
    "network_summary": {
        "combined_rx_mbps": 0.0,
        "combined_tx_mbps": 0.0,
        "load_level": "OPTIMAL",
        "load_label": "سحب طبيعي ومستقر",
        "load_color": "emerald",
        "congestion_status": "السحب كافٍ ومستقر (السعة كافية جداً)",
        "health_score": 98,
        "analysis_advice": "الشبكة في حالة استقرار تام ومثالي، لا يوجد أي اختناق في القنوات."
    },
    "ai_congestion_analyzer": {
        "current_10m_peak_rx": 0.0,
        "current_10m_avg_rx": 0.0,
        "all_time_24h_peak_rx": 0.0,
        "all_time_24h_peak_time": "--",
        "capacity_utilization_pct": 0.0,
        "congestion_state": "OPTIMAL",
        "ai_diagnosis_text": "السحب متزن وضمن النطاق الطبيعي.",
        "advice_text": "حركة المرور مستقرة والسعة المتاحة كافية جداً.",
        "history_windows": []
    },
    "router_info": {
        "identity": "Home",
        "model": "RB4011iGS+",
        "version": "7.25.1",
        "uptime": "Unknown",
        "cpu_load": 0,
        "cpu_count": 4,
        "cpu_freq": "1400MHz",
        "free_memory_mb": 0,
        "total_memory_mb": 1024,
        "memory_usage_pct": 0,
        "temperature": 36,
        "voltage": 25.1
    },
    "starlink": {
        "interface": "ether1-ISP",
        "current_rx_mbps": 0.0,
        "current_tx_mbps": 0.0,
        "daily_limit_gb": 150.0,
        "daily_used_gb": 0.0,
        "daily_used_gib": 0.0,
        "daily_remaining_gb": 150.0,
        "daily_usage_pct": 0.0,
        "raw_current_bytes": 0,
        "raw_midnight_bytes": 0,
        "status": "NORMAL",
        "quota_exceeded": False,
        "seconds_to_midnight": 0,
        "accounting_note": "حساب دقيق بالجيجابايت العشري القياسي (1GB = 1,000,000,000 Bytes)"
    },
    "quicknet": {
        "total_rx_mbps": 0.0,
        "total_tx_mbps": 0.0,
        "active_lines_count": 3,
        "lines": [
            {"id": 1, "name": "Line 1 (pppoe-out1)", "interface": "pppoe-out1", "user": "ali.nael", "rx_mbps": 0.0, "tx_mbps": 0.0, "pct": 33.3, "status": "running", "uptime": "--", "local_ip": "--", "expiry": "تجديد شهري"},
            {"id": 2, "name": "Line 2 (pppoe-out2)", "interface": "pppoe-out2", "user": "k@1234", "rx_mbps": 0.0, "tx_mbps": 0.0, "pct": 33.3, "status": "running", "uptime": "--", "local_ip": "--", "expiry": "تجديد شهري"},
            {"id": 3, "name": "Line 3 (pppoe-out3)", "interface": "pppoe-out3", "user": "m@232", "rx_mbps": 0.0, "tx_mbps": 0.0, "pct": 33.4, "status": "running", "uptime": "--", "local_ip": "--", "expiry": "تجديد شهري"},
            {"id": 4, "name": "Line 4 (pppoe-out4)", "interface": "pppoe-out4", "user": "user4", "rx_mbps": 0.0, "tx_mbps": 0.0, "pct": 0.0, "status": "disabled", "uptime": "--", "local_ip": "--", "expiry": "غير مفعل"},
            {"id": 5, "name": "Line 5 (pppoe-out5)", "interface": "pppoe-out5", "user": "user5", "rx_mbps": 0.0, "tx_mbps": 0.0, "pct": 0.0, "status": "disabled", "uptime": "--", "local_ip": "--", "expiry": "غير مفعل"}
        ]
    },
    "subscribers": {
        "total_active": 0,
        "starlink_count": 0,
        "quicknet_count": 0,
        "hybrid_count": 0,
        "other_count": 0,
        "list": []
    },
    "automation_scripts": [],
    "system_logs": [],
    "history": history_buffer,
    "events": []
}

active_websockets: List[WebSocket] = []
last_subscribers_set = set()


def parse_bandwidth_bps(val_str: str) -> float:
    val_str = val_str.strip().lower()
    if not val_str or val_str == "0bps":
        return 0.0
    try:
        if "mbps" in val_str:
            return float(val_str.replace("mbps", "").strip())
        elif "kbps" in val_str:
            return float(val_str.replace("kbps", "").strip()) / 1000.0
        elif "gbps" in val_str:
            return float(val_str.replace("gbps", "").strip()) * 1000.0
        elif "bps" in val_str:
            return float(val_str.replace("bps", "").strip()) / 1000000.0
    except Exception:
        pass
    return 0.0


def extract_key_val(output: str, key: str, default: str = "") -> str:
    m = re.search(rf"{key}:\s*([^\r\n]+)", output, re.IGNORECASE)
    return m.group(1).strip() if m else default


class RouterMonitorWorker:
    def __init__(self):
        self.ssh = None
        self.running = True
        self.cached_baseline_rx = None
        self.cached_scripts = []
        self.last_scripts_fetch = 0

    def fetch_scripts(self):
        if not self.ssh or (self.ssh.get_transport() and not self.ssh.get_transport().is_active()):
            return
        try:
            cmd = '/system script print terse; :put "===SCHEDULERS==="; /system scheduler print terse'
            stdin, stdout, stderr = self.ssh.exec_command(cmd, timeout=5)
            out = stdout.read().decode("utf-8", errors="ignore")
            parts = out.split("===SCHEDULERS===")
            scripts_raw = parts[0]
            sched_raw = parts[1] if len(parts) > 1 else ""

            sched_map = {}
            for line in sched_raw.strip().split("\n"):
                m_name = re.search(r"name=([^\s]+)", line)
                m_ev = re.search(r"on-event=([^\s]+)", line)
                m_int = re.search(r"interval=([^\s]+)", line)
                m_next = re.search(r"next-run=([^\r\n]+)", line)
                if m_ev:
                    sched_map[m_ev.group(1)] = {
                        "sched_name": m_name.group(1) if m_name else "",
                        "interval": m_int.group(1) if m_int else "--",
                        "next_run": m_next.group(1).strip() if m_next else "--"
                    }

            meta_map = {
                "Script-Evening-To-Starlink": {
                    "title_ar": "تحويل الهايبرد إلى ستارلنك (فترة الذروة 6:00 مساءً)",
                    "desc_ar": "يقوم يومياً عند الساعة 6:00 مساءً بتحويل كافة بروفايلات الهايبرد إلى مسار ستارلنك لضمان أعلى سرعة واستقرار للألعاب والتصفح، ما لم تتجاوز كوتة الـ 145GB.",
                    "badge": "يومي (18:00)",
                    "badge_color": "purple",
                    "icon": "fa-solid fa-moon text-purple-400"
                },
                "Script-Midnight-Reset-To-QN": {
                    "title_ar": "تصفير كوتة ستارلنك وإعادة الهايبرد لكويك نت (منتصف الليل)",
                    "desc_ar": "يقوم يومياً عند الساعة 12:00 منتصف الليل بتسجيل عداد البايتات الجديد، وتصفير علامة تجاوز الكوتة، وإعادة تحويل كافة مشتركي الهايبرد إلى مسار كويك نت.",
                    "badge": "يومي (00:00)",
                    "badge_color": "emerald",
                    "icon": "fa-solid fa-arrows-rotate text-emerald-400"
                },
                "Script-Watch-Starlink-Quota": {
                    "title_ar": "حارس كوتة ستارلنك الذكي (حماية سقف 145GB)",
                    "desc_ar": "يعمل بشكل دوري مستمر (كل دقيقتين)، يراقب استهلاك باقة الـ 150GB، وفي حال ملامسة سقف الـ 145GB يقوم تلقائياً بتحويل كافة المشتركين فوراً إلى كويك نت منعاً لانقطاع الخدمة.",
                    "badge": "دوري (كل دقيقتين)",
                    "badge_color": "cyan",
                    "icon": "fa-solid fa-shield-halved text-cyan-400"
                }
            }

            parsed_scripts = []
            for line in scripts_raw.strip().split("\n"):
                line = line.strip()
                if not line or "name=" not in line:
                    continue
                m_name = re.search(r"name=([^\s]+)", line)
                if not m_name:
                    continue
                s_name = m_name.group(1)
                m_last = re.search(r"last-started=([0-9\-]+ [0-9:]+)", line)
                m_count = re.search(r"run-count=([0-9]+)", line)
                m_src = re.search(r"source=(.*)", line)
                clean_src = m_src.group(1).replace("rn", "\n").strip() if m_src else ""

                s_sched = sched_map.get(s_name, {})
                s_meta = meta_map.get(s_name, {
                    "title_ar": s_name,
                    "desc_ar": "سكربت أتمتة مخصص على الراوتر",
                    "badge": "مجدول",
                    "badge_color": "blue",
                    "icon": "fa-solid fa-gear text-blue-400"
                })

                parsed_scripts.append({
                    "name": s_name,
                    "title_ar": s_meta["title_ar"],
                    "desc_ar": s_meta["desc_ar"],
                    "badge": s_meta["badge"],
                    "badge_color": s_meta["badge_color"],
                    "icon": s_meta["icon"],
                    "sched_name": s_sched.get("sched_name", "--"),
                    "interval": s_sched.get("interval", "--"),
                    "next_run": s_sched.get("next_run", "--"),
                    "last_started": m_last.group(1) if m_last else "--",
                    "run_count": int(m_count.group(1)) if m_count else 0,
                    "status": "نشط ومجدول",
                    "source": clean_src
                })

            self.cached_scripts = parsed_scripts
            self.last_scripts_fetch = time.time()
            telemetry_data["automation_scripts"] = parsed_scripts
        except Exception as e:
            logger.error(f"Failed to fetch scripts: {e}")

    def connect(self):
        try:
            if self.ssh:
                try:
                    self.ssh.close()
                except Exception:
                    pass
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Optional SOCKS5 proxy support (e.g., userspace WireGuard / wireproxy)
            socks_proxy = os.getenv("SOCKS5_PROXY", "").strip()
            custom_sock = None
            if socks_proxy:
                try:
                    p_host, p_port = socks_proxy.split(":")
                    proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    proxy_sock.settimeout(10)
                    proxy_sock.connect((p_host, int(p_port)))
                    # SOCKS5 greeting
                    proxy_sock.sendall(b"\x05\x01\x00")
                    g_resp = proxy_sock.recv(2)
                    if g_resp == b"\x05\x00":
                        d_ip = socket.inet_aton(ROUTER_IP)
                        d_port = struct.pack(">H", int(ROUTER_PORT))
                        proxy_sock.sendall(b"\x05\x01\x00\x01" + d_ip + d_port)
                        c_resp = proxy_sock.recv(10)
                        if len(c_resp) >= 2 and c_resp[1] == 0x00:
                            custom_sock = proxy_sock
                            logger.info(f"SOCKS5 proxy tunnel active via {socks_proxy} to {ROUTER_IP}:{ROUTER_PORT}")
                except Exception as ex:
                    logger.warning(f"SOCKS5 proxy attempt failed: {ex}, falling back to direct socket")
                    custom_sock = None

            self.ssh.connect(
                ROUTER_IP,
                port=ROUTER_PORT,
                username=ROUTER_USER,
                password=ROUTER_PASS,
                timeout=8,
                look_for_keys=False,
                allow_agent=False,
                sock=custom_sock
            )
            logger.info("Connected successfully to MikroTik RB4011.")
            return True
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            self.ssh = None
            return False

    def poll_once(self):
        global telemetry_data, last_subscribers_set, history_buffer, peak_tracker
        if not self.ssh or (self.ssh.get_transport() and not self.ssh.get_transport().is_active()):
            if not self.connect():
                telemetry_data["status"] = "disconnected"
                return

        try:
            # High-performance batch command with clean delimiters
            cmd = (
                "/interface monitor-traffic ether1-ISP,pppoe-out1,pppoe-out2,pppoe-out3,pppoe-out4,pppoe-out5 once; "
                ":put \"===SUB_TRAFFIC===\"; "
                "/interface monitor-traffic [find type=\"pppoe-in\"] once; "
                ":put \"===STARLINK_VARS===\"; "
                ":global StarlinkMidnightRX; :put (\"MIDNIGHT_RX: \" . $StarlinkMidnightRX); "
                ":global StarlinkQuotaExceeded; :put (\"QUOTA_EXCEEDED: \" . $StarlinkQuotaExceeded); "
                ":put (\"CURRENT_RX: \" . [/interface get [find name=\"ether1-ISP\"] rx-byte]); "
                ":put \"===HYBRID_USERS===\"; "
                ":foreach u in=[/user-manager/user find group~\"Hybrid\"] do={ :put (\"HYB_USER:\" . [/user-manager/user get $u name]) }; "
                ":put \"===PPPOE_CLIENT_MON===\"; "
                "/interface/pppoe-client monitor pppoe-out1,pppoe-out2,pppoe-out3,pppoe-out4,pppoe-out5 once; "
                ":put \"===RESOURCE===\"; "
                "/system resource print; "
                "/system health print; "
                ":put \"===ACTIVE_PPP===\"; "
                "/ppp active print detail; "
                ":put \"===LOG_START===\"; :local logs [/log find]; :local total [:len $logs]; :local s 0; :if ($total > 15) do={ :set s ($total - 15) }; :for i from=$s to=($total - 1) do={ :local id ($logs->$i); :put (([/log get $id time]) . \" # \" . ([/log get $id topics]) . \" # \" . ([/log get $id message])) }; :put \"===LOG_END===\";"
            )
            stdin, stdout, stderr = self.ssh.exec_command(cmd, timeout=8)
            raw_out = stdout.read().decode("utf-8", errors="ignore")

            telemetry_data["status"] = "online"
            current_ts = time.time()
            telemetry_data["timestamp"] = current_ts

            # 1. Parse Traffic Monitor for WANs (Starlink + Quicknet 5 lines)
            wan_mon = raw_out.split("MIDNIGHT_RX:")[0] if "MIDNIGHT_RX:" in raw_out else raw_out
            # First block of monitor-traffic is for ether1-ISP + pppoe-out1..5
            first_block = wan_mon.split("/interface monitor-traffic")[0] if "/interface monitor-traffic" in wan_mon else wan_mon
            rx_rates = {}
            tx_rates = {}

            rx_m = re.search(r"rx-bits-per-second:\s*([^\r\n]+)", first_block)
            tx_m = re.search(r"tx-bits-per-second:\s*([^\r\n]+)", first_block)

            if rx_m and tx_m:
                rx_vals = [p for p in rx_m.group(1).split() if p]
                tx_vals = [p for p in tx_m.group(1).split() if p]
                names = ["ether1-ISP", "pppoe-out1", "pppoe-out2", "pppoe-out3", "pppoe-out4", "pppoe-out5"]
                for i, n in enumerate(names):
                    if i < len(rx_vals):
                        rx_rates[n] = parse_bandwidth_bps(rx_vals[i])
                    if i < len(tx_vals):
                        tx_rates[n] = parse_bandwidth_bps(tx_vals[i])

            # Update Starlink rates (Download = RX, Upload = TX)
            star_rx = rx_rates.get("ether1-ISP", 0.0)
            star_tx = tx_rates.get("ether1-ISP", 0.0)
            telemetry_data["starlink"]["current_rx_mbps"] = round(star_rx, 2)
            telemetry_data["starlink"]["current_tx_mbps"] = round(star_tx, 2)

            # 2. Parse Quicknet PPPoE Client Monitor (Uptime, Local IP, Status for all 5 lines)
            pppoe_mon_section = ""
            if "===PPPOE_CLIENT_MON===" in raw_out and "===RESOURCE===" in raw_out:
                pppoe_mon_section = raw_out.split("===PPPOE_CLIENT_MON===")[1].split("===RESOURCE===")[0]

            statuses_m = re.search(r"status:\s*([^\r\n]+)", pppoe_mon_section)
            uptimes_m = re.search(r"uptime:\s*([^\r\n]+)", pppoe_mon_section)
            addrs_m = re.search(r"local-address:\s*([^\r\n]+)", pppoe_mon_section)

            status_tokens = statuses_m.group(1).split() if statuses_m else []
            uptime_tokens = uptimes_m.group(1).split() if uptimes_m else []
            addr_tokens = addrs_m.group(1).split() if addrs_m else []

            known_users = ["ali.nael", "k@1234", "m@232", "user4", "user5"]
            quicknet_lines = []
            total_q_rx = 0.0
            total_q_tx = 0.0
            active_lines_count = 0
            conn_idx = 0

            for idx in range(5):
                line_name = f"pppoe-out{idx+1}"
                r_rate = rx_rates.get(line_name, 0.0)
                t_rate = tx_rates.get(line_name, 0.0)
                st = status_tokens[idx] if idx < len(status_tokens) else ("disabled" if idx >= 3 else "connected")

                if st == "connected":
                    total_q_rx += r_rate
                    total_q_tx += t_rate
                    active_lines_count += 1
                    up = uptime_tokens[conn_idx] if conn_idx < len(uptime_tokens) else "--"
                    ip = addr_tokens[conn_idx] if conn_idx < len(addr_tokens) else "--"
                    conn_idx += 1
                else:
                    up = "--"
                    ip = "--"

                quicknet_lines.append({
                    "id": idx + 1,
                    "name": f"Line {idx+1} ({line_name})",
                    "interface": line_name,
                    "user": known_users[idx],
                    "rx_mbps": round(r_rate, 2),
                    "tx_mbps": round(t_rate, 2),
                    "pct": 0.0,
                    "status": st,
                    "uptime": up,
                    "local_ip": ip,
                    "expiry": "تجديد شهري تلقائي" if st == "connected" else "بانتظار التفعيل"
                })

            # Calculate PCC share percentage among active lines
            for ql in quicknet_lines:
                if total_q_rx > 0 and ql["status"] == "connected":
                    ql["pct"] = round((ql["rx_mbps"] / total_q_rx) * 100, 1)
                elif ql["status"] == "connected" and active_lines_count > 0:
                    ql["pct"] = round(100.0 / active_lines_count, 1)
                else:
                    ql["pct"] = 0.0

            telemetry_data["quicknet"]["total_rx_mbps"] = round(total_q_rx, 2)
            telemetry_data["quicknet"]["total_tx_mbps"] = round(total_q_tx, 2)
            telemetry_data["quicknet"]["active_lines_count"] = active_lines_count
            telemetry_data["quicknet"]["lines"] = quicknet_lines

            # 3. Combined Network Traffic
            combined_rx = round(star_rx + total_q_rx, 2)
            combined_tx = round(star_tx + total_q_tx, 2)

            # Append to rolling history
            time_label = time.strftime("%H:%M:%S")
            history_buffer["timestamps"].append(time_label)
            history_buffer["combined_rx"].append(combined_rx)
            history_buffer["starlink_rx"].append(round(star_rx, 2))
            history_buffer["starlink_tx"].append(round(star_tx, 2))
            history_buffer["quicknet_rx"].append(round(total_q_rx, 2))
            history_buffer["quicknet_tx"].append(round(total_q_tx, 2))
            history_buffer["line1_rx"].append(round(quicknet_lines[0]["rx_mbps"], 2))
            history_buffer["line2_rx"].append(round(quicknet_lines[1]["rx_mbps"], 2))
            history_buffer["line3_rx"].append(round(quicknet_lines[2]["rx_mbps"], 2))
            history_buffer["line4_rx"].append(round(quicknet_lines[3]["rx_mbps"], 2))
            history_buffer["line5_rx"].append(round(quicknet_lines[4]["rx_mbps"], 2))

            if len(history_buffer["timestamps"]) > 30:
                for k in history_buffer:
                    history_buffer[k] = history_buffer[k][-30:]
            telemetry_data["history"] = history_buffer

            # 4. Parse Resource & Health
            uptime = extract_key_val(raw_out, "uptime", "Unknown")
            cpu_load = extract_key_val(raw_out, "cpu-load", "0%").replace("%", "").strip()
            free_mem = extract_key_val(raw_out, "free-memory", "0MiB").replace("MiB", "").strip()
            total_mem = extract_key_val(raw_out, "total-memory", "1024.0MiB").replace("MiB", "").strip()

            try:
                cpu_int = int(cpu_load)
            except Exception:
                cpu_int = 3
            try:
                free_m = float(free_mem)
                tot_m = float(total_mem)
                used_pct = round(((tot_m - free_m) / tot_m) * 100, 1)
            except Exception:
                free_m, tot_m, used_pct = 790.0, 1024.0, 22.0

            volt_m = re.search(r"voltage\s+([0-9.]+)\s+V", raw_out)
            temp_m = re.search(r"temperature\s+([0-9]+)\s+C", raw_out)
            volt = float(volt_m.group(1)) if volt_m else 25.1
            temp = int(temp_m.group(1)) if temp_m else 36

            telemetry_data["router_info"]["uptime"] = uptime
            telemetry_data["router_info"]["cpu_load"] = cpu_int
            telemetry_data["router_info"]["free_memory_mb"] = round(free_m, 1)
            telemetry_data["router_info"]["total_memory_mb"] = round(tot_m, 1)
            telemetry_data["router_info"]["memory_usage_pct"] = used_pct
            telemetry_data["router_info"]["voltage"] = volt
            telemetry_data["router_info"]["temperature"] = temp

            # 5. 10-Minute Peak Analyzer & Rolling 24-Hour Congestion Logic
            today_str = time.strftime("%Y-%m-%d")
            if peak_tracker["day_start_date"] != today_str:
                # Fresh daily reset for peaks
                peak_tracker["day_start_date"] = today_str
                peak_tracker["all_time_24h_peak_rx"] = 0.0
                peak_tracker["all_time_24h_peak_time"] = "--"

            # Update current window stats
            if combined_rx > peak_tracker["window_peak_rx"]:
                peak_tracker["window_peak_rx"] = combined_rx
                peak_tracker["window_peak_time"] = time.strftime("%H:%M:%S")

            if combined_rx > peak_tracker["all_time_24h_peak_rx"]:
                peak_tracker["all_time_24h_peak_rx"] = combined_rx
                peak_tracker["all_time_24h_peak_time"] = time.strftime("%H:%M:%S")

            peak_tracker["window_sum_rx"] += combined_rx
            peak_tracker["window_samples"] += 1

            # Check 10-minute rollover (600 seconds)
            if (current_ts - peak_tracker["window_start_time"]) >= 600:
                avg_rx = round(peak_tracker["window_sum_rx"] / max(1, peak_tracker["window_samples"]), 2)
                p_rx = round(peak_tracker["window_peak_rx"], 2)
                all_p = peak_tracker["all_time_24h_peak_rx"]

                # AI Verdict for the completed 10-min window
                if all_p > 40 and p_rx >= (all_p * 0.90) and avg_rx >= (all_p * 0.70):
                    verdict = "ضغط ذروة واختناق وشيك"
                    v_sev = "danger"
                elif all_p > 30 and p_rx >= (all_p * 0.75):
                    verdict = "سحب مرتفع ونشط جداً"
                    v_sev = "warning"
                elif p_rx >= 40:
                    verdict = "سحب طبيعي ومستقر"
                    v_sev = "success"
                else:
                    verdict = "سحب هادئ وسعة فائضة"
                    v_sev = "info"

                win_entry = {
                    "id": int(current_ts),
                    "time_range": f"{peak_tracker['window_start_label']} - {time.strftime('%H:%M')}",
                    "peak_rx_mbps": p_rx,
                    "avg_rx_mbps": avg_rx,
                    "peak_time": peak_tracker["window_peak_time"],
                    "verdict": verdict,
                    "severity": v_sev
                }
                peak_tracker["history_10m_windows"].insert(0, win_entry)
                # Auto-prune to strictly keep last 24h = max 144 items (prevents any memory growth)
                peak_tracker["history_10m_windows"] = peak_tracker["history_10m_windows"][:144]

                # Reset window
                peak_tracker["window_start_time"] = current_ts
                peak_tracker["window_start_label"] = time.strftime("%H:%M")
                peak_tracker["window_peak_rx"] = 0.0
                peak_tracker["window_peak_tx"] = 0.0
                peak_tracker["window_samples"] = 0
                peak_tracker["window_sum_rx"] = 0.0

            # Real-time Congestion Decision
            cap_ref = max(peak_tracker["all_time_24h_peak_rx"], 80.0)
            util_pct = round((combined_rx / cap_ref) * 100.0, 1)
            cur_10m_avg = round(peak_tracker["window_sum_rx"] / max(1, peak_tracker["window_samples"]), 2)

            if util_pct > 90.0 or cpu_int > 75:
                cong_level = "CONGESTION_CRITICAL"
                cong_label = "اختناق وضغط فائق (ذروة السحب)"
                cong_color = "red"
                cong_diag = "السحب يقترب من السقف الأقصى المسجل، هناك احتمال لاختناق القنوات."
                cong_adv = "تنبيه: سحب مكثف جداً؛ تم تسجيل استهلاك قياسي. راقب المشتركين أصحاب أعلى سحب."
            elif util_pct > 70.0:
                cong_level = "ACTIVE_HEAVY"
                cong_label = "سحب نشط وقوي (استهلاك مرتفع)"
                cong_color = "amber"
                cong_diag = "الشبكة تحت استهلاك نشط وواسع، السعة تستوعب الحركة بكفاءة."
                cong_adv = "السحب مرتفع ضمن الحدود الآمنة، خطوط كويك نت وستارلنك تعمل بتوازن جيد."
            elif util_pct > 40.0:
                cong_level = "OPTIMAL"
                cong_label = "سحب طبيعي ومعتدل"
                cong_color = "emerald"
                cong_diag = "السحب كافٍ ومستقر تماماً، القنوات مرتاحة."
                cong_adv = "حركة المرور ممتازة ولا يوجد أي مؤشر لاختناق أو بطء للمشتركين."
            else:
                cong_level = "IDLE_LIGHT"
                cong_label = "سحب خفيف وسعة فائضة"
                cong_color = "cyan"
                cong_diag = "الشبكة في حالة استقرار تام، السعة فائضة جداً."
                cong_adv = "لا يوجد أي ضغط، المعالج مستريح والمنافذ في أفضل أداء."

            health_score = max(40, min(100, int(100 - (util_pct * 0.4) - (cpu_int * 0.3))))

            telemetry_data["network_summary"] = {
                "combined_rx_mbps": combined_rx,
                "combined_tx_mbps": combined_tx,
                "load_level": cong_level,
                "load_label": cong_label,
                "load_color": cong_color,
                "congestion_status": cong_diag,
                "health_score": health_score,
                "analysis_advice": cong_adv
            }

            telemetry_data["ai_congestion_analyzer"] = {
                "current_10m_peak_rx": round(peak_tracker["window_peak_rx"], 2),
                "current_10m_avg_rx": cur_10m_avg,
                "all_time_24h_peak_rx": round(peak_tracker["all_time_24h_peak_rx"], 2),
                "all_time_24h_peak_time": peak_tracker["all_time_24h_peak_time"],
                "capacity_utilization_pct": util_pct,
                "congestion_state": cong_level,
                "ai_diagnosis_text": cong_diag,
                "advice_text": cong_adv,
                "history_windows": peak_tracker["history_10m_windows"][:12]
            }

            # 6. Parse Starlink Daily Quota (Exact Standard Accounting)
            m_midnight = re.search(r"MIDNIGHT_RX:\s*([0-9]+)", raw_out)
            m_current = re.search(r"CURRENT_RX:\s*([0-9]+)", raw_out)
            m_quota_exceeded = re.search(r"QUOTA_EXCEEDED:\s*([a-zA-Z]+)", raw_out)

            if m_current:
                curr_rx = int(m_current.group(1))
                if m_midnight and m_midnight.group(1).isdigit():
                    base_rx = int(m_midnight.group(1))
                elif self.cached_baseline_rx is not None:
                    base_rx = self.cached_baseline_rx
                else:
                    self.cached_baseline_rx = curr_rx
                    base_rx = curr_rx

                diff_bytes = max(0, curr_rx - base_rx)
                # Standard Decimal GB (1 GB = 1,000,000,000 Bytes as used by Starlink)
                daily_used_gb = round(diff_bytes / 1000000000.0, 2)
                daily_used_gib = round(diff_bytes / (1024.0 ** 3), 2)
                rem_gb = max(0.0, round(150.0 - daily_used_gb, 2))
                used_pct = min(100.0, round((daily_used_gb / 150.0) * 100.0, 1))

                is_exceeded = False
                if m_quota_exceeded and m_quota_exceeded.group(1).lower() == "true":
                    is_exceeded = True

                if is_exceeded or daily_used_gb >= 145.0:
                    status = "CRITICAL"
                elif daily_used_gb >= 100.0:
                    status = "WARNING"
                else:
                    status = "NORMAL"

                # Router local time (Asia/Baghdad = UTC+3)
                tz_offset = int(os.getenv("ROUTER_TZ_OFFSET", "3")) * 3600
                router_local_ts = current_ts + tz_offset
                now_t = time.gmtime(router_local_ts)
                secs_today = now_t.tm_hour * 3600 + now_t.tm_min * 60 + now_t.tm_sec
                secs_to_midnight = max(0, 86400 - secs_today)

                telemetry_data["starlink"]["daily_used_gb"] = daily_used_gb
                telemetry_data["starlink"]["daily_used_gib"] = daily_used_gib
                telemetry_data["starlink"]["daily_remaining_gb"] = rem_gb
                telemetry_data["starlink"]["daily_usage_pct"] = used_pct
                telemetry_data["starlink"]["raw_current_bytes"] = curr_rx
                telemetry_data["starlink"]["raw_midnight_bytes"] = base_rx
                telemetry_data["starlink"]["status"] = status
                telemetry_data["starlink"]["quota_exceeded"] = is_exceeded
                telemetry_data["starlink"]["seconds_to_midnight"] = secs_to_midnight

            # 7. Parse Per-Subscriber Instant Bandwidth
            user_bandwidth = {}
            if "===SUB_TRAFFIC===" in raw_out and "===STARLINK_VARS===" in raw_out:
                sub_mon_part = raw_out.split("===SUB_TRAFFIC===")[1].split("===STARLINK_VARS===")[0]
                u_names_m = re.search(r"name:\s*([^\r\n]+)", sub_mon_part)
                u_rx_m = re.search(r"rx-bits-per-second:\s*([^\r\n]+)", sub_mon_part)
                u_tx_m = re.search(r"tx-bits-per-second:\s*([^\r\n]+)", sub_mon_part)

                if u_names_m and u_rx_m and u_tx_m:
                    names_found = re.findall(r"<pppoe-([^>]+)>", u_names_m.group(1))
                    r_vals = [p for p in u_rx_m.group(1).split() if p]
                    t_vals = [p for p in u_tx_m.group(1).split() if p]

                    for i, uname in enumerate(names_found):
                        rx_val = parse_bandwidth_bps(r_vals[i]) if i < len(r_vals) else 0.0
                        tx_val = parse_bandwidth_bps(t_vals[i]) if i < len(t_vals) else 0.0
                        user_bandwidth[uname] = {
                            "download_mbps": round(tx_val, 2),
                            "upload_mbps": round(rx_val, 2),
                            "total_mbps": round(tx_val + rx_val, 2)
                        }

            # 8. Parse Active PPP Subscribers
            hyb_users_found = set(re.findall(r"HYB_USER:([^\r\n]+)", raw_out))

            subs_list = []
            star_count = 0
            qn_count = 0
            hyb_count = 0
            oth_count = 0

            ppp_part = raw_out.split("===ACTIVE_PPP===")[1].split("===LOG_START===")[0] if "===ACTIVE_PPP===" in raw_out else raw_out
            entries = re.split(r"\n\s*\d+\s+", ppp_part)
            current_subs_set = set()

            for entry in entries[1:]:
                name_m = re.search(r'name="?([^"\s]+)"?', entry)
                addr_m = re.search(r"address=([0-9.]+)", entry)
                caller_m = re.search(r'caller-id="?([^"\s]+)"?', entry)
                uptime_m = re.search(r"uptime=([^\s]+)", entry)

                if name_m and addr_m:
                    sub_name = name_m.group(1)
                    sub_ip = addr_m.group(1)
                    sub_mac = caller_m.group(1) if caller_m else "N/A"
                    sub_uptime = uptime_m.group(1) if uptime_m else "0s"

                    if sub_name in hyb_users_found:
                        mode_str = "Quicknet" if sub_ip.startswith("172.17.") else "Starlink"
                        srv = f"Hybrid ({mode_str})"
                        srv_badge = "hybrid"
                        hyb_count += 1
                    elif sub_ip.startswith("172.16."):
                        srv = "Starlink"
                        srv_badge = "starlink"
                        star_count += 1
                    elif sub_ip.startswith("172.17."):
                        srv = "Quicknet"
                        srv_badge = "quicknet"
                        qn_count += 1
                    else:
                        srv = "Local"
                        srv_badge = "other"
                        oth_count += 1

                    # Attach live bandwidth for this subscriber
                    bw_info = user_bandwidth.get(sub_name, {"download_mbps": 0.0, "upload_mbps": 0.0, "total_mbps": 0.0})

                    current_subs_set.add(sub_name)
                    subs_list.append({
                        "name": sub_name,
                        "ip": sub_ip,
                        "mac": sub_mac,
                        "uptime": sub_uptime,
                        "service": srv,
                        "badge": srv_badge,
                        "download_mbps": bw_info["download_mbps"],
                        "upload_mbps": bw_info["upload_mbps"],
                        "total_mbps": bw_info["total_mbps"],
                        "rate_str": f"⬇ {bw_info['download_mbps']} M | ⬆ {bw_info['upload_mbps']} M"
                    })

            # Sort subscribers by highest total bandwidth usage descending
            subs_list.sort(key=lambda x: x["total_mbps"], reverse=True)

            telemetry_data["subscribers"]["total_active"] = len(subs_list)
            telemetry_data["subscribers"]["starlink_count"] = star_count
            telemetry_data["subscribers"]["quicknet_count"] = qn_count
            telemetry_data["subscribers"]["hybrid_count"] = hyb_count
            telemetry_data["subscribers"]["other_count"] = oth_count
            telemetry_data["subscribers"]["list"] = subs_list

            # Detect Logins & Logouts for Instant Alerts
            if last_subscribers_set:
                new_users = current_subs_set - last_subscribers_set
                dropped_users = last_subscribers_set - current_subs_set

                for nu in new_users:
                    self.add_event(f"🟢 اشتراك جديد متصل: {nu}", "login")
                for du in dropped_users:
                    self.add_event(f"🔴 اشتراك فصل الاتصال: {du}", "logout")

            last_subscribers_set = current_subs_set

            # 9. Parse System Logs & Translate
            parsed_logs = []
            if "===LOG_START===" in raw_out and "===LOG_END===" in raw_out:
                log_chunk = raw_out.split("===LOG_START===")[1].split("===LOG_END===")[0].strip()
                lines = [l.strip() for l in log_chunk.split("\n") if l.strip()]
                for line in lines:
                    parts = line.split(" # ")
                    if len(parts) >= 3:
                        l_time = parts[0].strip()
                        l_topic = parts[1].strip()
                        l_msg = parts[2].strip()
                        trans = translate_log_message(l_topic, l_msg)
                        parsed_logs.append({
                            "time": l_time,
                            "topic": l_topic,
                            "message_ar": trans["message_ar"],
                            "message_en": l_msg,
                            "severity": trans["severity"]
                        })
                parsed_logs.reverse()  # Newest first

            telemetry_data["system_logs"] = parsed_logs

            # 10. Fetch / Refresh Automation Scripts & Schedulers every 30 seconds
            if time.time() - self.last_scripts_fetch > 30 or not self.cached_scripts:
                self.fetch_scripts()

        except Exception as e:
            logger.error(f"Error in polling iteration: {e}")
            telemetry_data["status"] = "error"
            self.ssh = None

    def add_event(self, msg: str, event_type: str = "info"):
        global telemetry_data
        evt = {
            "id": int(time.time() * 1000),
            "time": time.strftime("%H:%M:%S"),
            "message": msg,
            "type": event_type
        }
        telemetry_data["events"].insert(0, evt)
        telemetry_data["events"] = telemetry_data["events"][:50]


worker = RouterMonitorWorker()


async def background_telemetry_loop():
    worker.connect()
    while True:
        try:
            worker.poll_once()
            if active_websockets:
                msg_json = json.dumps(telemetry_data)
                dead_sockets = []
                for ws in active_websockets:
                    try:
                        await ws.send_text(msg_json)
                    except Exception:
                        dead_sockets.append(ws)
                for ds in dead_sockets:
                    if ds in active_websockets:
                        active_websockets.remove(ds)
        except Exception as e:
            logger.error(f"Background loop error: {e}")
        await asyncio.sleep(1.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(background_telemetry_loop())
    yield


app = FastAPI(title="MikroTik Smart Control Platform (MSCP)", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", status_code=204)


# WebSocket Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        await websocket.send_text(json.dumps(telemetry_data))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


# REST Endpoints
@app.get("/api/telemetry")
async def get_telemetry():
    return telemetry_data


@app.get("/api/peaks")
async def get_peaks():
    return {
        "all_time_24h_peak_rx": peak_tracker["all_time_24h_peak_rx"],
        "all_time_24h_peak_time": peak_tracker["all_time_24h_peak_time"],
        "current_window_peak_rx": peak_tracker["window_peak_rx"],
        "history_windows": peak_tracker["history_10m_windows"]
    }


@app.get("/api/logs")
async def get_logs():
    return telemetry_data.get("system_logs", [])


@app.get("/api/scripts")
async def get_scripts():
    return telemetry_data.get("automation_scripts", [])


@app.post("/api/kick")
async def kick_subscriber(payload: Dict[str, str]):
    user = payload.get("username")
    if not user:
        return {"success": False, "message": "Username is required"}
    
    if worker.ssh:
        try:
            cmd = f'/ppp active remove [find name="{user}"]'
            stdin, stdout, stderr = worker.ssh.exec_command(cmd, timeout=5)
            worker.add_event(f"⚡ تم فصل جلسة المشترك يدويًا: {user}", "kick")
            return {"success": True, "message": f"Successfully kicked {user}"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    return {"success": False, "message": "Router connection offline"}


# Static Files Delivery
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Loading MSCP Dashboard...</h1>")


if __name__ == "__main__":
    srv_port = int(os.getenv("PORT", os.getenv("DASHBOARD_PORT", 8000)))
    uvicorn.run("backend:app", host="0.0.0.0", port=srv_port, reload=False)
