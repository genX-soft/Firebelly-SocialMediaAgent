from fastapi import Depends, FastAPI, HTTPException, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
import hmac
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update, text, func
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
import shutil
import hashlib
import secrets
from typing import Literal
from datetime import datetime, timedelta
import os
from urllib.parse import urlencode
import json
import urllib.error
import urllib.request
import requests
import asyncio

# # --- FIREBELLY AI CHATBOT ---
# try:
#     from .ai_reply import generate_ai_reply, should_auto_reply
# except ImportError:
#     from ai_reply import generate_ai_reply, should_auto_reply
# # ----------------------------

# --- FIREBELLY LANGGRAPH REPLY AGENT ---
import os
try:
  from .agents.reply_agent import generate_reply
except ImportError:
  from agents.reply_agent import generate_reply
 
RESTAURANT_ID = os.getenv("RESTAURANT_ID", os.getenv("TENANT_ID", ""))
    # ----------------------------------------

try:
  from .db import Base, engine, get_db, SessionLocal
  from .models import User, SocialAccount, Post, Interaction
except ImportError:
  from db import Base, engine, get_db, SessionLocal
  from models import User, SocialAccount, Post, Interaction

try:
    from .agents.content_agent import generate_content
except ImportError:
    from agents.content_agent import generate_content

# from pyngrok import ngrok

app = FastAPI(title="AutoSocial API")

# Startup event to setup ngrok tunnel
@app.on_event("startup")
async def startup_event():
    # Read the live ngrok tunnel URL from the local ngrok API
    # (since ngrok is already running manually in a separate terminal)
    try:
        import urllib.request, json
        with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=3) as resp:
            data = json.loads(resp.read().decode())
            for tunnel in data.get("tunnels", []):
                url = tunnel.get("public_url", "")
                if url.startswith("https://"):
                    os.environ["API_BASE_URL"] = url
                    print(f"--- NGROK TUNNEL DETECTED: {url} ---")
                    break
    except Exception as e:
        print(f"--- Could not read ngrok tunnel (is ngrok running?): {e} ---")
        print(f"--- Using API_BASE_URL from .env: {os.getenv('API_BASE_URL')} ---")

    # Start the scheduled post worker
    asyncio.create_task(_scheduled_post_worker())

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=False,
  allow_methods=["*"],
  allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
  os.makedirs(UPLOAD_DIR)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
  file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
  unique_filename = f"{secrets.token_hex(8)}{file_ext}"
  file_path = os.path.join(UPLOAD_DIR, unique_filename)
  
  with open(file_path, "wb") as buffer:
    shutil.copyfileobj(file.file, buffer)
    
  # In a real app, this should be the full external URL
  base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
  return {"url": f"{base_url}/uploads/{unique_filename}"}


class SignupRequest(BaseModel):
  name: str = Field(..., min_length=2, max_length=80)
  email: EmailStr
  password: str = Field(..., min_length=8, max_length=128)
  company: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
  email: EmailStr
  password: str = Field(..., min_length=8, max_length=128)


class AuthResponse(BaseModel):
  access_token: str
  token_type: str = "bearer"
  user: dict


class AccountCreateRequest(BaseModel):
  user_email: EmailStr
  platform: Literal["facebook", "instagram"]
  external_id: str = Field(..., min_length=2, max_length=128)
  page_name: str | None = Field(default=None, max_length=120)
  instagram_username: str | None = Field(default=None, max_length=120)
  profile_picture_url: str | None = Field(default=None, max_length=500)


class AccountDisconnectRequest(BaseModel):
  account_id: str = Field(..., min_length=2, max_length=128)
  user_email: EmailStr


class PostCreateRequest(BaseModel):
  user_email: EmailStr
  caption: str = Field(..., min_length=1, max_length=2000)
  media_url: str | None = Field(default=None, max_length=500)
  media_type: Literal["image", "video"] = "image"
  hashtags: str | None = Field(default=None, max_length=500)
  emojis: str | None = Field(default=None, max_length=200)
  targets: list[Literal["facebook", "instagram"]] = Field(default_factory=list)
  scheduled_at: datetime | None = None


class PostResponse(BaseModel):
  id: str
  user_email: EmailStr
  caption: str
  media_url: str | None
  media_type: str
  hashtags: str | None
  emojis: str | None
  targets: list[str]
  status: str
  error_message: str | None = None
  scheduled_at: datetime | None


class AccountsRefreshResponse(BaseModel):
  refreshed: int
  updated: int
  errors: list[dict]


class InteractionResponse(BaseModel):
  id: str
  platform: str
  external_id: str
  content: str
  sender_name: str | None
  type: str
  created_at: datetime


class PaginatedInteractions(BaseModel):
  data: list[InteractionResponse]
  total: int


class ReplyRequest(BaseModel):
  user_email: EmailStr
  platform: str
  external_id: str  # ID of the comment or message being replied to
  content: str

class AiSuggestRequest(BaseModel):
    user_email: EmailStr
    external_id: str
    platform: str
    message: str
    sender_name: str | None = None
    interaction_type: str = "message"


class MetricPoint(BaseModel):
  date: str
  value: int

class AnalyticsSummary(BaseModel):
  reach: int = 0
  engagement: int = 0
  follower_growth: int = 0
  top_posts: list[dict] = []
  engagement_over_time: list[MetricPoint] = []
  platform: str

class PostInsight(BaseModel):
  post_id: str
  platform: str
  fb_post_id: str | None = None
  ig_media_id: str | None = None
  caption: str
  media_url: str | None = None
  created_at: datetime
  likes: int = 0
  comments: int = 0
  shares: int = 0
  saves: int = 0
  reach: int = 0
  impressions: int = 0
  status: str = ""

class ContentGenerateRequest(BaseModel):
    mode: Literal["idea", "image", "surprise"]
    owner_idea: str | None = None
    image_url: str | None = None
    language: str = "auto"
    user_email: EmailStr
 
class ContentPublishRequest(BaseModel):
    user_email: EmailStr
    caption: str = Field(..., min_length=1, max_length=2000)
    hashtags: str | None = None
    media_url: str | None = None
    media_type: Literal["image", "video"] = "image"
    targets: list[Literal["facebook", "instagram"]] = Field(default_factory=list)
    scheduled_at: datetime | None = None


oauth_states: dict[str, dict] = {}




def _hash_password(password: str, salt: str) -> str:
  digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
  return digest.hex()


def _issue_token() -> str:
  return secrets.token_urlsafe(24)


def _post_to_dict(post: Post) -> dict:
  return {
    "id": post.id,
    "user_email": post.user_email,
    "caption": post.caption,
    "media_url": post.media_url,
    "media_type": post.media_type,
    "hashtags": post.hashtags,
    "emojis": post.emojis,
    "targets": post.targets.split(",") if post.targets else [],
    "status": post.status,
    "error_message": post.error_message,
    "scheduled_at": post.scheduled_at,
  }


def _interaction_to_dict(interaction: Interaction) -> dict:
  return {
    "id": interaction.id,
    "user_email": interaction.user_email,
    "platform": interaction.platform,
    "external_id": interaction.external_id,
    "content": interaction.content,
    "sender_name": interaction.sender_name,
    "type": interaction.type,
    "is_outgoing": interaction.is_outgoing,
    "created_at": interaction.created_at,
  }


def _get_fb_page_insights(access_token: str, page_id: str, days: int = 30):
  """Fetch Facebook Page insights from Meta Graph API."""
  endpoint = f"https://graph.facebook.com/v19.0/{page_id}/insights"
  params = {
    "metric": "page_post_engagements,page_impressions,page_fan_adds_unique",
    "period": "day",
    "access_token": access_token,
    "since": int((datetime.utcnow() - timedelta(days=days)).timestamp()),
    "until": int(datetime.utcnow().timestamp())
  }
  try:
    response = requests.get(endpoint, params=params)
    data = response.json()
    return data.get("data", [])
  except Exception as e:
    print(f"DEBUG [Analytics]: Error fetching FB insights: {e}")
    return []


def _get_ig_account_insights(access_token: str, ig_id: str, days: int = 30):
  """Fetch Instagram Business Account insights."""
  endpoint = f"https://graph.facebook.com/v19.0/{ig_id}/insights"
  params = {
    "metric": "impressions,reach,profile_views",
    "period": "day",
    "access_token": access_token,
    "since": int((datetime.utcnow() - timedelta(days=days)).timestamp()),
    "until": int(datetime.utcnow().timestamp())
  }
  try:
    response = requests.get(endpoint, params=params)
    data = response.json()
    return data.get("data", [])
  except Exception as e:
    print(f"DEBUG [Analytics]: Error fetching IG insights: {e}")
    return []


@app.get("/analytics/summary", response_model=list[AnalyticsSummary])
async def get_analytics_summary(user_email: EmailStr, db: Session = Depends(get_db)):
  email = user_email.lower().strip()
  accounts = db.execute(
    select(SocialAccount).where(
      SocialAccount.user_email == email,
      SocialAccount.is_connected == True
    )
  ).scalars().all()
  
  if not accounts:
    return []
    
  all_summaries = []
  
  for account in accounts:
    summary = AnalyticsSummary.model_validate({"platform": account.platform})
    
    if account.platform == "facebook":
      insights = _get_fb_page_insights(account.access_token, account.external_id, days=30)
      daily_data = {}
      for metric in insights:
        name = metric.get("name")
        values = metric.get("values", [])
        for val in values:
          date_str = val.get("end_time")[:10]  # YYYY-MM-DD
          if date_str not in daily_data: daily_data[date_str] = {"reach": 0, "engagement": 0}
          if name == "page_impressions":
            daily_data[date_str]["reach"] += val.get("value", 0)
            summary.reach += val.get("value", 0)
          elif name == "page_post_engagements":
            daily_data[date_str]["engagement"] += val.get("value", 0)
            summary.engagement += val.get("value", 0)
          elif name == "page_fan_adds_unique":
            summary.follower_growth += val.get("value", 0)
      
      for date in sorted(daily_data.keys()):
        summary.engagement_over_time.append(MetricPoint(date=date, value=daily_data[date]["engagement"]))
            
    elif account.platform == "instagram":
      insights = _get_ig_account_insights(account.access_token, account.external_id, days=30)
      daily_data = {}
      for metric in insights:
        name = metric.get("name")
        values = metric.get("values", [])
        for val in values:
          date_str = val.get("end_time")[:10]
          if date_str not in daily_data: daily_data[date_str] = {"reach": 0, "engagement": 0}
          if name == "impressions":
            daily_data[date_str]["reach"] += val.get("value", 0)
            summary.reach += val.get("value", 0)
          elif name == "reach":
            daily_data[date_str]["engagement"] += val.get("value", 0)
            summary.engagement += val.get("value", 0)
      
      for date in sorted(daily_data.keys()):
        summary.engagement_over_time.append(MetricPoint(date=date, value=daily_data[date]["reach"]))

    all_summaries.append(summary)
    
  return all_summaries


