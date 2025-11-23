#!/usr/bin/env python3
"""
MSS 경기지역본부 공지사항 새 글 체크 스크립트
"""

import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# 설정
MSS_URL = "https://www.mss.go.kr/site/gyeonggi/ex/bbs/List.do?cbIdx=323"
LAST_CHECKED_FILE = "last_checked.json"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")


def fetch_posts():
    """MSS 페이지에서 게시글 목록을 가져옴"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    response = requests.get(MSS_URL, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    posts = []

    # 테이블에서 게시글 행 찾기
    table = soup.find("table", class_="bbs_default_list")
    if not table:
        # 다른 테이블 구조 시도
        table = soup.find("table")

    if table:
        tbody = table.find("tbody")
        if tbody:
            rows = tbody.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 4:
                    # 제목과 링크 찾기
                    title_cell = cols[1] if len(cols) > 1 else cols[0]
                    link_tag = title_cell.find("a")

                    if link_tag:
                        title = link_tag.get_text(strip=True)
                        href = link_tag.get("href", "")

                        # 게시글 번호 추출 (첫 번째 열)
                        post_num = cols[0].get_text(strip=True)

                        # 날짜 찾기 (보통 뒤쪽 열)
                        date_text = ""
                        for col in cols:
                            text = col.get_text(strip=True)
                            if "." in text and len(text) == 10:  # YYYY.MM.DD 형식
                                date_text = text
                                break

                        # 전체 URL 생성
                        if href and not href.startswith("http"):
                            full_url = f"https://www.mss.go.kr{href}"
                        else:
                            full_url = href

                        posts.append({
                            "num": post_num,
                            "title": title,
                            "url": full_url,
                            "date": date_text
                        })

    return posts


def load_last_checked():
    """마지막으로 확인한 게시글 정보 로드"""
    if os.path.exists(LAST_CHECKED_FILE):
        with open(LAST_CHECKED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"posts": []}


def save_last_checked(data):
    """마지막으로 확인한 게시글 정보 저장"""
    with open(LAST_CHECKED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_slack_notification(new_posts):
    """Slack으로 새 글 알림 전송"""
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL이 설정되지 않았습니다.")
        return False

    for post in new_posts:
        message = {
            "text": f":mega: *MSS 경기지역본부 새 공지*",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "MSS 경기지역본부 새 공지"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*제목:*\n<{post['url']}|{post['title']}>"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*등록일:*\n{post['date']}"
                        }
                    ]
                },
                {
                    "type": "divider"
                }
            ]
        }

        response = requests.post(
            SLACK_WEBHOOK_URL,
            json=message,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code != 200:
            print(f"Slack 전송 실패: {response.status_code} - {response.text}")
            return False

        print(f"Slack 알림 전송 완료: {post['title']}")

    return True


def main():
    print(f"MSS 새 글 체크 시작: {datetime.now()}")

    # 현재 게시글 목록 가져오기
    current_posts = fetch_posts()
    print(f"현재 게시글 {len(current_posts)}개 확인")

    if not current_posts:
        print("게시글을 가져오지 못했습니다.")
        return

    # 마지막 확인 정보 로드
    last_checked = load_last_checked()
    last_titles = {p["title"] for p in last_checked.get("posts", [])}

    # 새 글 찾기
    new_posts = []
    for post in current_posts:
        if post["title"] not in last_titles:
            new_posts.append(post)
            print(f"새 글 발견: {post['title']}")

    # 첫 실행 여부 확인
    is_first_run = len(last_checked.get("posts", [])) == 0

    if new_posts:
        if is_first_run:
            print("첫 실행입니다. 현재 게시글을 저장하고 알림은 보내지 않습니다.")
        else:
            print(f"새 글 {len(new_posts)}개 발견! Slack 알림 전송 중...")
            send_slack_notification(new_posts)
    else:
        print("새 글이 없습니다.")

    # 현재 상태 저장 (상위 10개만 저장)
    save_last_checked({
        "posts": current_posts[:10],
        "last_checked": datetime.now().isoformat()
    })
    print("상태 저장 완료")


if __name__ == "__main__":
    main()
