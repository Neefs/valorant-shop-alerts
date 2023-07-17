from discord_webhook import DiscordWebhook, DiscordEmbed
import json
import requests
from riot_auth import RiotAuth
import asyncio
from PIL import Image
import pystray
import threading
import time
import subprocess
import datetime

try:
    with open("config.json", "r") as f:
        config = json.loads(f.read())
except FileNotFoundError:
    print("Config not found. Make sure to rename default_config.json to config.json.")
    exit(1)

with requests.Session() as s:
    r1 = s.get("https://valorant-api.com/v1/version")
    version = r1.json()["data"]["version"]

USER_AGENT = "RiotClient/{} %s (Windows;10;;Professional, x64)".format(version)
RiotAuth.RIOT_CLIENT_USER_AGENT = USER_AGENT
image = Image.open("icon.png")


class SkinAsset(object):
    def __init__(self, skinjson):
        for key in skinjson:
            setattr(self, key, skinjson[key])
    def __str__(self):
        return self.displayName

    @classmethod
    def from_uuid(cls, skin_uuid):
        with requests.Session() as session:
            r = session.get(f"https://valorant-api.com/v1/weapons/skinlevels/{skin_uuid}")
            if r.status_code != 200:
                return r.json()
        return cls(r.json()["data"])

class Player(object):
    def __init__(self, riot_id, auth_token, entitlement_token, puuid, shard="na"):
        self.riot_id = riot_id
        self.auth_token = auth_token
        self.entitlement_token = entitlement_token
        self.puuid = puuid
        self.shard = shard
        
        self.vp, self.radianite, self.kingdomcredits = self.get_currencies(self.auth_token, self.entitlement_token, self.puuid)
        self.skins = []
        self.shop_expiry_time = None

    def __str__(self) -> str:
        return self.riot_id

    @staticmethod
    def authenticate(username, password) -> RiotAuth:
        auth = RiotAuth()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(auth.authorize(username, password))
        return auth
    
    @staticmethod
    def get_puuid_riotid(auth_token) -> tuple:
        """return a tuple with puuid and riotid"""
        with requests.Session() as session:
            headers = {
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {auth_token}"
            }
            r = session.post("https://auth.riotgames.com/userinfo", headers=headers, json={})
            data = r.json()
        return (data["sub"], f"{data['acct']['game_name']}#{data['acct']['tag_line']}")
    
    @staticmethod
    def get_currencies(auth_token, entitlement_token, puuid, shard="na") -> tuple:
        """returns a tuple with vp radiantite and kingdom credits"""
        headers = {'Authorization': f'Bearer {auth_token}', 'X-Riot-Entitlements-JWT': entitlement_token, 'Content-Type': 'text/plain'}
        with requests.Session() as s:
            r = s.get(f"https://pd.{shard}.a.pvp.net/store/v1/wallet/{puuid}", headers=headers)
            d = r.json()["Balances"]
        return (d['85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741'], d['e59aa87c-4cbf-517a-5983-6e81511be9b7'], d['85ca954a-41f2-ce94-9b45-8ca3dd39a00d'])


    @classmethod
    def from_username_password(cls, username, password):
        auth = cls.authenticate(username, password)
        puuid, riotid = cls.get_puuid_riotid(auth.access_token)
        return cls(riotid, auth.access_token, auth.entitlements_token, puuid)
    
    def get_shop(self) -> list[SkinAsset]:
        with requests.Session() as session:
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "X-Riot-Entitlements-JWT": self.entitlement_token,
                "Content-Type": "text/plain"
            }
            body = [self.puuid]
            r = session.get(f"https://pd.{self.shard}.a.pvp.net/store/v2/storefront/{self.puuid}", headers=headers, json=body)
            data = r.json()["SkinsPanelLayout"]
        if not self.shop_expiry_time:
            self.shop_expiry_time = data["SingleItemOffersRemainingDurationInSeconds"]
        self.skins = [SkinAsset.from_uuid(skinuuid) for skinuuid in data["SingleItemOffers"]]
        for skin in self.skins:
            skin.price = data["SingleItemStoreOffers"][self.skins.index(skin)]["Cost"]["85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741"]
        return self.skins