@app.get("/analytics/top-posts")
async def get_top_posts(user_email: EmailStr, limit: int = 5, db: Session = Depends(get_db)):
  email = user_email.lower().strip()
  posts = db.execute(
    select(Post).where(Post.user_email == email, Post.status == "published")
    .order_by(Post.created_at.desc())
    .limit(limit)
  ).scalars().all()
  return [_post_to_dict(p) for p in posts]


@app.get("/analytics/post-insights")
async def get_post_insights(user_email: EmailStr, limit: int = 20, db: Session = Depends(get_db)):
        """
        Per-post metrics: likes, comments, shares, saves, reach, impressions.
        Fetches live from Meta for published posts that have a platform ID.
        Falls back to 0s if Meta API is unavailable (e.g. permissions pending).
        """
        email = user_email.lower().strip()
        posts = db.execute(
            select(Post).where(
                Post.user_email == email,
                Post.status == "published"
            ).order_by(Post.created_at.desc()).limit(limit)
        ).scalars().all()
 
        if not posts:
            return []
 
        graph_base = _get_graph_base_url()
        results = []
 
        for post in posts:
            insight = PostInsight(
                post_id=post.id,
                platform="facebook" if post.fb_post_id else "instagram" if post.ig_media_id else "unknown",
                fb_post_id=post.fb_post_id,
                ig_media_id=post.ig_media_id,
                caption=post.caption[:120] + ("..." if len(post.caption) > 120 else ""),
                media_url=post.media_url,
                created_at=post.created_at,
                status=post.status,
            )
 
            # Get account access token
            platform = "facebook" if post.fb_post_id else "instagram"
            account = db.execute(
                select(SocialAccount).where(
                    SocialAccount.user_email == email,
                    SocialAccount.platform == platform,
                    SocialAccount.is_connected == True
                )
            ).scalar_one_or_none()
 
            if not account or not account.access_token:
                results.append(insight)
                continue
 
            try:
                if post.fb_post_id:
                    # Facebook post insights
                    data = _http_get_json(
                        f"{graph_base}/{post.fb_post_id}",
                        {
                            "fields": "likes.summary(true),comments.summary(true),shares,impressions,reach",
                            "access_token": account.access_token,
                        }
                    )
                    insight.likes       = data.get("likes", {}).get("summary", {}).get("total_count", 0)
                    insight.comments    = data.get("comments", {}).get("summary", {}).get("total_count", 0)
                    insight.shares      = data.get("shares", {}).get("count", 0)
                    insight.impressions = data.get("impressions", 0)
                    insight.reach       = data.get("reach", 0)
 
                elif post.ig_media_id:
                    # Instagram media insights
                    data = _http_get_json(
                        f"{graph_base}/{post.ig_media_id}",
                        {
                            "fields": "like_count,comments_count,media_url,thumbnail_url",
                            "access_token": account.access_token,
                        }
                    )
                    insight.likes    = data.get("like_count", 0)
                    insight.comments = data.get("comments_count", 0)
 
                    # IG insights endpoint for reach/impressions/saves
                    try:
                        ig_ins = _http_get_json(
                            f"{graph_base}/{post.ig_media_id}/insights",
                            {
                                "metric": "impressions,reach,saved",
                                "access_token": account.access_token,
                            }
                        )
                        for metric in ig_ins.get("data", []):
                            name = metric.get("name")
                            val  = metric.get("values", [{}])[0].get("value", 0) if metric.get("values") else metric.get("value", 0)
                            if name == "impressions": insight.impressions = val
                            elif name == "reach":     insight.reach       = val
                            elif name == "saved":     insight.saves       = val
                    except Exception:
                        pass  # insights need extra permissions — degrade gracefully
 
            except Exception as e:
                print(f"WARNING [Post Insights]: Could not fetch for {post.id}: {e}")
 
            results.append(insight)
 
        return [r.model_dump() for r in results]
 

@app.delete("/inbox/comment/{external_id}")
def delete_comment(external_id: str, user_email: EmailStr, db: Session = Depends(get_db)):
        """
        Delete/hide a comment on Facebook or Instagram.
        Facebook: permanent delete via Graph API.
        Instagram: hidden via Graph API (Instagram doesn't support full delete).
        """
        email = user_email.lower().strip()
        interaction = db.execute(
            select(Interaction).where(
                Interaction.external_id == external_id,
                func.lower(Interaction.user_email) == email
            )
        ).scalar_one_or_none()
 
        if not interaction:
            raise HTTPException(status_code=404, detail="Comment not found")
 
        account = db.execute(
            select(SocialAccount).where(
                SocialAccount.user_email == email,
                SocialAccount.platform == interaction.platform,
                SocialAccount.is_connected == True
            )
        ).scalar_one_or_none()
 
        if not account or not account.access_token:
            raise HTTPException(status_code=400, detail=f"No connected account for {interaction.platform}")
 
        graph_base = _get_graph_base_url()
 
        try:
            if interaction.platform == "facebook":
                # DELETE /{comment-id} permanently removes it
                _http_post_json(
                    f"{graph_base}/{external_id}",
                    {"method": "delete", "access_token": account.access_token}
                )
            elif interaction.platform == "instagram":
                # Instagram: hide the comment (closest to delete available via API)
                _http_post_json(
                    f"{graph_base}/{external_id}",
                    {"hide": "true", "access_token": account.access_token}
                )
        except HTTPException as e:
            # If Meta API fails, still remove from local DB
            print(f"WARNING: Meta API comment delete failed: {e.detail}")
 
        # Remove from local DB regardless
        db.delete(interaction)
        db.commit()
 
        return {
            "status": "deleted",
            "platform": interaction.platform,
            "note": "Removed from inbox. Instagram comments are hidden on platform (Meta API limitation)."
            if interaction.platform == "instagram"
            else "Permanently deleted from Facebook."
        }
 
 
@app.get("/analytics/account-stats")
async def get_account_stats(user_email: EmailStr, db: Session = Depends(get_db)):
        """
        Live account-level stats: followers, following, total posts, profile views.
        Fetches directly from Meta — use the Refresh button, not auto-poll.
        """
        email = user_email.lower().strip()
        accounts = db.execute(
            select(SocialAccount).where(
                SocialAccount.user_email == email,
                SocialAccount.is_connected == True
            )
        ).scalars().all()
 
        if not accounts:
            return []
 
        graph_base = _get_graph_base_url()
        results = []
 
        for account in accounts:
            stat = {
                "platform": account.platform,
                "name": account.page_name or account.instagram_username,
                "profile_picture_url": account.profile_picture_url,
                "followers": 0,
                "following": 0,
                "total_posts": 0,
                "profile_views": 0,
            }
 
            if not account.access_token:
                results.append(stat)
                continue
 
            try:
                if account.platform == "facebook":
                    data = _http_get_json(
                        f"{graph_base}/{account.external_id}",
                        {
                            "fields": "fan_count,followers_count",
                            "access_token": account.access_token,
                        }
                    )
                    stat["followers"] = data.get("fan_count", data.get("followers_count", 0))
 
                elif account.platform == "instagram":
                    data = _http_get_json(
                        f"{graph_base}/{account.external_id}",
                        {
                            "fields": "followers_count,follows_count,media_count,profile_views",
                            "access_token": account.access_token,
                        }
                    )
                    stat["followers"]     = data.get("followers_count", 0)
                    stat["following"]     = data.get("follows_count", 0)
                    stat["total_posts"]   = data.get("media_count", 0)
                    stat["profile_views"] = data.get("profile_views", 0)
 
            except Exception as e:
                print(f"WARNING [Account Stats]: {account.platform}: {e}")
 
            results.append(stat)
 
        return results


def _get_oauth_config(platform: str) -> dict:
  authorize_url = os.getenv("META_OAUTH_AUTHORIZE_URL", "").strip()
  app_id = os.getenv("META_APP_ID", "").strip()
  redirect_uri = os.getenv("META_REDIRECT_URI", "").strip()
  frontend_redirect = os.getenv("META_FRONTEND_REDIRECT_URI", "").strip()
  scopes = os.getenv(
    "META_OAUTH_SCOPES_FACEBOOK" if platform == "facebook" else "META_OAUTH_SCOPES_INSTAGRAM",
    "",
  ).strip()

  if not authorize_url or not app_id or not redirect_uri:
    raise HTTPException(status_code=500, detail="Meta OAuth is not configured")

  return {
    "authorize_url": authorize_url,
    "app_id": app_id,
    "redirect_uri": redirect_uri,
    "frontend_redirect": frontend_redirect,
    "scopes": scopes,
  }


def _http_post_json(url: str, params: dict) -> dict:
  """Send a POST request with form-encoded params to the Graph API."""
  data = urlencode(params).encode()
  req = urllib.request.Request(url, data=data, method="POST")
  req.add_header("Content-Type", "application/x-www-form-urlencoded")
  try:
    with urllib.request.urlopen(req, timeout=15) as resp:
      return json.loads(resp.read())
  except urllib.error.HTTPError as exc:
    try:
      body = json.loads(exc.read())
      err = body.get("error", {})
      detail = err.get("message") or str(exc)
    except Exception:
      detail = str(exc)
    raise HTTPException(status_code=exc.code, detail=detail)
  except Exception as exc:
    raise HTTPException(status_code=502, detail=str(exc))


