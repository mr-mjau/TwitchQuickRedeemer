import requests
import json
import time
import sys
import uuid
import random
import math
import os
import heapq
import subprocess
import concurrent.futures
import configparser
from os import system
from collections import Counter

name = "Twitch Quick-redeemer"
system("title " + f"{name}")
version = 0.8

config = configparser.ConfigParser()
config.read("config.ini")


# ANSI color codes for formatting output
blue = "\033[94m"
green = "\033[92m"
yellow = "\033[93m"
red = "\033[91m"
white = "\033[0m"

# Replace these with values from your browser's Network tab
OAUTH_TOKEN = config.get("User_data", "Authorization")
CLIENT_ID = config.get("User_data", "Client_ID")
CLIENT_SESSION_ID = config.get("User_data", "Client_session_ID")

# URL for Twitch GraphQL API
DECAPI_URL = "https://decapi.me/twitch/id/{}"
TWITCH_GQL_URL = "https://gql.twitch.tv/gql"

# Base Referer URL for Twitch
REFERER_BASE = "https://www.twitch.tv/"

HEADERS = {
    "Authorization": f"OAuth {OAUTH_TOKEN}",
    "Client-ID": CLIENT_ID,
    "Client-Session-Id": CLIENT_SESSION_ID,
    "Referer": REFERER_BASE,
    "Content-Type": "application/json"
}

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

# Function to restart the script if "cancel" is entered
def restart_script():
    print("\n🔁 Resetting script in a moment...\n")
    time.sleep(3)
    main()

# Function to generate a Twitch-style transaction ID
def generate_transaction_id():
    return ''.join(random.choices('abcdef0123456789', k=32))  # 32-character hex string

def redeem_reward(channel_id, reward_id, reward_title, reward_cost, reward_prompt, user_input, debug=False):
    transaction_id = generate_transaction_id()

    payload = [{
        "operationName": "RedeemCustomReward",
        "variables": {
            "input": {
                "channelID": channel_id,
                "rewardID": reward_id,
                "transactionID": transaction_id,
                "cost": reward_cost,
                "prompt": reward_prompt,
                "title": reward_title,
                "textInput": user_input if user_input else None
            }
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "d56249a7adb4978898ea3412e196688d4ac3cea1c0c2dfd65561d229ea5dcc42"
            }
        }
    }]

    if debug:
        print(f"{yellow}[DEBUG]{white} Simulated redeem request for {red}'{reward_title}'{white}")
        print(json.dumps(payload, indent=4))
        return

    response = requests.post(TWITCH_GQL_URL, headers=HEADERS, json=payload)
    if response.status_code == 200:
        print(f"\u2705 Sent redeem request for '{reward_title}'")
    elif response.status_code == 401:
        print("\u274C Authentication error: Invalid or expired token.")
    elif response.status_code == 403:
        print("\u274C Forbidden: You do not have permission to redeem this reward.")
    elif response.status_code == 429:
        print("\u274C Rate limit exceeded! Try increasing the delay.")
    else:
        print(f"\u274C Error redeeming '{reward_title}': {response.text}")


def redeem_all_concurrently(redeem_list, delay_ms, debug=False):
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for r in redeem_list:
            futures.append(executor.submit(
                redeem_reward,
                r["channel_id"],
                r["reward_id"],
                r["reward_title"],
                r["reward_cost"],
                r["reward_prompt"],
                r["user_input"],
                debug
            ))
            time.sleep(delay_ms / 1000)  # Respect delay between submits
        concurrent.futures.wait(futures)

def redeem_all_accelerating(redeem_list, start_delay_ms, accel_percent, debug=False):
    delay = start_delay_ms
    min_delay = 50

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for r in redeem_list:
            futures.append(executor.submit(
                redeem_reward,
                r["channel_id"],
                r["reward_id"],
                r["reward_title"],
                r["reward_cost"],
                r["reward_prompt"],
                r["user_input"],
                debug
            ))
            if debug:
                print(f"{yellow}[DEBUG]{white} Waiting {red}{round(delay)}ms{white} before next task")
            time.sleep(delay / 1000)
            delay = max(min_delay, delay * (1 - accel_percent / 100))
        concurrent.futures.wait(futures)