stop_thread = threading.Event()
config_updated = False
flagged_skins = [SkinAsset.from_uuid(i) for i in config["flaggedItems"]]

def handle_skin(skin:SkinAsset) -> bool:
    global flagged_skins
    if flagged_skins == []:
        flagged_skins = [SkinAsset.from_uuid(i) for i in config["flaggedItems"]]
    if skin.uuid in [i.uuid for i in flagged_skins]:
        return True
    return False

def send_webhook(content="‎", embed:DiscordEmbed=None):
    if not content and embed:
        return False
    webhook = DiscordWebhook(config["discordWebhookUrl"], username="Valorant Shop Alerts")
    if embed:
        webhook.add_embed(embed)
    webhook.set_content(content)
    webhook.execute()

def logic(accounts:list[Player]):
    global flagged_skins, config
    for account in accounts:
        for skin in account.get_shop():
            if not handle_skin(skin):
                continue
            else:
                e = DiscordEmbed(title=f"{skin.displayName} found")
                e.set_author(account.riot_id)
                if skin.displayIcon:
                    e.set_image(skin.displayIcon)
                if skin.streamedVideo:
                    e.add_embed_field(name="Video", value=skin.streamedVideo)
                expires_in = datetime.datetime.now() + datetime.timedelta(seconds=account.shop_expiry_time)
                e.add_embed_field(name="Expires in", value=f"<t:{round(expires_in.timestamp())}:R>")
                if hasattr(skin, "price"):
                    e.add_embed_field(name="Cost", value=skin.price, inline=False)
                send_webhook(embed=e)
                

    
    

def update_config():
    global flagged_skins, config_updated, config
    with open("config.json", "r") as f:
        nc = json.loads(f.read())
        if config != nc:
            config = nc
            flagged_skins = [SkinAsset.from_uuid(i) for i in config["flaggedItems"]]
            config_updated = True


def handle_accounts(accounts = list[dict]) -> list[Player]:
    good = []
    for account in accounts:
        username = account["username"]
        password = account["password"]
        try:
            p = Player.from_username_password(username, password)
            good.append(p)
        except:
            send_webhook(f"{username} has incorrect login information or 2fa(not supported currently).")
            continue
    print([i.riot_id for i in good])
    return good

def maintask():
    global flagged_skins, config_updated, config
    loop = asyncio.get_event_loop_policy().new_event_loop()
    asyncio.set_event_loop(loop)
    accounts = handle_accounts(config["accounts"])
    if len(accounts) >=1:
        while not stop_thread.is_set():
            if config_updated:
                accounts = handle_accounts(config["accounts"])
                config_updated = not config_updated
            if not accounts[0].shop_expiry_time or accounts[0].shop_expiry_time <= 0:
                logic(accounts)
            else:
                time.sleep(10)
                for i in accounts:
                    i.shop_expiry_time -= 10
                update_config()
    else:
        send_webhook("No accounts found")
    loop.close()




def handle_menu_item(icon:pystray.Icon, item):
    if str(item).lower() == "edit config":
        subprocess.call([".venv/Scripts/python.exe", "updateconfig.py"])
        #subprocess to run updateconfig.py
        pass
    if str(item).lower() == "exit":
        stop_thread.set()
        icon.stop()

icon = pystray.Icon("Valorant Shop Alerts", image, menu=pystray.Menu(
    pystray.MenuItem("Edit Config", handle_menu_item),
    pystray.MenuItem("Exit", handle_menu_item),
))

thread1 = threading.Thread(target=maintask, daemon=True)
thread2 = threading.Thread(target=icon.run)
thread1.start()
thread2.start()
thread1.join()
thread2.join()