def _publish_to_facebook(account: SocialAccount, post: Post) -> tuple[str | None, str | None]:
  if not account.access_token:
    return "Missing access token — connect your Facebook account via OAuth first", None
  
  graph_base = _get_graph_base_url()
  caption = post.caption + (f"\n\n{post.hashtags}" if post.hashtags else "")
  params = {
    "message": caption,
    "access_token": account.access_token,
  }
  
  if post.media_url:
    if post.media_type == "image":
      endpoint = f"{graph_base}/{account.external_id}/photos"
      params["url"] = post.media_url
      print(f"DEBUG [FB Publish]: Posting photo to {endpoint}, image={post.media_url[:60]}")
    else:
      endpoint = f"{graph_base}/{account.external_id}/videos"
      params["file_url"] = post.media_url
      print(f"DEBUG [FB Publish]: Posting video to {endpoint}")
  else:
    endpoint = f"{graph_base}/{account.external_id}/feed"
    print(f"DEBUG [FB Publish]: Posting text to {endpoint}")
  
  try:
    resp = _http_post_json(endpoint, params)
    post_id = resp.get("id") or resp.get("post_id")
    print(f"DEBUG [FB Publish]: Response = {resp}, post_id = {post_id}")
    if not post_id:
      return f"Facebook returned no post ID. Response: {resp}", None
    return None, post_id
  except HTTPException as exc:
    print(f"ERROR [FB Publish]: HTTPException = {exc.detail}")
    return str(exc.detail), None
  except Exception as exc:
    print(f"ERROR [FB Publish]: Unexpected error = {exc}")
    return str(exc), None


def _publish_to_instagram(account: SocialAccount, post: Post) -> tuple[str | None, str | None]:
  if not account.access_token:
    return "Missing access token — connect your Instagram account via OAuth first", None
  
  if not post.media_url:
    return "Instagram requires media (image or video) for posts", None
    
  graph_base = _get_graph_base_url()
  caption = post.caption + (f"\n\n{post.hashtags}" if post.hashtags else "")

  try:
    # 1. Create media container
    container_params: dict = {
      "caption": caption,
      "access_token": account.access_token,
    }
    if post.media_type == "image":
      container_params["image_url"] = post.media_url
    else:
      container_params["video_url"] = post.media_url
      container_params["media_type"] = "VIDEO"

    container_data = _http_post_json(f"{graph_base}/{account.external_id}/media", container_params)
    container_id = container_data.get("id")
    if not container_id:
      return "Failed to create Instagram media container", None
      
    # 2. Publish media
    resp = _http_post_json(f"{graph_base}/{account.external_id}/media_publish", {
      "creation_id": container_id,
      "access_token": account.access_token,
    })
    return None, resp.get("id")
  except HTTPException as exc:
    return str(exc.detail), None


def _mirror_to_cloudinary(image_url: str) -> str:
  """Download a temporary image URL and re-upload to Cloudinary for permanent storage."""
  cloudinary_name   = os.getenv("CLOUDINARY_CLOUD_NAME", "")
  cloudinary_key    = os.getenv("CLOUDINARY_API_KEY", "")
  cloudinary_secret = os.getenv("CLOUDINARY_API_SECRET", "")
  if not (cloudinary_name and cloudinary_key and cloudinary_secret):
    return image_url
  try:
    import base64 as _b64, hashlib as _hl, time as _time
    resp = requests.get(image_url, timeout=30)
    resp.raise_for_status()
    file_bytes = resp.content
    timestamp  = str(int(_time.time()))
    public_id  = f"autosocial/dalle_{secrets.token_hex(8)}"
    sig_str    = f"public_id={public_id}&timestamp={timestamp}{cloudinary_secret}"
    signature  = _hl.sha256(sig_str.encode()).hexdigest()
    upload_resp = requests.post(
      f"https://api.cloudinary.com/v1_1/{cloudinary_name}/image/upload",
      data={
        "file":      f"data:image/jpeg;base64,{_b64.b64encode(file_bytes).decode()}",
        "public_id": public_id,
        "timestamp": timestamp,
        "api_key":   cloudinary_key,
        "signature": signature,
      },
      timeout=30,
    )
    if upload_resp.status_code == 200:
      cdn_url = upload_resp.json().get("secure_url", "")
      if cdn_url:
        print(f"INFO [Mirror]: Image mirrored to Cloudinary → {cdn_url[:60]}...")
        return cdn_url
  except Exception as e:
    print(f"WARNING [Mirror]: Cloudinary mirror failed: {e}")
  return image_url


def _process_post_publishing(db: Session, post: Post):
  if not post.targets:
    post.status = "failed"
    post.error_message = "No targets specified"
    db.commit()
    return

  targets = post.targets.split(",")
  errors = []
  
  for target_platform in targets:
    account = db.execute(
      select(SocialAccount).where(
        SocialAccount.user_email == post.user_email,
        SocialAccount.platform == target_platform,
        SocialAccount.is_connected == True
      )
    ).scalar_one_or_none()
    
    if not account:
      errors.append(f"No connected account for {target_platform}")
      continue
      
    error = None
    platform_id = None
    if target_platform == "facebook":
      error, platform_id = _publish_to_facebook(account, post)
      if platform_id:
        post.fb_post_id = platform_id
    elif target_platform == "instagram":
      error, platform_id = _publish_to_instagram(account, post)
      if platform_id:
        post.ig_media_id = platform_id
    
    if error:
      errors.append(f"{target_platform}: {error}")

  # Check if failures are due to local URLs
  if errors and post.media_url and ("localhost" in post.media_url or "127.0.0.1" in post.media_url):
    errors.append("NOTE: Meta API cannot access files on 'localhost'. Please use a public URL or an ngrok tunnel.")

  if errors:
    post.status = "failed"
    post.error_message = "; ".join(errors)
  else:
    post.status = "published"
  
  db.commit()




async def _sync_inbox_task():
  from db import SessionLocal
  import asyncio
  while True:
    try:
      with SessionLocal() as db:
        accounts = db.execute(select(SocialAccount).where(SocialAccount.is_connected == True)).scalars().all()
        log_msg = f"HEARTBEAT [Sync Task]: Starting sync for {len(accounts)} accounts."
        print(log_msg)
        with open("automation_debug.log", "a", encoding="utf-8") as f:
          f.write(f"\n--- {datetime.utcnow()} ---\n{log_msg}\n")
          
        for account in accounts:
          if account.platform == "facebook":
            await _sync_facebook_inbox(db, account)
          elif account.platform == "instagram":
            await _sync_instagram_inbox(db, account)
    except Exception as exc:
      err_msg = f"Inbox sync task error: {exc}"
      print(err_msg)
      with open("sync_heartbeat.log", "a", encoding="utf-8") as f:
        f.write(f"ERROR: {err_msg}\n")
    
    # await asyncio.sleep(300) # Sync every 5 minutes
    await asyncio.sleep(30) # Sync every 30 seconds


async def _sync_facebook_inbox(db: Session, account: SocialAccount):
  graph_base = _get_graph_base_url()
  comment_count: int = 0
  msg_count: int = 0
  for endpoint in ["feed", "posts"]:
    try:
      data = _http_get_json(f"{graph_base}/{account.external_id}/{endpoint}", {
        "fields": "id,comments{id,message,from,created_time}",
        "access_token": account.access_token,
        "limit": 25
      })
      items = data.get("data", [])
      print(f"DEBUG [FB Sync]: Found {len(items)} items in /{endpoint} for {account.page_name}")
      
      for item in items:
        comments = item.get("comments", {}).get("data", [])
        for comment in comments:
          _upsert_interaction(db, account, comment, "comment")
          comment_count += 1
    except Exception as e:
      print(f"Error syncing FB {endpoint} for {account.page_name}: {e}")

  print(f"HEARTBEAT [FB Sync]: Scanned feed/posts for {account.page_name}. Total discovered: {comment_count}")

  # 2. Fetch Conversations (Messages)
  try:
    conv_data = _http_get_json(f"{graph_base}/{account.external_id}/conversations", {
      "fields": "messages{id,message,from,created_time}",
      "access_token": account.access_token
    })
    conversations = conv_data.get("data", [])
    print(f"DEBUG [FB Sync]: Found {len(conversations)} conversations for {account.page_name}")
    msg_count = 0
    for conv in conversations:
      messages = conv.get("messages", {}).get("data", [])
      for msg in messages:
          _upsert_interaction(db, account, msg, "message")
          msg_count += 1
    if msg_count > 0:
      print(f"DEBUG [FB Sync]: Upserted {msg_count} messages for {account.page_name}")
  except Exception as e:
    print(f"Error syncing FB messages for {account.page_name}: {e}")


