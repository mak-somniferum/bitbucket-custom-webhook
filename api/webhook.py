from flask import Flask, request, jsonify
import os
from sys import platform as _platform
import logging
import requests
from dotenv import load_dotenv
import base64

# .env 파일 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

if _platform == "darwin":
    from pync import Notifier

# Bitbucket 설정
BITBUCKET_API_URL = "https://api.bitbucket.org/2.0"
BITBUCKET_AUTH_TOKEN = os.environ.get("BITBUCKET_AUTH_TOKEN")  # Bitbucket App Password나 OAuth token

# 사용자별 맞춤 메시지 설정
USER_MESSAGES = {
    "suhjin700": "열심히 코딩하시네요! 👍",
    # "user2": "오늘도 좋은 코드 감사합니다! 🎉",
    # 더 많은 사용자와 메시지를 추가할 수 있습니다
}

# PR 코멘트 설정
PR_COMMENTS = {
    "default": "@{712020:b486d9e0-cb42-427e-be16-9cdb6284476a} full review",
}

BITBUCKET_USERNAME = os.getenv("BITBUCKET_USERNAME")        # .env에 추가
BITBUCKET_APP_PASSWORD = os.getenv("BITBUCKET_APP_PASSWORD")  # (=기존 BITBUCKET_AUTH_TOKEN)


# 한글·유니코드 사용자 이름도 지원하는 Basic Auth 헤더 생성 함수
def build_basic_auth_header(username: str, password: str) -> str:
    token_bytes = f"{username}:{password}".encode("utf-8")
    b64_token = base64.b64encode(token_bytes).decode("ascii")
    return f"Basic {b64_token}"


def add_pr_comment(workspace, repo_slug, pr_id, comment):
    """PR에 코멘트를 추가하는 함수"""   
    if not (BITBUCKET_USERNAME and BITBUCKET_APP_PASSWORD):
        logger.error("Bitbucket authentication credentials not found")
        return False

    url = f"{BITBUCKET_API_URL}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
    headers = {
        "Authorization": build_basic_auth_header(BITBUCKET_USERNAME, BITBUCKET_APP_PASSWORD),
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(
            url,
            headers=headers,
            json={
                "content": {
                    "raw": comment,
                }
            },
            timeout=10
        )
        res.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        # Bitbucket가 반환한 상세 에러 메시지까지 로그로 남긴다.
        if e.response is not None:
            logger.error(
                "Error adding PR comment: %s | Response: %s",
                e,
                e.response.text
            )
        else:
            logger.error(f"Error adding PR comment: {e}")
        return False

@app.route("/webhook", methods=["POST"])
def webhook():
    """Bitbucket 웹훅을 처리하는 엔드포인트"""
    try:
        logger.info("Received webhook request")
        data = request.get_json()
        
        if not data:
            logger.error("No JSON data received")
            return jsonify({"error": "No data received"}), 400
            
        logger.info(f"Webhook data received: {data}")
        
        # 헤더에서 이벤트 타입 확인
        event_key = request.headers.get("X-Event-Key", "")
        logger.info(f"Event key: {event_key}")

        # PR 생성 이벤트 처리
        if event_key == "pullrequest:created" and data.get("pullrequest"):
            pr_data = data["pullrequest"]
            pr_id = pr_data.get("id")
            pr_author = pr_data.get("author", {}).get("username", "unknown")
            
            # 저장소 정보 추출
            repo_info = data.get("repository", {})
            full_name = repo_info.get("full_name", "")
            if "/" in full_name:
                workspace, repo_slug = full_name.split("/", 1)
            else:
                workspace = repo_info.get("owner", {}).get("username", "")
                repo_slug = repo_info.get("name", "")
            
            # PR 작성자에 따른 맞춤 코멘트 선택
            # PR 작성자와 무관하게 고정 메시지 사용
            comment = PR_COMMENTS["default"]
            
            # PR에 코멘트 추가
            if add_pr_comment(workspace, repo_slug, pr_id, comment):
                logger.info(f"Successfully added comment to PR #{pr_id}")
            else:
                logger.error(f"Failed to add comment to PR #{pr_id}")
            
            return jsonify({
                "status": "success",
                "message": f"Processed PR creation and added comment"
            }), 200
            
        # 기존 push 이벤트 처리
        elif "actor" in data and "push" in data:
            commit_author = data["actor"].get("username", "unknown")
            
            # changes 배열 검증
            if not data["push"].get("changes"):
                logger.error("No changes in push data")
                return jsonify({"error": "No changes found in push data"}), 400

            change = data["push"]["changes"][0]
            if not change.get("new") or not change["new"].get("target"):
                logger.error("Invalid change data structure")
                return jsonify({"error": "Invalid change data"}), 400

            target = change["new"]["target"]
            commit_hash = target.get("hash", "")[:7]
            commit_url = target.get("links", {}).get("html", {}).get("href", "")

            if _platform == "darwin":
                custom_message = USER_MESSAGES.get(commit_author, f"{commit_author} committed {commit_hash}")
                message = f"{custom_message}\nClick to view in Bitbucket"
                Notifier.notify(
                    message=message,
                    title="Webhook received!",
                    open=commit_url
                )
            
            logger.info(f"Successfully processed webhook for commit {commit_hash} by {commit_author}")
            return jsonify({
                "status": "success",
                "data": {
                    "author": commit_author,
                    "commit": commit_hash,
                    "url": commit_url,
                    "message": USER_MESSAGES.get(commit_author, f"{commit_author} committed {commit_hash}")
                }
            }), 200
        
        else:
            logger.error("Unsupported webhook event")
            return jsonify({"error": "Unsupported webhook event"}), 400

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/webhook", methods=["GET"])
def webhook_info():
    """웹훅 상태 확인용 엔드포인트"""
    return jsonify({
        "status": "active",
        "message": "Bitbucket webhook endpoint is running. Configure your repository webhook to point to this URL."
    }) 