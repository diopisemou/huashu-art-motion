"""YouTube Data API v3: one-time OAuth, token refresh, resumable upload."""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from .config import Config

log = logging.getLogger("shorts.youtube")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]   # analytics: per-video retention for the format chooser
DEVICE_SCOPES = ["https://www.googleapis.com/auth/youtube"]   # the device-code flow only allows the broad YouTube scope


def _paths(cfg: Config) -> tuple[Path, Path]:
    secret = Path(os.environ.get("YT_CLIENT_SECRET", "secrets/client_secret.json"))
    token = Path(os.environ.get("YT_TOKEN", "secrets/token.json"))
    if not secret.is_absolute():
        secret = cfg.root / secret
    if not token.is_absolute():
        token = cfg.root / token
    return secret, token


def _save_token(token: Path, creds) -> Path:
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(creds.to_json())
    os.chmod(token, 0o600)
    log.info("saved token -> %s", token)
    print(f"\nToken saved to {token}.\nFor the cloud Routine / CI, paste the whole content of that file into the secret YT_TOKEN_JSON.")
    return token


def authorize(cfg: Config, device: bool = False) -> Path:
    """One-time, on a machine where you can open a browser. Default: local redirect server. --device: device-code
    flow (you type a short code at google.com/device), which works from any terminal, including a remote one."""
    secret, token = _paths(cfg)
    if not secret.exists():
        raise SystemExit(
            f"missing {secret}. In Google Cloud Console: enable 'YouTube Data API v3', create an OAuth client "
            "(Desktop app), download the JSON there. Add your Google account as a test user, or publish the app."
        )
    if device:
        return _save_token(token, _device_flow(secret))
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=False, prompt="consent", access_type="offline")
    return _save_token(token, creds)


def _device_flow(secret: Path):
    """OAuth 2.0 for limited-input devices. Needs an OAuth client of type 'TVs and Limited Input devices'
    (a Desktop client is refused with invalid_client; create the TV client in the same project and point
    YT_CLIENT_SECRET at its JSON)."""
    import requests
    from google.oauth2.credentials import Credentials

    cs = json.loads(secret.read_text())
    cs = cs.get("installed") or cs.get("web") or cs
    r = requests.post("https://oauth2.googleapis.com/device/code",
                      data={"client_id": cs["client_id"], "scope": " ".join(DEVICE_SCOPES)}, timeout=30)
    if r.status_code != 200:
        raise SystemExit(f"device flow refused ({r.status_code}): {r.text[:300]}\n"
                         "Use `shorts auth` (browser) instead, or create a 'TVs and Limited Input devices' OAuth client.")
    d = r.json()
    print(f"\n1. Open {d.get('verification_url', 'https://www.google.com/device')}\n2. Enter the code: {d['user_code']}\n"
          f"3. Sign in with the channel's Google account and approve.\nWaiting (code valid {d.get('expires_in', 1800) // 60} min)...")
    interval = int(d.get("interval", 5))
    deadline = time.time() + int(d.get("expires_in", 1800))
    while time.time() < deadline:
        time.sleep(interval)
        t = requests.post("https://oauth2.googleapis.com/token",
                          data={"client_id": cs["client_id"], "client_secret": cs["client_secret"], "device_code": d["device_code"],
                                "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}, timeout=30)
        j = t.json()
        if t.status_code == 200:
            return Credentials(token=j["access_token"], refresh_token=j.get("refresh_token"),
                               token_uri="https://oauth2.googleapis.com/token", client_id=cs["client_id"],
                               client_secret=cs["client_secret"], scopes=j.get("scope", " ".join(DEVICE_SCOPES)).split())
        err = j.get("error")
        if err == "slow_down":
            interval += 5
        elif err == "authorization_pending":
            continue
        else:
            raise SystemExit(f"device flow failed: {j}")
    raise SystemExit("device code expired; run `shorts auth --device` again")


def credentials(cfg: Config):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    _secret, token = _paths(cfg)
    raw = os.environ.get("YT_TOKEN_JSON")
    if raw:
        info = json.loads(raw)
    elif token.exists():
        info = json.loads(token.read_text())
    else:
        raise SystemExit("no YouTube token: run `shorts auth` once, or set YT_TOKEN_JSON")
    creds = Credentials.from_authorized_user_info(info, info.get("scopes") or SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            if not raw:
                token.write_text(creds.to_json())
        else:
            raise SystemExit("YouTube token is invalid and has no refresh token; run `shorts auth` again")
    return creds


def upload(cfg: Config, video: Path, *, title: str, description: str, tags: list[str],
           privacy: str | None = None, publish_at: str | None = None, dry_run: bool = False) -> dict:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    privacy = privacy or str(cfg.get("publish.privacy", "public"))
    publish_at = publish_at if publish_at is not None else (cfg.get("publish.publish_at") or "")
    status = {"privacyStatus": "private" if publish_at else privacy,
              "selfDeclaredMadeForKids": bool(cfg.get("publish.made_for_kids", False))}
    if publish_at:
        status["publishAt"] = publish_at  # RFC3339; YouTube flips private -> public at that time
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:30],
            "categoryId": str(cfg.get("publish.category_id", "28")),
            "defaultLanguage": cfg.language,
            "defaultAudioLanguage": cfg.language,
        },
        "status": status,
    }
    if dry_run:
        log.info("dry run: would upload %s with %s", video, json.dumps(body, ensure_ascii=False)[:400])
        return {"id": None, "dry_run": True, "body": body}

    yt = build("youtube", "v3", credentials=credentials(cfg), cache_discovery=False)
    media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media,
                             notifySubscribers=bool(cfg.get("publish.notify_subscribers", True)))
    response, retries = None, 0
    while response is None:
        try:
            status_, response = req.next_chunk()
            if status_:
                log.info("upload %d%%", int(status_.progress() * 100))
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retries < 6:
                retries += 1
                wait = 2 ** retries
                log.warning("upload hiccup %s, retrying in %ss", e.resp.status, wait)
                time.sleep(wait)
            else:
                raise
    vid = response["id"]
    log.info("uploaded: https://youtube.com/shorts/%s (%s)", vid, status["privacyStatus"])
    return {"id": vid, "url": f"https://youtube.com/shorts/{vid}", "privacy": status["privacyStatus"], "publish_at": publish_at or None}