async def _sync_instagram_inbox(db: Session, account: SocialAccount):
  graph_base = _get_graph_base_url()
  # 1. Fetch Media Comments (Including replies and higher limits)
  try:
    media_data = _http_get_json(f"{graph_base}/{account.external_id}/media", {
      "fields": "id,comments.limit(50){id,text,from,timestamp,replies{id,text,from,timestamp}}",
      "access_token": account.access_token,
      "limit": 25
    })
    media_items = media_data.get("data", [])
    comment_count = 0
    for media in media_items:
      comments_list = media.get("comments", {}).get("data", [])
      for comment in comments_list:
        # Process top-level comment
        c_data = {
          "id": comment.get("id"),
          "message": comment.get("text"),
          "from": comment.get("from"),
          "created_time": comment.get("timestamp")
        }
        _upsert_interaction(db, account, c_data, "comment")
        comment_count += 1
        
        # Process replies to this comment
        replies = comment.get("replies", {}).get("data", [])
        for reply in replies:
          r_data = {
            "id": reply.get("id"),
            "message": reply.get("text"),
            "from": reply.get("from"),
            "created_time": reply.get("timestamp")
          }
          _upsert_interaction(db, account, r_data, "reply")
          comment_count += 1
    
    log_msg = f"DEBUG [IG Sync]: Discovered {comment_count} total interactions (comments + replies) across {len(media_items)} media items."
    with open("automation_debug.log", "a", encoding="utf-8") as f:
      f.write(f"{datetime.utcnow()} {log_msg}\n")
    print(f"HEARTBEAT [IG Sync]: Scanned media for {account.instagram_username}. Total discovered: {comment_count}")
  except Exception as e:
    print(f"Error syncing IG comments for {account.instagram_username}: {e}")

  # 2. Fetch IG Direct Messages
  try:
    if not account.linked_page_id:
      print(f"DEBUG: Missing linked_page_id for {account.instagram_username}. Attempting self-healing...")
      try:
        pages_data = _http_get_json(f"{graph_base}/me/accounts", {
          "fields": "id,instagram_business_account,name",
          "access_token": account.access_token,
        })
        for p in pages_data.get("data", []):
          ig_node = p.get("instagram_business_account")
          if isinstance(ig_node, dict) and ig_node.get("id") == account.external_id:
            account.linked_page_id = p.get("id")
            db.commit()
            print(f"SUCCESS: Recovered linked_page_id {account.linked_page_id} from Page '{p.get('name')}'")
            break
      except Exception as ex:
        print(f"WARNING: Self-healing failed for {account.instagram_username}: {ex}")

    # Use the linked Page ID for IG Business Messaging
    target_id = account.linked_page_id or account.external_id
    
    conv_data = _http_get_json(f"{graph_base}/{target_id}/conversations", {
      "fields": "messages.limit(50){id,message,from,created_time}",
      "access_token": account.access_token,
      "platform": "instagram"
    })
    
    total_msgs = 0
    if not conv_data or not isinstance(conv_data, dict):
       return

    for conv in conv_data.get("data", []):
      messages_list = conv.get("messages", {}).get("data", [])
      for msg in messages_list:
        text = msg.get("message")
        if not text: continue
        
        ts_raw = msg.get("created_time")
        try:
          parsed_ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")) if ts_raw else datetime.utcnow()
        except:
          parsed_ts = datetime.utcnow()

        _upsert_interaction(db, account, {
          "id": msg.get("id"),
          "message": text,
          "from": msg.get("from"),
          "created_time": parsed_ts.isoformat()
        }, "message")
        total_msgs += 1
    
    if total_msgs > 0:
      print(f"Synced {total_msgs} IG messages for {account.instagram_username}")
      
  except Exception as e:
    print(f"CRITICAL: Failed to sync IG messages for {account.instagram_username}: {e}")


def _get_ig_user_profile(db: Session, account: SocialAccount, sender_id: str) -> dict:
  """Fetch Instagram user profile (name, username) using Page Access Token."""
  graph_base = _get_graph_base_url()
  try:
    # Use the account's access token (which is already a Page Access Token) to query the IGSID
    data = _http_get_json(f"{graph_base}/{sender_id}", {
      "fields": "name,username,profile_pic",
      "access_token": account.access_token
    })
    return data
  except Exception as e:
    print(f"WARNING: Failed to fetch IG profile for {sender_id}: {e}")
    return {}


def _upsert_interaction(db: Session, account: SocialAccount, item_data: dict, itype: str):
  ext_id = item_data.get("id")
  if not ext_id:
    return

  existing = db.execute(select(Interaction).where(
    Interaction.external_id == ext_id,
    Interaction.user_email == account.user_email
  )).scalar_one_or_none()
  
  if existing:
    with open("webhook_debug.log", "a", encoding="utf-8") as f:
      f.write(f"DEBUG [Upsert]: Interaction {ext_id} already exists for {account.user_email}. Skipping.\n")
    return

  sender = item_data.get("from", {})
  s_id = sender.get("id")
  sender_name = sender.get("name") or sender.get("username")
  
  # Identify if message is outgoing (sent by the page/account itself)
  is_outgoing = False
  if s_id:
    # 1. Compare by ID
    if s_id == account.external_id:
      is_outgoing = True
      sender_name = account.instagram_username if account.platform == "instagram" else account.page_name
    # 2. Compare by Name (Facebook)
    elif account.platform == "facebook" and sender_name == account.page_name:
      is_outgoing = True
    # 3. Compare by Name (Instagram)
    elif account.platform == "instagram" and sender_name == account.instagram_username:
      is_outgoing = True

  # Enrich Instagram sender name if missing and not outgoing
  if not sender_name and account.platform == "instagram" and s_id and not is_outgoing:
    profile = _get_ig_user_profile(db, account, s_id)
    sender_name = profile.get("name") or profile.get("username")

  if not sender_name:
    sender_name = "Unknown"

  content = item_data.get("message") or item_data.get("text") or ""
  
  with open("webhook_debug.log", "a", encoding="utf-8") as f:
    f.write(f"DEBUG [Upsert]: Creating new interaction {ext_id} for {account.platform}. Sender: {sender_name}, Content: {content[:30]}\n")
  
  interaction = Interaction(
    id=secrets.token_hex(16),
    user_email=account.user_email,
    platform=account.platform,
    external_id=ext_id,
    content=content,
    sender_name=sender_name,
    type=itype,
    is_outgoing=is_outgoing,
    created_at=datetime.fromisoformat(item_data.get("created_time", datetime.utcnow().isoformat()).replace("Z", "+00:00"))
  )
  db.add(interaction)
  db.commit()
  with open("webhook_debug.log", "a", encoding="utf-8") as f:
    f.write(f"SUCCESS [Upsert]: Saved interaction {ext_id} to DB. Sender: {sender_name}, Outgoing: {is_outgoing}\n")


def _get_graph_base_url() -> str:
  base = os.getenv("META_GRAPH_API_BASE_URL", "").strip()
  if not base:
    base = "https://graph.facebook.com/v19.0"
  return base.rstrip("/")


def _extract_meta_error(payload: str) -> str | None:
  try:
    data = json.loads(payload)
  except json.JSONDecodeError:
    return None
  if isinstance(data, dict):
    error = data.get("error")
    if isinstance(error, dict):
      message = error.get("message")
      if isinstance(message, str):
        return message
  return None


def _http_get_json(url: str, params: dict) -> dict:
  request_url = f"{url}?{urlencode(params)}"
  try:
    with urllib.request.urlopen(request_url, timeout=15) as response:
      payload = response.read().decode("utf-8")
  except urllib.error.HTTPError as error:
    payload = ""
    if error.fp:
      payload = error.fp.read().decode("utf-8")
    message = _extract_meta_error(payload) or f"Meta API error ({error.code})"
    raise HTTPException(status_code=400, detail=message) from error
  except urllib.error.URLError as error:
    raise HTTPException(status_code=400, detail="Meta API request failed") from error

  try:
    data = json.loads(payload)
  except json.JSONDecodeError as error:
    raise HTTPException(status_code=400, detail="Meta API returned invalid JSON") from error

  if isinstance(data, dict) and "error" in data:
    message = _extract_meta_error(payload) or "Meta API error"
    raise HTTPException(status_code=400, detail=message)

  if not isinstance(data, dict):
    raise HTTPException(status_code=400, detail="Meta API returned unexpected response")

  return data


def _upsert_social_account(
  db: Session,
  *,
  user_email: str,
  platform: str,
  external_id: str,
  page_name: str | None = None,
  instagram_username: str | None = None,
  profile_picture_url: str | None = None,
  access_token: str | None = None,
  token_expires_at: datetime | None = None,
  linked_page_id: str | None = None,
) -> SocialAccount:
  # Look up by platform + external_id only. This ensures the same social page
  # is never duplicated across different user email sessions.
  existing = db.execute(
    select(SocialAccount).where(
      SocialAccount.platform == platform,
      SocialAccount.external_id == external_id,
    )
  ).scalar_one_or_none()

  if existing:
    old_email = existing.user_email
    # Always update user_email to the one used in the current OAuth session
    existing.user_email = user_email
    existing.page_name = page_name or existing.page_name
    existing.instagram_username = instagram_username or existing.instagram_username
    existing.profile_picture_url = profile_picture_url or existing.profile_picture_url
    existing.access_token = access_token or existing.access_token
    existing.token_expires_at = token_expires_at or existing.token_expires_at
    existing.linked_page_id = linked_page_id or existing.linked_page_id
    existing.is_connected = True
    # Migrate any interactions stored under the old email to the new one
    if old_email and old_email != user_email:
      db.execute(
        update(Interaction)
        .where(Interaction.platform == platform, Interaction.user_email == old_email)
        .values(user_email=user_email)
      )
      print(f"INFO [Account Upsert]: Migrated interactions for {platform} from {old_email} -> {user_email}")
    db.commit()
    db.refresh(existing)
    return existing

  account = SocialAccount(
    id=secrets.token_hex(8),
    user_email=user_email,
    platform=platform,
    external_id=external_id,
    page_name=page_name,
    instagram_username=instagram_username,
    profile_picture_url=profile_picture_url,
    access_token=access_token,
    token_expires_at=token_expires_at,
    linked_page_id=linked_page_id,
    is_connected=True,
  )
  db.add(account)
  db.commit()
  db.refresh(account)
  return account


