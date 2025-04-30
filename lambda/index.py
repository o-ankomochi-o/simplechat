# lambda/index.py
import json
import os
import re  # 正規表現モジュールをインポート
import urllib.request  # 独自APIにリクエストを送信するためのモジュール

from botocore.exceptions import ClientError


# Lambda コンテキストからリージョンを抽出する関数
def extract_region_from_arn(arn):
    # ARN 形式: arn:aws:lambda:region:account-id:function:function-name
    match = re.search("arn:aws:lambda:([^:]+):", arn)
    if match:
        return match.group(1)
    return "us-east-1"  # デフォルト値


# 独自のAPIのURL
API_URL = "https://145a-34-138-228-164.ngrok-free.app/predict"


def lambda_handler(event, context):
    try:
        # コンテキストから実行リージョンを取得
        region = extract_region_from_arn(context.invoked_function_arn)
        print(f"Function running in region: {region}")

        print("Received event:", json.dumps(event))

        # Cognitoで認証されたユーザー情報を取得
        user_info = None
        if "requestContext" in event and "authorizer" in event["requestContext"]:
            user_info = event["requestContext"]["authorizer"]["claims"]
            print(
                f"Authenticated user: {user_info.get('email') or user_info.get('cognito:username')}"
            )

        # リクエストボディの解析
        body = json.loads(event["body"])
        message = body["message"]
        conversation_history = body.get("conversationHistory", [])

        print("Processing message:", message)

        # 会話履歴を使用
        messages = conversation_history.copy()

        # ユーザーメッセージを追加
        messages.append({"role": "user", "content": message})

        # 独自APIへ送信するリクエストペイロードを構築
        request_payload = {
            "prompt": message,
            "conversation": messages,  # 会話履歴を送信
        }

        # リクエストのJSONデータを準備
        json_data = json.dumps(request_payload).encode("utf-8")

        print("Calling custom API with payload:", json.dumps(request_payload))

        # HTTPリクエストの作成
        req = urllib.request.Request(
            API_URL,
            data=json_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        # APIリクエストの送信と応答の取得
        with urllib.request.urlopen(req) as response:
            response_body = response.read()
            response_json = json.loads(response_body.decode("utf-8"))
            print("API response:", json.dumps(response_json, default=str))

            # APIからの応答を取得（APIの仕様に合わせて調整）
            assistant_response = response_json.get("response", "")

            # レスポンスの検証
            if not assistant_response:
                raise Exception("No response content from the API")

        # アシスタントの応答を会話履歴に追加
        messages.append({"role": "assistant", "content": assistant_response})

        # 成功レスポンスの返却
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST",
            },
            "body": json.dumps(
                {
                    "success": True,
                    "response": assistant_response,
                    "conversationHistory": messages,
                }
            ),
        }

    except Exception as error:
        print("Error:", str(error))

        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST",
            },
            "body": json.dumps({"success": False, "error": str(error)}),
        }
