# fatsecret.py

import requests
from datetime import datetime, timedelta
from prisma import Prisma
from prisma.models import FatSecretToken
from dotenv import load_dotenv
import os

load_dotenv()

FATSECRET_CLIENT_ID = os.getenv("FATSECRET_CLIENT_ID")
FATSECRET_CLIENT_SECRET = os.getenv("FATSECRET_CLIENT_SECRET")
FATSECRET_BASE_URL = "https://oauth.fatsecret.com"

# Получить токен по клиентским ключам (OAuth2 client_credentials)
def get_client_token():
    response = requests.post(
        f"{FATSECRET_BASE_URL}/connect/token",
        data={
            "grant_type": "client_credentials",
            "scope": "basic",
        },
        auth=(FATSECRET_CLIENT_ID, FATSECRET_CLIENT_SECRET),
    )
    return response.json()

# Сохранить токен в базу
async def save_user_token(tg_id: int, token_data: dict):
    db = Prisma()
    await db.connect()
    user = await db.user.find_unique(where={"tg_id": tg_id})
    if not user:
        await db.disconnect()
        return  # или кинуть ошибку

    expires_in = int(token_data.get("expires_in", 3600))
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    await db.fatsecrettoken.upsert(
    where={"userId": user.id},
    data={
        "create": {
            "user": {"connect": {"id": user.id}},
            "accessToken": token_data["access_token"],
            "refreshToken": token_data.get("refresh_token", ""),
            "expiresAt": expires_at,
            "scope": token_data.get("scope"),
            "tokenType": token_data.get("token_type"),
        },
        "update": {
            "accessToken": token_data["access_token"],
            "refreshToken": token_data.get("refresh_token", ""),
            "expiresAt": expires_at,
            "scope": token_data.get("scope"),
            "tokenType": token_data.get("token_type"),
        },
    },
)


    await db.disconnect()

# Получить access_token из базы (если живой)
async def get_user_token(user_id: int) -> str | None:
    db = Prisma()
    await db.connect()
    token = await db.fatsecrettoken.find_unique(where={"userId": user_id})
    await db.disconnect()

    if not token or token.expiresAt < datetime.utcnow():
        return None

    return token.accessToken
async def get_food_entries(access_token: str, date: str = None):
    """
    Получить записи питания пользователя (дата в формате YYYY-MM-DD, по умолчанию сегодня).
    """
    if date is None:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    response = requests.get(
        "https://platform.fatsecret.com/rest/server.api",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        params={
            "method": "food_entries.get.v2",
            "format": "json",
            "date": date,
        },
    )
    return response.json()


from urllib.parse import urlencode

def build_authorize_url(user_id: int) -> str:
    """
    Построить ссылку авторизации через OAuth (Authorization Code Flow).
    Пользователь должен перейти по ссылке и авторизоваться.
    """
    params = {
        "client_id": FATSECRET_CLIENT_ID,
        "response_type": "code",
        "scope": "basic",
        "state": str(user_id),
        "redirect_uri": "https://yourdomain.com/fatsecret/callback",  # <- замени на свой redirect URI
    }
    return f"https://www.fatsecret.com/oauth/authorize?{urlencode(params)}"

