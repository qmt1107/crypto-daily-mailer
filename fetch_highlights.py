"""
CoinGecko 일일 하이라이트 메일 발송 스크립트 (진단판)
- 각 단계별로 상세한 로그 출력
- 환경변수 검증
- 명확한 에러 메시지
"""
import os
import sys
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

COINGECKO_API = "https://api.coingecko.com/api/v3"
TIMEOUT = 30
KST = timezone(timedelta(hours=9))  # zoneinfo 의존성 제거


# ---------- 환경변수 검증 ---------- #
def check_env():
    required = ["GMAIL_USER", "GMAIL_APP_PASSWORD", "RECIPIENT_EMAIL"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"❌ ERROR: 다음 환경변수가 비어있습니다: {missing}")
        print("   GitHub Settings → Secrets → Actions 에서 확인하세요.")
        sys.exit(1)

    user = os.environ["GMAIL_USER"]
    pwd = os.environ["GMAIL_APP_PASSWORD"]
    recv = os.environ["RECIPIENT_EMAIL"]

    print(f"✓ GMAIL_USER: {user}")
    print(f"✓ GMAIL_APP_PASSWORD: {'*' * len(pwd)} (길이 {len(pwd)})")
    print(f"✓ RECIPIENT_EMAIL: {recv}")

    pwd_clean = pwd.replace(" ", "")
    if len(pwd_clean) != 16:
        print(f"⚠️  경고: 앱 비밀번호 길이가 {len(pwd_clean)}자리입니다 (정상: 16자리)")
        print("   일반 Gmail 비밀번호가 아닌 '앱 비밀번호'를 사용해야 합니다.")
        print("   https://myaccount.google.com/apppasswords")

    if " " in pwd:
        print("⚠️  앱 비밀번호에 공백이 포함되어 있습니다. 공백 제거 후 사용합니다.")


# ---------- API 호출 ---------- #
def safe_get(url, params=None, label=""):
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        if r.status_code == 429:
            print(f"⚠️  {label}: CoinGecko 호출 한도 초과 (429). 잠시 후 재시도하세요.")
            sys.exit(1)
        if r.status_code == 403:
            print(f"⚠️  {label}: CoinGecko가 요청을 거부했습니다 (403).")
            sys.exit(1)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        print(f"❌ {label}: 타임아웃 ({TIMEOUT}초)")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"❌ {label}: 네트워크 오류 - {e}")
        sys.exit(1)


def fetch_trending():
    return safe_get(f"{COINGECKO_API}/search/trending", label="트렌딩").get("coins", [])[:7]


def fetch_markets():
    return safe_get(
        f"{COINGECKO_API}/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "price_change_percentage": "24h",
        },
        label="마켓 데이터",
    )


def fetch_global():
    return safe_get(f"{COINGECKO_API}/global", label="글로벌 통계").get("data", {})


# ---------- 데이터 가공 ---------- #
def split_gainers_losers(markets, n=5):
    valid = [c for c in markets if c.get("price_change_percentage_24h") is not None]
    sorted_by_change = sorted(valid, key=lambda x: x["price_change_percentage_24h"], reverse=True)
    return sorted_by_change[:n], sorted_by_change[-n:][::-1]


def fmt_price(p):
    if p is None:
        return "-"
    if p >= 1:
        return f"${p:,.2f}"
    if p >= 0.01:
        return f"${p:.4f}"
    return f"${p:.8f}"


def fmt_pct(p):
    if p is None:
        return "-"
    return f"{p:+.2f}%"


def fmt_big(n):
    if n is None:
        return "-"
    if n >= 1e12:
        return f"${n/1e12:.2f}T"
    if n >= 1e9:
        return f"${n/1e9:.2f}B"
    if n >= 1e6:
        return f"${n/1e6:.2f}M"
    return f"${n:,.0f}"


# ---------- HTML 빌드 ---------- #
def coin_row(rank, name, symbol, price, change_pct, image=""):
    is_positive = (change_pct or 0) >= 0
    color = "#16a34a" if is_positive else "#dc2626"
    img = f'<img src="{image}" width="20" height="20" style="vertical-align:middle;border-radius:50%;margin-right:6px;">' if image else ""
    return f"""
    <tr>
      <td style="padding:10px 8px;border-bottom:1px solid #eee;color:#888;font-size:13px;">{rank}</td>
      <td style="padding:10px 8px;border-bottom:1px solid #eee;">{img}<strong>{name}</strong> <span style="color:#888;font-size:12px;">{symbol.upper()}</span></td>
      <td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;font-variant-numeric:tabular-nums;">{price}</td>
      <td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;color:{color};font-weight:600;font-variant-numeric:tabular-nums;">{fmt_pct(change_pct)}</td>
    </tr>
    """


def section(title, emoji, rows):
    return f"""
    <h2 style="font-size:18px;margin:28px 0 12px;color:#1f2937;">{emoji} {title}</h2>
    <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;background:#fff;border:1px solid #eee;border-radius:8px;overflow:hidden;">
      <thead><tr style="background:#f9fafb;">
        <th style="padding:10px 8px;text-align:left;font-size:12px;color:#6b7280;font-weight:500;">#</th>
        <th style="padding:10px 8px;text-align:left;font-size:12px;color:#6b7280;font-weight:500;">코인</th>
        <th style="padding:10px 8px;text-align:right;font-size:12px;color:#6b7280;font-weight:500;">가격</th>
        <th style="padding:10px 8px;text-align:right;font-size:12px;color:#6b7280;font-weight:500;">24h 변동</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    """


