import requests
import logging
import os
from dotenv import load_dotenv
from pathlib import Path
from uptime_kuma_api import (
    UptimeKumaApi,
    MonitorType,
    UptimeKumaException,
    AuthMethod,
)
from uptime_kuma_api.exceptions import Timeout

UPTIME_KUMA_URL = "http://192.168.30.84:3001"
BASE_DIR = Path(__file__).resolve().parent

# Setup logging
logger = logging.getLogger("webmonitor_sync")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler = logging.FileHandler("/var/log/webmonitorsync/sync.log")
file_handler.setFormatter(formatter)
console_handler = logging.StreamHandler()
logger.addHandler(file_handler)
logger.addHandler(console_handler)


def get_haproxy_sites():
    headers = {"Authorization": f"Bearer {os.getenv('HAPROXY_API_KEY')}"}
    try:
        res = requests.get("https://aliveview.com/web/api/get_domains", headers=headers)
        res.raise_for_status()
        data = res.json()
        logger.info("Fetched list of sites from HAProxy")
        return [f"https://{site['domain']}" for site in data]
    except requests.exceptions.RequestException as e:
        logger.exception(str(e))
        return []


def get_uptimekuma_monitors():
    api = UptimeKumaApi(UPTIME_KUMA_URL)
    try:
        api.login(os.getenv("UPTIMEKUMA_USERNAME"), os.getenv("UPTIMEKUMA_PASSWORD"))
    except UptimeKumaException:
        logger.exception("Failed to authenticate with UptimeKuma")
        return []
    try:
        monitors = api.get_monitors()
    except Timeout:
        logger.error(
            "Timeout while fetching monitor list. The list is likely empty, therefore, returning an empty list."
        )
        return []
    urls = [m["url"] for m in monitors]
    logger.info("Fetched list of sites from UptimeKuma")
    api.disconnect()
    return urls


def update_uptime_kuma(sites):
    api = UptimeKumaApi(UPTIME_KUMA_URL)
    try:
        api.login(os.getenv("UPTIMEKUMA_USERNAME"), os.getenv("UPTIMEKUMA_PASSWORD"))
    except UptimeKumaException:
        logger.exception("Failed to authenticate with UptimeKuma")
        return []
    for site in sites:
        logger.info(f"Creating monitor for {site}")
        try:
            api.add_monitor(
                type=MonitorType.HTTP,
                name=site,
                description=None,
                url=site,
                method="GET",
                interval=60,
                retryInterval=30,
                resendInterval=0,
                maxretries=5,
                timeout=30,
                expiryNotification=False,
                ignoreTls=False,
                upsideDown=False,
                maxredirects=10,
                accepted_statuscodes=["200-299"],
                dns_resolve_type="A",
                dns_resolve_server="1.1.1.1",
                notificationIDList=[1],
                authMethod=AuthMethod.NONE,
                httpBodyEncoding="json",
            )
        except UptimeKumaException as e:
            logger.exception(f"Unable to create a monitor for {site}")


def main():
    logger.info("Starting sync")
    haproxy_list = get_haproxy_sites()
    uptimekuma_list = get_uptimekuma_monitors()
    missing_sites = [u for u in haproxy_list if u not in uptimekuma_list]
    if len(missing_sites) > 0:
        logger.info(f"Found the following new sites from HAProxy: {missing_sites}")
        update_uptime_kuma(missing_sites)
    else:
        logger.info("No new sites to add.")
    logger.info(f"Sync complete.")


if __name__ == "__main__":
    load_dotenv()
    main()