warningMsg = """Excessive use of automated redeems may violate Twitch's Terms of Service.
As of Jan. 1, 2025, Twitch will automatically restrict accounts making 800 or more redeems/minute (75ms intervals).
Redeeming faster is possible, but only in limited quantities. Manual bans may occur at lower thresholds.
Use this script responsibly. The author is not liable for any actions taken against your account."""

def warn():
    from pathlib import Path

    app_name = "TwitchQuickRedeemer"
    config_dir = Path(os.getenv('APPDATA') if os.name == 'nt' else Path.home() / ".config") / app_name
    agreement_file = config_dir / "user_agreed.txt"

    if agreement_file.exists():
        main()  # User already agreed before

    clear_console()
    print(f"\n-------------- Warning --------------")
    print(f"{blue}{warningMsg}{white}")
    print("-------------------------------------\n")
    TOSagree = input("I understand [yes/no]: ").strip().lower()

    if TOSagree not in ["yes", "y", "agree"]:
        print(f"\n❌ You failed to agree. The script will now exit.")
        input(f"\nPress any key to exit...")
        sys.exit()
    else:
        config_dir.mkdir(parents=True, exist_ok=True)
        with open(agreement_file, "w") as f:
            f.write("User agreed to warning.\n")
        main()

def main():
    debug = False
    clear_console()
    # Step 1: Ask for the target channel name
    print(f"\nName: {blue}{name}{white}")
    print(f"Description: {blue}Redeems channel-point rewards using API-calls{white}")
    print(f"Version: {blue}{version}{white}")
    channel_name = input("\n🎯 Name of the channel to target: ").strip().lower()

    if len(channel_name) < 3:
        print("Not a valid username")
        restart_script()

    # Step 2: Fetch the channel ID dynamically using DecAPI
    print(f"\n🔄 Fetching channel ID for {yellow}{channel_name}{white}...")
    response = requests.get(DECAPI_URL.format(channel_name))

    if response.status_code == 200 and response.text.isdigit():
        channel_id = response.text.strip()
        print(f"✅ Successfully fetched Channel ID: {yellow}{channel_id}{white}")
        time.sleep(1)
    else:
        print(f"❌ Error fetching channel ID. Response: {red}{response.text}{white}")
        time.sleep(2)
        restart_script()

    # Update REFERER for this channel
    HEADERS["Referer"] = f"{REFERER_BASE}{channel_name}"

    # Payload to fetch available Channel Point rewards
    FETCH_PAYLOAD = [
        {
            "operationName": "ChannelPointsContext",
            "variables": {
                "channelLogin": channel_name,
                "includeGoalTypes": ["CREATOR", "BOOST"]
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "374314de591e69925fce3ddc2bcf085796f56ebb8cad67a0daa3165c03adc345"
                }
            }
        }
    ]

    # Send the request to fetch rewards
    response = requests.post(TWITCH_GQL_URL, headers=HEADERS, json=FETCH_PAYLOAD)

    clear_console()
    # Parse response
    try:
        data = response.json()
        
        # Extract Channel Point balance
        balance = data[0]["data"]["community"]["channel"]["self"]["communityPoints"]["balance"]
        f_balance = f"{balance:,}"
        
        # Extract custom rewards
        rewards = data[0]["data"]["community"]["channel"]["communityPointsSettings"]["customRewards"]
        enabled_rewards = [r for r in rewards if r["isEnabled"]]  # ✅ Filter enabled redeems only
        rewards_sorted = sorted(enabled_rewards, key=lambda x: x["cost"])  # Sort by cost (cheapest to most expensive)
        
        print(f"\nSelected channel: {blue}{channel_name}{white}")
        print(f"Channel-point balance: {blue}{f_balance}{white}\n")
        
        
        reward_dict = {}
        disabled_rewards = []
        shown_rewards = 0

        onlyNoCooldown = input(f"Do you want to {yellow}only list{white} redeems with {yellow}0s cooldown{white}? (Spammable redeems) [yes/no]: ").strip().lower()

        for index, reward in enumerate(rewards_sorted, start=1):
            title = reward["title"]
            cost = reward["cost"]
            f_cost = f"{cost:,}"
            prompt = reward["prompt"] if reward["prompt"] else ""
            cooldown = reward["globalCooldownSetting"]["globalCooldownSeconds"] if reward["globalCooldownSetting"]["isEnabled"] else 0
            max_affordable = balance // cost if cost > 0 else "-1"
            f_max_affordable = f"{max_affordable:,}"
            is_input_required = reward["isUserInputRequired"]
            is_enabled = reward["isEnabled"]

            if not is_enabled:
                disabled_rewards.append({
                    "index": index,
                    "title": title,
                    "cost": f_cost,
                    "cooldown": cooldown,
                    "input": is_input_required
                })
                continue  # Skip adding to selectable rewards

            if onlyNoCooldown in ["yes", "y", "1"] and reward["globalCooldownSetting"]["isEnabled"]:
                continue  # Skip non-zero cooldowns if filtered

            if is_input_required:
                print(f"{index}. {blue}{title}{white} | {green}Cost: {f_cost}{white} | {yellow}Cooldown: {cooldown}s{white} | {red}You can afford: {f_max_affordable}x{white} | Requires user input")
            else:
                print(f"{index}. {blue}{title}{white} | {green}Cost: {f_cost}{white} | {yellow}Cooldown: {cooldown}s{white} | {red}You can afford: {f_max_affordable}x{white}")

            reward_dict[index] = {
                "id": reward["id"],
                "title": title,
                "cost": cost,
                "prompt": prompt,
                "cooldown": cooldown,
                "max_affordable": max_affordable,
                "is_input_required": is_input_required
            }
            shown_rewards += 1

        if disabled_rewards:
            print(f"\n{yellow}Unavailable Redeems (disabled):{white}")
            for d in disabled_rewards:
                style = "\033[90m"  # ANSI gray
                end_style = white
                if d["input"]:
                    print(f"{style}{d['index']}. {d['title']} | Cost: {d['cost']} | Cooldown: {d['cooldown']}s | Requires input{end_style}")
                else:
                    print(f"{style}{d['index']}. {d['title']} | Cost: {d['cost']} | Cooldown: {d['cooldown']}s{end_style}")

        if onlyNoCooldown in ["yes", "y", "1"] and shown_rewards == 0:
            print(f"\n{red}No redeems without cooldown available for {channel_name}.{white}")
            input("Press Enter to restart the script...")
            restart_script()

    except KeyError as e:
        print(f"❌ Error fetching rewards: {e}")
        print("⚠️ Twitch may have changed the API structure or the request is missing authentication.")
        restart_script()

    if len(rewards_sorted) == 0:
        input("\nPress enter to reset ")
        restart_script()
    else:
        print("\n[Type 0 at any time to reset]\n")
    
    selected_rewards = []
    total_cost = 0  # Track total channel points required

    # Allow user to pick multiple redeems
    while True:
        try:
            chosen_number = int(input("🔢 Enter the number of a redeem to add (or 0 to finish): "))
            if chosen_number == 0:
                break
            elif chosen_number in reward_dict:
                selected_reward = reward_dict[chosen_number]
                reward_id = selected_reward["id"]
                reward_title = selected_reward["title"]
                reward_cost = selected_reward["cost"]
                reward_prompt = selected_reward["prompt"]
                max_affordable = selected_reward["max_affordable"]
                is_input_required = selected_reward["is_input_required"]

                if max_affordable == 0:
                    print(f"❌ You cannot afford '{reward_title}'. Please select a different redeem.")
                    continue

                # Ask how many times to redeem this
                while True:
                    try:
                        num_redeems = int(input(f"🧮 How many times to redeem '{reward_title}'? (Max: {max_affordable}): "))
                        if num_redeems == 0:
                            print("❌ Cannot redeem 0 times. Try again.")
                        elif num_redeems > max_affordable:
                            print(f"❌ Enter a number from 1 to {max_affordable}.")
                        else:
                            break
                    except ValueError:
                        print("❌ Please enter a valid number.")

                # Handle user input if required
                user_input = ""
                if is_input_required:
                    while True:
                        user_input = input("🖋️ Redeem requires user input: ").strip()
                        if len(user_input) < 1:
                            print("❌ Please enter a string.")
                        elif user_input == ".":
                            print("❌ The string '.' is known to cause conflict with some custom redeems.")
                        elif user_input == "0":
                            restart_script()
                        else:
                            break

                selected_rewards.append({
                    "id": reward_id,
                    "title": reward_title,
                    "num_redeems": num_redeems,
                    "cost": reward_cost,  # Total cost for this redeem
                    "prompt": reward_prompt,
                    "user_input": user_input  # Store user input
                })

                total_cost += reward_cost * num_redeems  # Update total cost
            else:
                print("❌ Invalid number. Please enter a valid option.")
        except ValueError:
            print("❌ Please enter a number.")

    if not selected_rewards:
        print("❌ No rewards selected. Resetting...")
        restart_script()

    #Check if the user has enough points
    if total_cost > balance:
        print(f"\n❌ Insufficient points. You need {red}{total_cost:,}{white} points, you only have {blue}{balance:,}{white}.")
        
        input("Press enter to reset... ")
        print(f"\n❌ Operation canceled.")
        restart_script()

    use_accel = input("\n⚡ Do you want to use accelerating redeems? [yes/no]: ").strip().lower()
    accel_mode = use_accel in ["yes", "y", "1"]

    if accel_mode:
        print(f"\nRedeems will keep accelerating until a redeem occurs every {red}50ms{white}.") 
        print(f"This is a reminder that making {red}excessive redeems{white} at this pace can result in a {red}ban{white}.")
        while True:
            try:
                start_delay = int(input("\n⌛ Starting delay between redeems (ms): "))
                if start_delay < 1000:
                    print("❌ Start delay must be at least 1s.")
                else:
                    break
            except ValueError:
                print("❌ Please enter a valid number.")

        while True:
            try:
                accel_percent = float(input("📉 Acceleration (% per redeem): "))
                if accel_percent <= 0 or accel_percent >= 50:
                    print("❌ Enter a percentage between 0 and 50.")
                else:
                    break
            except ValueError:
                print("❌ Please enter a valid percentage.")
    else:
        while True:
            try:
                delay_ms = int(input("⌛ Delay between redeems (ms): "))
                if delay_ms < 40:
                    print("❌ Twitch cannot keep up with too small of a delay. Minimum delay 40ms.")
                else:
                    break
            except ValueError:
                print("❌ Please enter a valid number.")

    if len(selected_rewards) > 1:
        print(f'\n⚠️ When redeeming multiple rewards, the order will be mixed randomly.')

    # Print a summary of what will be redeemed
    print("\n⚠️ You are about to redeem:")

    total_redeems = sum(r["num_redeems"] for r in selected_rewards)
    for r in selected_rewards:
        if r.get("user_input"):
            print(f"- {blue}{r['title']}{white} | {green}{r['num_redeems']} times{white} | With input {yellow}{r['user_input']}{white}")
        else:
            print(f"- {blue}{r['title']}{white} | {green}{r['num_redeems']} times{white}")

        
    if accel_mode:
        # Estimate total time using a geometric progression
        delay = start_delay
        total_ms = 0
        for _ in range(total_redeems):
            total_ms += delay
            delay = max(50, delay * (1 - accel_percent / 100))
        total_ms = round(total_ms)
    else:
        total_ms = delay_ms * total_redeems

    f_total_ms = f"{total_ms:,}"
    if accel_mode:
        print(f"- {yellow}Accelerating delay (start: {start_delay}ms, {accel_percent}%/redeem){white} | {red}Estimated {f_total_ms}ms total{white}")
    else:
        print(f"- {yellow}{delay_ms}ms delay{white} | {red}Totalling {f_total_ms}ms{white}")
    print(f"- {green}Cost {total_cost}{white} | Remaining {green}{balance - total_cost}{white}")

    confirmation = input("Please Confirm [yes/no/test]: ").strip().lower()

    if confirmation in ["test", "debug", "simulate"]:
        debug = True
    elif confirmation not in ["yes", "y", "1"]:
        print("❌ Operation canceled.")
        restart_script()


    # Step 1: Create a list of redeems in original order
    redemption_list = []
    for r in selected_rewards:
        redemption_list.extend([{
            "channel_id": channel_id,
            "reward_id": r["id"],
            "reward_title": r["title"],
            "reward_cost": r["cost"],
            "reward_prompt": r["prompt"],
            "user_input": r["user_input"]
        }] * r["num_redeems"])

    random.shuffle(redemption_list)  # Mixed redeem order

    print("\nStarting mixed redeems...")
    if accel_mode:
        redeem_all_accelerating(redemption_list, start_delay, accel_percent, debug)
    else:
        redeem_all_concurrently(redemption_list, delay_ms, debug)

    print("\n✅ All redemptions were attempted.")

    _reset = input("🔁 Reset script? [yes/exit]: ")
    if _reset in ["yes", "y", "1"]:
        restart_script()
    else:
        exit()

warn()