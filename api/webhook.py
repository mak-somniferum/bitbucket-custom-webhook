from flask import Flask, request, jsonify
import os
from sys import platform as _platform
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

if _platform == "darwin":
    from pync import Notifier

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
        
        # 데이터 구조 검증
        if "actor" not in data or "push" not in data:
            logger.error("Invalid webhook data structure")
            return jsonify({"error": "Invalid data structure"}), 400

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
            message = f"{commit_author} committed {commit_hash}\nClick to view in Bitbucket"
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
                "url": commit_url
            }
        }), 200

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