# main.py (종합 분석 기능 추가 버전)

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv

import feedparser
import re 
from googletrans import Translator
import requests 
from collections import Counter # 출처 빈도수 계산을 위한 라이브러리 추가

# .env 파일 로드
load_dotenv()

# --- (이전 코드와 동일: NewsArticle 모델 정의, Translator 객체 초기화) ---
class NewsArticle(BaseModel):
    title: str
    url: str
    source: str
    summary: Optional[str] = None 

translator = Translator()

# .env에서 텔레그램 설정 로드
TELEGRAM_BOT_TOKEN = os.getenv('telegram_bot_token')
TELEGRAM_CHAT_ID = os.getenv('telegram_chat_id')


# --- 텔레그램 메시지 전송 함수 ---
def send_telegram_message(message: str) -> bool:
    """
    텔레그램으로 메시지를 전송합니다.
    
    Args:
        message: 전송할 메시지 내용
    
    Returns:
        성공 시 True, 실패 시 False
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ 텔레그램 설정이 없습니다. .env 파일을 확인하세요.")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"  # HTML 포맷 지원 (마크다운도 가능: "Markdown")
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print("✅ 텔레그램 메시지 전송 성공!")
            return True
        else:
            print(f"❌ 텔레그램 전송 실패: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 텔레그램 메시지 전송 중 오류 발생: {e}")
        return False


def send_news_to_telegram(news: List[NewsArticle]) -> bool:
    """
    수집한 뉴스를 텔레그램으로 전송합니다.
    
    Args:
        news: 뉴스 기사 리스트
    
    Returns:
        성공 시 True, 실패 시 False
    """
    if not news or news[0].url == '#':
        message = "🚨 뉴스 수집에 실패했습니다. 나중에 다시 시도해주세요."
        return send_telegram_message(message)
    
    # 메시지 포맷 구성
    message = "<b>📰 AI 뉴스 스크랩 (최신 10개)</b>\n\n"
    
    for idx, article in enumerate(news, 1):
        message += f"<b>{idx}. {article.title}</b>\n"
        message += f"출처: {article.source}\n"
        if article.summary:
            message += f"요약: {article.summary}\n"
        message += f"링크: <a href='{article.url}'>기사 보기</a>\n"
        message += "─" * 40 + "\n"
    
    return send_telegram_message(message)


# --- 2. RSS 피드 파싱 및 번역 로직 구현 (변경 없음) ---
def parse_rss_feed() -> List[NewsArticle]:
    # ... (이전 parse_rss_feed 함수 내용 전체를 그대로 유지합니다.) ...
    feed_url = "https://techcrunch.com/category/artificial-intelligence/feed/" 
    news_list: List[NewsArticle] = []
    
    clean_html = re.compile('<.*?>') 

    try:
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries[:10]:
            original_title = entry.title
            try:
                translated_title = translator.translate(original_title, dest='ko').text
            except Exception:
                translated_title = original_title + " (번역 실패)"

            raw_summary = entry.summary if hasattr(entry, 'summary') else ""
            clean_summary = re.sub(clean_html, '', raw_summary).strip()
            
            truncated_summary_ko = None
            if clean_summary:
                try:
                    translated_text = translator.translate(clean_summary, dest='ko').text
                    truncated_summary_ko = translated_text[:200]
                    if len(translated_text) > 200:
                         truncated_summary_ko += "..."
                except Exception:
                    truncated_summary_ko = clean_summary[:200] + "... (번역 실패)"

            news_list.append(NewsArticle(
                title=translated_title,
                url=entry.link,
                source=entry.author if hasattr(entry, 'author') else feed.feed.title,
                summary=truncated_summary_ko
            ))
            
        return news_list

    except Exception as e:
        print(f"🚨 RSS 피드 파싱 중 심각한 오류 발생: {e}")
        return [
            NewsArticle(title=f"🚨 RSS 피드 오류: {e}", url="#", source="오류", summary="뉴스 가져오기에 실패했습니다."),
        ]


# --- 🌟 4. 새로운 종합 분석 로직 구현 🌟 ---
def analyze_news_data(news: List[NewsArticle]) -> str:
    """
    10개 기사의 출처 및 주제 동향을 바탕으로 종합 분석 텍스트를 생성합니다.
    """
    if not news or news[0].url == '#':
        return "데이터 수집에 실패하여 종합 분석을 수행할 수 없습니다."

    sources = [article.source for article in news if article.source and article.source != '오류']
    source_counts = Counter(sources)
    
    total_articles = len(news)
    
    # 1. 출처 빈도 분석
    if source_counts:
        most_common_source, count = source_counts.most_common(1)[0]
        source_analysis = f"총 {total_articles}개의 기사가 수집되었으며, 주요 출처는 '{most_common_source}' (총 {count}건)입니다."
    else:
        source_analysis = f"총 {total_articles}개의 기사가 수집되었으나, 출처 정보가 불분명합니다."
        
    # 2. 주제 동향 분석 (키워드 추출 기반의 가상 분석)
    # 실제 자연어 처리를 하지 않고 제목에 포함된 특정 키워드 빈도를 이용해 가상 분석을 수행합니다.
    keywords = ['모델', '스타트업', '반도체', '투자', '규제', 'GPT', '러닝', '로봇', '칩']
    title_text = " ".join([article.title for article in news])
    
    keyword_summary = {}
    for kw in keywords:
        kw_count = title_text.count(kw)
        if kw_count > 0:
            keyword_summary[kw] = kw_count
            
    if keyword_summary:
        sorted_keywords = sorted(keyword_summary.items(), key=lambda item: item[1], reverse=True)
        top_keywords = ", ".join([f"{k} ({v}회)" for k, v in sorted_keywords[:3]])
        trend_analysis = f"현재 주요 관심사는 {top_keywords} 등으로, 인공지능 모델의 상용화와 관련 투자, 그리고 하드웨어(반도체/칩) 기술에 대한 동향이 두드러집니다."
    else:
        trend_analysis = "현재 기사 제목만으로는 명확한 주요 동향 키워드를 파악하기 어렵습니다."
        
    # 최종 분석 결합
    final_analysis = (
        "**AI 뉴스 종합 분석 결과**\n\n"
        f"1. **데이터 개요:** {source_analysis}\n"
        f"2. **기술 동향:** {trend_analysis} \n\n"
        "이 분석은 10개 기사의 제목과 출처를 기반으로 한 단순 통계이며, 실제 내용 분석을 위해서는 추가적인 NLP(자연어 처리) 모델이 필요합니다. "
        "전반적으로 AI 기술의 상업적 적용과 관련된 뉴스가 활발하게 보도되고 있음을 알 수 있습니다."
    )
    
    return final_analysis

# --- 3. FastAPI 애플리케이션 및 라우트 정의 ---
app = FastAPI(
    title="인공지능 번역 RSS 뉴스 피드 앱",
    description="FastAPI, feedparser, googletrans를 이용해 인공지능 뉴스를 번역 및 게시합니다."
)

templates = Jinja2Templates(directory="templates")

@app.get("/", summary="뉴스 웹 페이지 표시")
async def news_webpage(request: Request):
    news = parse_rss_feed() 
    
    # 🌟 추가: 종합 분석 내용 생성
    analysis_text = analyze_news_data(news)

    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "news": news, "title": "인공지능 (AI) 번역 뉴스", "analysis": analysis_text} # 템플릿에 분석 내용 전달
    )

@app.get("/api/news", response_model=List[NewsArticle], summary="뉴스 데이터 (JSON) 반환")
async def get_latest_news_api():
    return parse_rss_feed()

@app.get("/api/send-telegram", summary="뉴스를 텔레그램으로 전송")
async def send_news_telegram():
    """
    수집한 최신 뉴스를 텔레그램 채팅으로 전송합니다.
    """
    news = parse_rss_feed()
    success = send_news_to_telegram(news)
    
    return {
        "status": "success" if success else "failed",
        "message": "뉴스가 텔레그램으로 전송되었습니다!" if success else "텔레그램 전송에 실패했습니다."
    }