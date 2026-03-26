import json
import logging
import os
from typing import Optional, Union

import requests
from playwright.sync_api import Browser, Playwright, sync_playwright

from discogs_alert import entities as da_entities, scrape as da_scrape

logger = logging.getLogger(__name__)


class Client:
    """API Client to interact with discogs server. Taken & modified from https://github.com/joalla/discogs_client."""

    _base_url = "https://api.discogs.com"
    _base_url_non_api = "https://www.discogs.com"
    _request_token_url = "https://api.discogs.com/oauth/request_token"
    _authorise_url = "https://www.discogs.com/oauth/authorize"
    _access_token_url = "https://api.discogs.com/oauth/access_token"

    def __init__(self, user_agent, *args, **kwargs):
        self.user_agent = user_agent
        self.verbose = False
        self.rate_limit = None
        self.rate_limit_used = None
        self.rate_limit_remaining = None

    def _request(self, method, url, data=None, headers=None):
        raise NotImplementedError

    def _get(self, url: str, is_api: bool = True):
        response_content, status_code = self._request("GET", url, headers=None)
        if status_code != 200:
            logger.info(f"ERROR: status_code: {status_code}, content: {response_content}")
            return False
        return json.loads(response_content) if is_api else response_content

    def _delete(self, url: str, is_api: bool = True):
        return self._request("DELETE", url)

    def _patch(self, url: str, data, is_api: bool = True):
        return self._request("PATCH", url, data=data)

    def _post(self, url: str, data, is_api: bool = True):
        return self._request("POST", url, data=data)

    def _put(self, url: str, data, is_api: bool = True):
        return self._request("PUT", url, data=data)

    def get_list(self, list_id: int) -> da_entities.UserList:
        user_list_dict = self._get(f"{self._base_url}/lists/{list_id}")
        user_list_dict["items"] = [da_entities.Release(**item) for item in user_list_dict["items"]]
        return da_entities.UserList(**user_list_dict)

    def get_listing(self, listing_id: int) -> da_entities.Listing:
        listing_dict = self._get(f"{self._base_url}/marketplace/listings/{listing_id}")
        return da_entities.Listing(**listing_dict)

    def get_release(self, release_id: int) -> da_entities.Release:
        release_dict = self._get(f"{self._base_url}/releases/{release_id}")
        return da_entities.Release(**release_dict)

    def get_release_stats(self, release_id: int) -> Union[da_entities.ReleaseStats, bool]:
        release_stats_dict = self._get(f"{self._base_url}/marketplace/stats/{release_id}")
        return da_entities.ReleaseStats(**release_stats_dict) if isinstance(release_stats_dict, dict) else False

    def get_wantlist(self, username: str):
        # TODO: add entities to deserialise this correctly
        url = f"{self._base_url}/users/{username}/wants"
        return self._get(url)


class UserTokenClient(Client):
    """A client for sending requests with a user token (for non-oauth authentication)."""

    def __init__(self, user_agent: str, user_token: str, *args, **kwargs):
        super().__init__(user_agent, *args, **kwargs)
        self.user_token = user_token

    def _request(self, method: str, url: str, data=None, headers=None):
        params = {"token": self.user_token}
        resp = requests.request(method, url, params=params, data=data, headers=headers)
        self.rate_limit = int(resp.headers.get("X-Discogs-Ratelimit"))
        self.rate_limit_used = int(resp.headers.get("X-Discogs-Ratelimit-Used"))
        self.rate_limit_remaining = int(resp.headers.get("X-Discogs-Ratelimit-Remaining"))
        return resp.content, resp.status_code


class AnonClient(Client):
    """A Client for anonymous scraping requests (when not using the Discogs API, i.e. for the marketplace).

    Uses Playwright to render marketplace pages. Launches headless Firefox by default
    (Chromium gets blocked by Cloudflare's bot detection). Can connect to an external
    CDP endpoint via DA_CDP_ENDPOINT for Chromium-based browsers if needed.
    """

    def __init__(self, user_agent: str, *args, **kwargs):
        super().__init__(user_agent, *args, **kwargs)
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._connect()

    def _connect(self):
        self._playwright = sync_playwright().start()
        cdp_endpoint = os.getenv("DA_CDP_ENDPOINT")

        if cdp_endpoint:
            logger.info(f"Connecting to external CDP endpoint: {cdp_endpoint}")
            self._browser = self._playwright.chromium.connect_over_cdp(cdp_endpoint)
        else:
            logger.info("Launching headless Firefox via Playwright")
            self._browser = self._playwright.firefox.launch(headless=True)

    def close(self):
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def get_marketplace_listings(self, release_id: int) -> da_entities.Listings:
        """Get list of listings currently for sale for particular release (by release's discogs ID)"""
        page = self._browser.new_page()
        try:
            page.goto(
                f"{self._base_url_non_api}/sell/release/{release_id}?ev=rb&sort=price%2Casc",
                wait_until="load",
                timeout=60000,
            )
            # Cloudflare may challenge first; wait for the marketplace table to appear
            page.wait_for_selector("table.mpitems", timeout=30000)
            html = page.content()
        finally:
            page.close()
        return da_scrape.scrape_listings_from_marketplace(html, release_id)
