from flask import Flask, request, jsonify
import os
from sys import platform as _platform
import logging
import requests
from dotenv import load_dotenv

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
    "서진": "열심히 코딩하시네요! 👍",
    # "user2": "오늘도 좋은 코드 감사합니다! 🎉",
    # 더 많은 사용자와 메시지를 추가할 수 있습니다
}

# PR 코멘트 설정
PR_COMMENTS = {
    "default": "PR 검토 부탁드립니다! 🙏",
    "서진": "코드 리뷰 시작하겠습니다. 👀"
}

def add_pr_comment(workspace, repo_slug, pr_id, comment):
    """PR에 코멘트를 추가하는 함수"""
    if not BITBUCKET_AUTH_TOKEN:
        logger.error("Bitbucket authentication token not found")
        return False

    url = f"{BITBUCKET_API_URL}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
    headers = {
        "Authorization": f"Bearer {BITBUCKET_AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, json={"content": {"raw": comment}})
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error adding PR comment: {str(e)}")
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
        
        # PR 생성 이벤트 처리
        if data.get("pullrequest") and data.get("event") == "pullrequest:created":
            pr_data = data["pullrequest"]
            pr_id = pr_data.get("id")
            pr_author = pr_data.get("author", {}).get("username", "unknown")
            
            # 저장소 정보 추출
            repository = pr_data.get("destination", {}).get("repository", {})
            workspace = repository.get("workspace", {}).get("slug")
            repo_slug = repository.get("slug")
            
            # PR 작성자에 따른 맞춤 코멘트 선택
            comment = PR_COMMENTS.get(pr_author, PR_COMMENTS["default"])
            
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