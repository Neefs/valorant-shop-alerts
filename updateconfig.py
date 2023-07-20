import json
import time
import requests
import difflib


class SkinAsset(object):
    def __init__(self, skinjson):
        for key in skinjson:
            setattr(self, key, skinjson[key])

    def __str__(self):
        return self.displayName

    @classmethod
    def from_uuid(cls, skin_uuid):
        with requests.Session() as session:
            r = session.get(
                f"https://valorant-api.com/v1/weapons/skinlevels/{skin_uuid}"
            )
            if r.status_code != 200:
                return r.json()
        return cls(r.json()["data"])


skins = []

with open("config.json", "r") as f:
    config = json.loads(f.read())


def save_config():
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)


def anything_else():
    print("\nAnything else? (y/n)\n")
    option = input("> ")
    if option.lower() == "n":
        return
    main()


def view_webhook():
    print(config["discordWebhookUrl"] + "\n\nPausing for 5 seconds.")
    time.sleep(5)
    anything_else()


def update_webhook():
    webhook = input("Enter discord webhook url: ")
    config["discordWebhookUrl"] = webhook
    print(f"Webhook changed to: {webhook}")
    save_config()
    anything_else()


def view_accounts():
    print("\n".join([acc["username"] for acc in config["accounts"]]))
    anything_else()


def add_account():
    username = input("username: ")
    password = input("password: ")
    config["accounts"].append({"username": username, "password": password})
    print(f"Account Created. Username: {username}")
    save_config()
    anything_else()


def remove_account():
    print("What is the username of the account you would like to remove?")
    username = input("> ").lower()
    acc_removed = False

    for acc in config["accounts"]:
        if acc["username"].lower() == username:
            config["accounts"].remove(acc)
            acc_removed = True
            break

    if acc_removed:
        save_config()
        print("Account removed successfully.")
    else:
        print("Account not found")

    anything_else()


def view_flagged_items():
    print(", ".join(str(SkinAsset.from_uuid(i)) for i in config["flaggedItems"]))
    anything_else()


def add_flagged_item():
    global skins
    # use difflib to find closest match if no skin is found with string and ask user if thats what they meant.
    if skins == []:
        with requests.Session() as session:
            r = session.get("https://valorant-api.com/v1/weapons/skinlevels")
            if r.status_code != 200:
                print(f"Error: {r.json()}")
                return anything_else()
        data = r.json()["data"]
        for skin in data:
            if skin["displayName"].lower().find("level") > 0:
                continue
            skins.append(SkinAsset(skin))
    skin_names = [i.displayName.lower() for i in skins]
    while True:
        added_skin = input("Skin name: ").lower()
        if added_skin not in skin_names:
            matches = difflib.get_close_matches(added_skin, skin_names)
            print(f'Did you mean "{matches[0]}"? (y/n)')
            t = input("> ")
            if t.lower() in ["y", "yes"]:
                added_skin = matches[0]
                break
        else:
            break
    config["flaggedItems"].append(skins[skin_names.index(added_skin)].uuid)
    save_config()
    print(f"{added_skin} added to flagged skins.")
    anything_else()


def remove_flagged_item():
    flagged_items = [SkinAsset.from_uuid(i) for i in config["flaggedItems"]]
    if flagged_items == []:
        print("No flagged items found")
        return anything_else()
    for i in flagged_items:
        print(f"{flagged_items.index(i)+1}. {i}\n")
    while True:
        item = input("select item number: ")
        if item.isdigit():
            if int(item) >= 1 or int(item) <= len(flagged_items):
                break

    config["flaggedItems"].remove(flagged_items[int(item) - 1].uuid)
    save_config()
    print("Item removed successfully.")

    anything_else()


def _exit():
    return


def main():
    while True:
        print(
            """
            1. View Webhook
            2. Update Webhook
            3. View accounts
            4. Add account
            5. Remove account
            6. View flagged items
            7. Add flagged item
            8. Remove flagged item
            9. Exit
            """.replace(
                "  ", ""
            )
        )
        option = input("> ")
        if option.isdigit():
            if int(option) >= 1 and int(option) <= 9:
                break
        print("Not valid entry.\n\n")

    options = {
        1: view_webhook,
        2: update_webhook,
        3: view_accounts,
        4: add_account,
        5: remove_account,
        6: view_flagged_items,
        7: add_flagged_item,
        8: remove_flagged_item,
        9: _exit,
    }
    options[int(option)]()


main()
