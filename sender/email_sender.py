import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.settings import SENDER, QQ_AUTH_CODE, RECEIVER, CLASH_PROXY


def send_email(html: str, date_str: str, total: int):
    """
    发送逻辑（双重保障）：
    1. 优先 QQ SMTP 直连
    2. 直连失败，用 socks 劫持 socket 走 Clash 代理重试
       （smtplib 不读系统代理，必须用 socks.set_default_proxy 接管）
    """
    import socket
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🤖 AI Agent {date_str} · {total}条"
    msg["From"]    = SENDER
    msg["To"]      = RECEIVER
    msg.attach(MIMEText(html, "html", "utf-8"))
    raw = msg.as_string()

    # ── 方案1：QQ SMTP 直连 ──────────────────────────────────
    try:
        with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=20) as server:
            server.login(SENDER, QQ_AUTH_CODE)
            server.sendmail(SENDER, [RECEIVER], raw)
        print(f"[OK] QQ邮件已发送 → {RECEIVER}")
        return
    except Exception as e:
        print(f"[WARN] QQ SMTP直连失败: {e}，尝试走Clash代理...")

    # ── 方案2：socks劫持socket走Clash代理 ────────────────────
    _orig_socket = socket.socket   # 保存原始socket，发完后还原
    try:
        import socks
        socks.set_default_proxy(socks.HTTP, "127.0.0.1", 7897)
        socket.socket = socks.socksocket
        with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=20) as server:
            server.login(SENDER, QQ_AUTH_CODE)
            server.sendmail(SENDER, [RECEIVER], raw)
        print(f"[OK] QQ邮件（Clash代理）已发送 → {RECEIVER}")
    except Exception as e:
        print(f"[ERROR] 代理发送也失败: {e}")
        raise
    finally:
        # 务必还原socket，否则后续所有网络请求都走代理
        socket.socket = _orig_socket