def _handle_meta_callback(code: str, state: str, db: Session) -> dict:
  state_entry = _validate_oauth_state(state)
  user_email = state_entry.get("user_email")
  if not user_email:
    raise HTTPException(status_code=400, detail="User email is missing for this OAuth session")

  app_id = os.getenv("META_APP_ID", "").strip()
  app_secret = os.getenv("META_APP_SECRET", "").strip()
  redirect_uri = os.getenv("META_REDIRECT_URI", "").strip()
  if not app_id or not app_secret or not redirect_uri:
    raise HTTPException(status_code=500, detail="Meta OAuth is not configured")

  graph_base = _get_graph_base_url()
  token_data = _http_get_json(
    f"{graph_base}/oauth/access_token",
    {
      "client_id": app_id,
      "client_secret": app_secret,
      "redirect_uri": redirect_uri,
      "code": code,
    },
  )
  access_token = token_data.get("access_token")
  if not access_token:
    raise HTTPException(status_code=400, detail="Meta access token was not returned")
  expires_in = token_data.get("expires_in")
  token_expires_at = None
  if isinstance(expires_in, int):
    token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

  pages_data = _http_get_json(
    f"{graph_base}/me/accounts",
    {
      "fields": "id,name,picture.type(large),access_token",
      "access_token": access_token,
    },
  )
  pages = pages_data.get("data", [])
  if not isinstance(pages, list):
    pages = []

  connected_accounts: list[dict] = []
  
  # Unified discovery logic: Process all pages and their linked IG accounts
  for page in pages:
    page_id = page.get("id")
    if not page_id:
      continue
    
    page_access_token = page.get("access_token") or access_token
    picture_url = None
    picture = page.get("picture")
    if isinstance(picture, dict):
      data = picture.get("data")
      if isinstance(data, dict):
        picture_url = data.get("url")
    
    # 1. Upsert Facebook Page
    fb_account = _upsert_social_account(
      db,
      user_email=user_email,
      platform="facebook",
      external_id=page_id,
      page_name=page.get("name"),
      profile_picture_url=picture_url,
      access_token=page_access_token,
      token_expires_at=token_expires_at,
    )
    
    # 1a. Ensure Page is subscribed to Webhooks
    _subscribe_fb_page(fb_account)
    
    connected_accounts.append({
      "id": fb_account.id,
      "platform": fb_account.platform,
      "external_id": fb_account.external_id,
      "page_name": fb_account.page_name,
    })

    # 2. Check for linked Instagram Business Account
    try:
      ig_info = _http_get_json(
        f"{graph_base}/{page_id}",
        {
          "fields": "instagram_business_account",
          "access_token": page_access_token,
        },
      )
      ig_node = ig_info.get("instagram_business_account")
      if isinstance(ig_node, dict):
        ig_id = ig_node.get("id")
        if ig_id:
          ig_profile = _http_get_json(
            f"{graph_base}/{ig_id}",
            {
              "fields": "username,profile_picture_url",
              "access_token": page_access_token,
            },
          )
          ig_account = _upsert_social_account(
            db,
            user_email=user_email,
            platform="instagram",
            external_id=ig_id,
            instagram_username=ig_profile.get("username"),
            profile_picture_url=ig_profile.get("profile_picture_url"),
            access_token=page_access_token,
            token_expires_at=token_expires_at,
            linked_page_id=page_id,
          )
          connected_accounts.append({
            "id": ig_account.id,
            "platform": ig_account.platform,
            "external_id": ig_account.external_id,
            "instagram_username": ig_account.instagram_username,
          })
    except Exception as e:
      print(f"Warning: Failed to fetch Instagram link for page {page_id}: {e}")

  return {
    "status": "connected",
    "user_email": user_email,
    "connected_accounts": connected_accounts,
    "pages_checked": len(pages),
  }


def _validate_oauth_state(state: str) -> dict:
  state_entry = oauth_states.pop(state, None)
  if not state_entry:
    raise HTTPException(status_code=400, detail="Invalid or expired state")
  return state_entry


@app.on_event("startup")  
def on_startup():
  Base.metadata.create_all(bind=engine)
  _ensure_db_schema()

  # Create memory tables for LangGraph agent
  try:
        from tools.memory_tools import ensure_memory_schema
        ensure_memory_schema()
  except Exception as e:
        print(f"WARNING: Could not create memory schema: {e}")
  
  import asyncio
  asyncio.create_task(_scheduled_post_worker())
  asyncio.create_task(_sync_inbox_task())


def _ensure_db_schema():
  if engine.dialect.name != "postgresql":
    return
  try:
    with engine.connect() as conn:
      # Ensure interactions table
      conn.execute(text("""
        CREATE TABLE IF NOT EXISTS interactions (
          id VARCHAR(32) PRIMARY KEY,
          user_email VARCHAR(255),
          platform VARCHAR(32),
          external_id VARCHAR(128) UNIQUE,
          content TEXT,
          sender_name VARCHAR(120),
          type VARCHAR(32),
          created_at TIMESTAMPTZ DEFAULT NOW()
        )
      """))
      
      # Social Accounts table columns
      for column, ddl in (
        ("access_token", "TEXT"),
        ("token_expires_at", "TIMESTAMPTZ"),
        ("profile_picture_url", "TEXT"),
        ("linked_page_id", "VARCHAR(128)"),
      ):
        exists = conn.execute(
          text(
            "select 1 from information_schema.columns "
            "where table_name = 'social_accounts' and column_name = :col"
          ),
          {"col": column},
        ).first()
        if not exists:
          conn.execute(text(f"alter table social_accounts add column {column} {ddl}"))

      # Posts table columns
      exists = conn.execute(
        text(
          "select 1 from information_schema.columns "
          "where table_name = 'posts' and column_name = 'error_message'"
        )
      ).first()
      if not exists:
        conn.execute(text("alter table posts add column error_message TEXT"))
      
      exists = conn.execute(
        text(
          "select 1 from information_schema.columns "
          "where table_name = 'posts' and column_name = 'scheduled_at'"
        )
      ).first()
      if not exists:
        conn.execute(text("alter table posts add column scheduled_at TIMESTAMPTZ"))
        
      conn.commit()
  except Exception as exc:
    print(f"Failed to ensure db schema: {exc}")


@app.get("/")
def root():
  return {"message": "AutoSocial API running"}


@app.get("/health")
def health():
  return {"status": "ok"}


