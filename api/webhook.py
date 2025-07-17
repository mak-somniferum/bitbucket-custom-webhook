from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
from sys import platform as _platform

# macOS 알림을 위한 조건부 임포트
if _platform == "darwin":
    from pync import Notifier

def handle_webhook(request_body):
    """웹훅 데이터를 처리하는 함수"""
    try:
        data = json.loads(request_body)
        
        # 데이터 구조 검증
        if "actor" not in data or "push" not in data:
            return {"error": "Invalid data structure"}, 400

        commit_author = data["actor"].get("username", "unknown")
        
        # changes 배열 검증
        if not data["push"].get("changes"):
            return {"error": "No changes found in push data"}, 400

        change = data["push"]["changes"][0]
        if not change.get("new") or not change["new"].get("target"):
            return {"error": "Invalid change data"}, 400

        target = change["new"]["target"]
        commit_hash = target.get("hash", "")[:7]
        commit_url = target.get("links", {}).get("html", {}).get("href", "")

        # macOS 알림 (로컬 개발 환경용)
        if _platform == "darwin":
            message = f"{commit_author} committed {commit_hash}\nClick to view in Bitbucket"
            Notifier.notify(
                message=message,
                title="Webhook received!",
                open=commit_url
            )

        return {
            "status": "success",
            "data": {
                "author": commit_author,
                "commit": commit_hash,
                "url": commit_url
            }
        }, 200

    except json.JSONDecodeError:
        return {"error": "Invalid JSON"}, 400
    except Exception as e:
        return {"error": str(e)}, 500

def handler(request):
    """Vercel Serverless Function handler"""
    if request.method == "POST":
        try:
            body = request.get_body().decode()
            response, status_code = handle_webhook(body)
            return {
                "statusCode": status_code,
                "body": json.dumps(response),
                "headers": {
                    "Content-Type": "application/json"
                }
            }
        except Exception as e:
            return {
                "statusCode": 500,
                "body": json.dumps({"error": str(e)}),
                "headers": {
                    "Content-Type": "application/json"
                }
            }
    else:
        return {
            "statusCode": 200,
            "body": "Bitbucket webhook endpoint is running. Configure your repository webhook to point to this URL.",
            "headers": {
                "Content-Type": "text/plain"
            }
        } 