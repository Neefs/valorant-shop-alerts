import json
import requests
from riot_auth import RiotAuth
import asyncio

USERNAME = ""
PASSWORD = ""

class Player(object):
    def __init__(self, auth_token, entitlement_token, puuid):
        self.auth_token = auth_token
        self.entitlement_token = entitlement_token
        self.puuid = puuid

with requests.Session() as s:
    r1 = s.get("https://valorant-api.com/v1/version")
    version = r1.json()["data"]["version"]

USER_AGENT = "RiotClient/{} %s (Windows;10;;Professional, x64)".format(version)
RiotAuth.RIOT_CLIENT_USER_AGENT = USER_AGENT

auth = RiotAuth()
asyncio.run(auth.authorize(USERNAME, PASSWORD))

def get_puuid(auth_token):
    with requests.Session() as session:
        headers = {
            "User-Agent": USER_AGENT,
            "Authorization": f"Bearer {auth_token}"
        }
        r = session.post("https://auth.riotgames.com/userinfo", headers=headers, json={})
        data = r.json()
        puuid = data['sub']
    return puuid

def get_skins(auth_token, entitlement_token, puuid, shard="na"):
    with requests.Session() as session:
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "X-Riot-Entitlements-JWT": entitlement_token,
            "Content-Type": "text/plain"
        }
        body = [puuid]
        r = session.get(f"https://pd.{shard}.a.pvp.net/store/v2/storefront/{puuid}", headers=headers, json=body)
        data = r.json()
    daily_shop = data["SkinsPanelLayout"]
    daily_items = daily_shop['SingleItemOffers']
    with requests.Session() as session:
        temp = []
        for i in daily_items:
            r = session.get(f"https://valorant-api.com/v1/weapons/skinlevels/{i}")
            if r.status_code == 200:
                data = r.json()["data"]
                temp.append(data["displayName"])
        daily_items = temp
            
    print("\n".join(daily_items))
        # with open("t.json", "w") as f:
        #     json.dump(data, f, indent=4)

def get_all_skins():
    with requests.Session() as session:
        r = session.get("https://valorant-api.com/v1/weapons/skinlevels")
        if r.status_code != 200:
            return r.json()
        data = r.json()["data"]
    skin_names = []
    for skin in data:
        if skin["displayName"].lower().find("level") > 0:
            continue
        skin_names.append(skin["displayName"])
    with open("skinnames.json", "w") as f:
        json.dump(skin_names, f, indent=4)
    # with open("skins.json", "w") as f:
    #     json.dump(data, f, indent=4)

get_all_skins()
get_skins(auth.access_token, auth.entitlements_token, get_puuid(auth.access_token))
