import os
import requests
import smtplib
import feedparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai

# 환경 변수 설정
CG_API_KEY = os.environ.get("CG_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS")

def get_onchain_trending():
    """사용자가 공유한 최신 API: 온체인 트렌딩 풀 데이터 가져오기"""
    # 문서에 명시된 온체인 트렌딩 엔드포인트
    url = "https://demo-api.coingecko.com/api/v3/onchain/networks/trending_pools"
    headers = {
        "accept": "application/json",
        "x-cg-demo-api-key": CG_API_KEY
    }
    params = {
        "include": "base_token,dex,network",
        "duration": "24h"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get('data', [])[:20] # 상위 20개 트렌딩 풀
    except Exception as e:
        print(f"온체인 데이터 수집 에러: {e}")
        return None

def get_crypto_news():
    """최신 크립토 뉴스 수집"""
    feed_url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
    try:
        feed = feedparser.parse(feed_url)
        return "\n".join([f"- {entry.title}" for entry in feed.entries[:10]])
    except:
        return "뉴스를 가져올 수 없습니다."

def analyze_onchain_with_ai(trending_pools, news):
    """Gemini AI로 온체인 급등주 분석"""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # 풀 데이터 문자열로 가공
    pool_info = []
    for i, pool in enumerate(trending_pools):
        attr = pool.get('attributes', {})
        name = attr.get('name', 'N/A')
        volume = attr.get('volume_usd', {}).get('h24', '0')
        price_change = attr.get('price_change_percentage', {}).get('h24', '0')
        pool_info.append(f"{i+1}. {name} | 24h변동: {price_change}% | 24h거래량: ${volume}")
    
    pool_data_str = "\n".join(pool_info)
    
    prompt = f"""
    당신은 탈중앙화 거래소(DEX) 전문 온체인 분석가입니다. 
    아래의 [실시간 온체인 트렌딩 풀] 데이터와 [주요 뉴스]를 분석하여 투자 보고서를 작성하세요.
    
    [실시간 온체인 트렌딩 풀 데이터]:
    {pool_data_str}
    
    [최신 주요 뉴스]:
    {news}
    
    [보고서 포함 내용]:
    1. 오늘 DEX 시장에서 가장 돈이 몰리고 있는 테마(밈코인, AI, RWA 등)를 진단하세요.
    2. 트렌딩 풀 중 10배 상승 가능성이 보이지만 리스크가 큰 '초고위험' 코인 3개를 선정하고 이유를 설명하세요.
    3. 수집된 20개 풀 리스트를 가독성 있게 정리하세요.
    4. 온체인 매매 시 주의해야 할 점(러그풀 가능성 등)을 경고하세요.
    
    전문적이고 냉철한 톤으로 한글로 작성하세요.
    """
    
    response = model.generate_content(prompt)
    return response.text

def send_mail(body):
    """결과 이메일 발송"""
    msg = MIMEMultipart()
    msg['Subject'] = f"🔥 [ON-CHAIN] 오늘의 고위험·고수익 트렌딩 분석 리포트"
    msg['From'] = GMAIL_USER
    msg['To'] = GMAIL_USER
    
    msg.attach(MIMEText(body, 'plain'))
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASS)
        server.send_message(msg)

if __name__ == "__main__":
    trending = get_onchain_trending()
    news = get_crypto_news()
    
    if trending:
        report = analyze_onchain_with_ai(trending, news)
        send_mail(report)
        print("온체인 분석 리포트 발송 완료!")
    else:
        print("데이터 수집 실패.")
