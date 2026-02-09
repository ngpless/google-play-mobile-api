#!/usr/bin/env python3
"""
Google Play Mobile API Search - Drop-in replacement for google-play-scraper

Uses the official Android mobile API instead of web scraping.
Removes the 30-result limit by using pagination.

Requirements:
    pip install playstoreapi

Usage:
    from gplay_mobile_search import search, MobilePlayAPI
    
    # Initialize once (saves tokens for reuse)
    api = MobilePlayAPI()
    api.login_anonymous()  # or api.login(email, password)
    
    # Search with pagination
    results = api.search("vpn", n_hits=100, lang="en", country="us")
"""

import os
import json
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

try:
    from playstoreapi.googleplay import GooglePlayAPI
except ImportError:
    raise ImportError("Install playstoreapi: pip install -U git+https://github.com/AbhiTheModder/playstoreapi")


@dataclass
class AppInfo:
    """App information matching google-play-scraper format"""
    appId: str
    title: str
    score: Optional[float] = None
    developer: Optional[str] = None
    developerId: Optional[str] = None
    icon: Optional[str] = None
    installs: Optional[str] = None
    price: float = 0.0
    currency: str = "USD"
    free: bool = True
    summary: Optional[str] = None


class MobilePlayAPI:
    """
    Google Play Mobile API wrapper with pagination support.
    
    This uses the same API that Android devices use, bypassing
    the 30-result web scraping limit.
    """
    
    CONFIG_PATH = os.path.expanduser("~/.config/gplay_mobile_api.json")
    
    def __init__(self, locale: str = "en_US", timezone: str = "UTC", delay: float = 2.0):
        self.api = GooglePlayAPI(locale=locale, timezone=timezone, delay=delay)
        self._logged_in = False
        self.locale = locale
        self.delay = delay
        
    def _load_config(self) -> Optional[dict]:
        """Load saved tokens from config file"""
        if os.path.exists(self.CONFIG_PATH):
            try:
                with open(self.CONFIG_PATH, 'r') as f:
                    return json.load(f)
            except:
                pass
        return None
    
    def _save_config(self):
        """Save tokens to config file for reuse"""
        os.makedirs(os.path.dirname(self.CONFIG_PATH), exist_ok=True)
        config = {
            "gsfId": self.api.gsfId,
            "authSubToken": self.api.authSubToken,
            "deviceCheckinConsistencyToken": self.api.deviceCheckinConsistencyToken,
            "deviceConfigToken": self.api.deviceConfigToken,
            "dfeCookie": self.api.dfeCookie,
        }
        with open(self.CONFIG_PATH, 'w') as f:
            json.dump(config, f)
    
    def login_anonymous(self, force_new: bool = False) -> bool:
        """
        Login using Aurora Store's token dispenser (no Google account needed).
        Tokens are cached for reuse.
        
        Args:
            force_new: Force getting new tokens even if cached ones exist
            
        Returns:
            True if login successful
        """
        if not force_new:
            config = self._load_config()
            if config and config.get("gsfId") and config.get("authSubToken"):
                try:
                    self.api.login(
                        gsfId=int(config["gsfId"]),
                        authSubToken=config["authSubToken"],
                        check=True,
                        deviceCheckinConsistencyToken=config.get("deviceCheckinConsistencyToken"),
                        deviceConfigToken=config.get("deviceConfigToken"),
                        dfeCookie=config.get("dfeCookie"),
                    )
                    self._logged_in = True
                    return True
                except:
                    pass  # Tokens expired, get new ones
        
        # Get new anonymous tokens
        self.api.login(anonymous=True)
        self._save_config()
        self._logged_in = True
        return True
    
    def login(self, email: str, password: str) -> bool:
        """
        Login with Google account credentials.
        
        Note: May require app-specific password if 2FA is enabled.
        """
        self.api.login(email=email, password=password)
        self._save_config()
        self._logged_in = True
        return True
    
    def _parse_app(self, item: dict) -> Dict[str, Any]:
        """Convert mobile API response to google-play-scraper format"""
        # The mobile API returns nested structures
        # Extract relevant fields
        
        app_id = item.get("id") or item.get("docid") or ""
        title = ""
        score = None
        developer = None
        icon = None
        installs = None
        price = 0.0
        free = True
        summary = None
        
        # Navigate nested structure
        if "title" in item:
            title = item["title"]
        
        # Details can be in various places
        details = item.get("details", {}).get("appDetails", {})
        if details:
            developer = details.get("developerName")
            installs = details.get("numDownloads")
        
        # Aggregate rating
        agg = item.get("aggregateRating", {})
        if agg:
            score = agg.get("starRating")
        
        # Images
        images = item.get("image", [])
        for img in images:
            if img.get("imageType") == 4:  # App icon
                icon = img.get("imageUrl")
                break
        
        # Offer (price)
        offer = item.get("offer", [])
        if offer:
            first_offer = offer[0] if isinstance(offer, list) else offer
            if isinstance(first_offer, dict):
                micros = first_offer.get("micros", 0)
                if isinstance(micros, str):
                    micros = int(micros) if micros.isdigit() else 0
                price = micros / 1_000_000
                free = price == 0
        
        # Description snippet
        if "descriptionHtml" in item:
            summary = item["descriptionHtml"][:200]
        elif "descriptionShort" in item:
            summary = item["descriptionShort"]
        
        return {
            "appId": app_id,
            "title": title,
            "score": score,
            "developer": developer,
            "developerId": details.get("developerEmail", "").split("@")[0] if details.get("developerEmail") else None,
            "icon": icon,
            "installs": installs,
            "price": price,
            "currency": "USD",
            "free": free,
            "summary": summary,
        }
    
    def _extract_apps_from_response(self, data: list) -> tuple:
        """
        Extract apps and next page URL from search response.
        
        Returns:
            (list of apps, nextPageUrl or None)
        """
        apps = []
        next_page_url = None
        
        for doc in data:
            if not isinstance(doc, dict):
                continue
                
            # Check for nextPageUrl in containerMetadata
            container = doc.get("containerMetadata", {})
            if container.get("nextPageUrl"):
                next_page_url = container["nextPageUrl"]
            
            # Apps can be in subItem
            sub_items = doc.get("subItem", [])
            for cluster in sub_items:
                if not isinstance(cluster, dict):
                    continue
                    
                # Check for nextPageUrl in cluster
                cluster_container = cluster.get("containerMetadata", {})
                if cluster_container.get("nextPageUrl"):
                    next_page_url = cluster_container["nextPageUrl"]
                
                # Apps in cluster's subItem
                for app in cluster.get("subItem", []):
                    if isinstance(app, dict) and app.get("id"):
                        apps.append(self._parse_app(app))
            
            # Or directly as an app
            if doc.get("id") and not doc.get("subItem"):
                apps.append(self._parse_app(doc))
        
        return apps, next_page_url
    
    def search(
        self,
        query: str,
        n_hits: int = 50,
        lang: str = "en",
        country: str = "us"
    ) -> List[Dict[str, Any]]:
        """
        Search Google Play Store using mobile API.
        
        Args:
            query: Search query string
            n_hits: Maximum number of results (no 30 limit!)
            lang: Language code (en, ru, de, etc.)
            country: Country code (us, ru, de, etc.)
            
        Returns:
            List of app dictionaries matching google-play-scraper format
        """
        if not self._logged_in:
            self.login_anonymous()
        
        # Set locale based on lang/country
        locale = f"{lang}_{country.upper()}"
        self.api.setLocale(locale)
        
        all_apps = []
        next_page = None
        seen_ids = set()
        
        max_retries = 3
        
        while len(all_apps) < n_hits:
            # Make request with retry
            data = None
            for attempt in range(max_retries):
                try:
                    if next_page:
                        data = self.api.search(nextPageUrl=next_page)
                    else:
                        data = self.api.search(query=query)
                    break
                except Exception as e:
                    if "429" in str(e):
                        # Rate limited - wait and retry
                        wait_time = (attempt + 1) * 5
                        print(f"Rate limited, waiting {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"Search error: {e}")
                        break
            
            if data is None:
                break
            
            if not data:
                break
            
            # Extract apps
            apps, next_page = self._extract_apps_from_response(data)
            
            # Deduplicate and add
            for app in apps:
                app_id = app.get("appId")
                if app_id and app_id not in seen_ids:
                    seen_ids.add(app_id)
                    all_apps.append(app)
                    
                    if len(all_apps) >= n_hits:
                        break
            
            # No more pages
            if not next_page:
                break
        
        return all_apps[:n_hits]
    
    def details(self, package_name: str) -> Dict[str, Any]:
        """Get detailed info about an app by package name"""
        if not self._logged_in:
            self.login_anonymous()
        
        return self.api.details(package_name)


# Convenience function matching google-play-scraper interface
_default_api = None

def search(
    query: str,
    n_hits: int = 30,
    lang: str = "en",
    country: str = "us"
) -> List[Dict[str, Any]]:
    """
    Drop-in replacement for google_play_scraper.search()
    
    Same interface but uses mobile API - no 30-result limit!
    """
    global _default_api
    if _default_api is None:
        _default_api = MobilePlayAPI()
        _default_api.login_anonymous()
    
    return _default_api.search(query, n_hits, lang, country)


if __name__ == "__main__":
    # Test
    print("Testing Google Play Mobile API Search...")
    
    api = MobilePlayAPI()
    api.login_anonymous()
    
    results = api.search("vpn", n_hits=50, lang="en", country="us")
    print(f"\nFound {len(results)} apps for 'vpn':")
    
    for i, app in enumerate(results[:10], 1):
        print(f"{i}. {app['title']} ({app['appId']}) - {app['score']}")
    
    if len(results) > 30:
        print(f"\n✓ Success! Got {len(results)} results (more than 30 limit)")
    else:
        print(f"\n⚠ Got {len(results)} results")