def build_html(trending, gainers, losers, global_data, today_str):
    total_mcap = global_data.get("total_market_cap", {}).get("usd")
    total_vol = global_data.get("total_volume", {}).get("usd")
    mcap_change = global_data.get("market_cap_change_percentage_24h_usd")
    btc_dom = global_data.get("market_cap_percentage", {}).get("btc", 0)
    eth_dom = global_data.get("market_cap_percentage", {}).get("eth", 0)
    mcap_color = "#16a34a" if (mcap_change or 0) >= 0 else "#dc2626"

    trending_rows = []
    for i, item in enumerate(trending, 1):
        c = item.get("item", {})
        price_btc = c.get("data", {}).get("price")
        price_str = fmt_price(price_btc) if isinstance(price_btc, (int, float)) else "-"
        change = c.get("data", {}).get("price_change_percentage_24h", {}).get("usd")
        trending_rows.append(coin_row(
            rank=c.get("market_cap_rank") or i,
            name=c.get("name", ""),
            symbol=c.get("symbol", ""),
            price=price_str,
            change_pct=change,
            image=c.get("small", ""),
        ))

    gainer_rows = [coin_row(
        rank=i, name=c["name"], symbol=c["symbol"],
        price=fmt_price(c.get("current_price")),
        change_pct=c.get("price_change_percentage_24h"),
        image=c.get("image", ""),
    ) for i, c in enumerate(gainers, 1)]

    loser_rows = [coin_row(
        rank=i, name=c["name"], symbol=c["symbol"],
        price=fmt_price(c.get("current_price")),
        change_pct=c.get("price_change_percentage_24h"),
        image=c.get("image", ""),
    ) for i, c in enumerate(losers, 1)]

    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border-radius:12px;padding:32px;">
<tr><td>
<h1 style="margin:0 0 4px;font-size:24px;color:#111827;">📊 CoinGecko 하이라이트</h1>
<p style="margin:0 0 24px;color:#6b7280;font-size:14px;">{today_str}</p>
<table width="100%" cellspacing="0" cellpadding="0" style="background:#f9fafb;border-radius:8px;padding:16px;margin-bottom:8px;">
<tr>
<td style="padding:8px;"><div style="font-size:12px;color:#6b7280;">전체 시가총액</div><div style="font-size:18px;font-weight:600;color:#111827;">{fmt_big(total_mcap)}</div><div style="font-size:13px;color:{mcap_color};font-weight:600;">{fmt_pct(mcap_change)}</div></td>
<td style="padding:8px;"><div style="font-size:12px;color:#6b7280;">24h 거래량</div><div style="font-size:18px;font-weight:600;color:#111827;">{fmt_big(total_vol)}</div></td>
</tr><tr>
<td style="padding:8px;"><div style="font-size:12px;color:#6b7280;">BTC 도미넌스</div><div style="font-size:18px;font-weight:600;color:#111827;">{btc_dom:.1f}%</div></td>
<td style="padding:8px;"><div style="font-size:12px;color:#6b7280;">ETH 도미넌스</div><div style="font-size:18px;font-weight:600;color:#111827;">{eth_dom:.1f}%</div></td>
</tr></table>
{section("트렌딩", "🔥", trending_rows)}
{section("상승 Top 20", "📈", gainer_rows)}
{section("하락 Top 20", "📉", loser_rows)}
<p style="margin-top:32px;padding-top:16px;border-top:1px solid #eee;color:#9ca3af;font-size:12px;text-align:center;">Powered by CoinGecko API · 자동 발송 메일</p>
</td></tr></table></td></tr></table></body></html>"""


# ---------- 메일 전송 ---------- #
def send_email(html_body, subject):
    sender = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")
    recipient = os.environ["RECIPIENT_EMAIL"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(sender, password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        print("❌ Gmail 인증 실패!")
        print(f"   에러: {e}")
        print("   체크리스트:")
        print("   1) Google 계정 2단계 인증이 켜져 있나요?")
        print("   2) 일반 비밀번호가 아닌 '앱 비밀번호'를 사용했나요?")
        print("   3) 앱 비밀번호는 16자리입니다 (공백 제외)")
        print("   4) GMAIL_USER 와 앱 비밀번호 발급한 계정이 같은가요?")
        sys.exit(1)
    except smtplib.SMTPException as e:
        print(f"❌ SMTP 에러: {type(e).__name__} - {e}")
        sys.exit(1)


# ---------- main ---------- #
def main():
    print("=" * 50)
    print("CoinGecko 일일 메일 발송 시작")
    print("=" * 50)

    print("\n[1/4] 환경변수 검증...")
    check_env()

    print("\n[2/4] CoinGecko 데이터 수집...")
    trending = fetch_trending()
    print(f"  ✓ 트렌딩 {len(trending)}개")
    markets = fetch_markets()
    print(f"  ✓ 마켓 {len(markets)}개")
    global_data = fetch_global()
    print(f"  ✓ 글로벌 통계 수신")
    gainers, losers = split_gainers_losers(markets, n=20)

    print("\n[3/4] HTML 메일 본문 생성...")
    today = datetime.now(KST)
    today_str = today.strftime("%Y년 %m월 %d일")
    subject = f"📊 CoinGecko 하이라이트 - {today.strftime('%m/%d')}"
    html = build_html(trending, gainers, losers, global_data, today_str)
    print(f"  ✓ HTML 생성 완료 ({len(html):,} 글자)")

    print(f"\n[4/4] 메일 전송: {subject}")
    send_email(html, subject)
    print("\n✅ 발송 완료!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단됨")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 예상치 못한 에러: {type(e).__name__}")
        print(f"   메시지: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