@app.post("/auth/signup", response_model=AuthResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
  email = payload.email.lower()
  existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
  if existing:
    raise HTTPException(status_code=400, detail="Email already registered")

  salt = secrets.token_hex(16)
  password_hash = _hash_password(payload.password, salt)
  user = User(
    id=secrets.token_hex(8),
    name=payload.name,
    email=email,
    company=payload.company,
    salt=salt,
    password_hash=password_hash,
  )
  db.add(user)
  db.commit()
  db.refresh(user)

  return {
    "access_token": _issue_token(),
    "user": {
      "id": user.id,
      "name": user.name,
      "email": user.email,
      "company": user.company,
    },
  }


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
  email = payload.email.lower()
  user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
  if not user:
    raise HTTPException(status_code=401, detail="Invalid email or password")

  password_hash = _hash_password(payload.password, user.salt)
  if password_hash != user.password_hash:
    raise HTTPException(status_code=401, detail="Invalid email or password")

  return {
    "access_token": _issue_token(),
    "user": {
      "id": user.id,
      "name": user.name,
      "email": user.email,
      "company": user.company,
    },
  }


@app.get("/accounts")
def list_accounts(user_email: EmailStr, db: Session = Depends(get_db)):
  accounts = db.execute(
    select(SocialAccount).where(SocialAccount.user_email == user_email.lower())
  ).scalars().all()

  return [
    {
      "id": account.id,
      "platform": account.platform,
      "external_id": account.external_id,
      "page_name": account.page_name,
      "instagram_username": account.instagram_username,
      "profile_picture_url": account.profile_picture_url,
      "is_connected": account.is_connected,
    }
    for account in accounts
  ]


@app.post("/accounts/refresh", response_model=AccountsRefreshResponse)
def refresh_accounts(
  user_email: EmailStr,
  platform: Literal["facebook", "instagram", "all"] = "all",
  db: Session = Depends(get_db),
):
  query = select(SocialAccount).where(SocialAccount.user_email == user_email.lower())
  if platform != "all":
    query = query.where(SocialAccount.platform == platform)
  accounts = db.execute(query).scalars().all()

  graph_base = _get_graph_base_url()
  updated = 0
  errors: list[dict] = []

  for account in accounts:
    if not account.access_token:
      errors.append(
        {
          "id": account.id,
          "platform": account.platform,
          "error": "Missing access token",
        }
      )
      continue
    try:
      if account.platform == "facebook":
        data = _http_get_json(
          f"{graph_base}/{account.external_id}",
          {
            "fields": "name,picture.type(large)",
            "access_token": account.access_token,
          },
        )
        account.page_name = data.get("name") or account.page_name
        picture = data.get("picture")
        if isinstance(picture, dict):
          picture_data = picture.get("data")
          if isinstance(picture_data, dict):
            account.profile_picture_url = (
              picture_data.get("url") or account.profile_picture_url
            )
      elif account.platform == "instagram":
        data = _http_get_json(
          f"{graph_base}/{account.external_id}",
          {
            "fields": "username,profile_picture_url",
            "access_token": account.access_token,
          },
        )
        account.instagram_username = data.get("username") or account.instagram_username
        account.profile_picture_url = data.get("profile_picture_url") or account.profile_picture_url
      updated += 1
    except HTTPException as exc:
      errors.append(
        {
          "id": account.id,
          "platform": account.platform,
          "error": str(exc.detail),
        }
      )

  db.commit()
  return {"refreshed": len(accounts), "updated": updated, "errors": errors}


@app.post("/accounts/connect")
def connect_account(payload: AccountCreateRequest, db: Session = Depends(get_db)):
  account = SocialAccount(
    id=secrets.token_hex(8),
    user_email=payload.user_email.lower(),
    platform=payload.platform,
    external_id=payload.external_id,
    page_name=payload.page_name,
    instagram_username=payload.instagram_username,
    profile_picture_url=payload.profile_picture_url,
    is_connected=True,
  )
  db.add(account)
  db.commit()
  db.refresh(account)

  return {
    "id": account.id,
    "platform": account.platform,
    "external_id": account.external_id,
    "page_name": account.page_name,
    "instagram_username": account.instagram_username,
    "profile_picture_url": account.profile_picture_url,
    "is_connected": account.is_connected,
  }


@app.post("/accounts/disconnect")
def disconnect_account(payload: AccountDisconnectRequest, db: Session = Depends(get_db)):
  account = db.execute(
    select(SocialAccount).where(
        SocialAccount.id == payload.account_id,
        SocialAccount.user_email == payload.user_email.lower()
    )
  ).scalar_one_or_none()
  if not account:
    raise HTTPException(status_code=404, detail="Account not found or not owned by user")

  account.is_connected = False
  db.commit()

  return {"status": "disconnected", "id": account.id}


@app.get("/oauth/meta/authorize")
def meta_authorize(platform: Literal["facebook", "instagram"], user_email: EmailStr | None = None):
  config = _get_oauth_config(platform)
  state = secrets.token_urlsafe(24)
  oauth_states[state] = {
    "platform": platform,
    "user_email": user_email.lower() if user_email else None,
    "created_at": datetime.utcnow(),
  }

  params = {
    "client_id": config["app_id"],
    "redirect_uri": config["redirect_uri"],
    "response_type": "code",
    "state": state,
  }
  if config["scopes"]:
    params["scope"] = config["scopes"]

  url = f"{config['authorize_url']}?{urlencode(params)}"
  return {"url": url}


@app.get("/oauth/meta/callback")
def meta_callback(code: str | None = None, state: str | None = None, db: Session = Depends(get_db)):
  if not code or not state:
    raise HTTPException(status_code=400, detail="Missing code or state")
  return _handle_meta_callback(code, state, db)


@app.get("/oauth/meta/callback-redirect")
def meta_callback_redirect(code: str | None = None, state: str | None = None, db: Session = Depends(get_db)):
  if not code or not state:
    raise HTTPException(status_code=400, detail="Missing code or state")
  frontend_redirect = os.getenv("META_FRONTEND_REDIRECT_URI", "").strip()
  if not frontend_redirect:
    raise HTTPException(status_code=500, detail="META_FRONTEND_REDIRECT_URI is not configured")

  status = "received"
  message = None
  platform = "unknown"
  try:
    result = _handle_meta_callback(code, state, db)
    platform = result.get("platform", platform)
  except HTTPException as exc:
    status = "error"
    message = str(exc.detail)
  params = {
    "status": status,
    "platform": platform,
  }
  if message:
    params["message"] = message
  url = f"{frontend_redirect}?{urlencode(params)}"
  return RedirectResponse(url=url, status_code=302)


@app.post("/posts", response_model=PostResponse)
def create_post(payload: PostCreateRequest, db: Session = Depends(get_db)):
  post = Post(
    id=secrets.token_hex(8),
    user_email=payload.user_email.lower(),
    caption=payload.caption,
    media_url=payload.media_url,
    media_type=payload.media_type,
    hashtags=payload.hashtags,
    emojis=payload.emojis,
    targets=",".join(payload.targets) if payload.targets else None,
    status="draft",
  )
  db.add(post)
  db.commit()
  db.refresh(post)

  return _post_to_dict(post)


@app.post("/posts/publish", response_model=PostResponse)
def publish_post(payload: PostCreateRequest, db: Session = Depends(get_db)):
  status = "publishing"
  if payload.scheduled_at:
    try:
      # Normalize to naive UTC for comparison with datetime.utcnow()
      scheduled_at_naive = payload.scheduled_at.replace(tzinfo=None)
      if scheduled_at_naive > datetime.utcnow():
        status = "scheduled"
    except Exception as e:
      print(f"WARNING: Scheduling date comparison failed: {e}")
      # Fallback: if we can't compare safely, assume it's for now or 
      # just let it stay 'publishing'

  post = Post(
    id=secrets.token_hex(8),
    user_email=payload.user_email.lower(),
    caption=payload.caption,
    media_url=payload.media_url,
    media_type=payload.media_type,
    hashtags=payload.hashtags,
    emojis=payload.emojis,
    targets=",".join(payload.targets) if payload.targets else None,
    status=status,
    scheduled_at=payload.scheduled_at,
  )
  db.add(post)
  db.commit()
  db.refresh(post)

  if status == "publishing":
    _process_post_publishing(db, post)
  
  return _post_to_dict(post)


@app.get("/posts", response_model=list[PostResponse])
def list_posts(user_email: EmailStr, db: Session = Depends(get_db)):
  posts = db.execute(
    select(Post).where(Post.user_email == user_email.lower()).order_by(Post.created_at.desc())
  ).scalars().all()

  return [_post_to_dict(post) for post in posts]


@app.post("/posts/{post_id}/publish", response_model=PostResponse)
def publish_post_by_id(post_id: str, user_email: EmailStr, db: Session = Depends(get_db)):
  post = db.execute(
    select(Post).where(
        Post.id == post_id,
        Post.user_email == user_email.lower()
    )
  ).scalar_one_or_none()

  if not post:
    raise HTTPException(status_code=404, detail="Post not found or not owned by user")

  post.status = "publishing"
  db.commit()
  db.refresh(post)

  _process_post_publishing(db, post)
  return _post_to_dict(post)


@app.get("/posts/{post_id}", response_model=PostResponse)
def get_post(post_id: str, db: Session = Depends(get_db)):
  post = db.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
  if not post:
    raise HTTPException(status_code=404, detail="Post not found")
  return _post_to_dict(post)


@app.put("/posts/{post_id}", response_model=PostResponse)
def update_post(post_id: str, payload: PostCreateRequest, db: Session = Depends(get_db)):
  post = db.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
  if not post:
    raise HTTPException(status_code=404, detail="Post not found")

  post.caption = payload.caption
  post.media_url = payload.media_url
  post.media_type = payload.media_type
  post.hashtags = payload.hashtags
  post.emojis = payload.emojis
  post.targets = ",".join(payload.targets) if payload.targets else None
  # If it was failed, allow updating it back to draft for retry/edit
  if post.status == "failed":
    post.status = "draft"
    post.error_message = None

  db.commit()
  db.refresh(post)
  return _post_to_dict(post)


@app.delete("/posts/{post_id}")
def delete_post(post_id: str, user_email: EmailStr, db: Session = Depends(get_db)):
  post = db.execute(
    select(Post).where(
        Post.id == post_id,
        Post.user_email == user_email.lower()
    )
  ).scalar_one_or_none()
  if not post:
    raise HTTPException(status_code=404, detail="Post not found or not owned by user")

  # 1. Try deleting from social platforms
  graph_base = _get_graph_base_url()
  
  # Facebook Deletion
  if post.fb_post_id:
    # We need the access token for the account that posted it
    account = db.execute(
      select(SocialAccount).where(
        SocialAccount.user_email == post.user_email,
        SocialAccount.platform == "facebook",
        SocialAccount.is_connected == True
      )
    ).scalar_one_or_none()
    
    if account and account.access_token:
        try:
            # DELETE /{post-id}?access_token={access-token}
            _http_post_json(f"{graph_base}/{post.fb_post_id}", {
                "method": "delete",
                "access_token": account.access_token
            })
            print(f"INFO: Successfully deleted FB post {post.fb_post_id}")
        except Exception as e:
            print(f"WARNING: Failed to delete FB post {post.fb_post_id}: {e}")

  # Instagram Deletion (Note: Instagram Content Publishing API generally does NOT support DELETE)
  if post.ig_media_id:
      print(f"INFO: Instagram media {post.ig_media_id} cannot be deleted via API (Meta restriction). Removing from local DB only.")

  # 2. Delete from local database
  db.delete(post)
  db.commit()
  return {"detail": "Post deleted from database (and Facebook if applicable)"}


@app.get("/inbox", response_model=PaginatedInteractions)
def list_interactions(
  user_email: EmailStr, 
  page: int = 1, 
  page_size: int = 10, 
  platform: str | None = None,
  interaction_type: str | None = None,
  db: Session = Depends(get_db)
):
  print(f"DEBUG [/inbox]: Request for {user_email}, platform={platform}, type={interaction_type}, page={page}")
  offset = (page - 1) * page_size
  
  # Basic query (Case-insensitive to prevent hidden messages)
  stmt = select(Interaction).where(func.lower(Interaction.user_email) == user_email.lower())
  
  # Apply filters
  if platform and platform != "all":
    stmt = stmt.where(Interaction.platform == platform.lower())
  if interaction_type and interaction_type != "all":
    # Client might send 'comments' or 'messages', but DB uses 'comment' or 'message'
    db_type = interaction_type.rstrip('s') 
    stmt = stmt.where(Interaction.type == db_type)
  
  # Get total count
  total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
  
  # Get paginated data
  interactions = db.execute(
    stmt.order_by(Interaction.created_at.desc()).offset(offset).limit(page_size)
  ).scalars().all()

  return {
    "data": [_interaction_to_dict(i) for i in interactions],
    "total": total
  }


@app.post("/inbox/reply")
def reply_interaction(payload: ReplyRequest, db: Session = Depends(get_db)):
  # 1. Fetch the interaction to know its type and ensure ownership
  interaction = db.execute(
    select(Interaction).where(
        Interaction.external_id == payload.external_id,
        Interaction.user_email == payload.user_email.lower()
    )
  ).scalar_one_or_none()
  
  if not interaction:
    raise HTTPException(status_code=404, detail="Interaction not found or not owned by user")

  # 2. Fetch the connected account
  account = db.execute(
    select(SocialAccount).where(
      SocialAccount.user_email == payload.user_email.lower(),
      SocialAccount.platform == interaction.platform,
      SocialAccount.is_connected == True
    )
  ).scalar_one_or_none()
  
  if not account:
    raise HTTPException(status_code=400, detail=f"No connected account for {interaction.platform}")

  graph_base = _get_graph_base_url()
  
  try:
    if interaction.type == "comment":
      if interaction.platform == "facebook":
        # Reply to FB Page Comment: POST /{comment-id}/comments
        endpoint = f"{graph_base}/{interaction.external_id}/comments"
        _http_post_json(endpoint, {
          "message": payload.content,
          "access_token": account.access_token
        })
      elif interaction.platform == "instagram":
        # Reply to IG Media Comment: POST /{comment-id}/replies
        endpoint = f"{graph_base}/{interaction.external_id}/replies"
        _http_post_json(endpoint, {
          "message": payload.content,
          "access_token": account.access_token
        })
      return {"status": "success", "message": "Reply posted successfully"}
    
    elif interaction.type == "message":
      # Need the sender's PSID/IGSID to reply. We fetch it using the message ID.
      msg_data = _http_get_json(f"{graph_base}/{interaction.external_id}", {
          "fields": "from",
          "access_token": account.access_token
      })
      sender_id = msg_data.get("from", {}).get("id")
      
      if not sender_id:
          raise HTTPException(status_code=400, detail="Could not retrieve sender ID to send reply.")

      target_page_id = account.linked_page_id or account.external_id
      endpoint = f"{graph_base}/{target_page_id}/messages"
      
      _http_post_json(endpoint, {
          "recipient": {"id": sender_id},
          "message": {"text": payload.content},
          "access_token": account.access_token
      })

      # Save the sent reply back to our interactions so it shows in the UI
      sent_interaction = Interaction(
          id=secrets.token_hex(16),
          user_email=payload.user_email.lower(),
          platform=interaction.platform,
          external_id=f"sent_{secrets.token_hex(8)}",
          content=payload.content,
          sender_name="You",
          type=interaction.type,
          is_outgoing=True,
          created_at=datetime.utcnow()
      )
      db.add(sent_interaction)
      db.commit()
      
      return {"status": "success", "message": "Message reply sent successfully"}
  except HTTPException as exc:
    raise exc
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Failed to post reply: {e}")

  return {"status": "error", "message": "Unsupported interaction type"}


def _verify_meta_signature(payload: bytes, signature: str) -> bool:
  app_secret = os.getenv("META_APP_SECRET", "").strip()
  if not signature or not app_secret:
    return False
  signature_to_check = signature.replace("sha256=", "")
  expected = hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
  return hmac.compare_digest(expected, signature_to_check)


@app.get("/webhook/meta")
def verify_meta_webhook(request: Request):
  # Used for Meta Webhook verification (hub.challenge)
  verify_token = os.getenv("META_WEBHOOK_VERIFY_TOKEN", "autosocial_secret")
  mode = request.query_params.get("hub.mode")
  token = request.query_params.get("hub.verify_token")
  challenge = request.query_params.get("hub.challenge")
  
  if mode == "subscribe" and token == verify_token:
    return Response(content=challenge, media_type="text/plain")
  return Response(content="Verification failed", status_code=403)


@app.post("/webhook/meta")
async def handle_meta_webhook(request: Request, db: Session = Depends(get_db)):
  body = await request.body()
  signature = request.headers.get("X-Hub-Signature-256")
  
  # Validate signature
  is_valid = _verify_meta_signature(body, signature)
  log_output = [
      f"\n--- {datetime.utcnow()} ---",
      f"Signature: {signature}",
      f"Body: {body.decode('utf-8', errors='ignore')}",
      f"DEBUG [Webhook]: Signature valid: {is_valid}"
  ]

  if not is_valid:
    log_output.append(f"WARNING [Webhook]: Signature verification failed")
  
  try:
    data = json.loads(body)
    obj = data.get("object")
    entries = data.get("entry", [])
    log_output.append(f"DEBUG [Webhook]: Received object: {obj}, entries: {len(entries)}")
      
    for entry in entries:
      # Facebook Page Events
      if obj == "page":
        changes = entry.get("changes", [])
        for change in changes:
          field = change.get("field")
          val = change.get("value", {})
          log_output.append(f"DEBUG [Webhook]: FB Page change field: {field}, item: {val.get('item')}, verb: {val.get('verb')}")
          if field == "feed":
            _handle_fb_webhook_comment(db, entry.get("id"), val)
        
        # Facebook Page Messages (DMs)
        messaging = entry.get("messaging", [])
        standby = entry.get("standby", [])
        
        if messaging:
            log_output.append(f"DEBUG [Webhook]: FB Page Messaging event count: {len(messaging)}")
        for msg in messaging:
          _handle_fb_webhook_message(db, entry.get("id"), msg)
          
        if standby:
            log_output.append(f"DEBUG [Webhook]: FB Page Standby event count: {len(standby)}")
        for msg in standby:
          _handle_fb_webhook_message(db, entry.get("id"), msg)
      
      # Instagram Business Events
      elif obj == "instagram":
        # Messages (DMs)
        messaging = entry.get("messaging", [])
        standby = entry.get("standby", [])
        
        if messaging:
            log_output.append(f"DEBUG [Webhook]: IG Messaging event count: {len(messaging)}")
        for msg in messaging:
          _handle_ig_webhook_message(db, entry.get("id"), msg)
          
        if standby:
            log_output.append(f"DEBUG [Webhook]: IG Standby event count: {len(standby)}")
        for msg in standby:
          _handle_ig_webhook_message(db, entry.get("id"), msg)
         
        # Comments
        changes = entry.get("changes", [])
        if changes:
             log_output.append(f"DEBUG [Webhook]: IG Change event count: {len(changes)}")
        for change in changes:
          if change.get("field") == "comments":
            _handle_ig_webhook_comment(db, entry.get("id"), change.get("value", {}))
            
  except Exception as e:
    err_msg = f"CRITICAL [Webhook]: Processing error: {e}"
    print(err_msg)
    import traceback
    log_output.append(err_msg)
    log_output.append(traceback.format_exc())
    traceback.print_exc()
    
  with open("webhook_debug.log", "a", encoding="utf-8") as f:
    f.write("\n".join(log_output) + "\n")
  
  return {"status": "received"}


def _handle_fb_webhook_comment(db: Session, page_id: str, value: dict):
  if value.get("item") != "comment" or value.get("verb") != "add":
    return
    
  accounts = db.execute(select(SocialAccount).where(
    SocialAccount.external_id == page_id, 
    SocialAccount.platform == "facebook"
  )).scalars().all()
  
  if not accounts: 
    with open("webhook_debug.log", "a", encoding="utf-8") as f:
      f.write(f"DEBUG [Webhook FB]: No account found for page_id {page_id}\n")
    return
  
  item_data = {
    "id": value.get("comment_id"),
    "message": value.get("message"),
    "from": value.get("from"),
    "created_time": datetime.utcnow().isoformat()
  }
  
  for account in accounts:
    _upsert_interaction(db, account, item_data, "comment")


def _handle_fb_webhook_message(db: Session, page_id: str, msg: dict):
  accounts = db.execute(select(SocialAccount).where(
    SocialAccount.external_id == page_id, 
    SocialAccount.platform == "facebook"
  )).scalars().all()
  
  if not accounts: return
  
  message = msg.get("message", {})
  mid = message.get("mid")
  print(f"DEBUG [Webhook]: Processing FB Message {mid} from {page_id}")
  item_data = {
    "id": mid,
    "message": message.get("text"),
    "from": msg.get("sender"),
    "created_time": datetime.utcnow().isoformat()
  }
  
  for account in accounts:
    _upsert_interaction(db, account, item_data, "message")
    # --- FIREBELLY AI AUTO-REPLY ---
    sender_id = msg.get("sender", {}).get("id")
    if mid and message.get("text") and sender_id and sender_id != page_id:
        _trigger_ai_auto_reply(
            db=db,
            external_id=mid,
            platform="facebook",
            message_text=message.get("text", ""),
            sender_name=None,
            user_email=accounts[0].user_email if accounts else None,
        )
    # --------------------------------


def _handle_ig_webhook_message(db: Session, ig_id: str, msg: dict):
  accounts = db.execute(select(SocialAccount).where(
    SocialAccount.external_id == ig_id, 
    SocialAccount.platform == "instagram"
  )).scalars().all()
  
  if not accounts: return
  
  message = msg.get("message", {})
  mid = message.get("mid")
  print(f"DEBUG [Webhook]: Processing IG Message {mid} from {ig_id}")
  item_data = {
    "id": mid,
    "message": message.get("text"),
    "from": msg.get("sender"),
    "created_time": datetime.utcnow().isoformat()
  }
  
  for account in accounts:
    _upsert_interaction(db, account, item_data, "message")
    # --- FIREBELLY AI AUTO-REPLY ---
    sender_id = msg.get("sender", {}).get("id")
    if mid and message.get("text") and sender_id and sender_id != ig_id:
        _trigger_ai_auto_reply(
            db=db,
            external_id=mid,
            platform="instagram",
            message_text=message.get("text", ""),
            sender_name=None,
            user_email=accounts[0].user_email if accounts else None,
        )
    # --------------------------------


def _subscribe_fb_page(account: SocialAccount):
  """Subscribes the FB Page to the App for real-time webhooks."""
  if account.platform != "facebook":
    return
  
  graph_base = _get_graph_base_url()
  try:
    # Fields to subscribe to: feed (comments), messages (DMs), messaging_postbacks
    fields = "feed,messages,messaging_postbacks"
    resp = _http_post_json(
      f"{graph_base}/{account.external_id}/subscribed_apps",
      {
        "subscribed_fields": fields,
        "access_token": account.access_token
      }
    )
    if resp.get("success"):
      print(f"SUCCESS [Sub]: Subscribed Page {account.external_id} ({account.page_name}) to webhooks.")
    else:
      print(f"WARNING [Sub]: Subscription response for {account.page_name}: {resp}")
  except Exception as e:
    print(f"ERROR [Sub]: Failed to subscribe Page {account.page_name}: {e}")

def _trigger_ai_auto_reply(
    db: Session,
    external_id: str,
    platform: str,
    message_text: str,
    sender_name: str | None,
    user_email: str | None,
):
    if not user_email:
        return
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING [AI Auto Reply]: OPENAI_API_KEY not set, skipping.")
        return

    try:
        # result = generate_ai_reply(
        #     message=message_text,
        #     platform=platform,
        #     sender_name=sender_name or "there",
        # )
        # ai_reply_text = result["reply"]
        result = generate_reply(
            message=message_text,
            platform=platform,
            interaction_type="message",
            customer_id=external_id,
            customer_name=sender_name,
            restaurant_id=RESTAURANT_ID,
        )
        ai_reply_text = result["reply"]

        interaction = db.execute(
            select(Interaction).where(
                Interaction.external_id == external_id,
                func.lower(Interaction.user_email) == user_email.lower()
            )
        ).scalar_one_or_none()

        if not interaction:
            return

        account = db.execute(
            select(SocialAccount).where(
                SocialAccount.user_email == user_email.lower(),
                SocialAccount.platform == platform,
                SocialAccount.is_connected == True
            )
        ).scalar_one_or_none()

        if not account:
            return

        graph_base = _get_graph_base_url()
        msg_data = _http_get_json(f"{graph_base}/{external_id}", {
            "fields": "from",
            "access_token": account.access_token
        })
        sender_psid = msg_data.get("from", {}).get("id")

        if not sender_psid:
            return

        target_id = account.linked_page_id or account.external_id
        _http_post_json(f"{graph_base}/{target_id}/messages", {
            "recipient": {"id": sender_psid},
            "message": {"text": ai_reply_text},
            "access_token": account.access_token
        })

        sent = Interaction(
            id=secrets.token_hex(16),
            user_email=user_email.lower(),
            platform=platform,
            external_id=f"ai_{secrets.token_hex(8)}",
            content=ai_reply_text,
            sender_name="Firebelly (AI)",
            type="message",
            is_outgoing=True,
            created_at=datetime.utcnow()
        )
        db.add(sent)
        db.commit()
        print(f"SUCCESS [AI Auto Reply]: Replied to {external_id} on {platform}.")

    except Exception as e:
        print(f"ERROR [AI Auto Reply]: Failed silently: {e}")


def _handle_ig_webhook_comment(db: Session, ig_id: str, value: dict):
  accounts = db.execute(select(SocialAccount).where(
    SocialAccount.external_id == ig_id, 
    SocialAccount.platform == "instagram"
  )).scalars().all()
  
  if not accounts: return
  
  cid = value.get("id")
  print(f"DEBUG [Webhook]: Processing IG Comment {cid} from {ig_id}")
  item_data = {
    "id": cid,
    "message": value.get("text"),
    "from": value.get("from"),
    "created_time": datetime.utcnow().isoformat()
  }
  
  for account in accounts:
    _upsert_interaction(db, account, item_data, "comment")


# @app.post("/inbox/ai-suggest")
# def ai_suggest_reply(payload: AiSuggestRequest, db: Session = Depends(get_db)):
#         result = generate_ai_reply(
#             message=payload.message,
#             platform=payload.platform,
#             sender_name=payload.sender_name or "there",
#             interaction_type=payload.interaction_type,
#         )
#         return {
#             "suggested_reply": result["reply"],
#             "escalate": result["escalate"],
#             "confidence": result["confidence"],
#             "ai_persona": result.get("ai_persona", "ember"),
#         }

@app.post("/inbox/ai-suggest")
def ai_suggest_reply(payload: AiSuggestRequest, db: Session = Depends(get_db)):
  result = generate_reply(
    message=payload.message,
    platform=payload.platform,
    interaction_type=payload.interaction_type,
    customer_id=payload.external_id,
    customer_name=payload.sender_name,
    restaurant_id=RESTAURANT_ID,
    )
  return {
            "suggested_reply": result["reply"],
            "escalate": result["escalate"],
            "confidence": result["confidence"],
            "ai_persona": result.get("ai_persona", "ember"),
            "intent": result.get("intent", "general"),
        }

@app.post("/content/generate")
async def content_generate(payload: ContentGenerateRequest):
    result = generate_content(
        mode=payload.mode,
        restaurant_id=RESTAURANT_ID,
        owner_idea=payload.owner_idea,
        image_url=payload.image_url,
        language=payload.language,
    )
    return result


@app.post("/content/generate-from-image")
async def content_generate_from_image(
    file: UploadFile = File(...),
    user_email: str = "",
    platform: str = "both",
    owner_idea: str | None = None,
):
    """
    Accepts a user-uploaded image, saves it, then runs the content agent
    in 'image' mode. The agent uses GPT-4o Vision to analyse the image
    and writes captions based on it. No DALL-E image is generated since
    the user already provided one.
    """
    # Save uploaded file to disk
    ext = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
    tmp_name = f"{secrets.token_hex(8)}{ext}"
    tmp_path = os.path.join(UPLOAD_DIR, tmp_name)
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Build a publicly accessible URL for the image
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    image_url = f"{base_url}/uploads/{tmp_name}"

    result = generate_content(
        mode="image",
        restaurant_id=RESTAURANT_ID,
        owner_idea=owner_idea or None,
        image_url=image_url,
        language="auto",
    )
    return result


@app.post("/content/publish", response_model=PostResponse)
def content_publish(payload: ContentPublishRequest, db: Session = Depends(get_db)):
    status = "publishing"
    if payload.scheduled_at:
        try:
            if payload.scheduled_at.replace(tzinfo=None) > datetime.utcnow():
                status = "scheduled"
        except Exception:
            pass

    # Mirror temporary image URLs (DALL-E) to Cloudinary for permanent storage
    media_url = payload.media_url
    if media_url and any(x in media_url for x in ["oaidalleapiprodscus", "blob.core.windows.net"]):
        print(f"INFO [Publish]: Mirroring temporary image to Cloudinary...")
        media_url = _mirror_to_cloudinary(media_url)

    post = Post(
        id=secrets.token_hex(8),
        user_email=payload.user_email.lower(),
        caption=payload.caption,
        media_url=media_url,
        media_type=payload.media_type,
        hashtags=payload.hashtags,
        targets=",".join(payload.targets) if payload.targets else None,
        status=status,
        scheduled_at=payload.scheduled_at,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    if status == "publishing":
        _process_post_publishing(db, post)

    return _post_to_dict(post)


# Alias — frontend ContentStudio calls /posts/publish
@app.post("/posts/publish", response_model=PostResponse)
def posts_publish(payload: ContentPublishRequest, db: Session = Depends(get_db)):
    return content_publish(payload, db)


@app.post("/inbox/ai-auto-reply")
async def ai_auto_reply(payload: AiSuggestRequest, db: Session = Depends(get_db)):
    result = generate_reply(
        message=payload.message,
        platform=payload.platform,
        interaction_type=payload.interaction_type,
        customer_id=payload.external_id,
        customer_name=payload.sender_name,
        restaurant_id=RESTAURANT_ID,
    )
    suggested = result["reply"]

    interaction = db.execute(
        select(Interaction).where(
            Interaction.external_id == payload.external_id,
            func.lower(Interaction.user_email) == payload.user_email.lower()
        )
    ).scalar_one_or_none()

    if not interaction:
        return {"status": "error", "message": "Interaction not found", "reply": suggested}

    account = db.execute(
        select(SocialAccount).where(
            SocialAccount.user_email == payload.user_email.lower(),
            SocialAccount.platform == interaction.platform,
            SocialAccount.is_connected == True
        )
    ).scalar_one_or_none()

    if not account:
        return {"status": "error", "message": f"No connected account for {interaction.platform}", "reply": suggested}

    graph_base = _get_graph_base_url()
    try:
        if interaction.type == "message":
            msg_data = _http_get_json(f"{graph_base}/{interaction.external_id}", {
                "fields": "from",
                "access_token": account.access_token
            })
            sender_id = msg_data.get("from", {}).get("id")
            if not sender_id:
                return {"status": "error", "message": "Could not get sender ID", "reply": suggested}

            target_page_id = account.linked_page_id or account.external_id
            _http_post_json(f"{graph_base}/{target_page_id}/messages", {
                "recipient": {"id": sender_id},
                "message": {"text": suggested},
                "access_token": account.access_token
            })

        elif interaction.type == "comment":
            if interaction.platform == "facebook":
                _http_post_json(f"{graph_base}/{interaction.external_id}/comments", {
                    "message": suggested,
                    "access_token": account.access_token
                })
            elif interaction.platform == "instagram":
                _http_post_json(f"{graph_base}/{interaction.external_id}/replies", {
                    "message": suggested,
                    "access_token": account.access_token
                })

        sent = Interaction(
            id=secrets.token_hex(16),
            user_email=payload.user_email.lower(),
            platform=interaction.platform,
            external_id=f"ai_sent_{secrets.token_hex(8)}",
            content=suggested,
            sender_name="Firebelly (AI)",
            type=interaction.type,
            is_outgoing=True,
            created_at=datetime.utcnow()
        )
        db.add(sent)
        db.commit()

        return {
            "status": "sent",
            "reply": suggested,
            "escalate": result["escalate"],
            "confidence": result["confidence"],
        }

    except Exception as e:
        return {"status": "error", "message": str(e), "reply": suggested}


@app.post("/debug/sync")
async def debug_sync(user_email: EmailStr, db: Session = Depends(get_db)):
    # Normalize email
    email = user_email.lower().strip()
    accounts = db.execute(
        select(SocialAccount).where(
            SocialAccount.user_email == email,
            SocialAccount.is_connected == True
        )
    ).scalars().all()
    
    if not accounts:
        return {
          "status": "failed",
          "reason": f"No connected social accounts found for {email}. Please go to the Accounts page and connect Meta/Instagram.",
          "checked_email": email
        }
    
    results = []
    ig_count: int = 0
    for account in accounts:
        if account.platform == "facebook":
            try:
                # Ensure Page is subscribed to webhooks
                _subscribe_fb_page(account)
                await _sync_facebook_inbox(db, account)
                results.append(f"Successfully synced FB for {account.page_name}")
            except Exception as e:
                results.append(f"FAILED to sync FB for {account.page_name}: {str(e)}")
        elif account.platform == "instagram":
            ig_count += 1
            try:
                await _sync_instagram_inbox(db, account)
                results.append(f"Successfully synced IG for {account.instagram_username}")
            except Exception as e:
                results.append(f"FAILED to sync IG for {account.instagram_username}: {str(e)}")
                
    if ig_count == 0:
        results.append("WARNING: No Instagram account found for this user in the database. Synchronization skipped for IG.")
            
    return {
      "status": "done",
      "checked_email": email,
      "results": results,
      "total_accounts": len(accounts),
      "has_instagram": ig_count > 0
    }


async def _scheduled_post_worker():
  """Background task to publish scheduled posts when their time is due."""
  from datetime import timezone
  import asyncio
  
  print("--- SCHEDULED POST WORKER STARTED ---")
  while True:
    try:
      with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        # Find posts that are scheduled and whose time has come
        due_posts = db.execute(
          select(Post).where(
            Post.status == "scheduled",
            Post.scheduled_at <= now
          )
        ).scalars().all()

        if due_posts:
          print(f"--- FOUND {len(due_posts)} DUE POSTS ---")

        for post in due_posts:
          print(f"--- PROCESSING SCHEDULED POST: {post.id} ---")
          # Mark as publishing so other workers don't grab it (if we had multiple)
          post.status = "publishing"
          db.commit()
          
          try:
            _process_post_publishing(db, post)
            print(f"--- SUCCESSFULLY PROCESSED SCHEDULED POST: {post.id} ---")
          except Exception as e:
            print(f"--- FAILED TO PUBLISH SCHEDULED POST {post.id}: {e} ---")
            post.status = "failed"
            post.error_message = str(e)
            db.commit()
    except Exception as e:
      print(f"--- SCHEDULED POST WORKER ERROR: {e} ---")
    
    await asyncio.sleep(60) # Check every minute