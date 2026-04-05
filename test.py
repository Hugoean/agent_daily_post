import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SENDER   = "2916702930@qq.com"
AUTH     = "kkbxawxbxedgdfaa"
RECEIVER = "2916702930@qq.com"

msg = MIMEMultipart("alternative")
msg["Subject"] = "测试：AI Agent推送"
msg["From"]    = SENDER
msg["To"]      = RECEIVER
msg.attach(MIMEText("<h1>发送成功</h1><p>邮件推送功能正常</p>", "html", "utf-8"))

with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=10) as s:
    s.login(SENDER, AUTH)
    s.sendmail(SENDER, [RECEIVER], msg.as_string())
    print("[OK] 发送成功，检查QQ收件箱")