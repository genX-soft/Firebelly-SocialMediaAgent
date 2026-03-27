"""
agents/content_agent.py
------------------------
LangGraph-powered content generation agent for AutoSocial.

Three modes:
  A (idea)    — owner describes what they want
  B (image)   — GPT-4o Vision analyses image + owner idea → caption
  C (surprise)— AI picks pillar, dish, timing fully autonomously

Graph flow:
  load_restaurant_context
        ↓
  load_recent_posts
        ↓
  analyse_image  (Mode B only, skipped otherwise)
        ↓
  pick_content_strategy
        ↓
  generate_captions  (IG + FB separately)
        ↓
  generate_image  (DALL-E, skipped if user provided image)
        ↓
  generate_hashtags
        ↓
  suggest_posting_time
        ↓
  END → return ContentOutput
"""

import os
import base64
import requests
from typing import TypedDict, Optional
from datetime import datetime, timedelta

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

from config.restaurant_config import get_restaurant_context
from config.cms_client import TENANT_ID

# ── LLMs ─────────────────────────────────────────────────────────────────────
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.85,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)
llm_precise = ChatOpenAI(
    model="gpt-4o",
    temperature=0.3,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)

# ── Content pillars ───────────────────────────────────────────────────────────
CONTENT_PILLARS = ["food", "experience", "offers", "behind_the_scenes"]

# ── Indian occasions ──────────────────────────────────────────────────────────
INDIAN_OCCASIONS = {
    1:  [(14, "Makar Sankranti"), (15, "Pongal"), (26, "Republic Day")],
    2:  [(14, "Valentine's Day")],
    3:  [(8, "Holi")],
    4:  [(14, "Baisakhi")],
    5:  [(12, "Mother's Day")],
    6:  [(21, "Father's Day")],
    8:  [(15, "Independence Day"), (19, "Raksha Bandhan")],
    9:  [(7, "Ganesh Chaturthi")],
    10: [(2, "Gandhi Jayanti"), (12, "Dussehra")],
    11: [(1, "Diwali"), (14, "Children's Day")],
    12: [(25, "Christmas"), (31, "New Year's Eve")],
}


def _get_upcoming_occasions(days_ahead: int = 7) -> list[str]:
    today = datetime.now()
    occasions = []
    for i in range(days_ahead + 1):
        check = today + timedelta(days=i)
        for day, name in INDIAN_OCCASIONS.get(check.month, []):
            if check.day == day:
                label = "today!" if i == 0 else "tomorrow" if i == 1 else f"in {i} days"
                occasions.append(f"{name} ({label})")
    return occasions


def _get_day_context() -> str:
    day = datetime.now().strftime("%A")
    guidance = {
        "Monday":    "Start of week — lighter, motivational. Lunch specials work well.",
        "Tuesday":   "Mid-week — signature dish spotlights, value posts.",
        "Wednesday": "Hump day — tease weekend specials and events.",
        "Thursday":  "Pre-weekend — push Sunday Brunch and reservations strongly.",
        "Friday":    "TGIF — celebration, date night, high engagement day.",
        "Saturday":  "Peak day — experiential, ambiance, brunch content.",
        "Sunday":    "Brunch day — Sunday Brunch push in morning, warm content in evening.",
    }
    return f"Today is {day}. {guidance.get(day, '')}"


def _get_season() -> str:
    month = datetime.now().month
    if month in [12, 1, 2]:
        return "Winter — perfect weather for warm wood-fired food and outdoor seating."
    elif month in [3, 4, 5]:
        return "Summer — refreshing drinks, light dishes, shaded seating."
    elif month in [6, 7, 8, 9]:
        return "Monsoon — cosy indoors, hot soups, comfort food vibes."
    return "Festive season — celebratory meals, family gatherings."


def _format_datetime(iso_str: str) -> str:
    """Format ISO datetime string to human-readable format."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%A, %d %b · %I:%M %p")
    except Exception:
        return iso_str


# ── Graph State ───────────────────────────────────────────────────────────────

class ContentState(TypedDict):
    # Input
    restaurant_id: str
    mode: str                          # 'idea' | 'image' | 'surprise'
    owner_idea: Optional[str]
    image_url: Optional[str]
    language: str
    user_provided_image: bool          # True if user uploaded an image (skip generation)

    # Loaded context
    restaurant_context: str
    restaurant_name: str
    restaurant_tone: str
    day_context: str
    season_context: str
    upcoming_occasions: list
    recent_post_topics: list

    # Strategy
    chosen_pillar: str
    chosen_dish: Optional[str]
    content_angle: str
    content_pillar_label: str
    image_description: Optional[str]

    # Output
    caption_instagram: str
    caption_facebook: str
    hashtags_brand: list
    hashtags_niche: list
    hashtags_discovery: list
    suggested_time: str
    suggested_time_reason: str
    generated_image_url: Optional[str]
    image_prompt: Optional[str]


# ── Node 1: Load restaurant context ──────────────────────────────────────────

def load_restaurant_context(state: ContentState) -> ContentState:
    ctx = get_restaurant_context(state.get("restaurant_id", TENANT_ID))
    return {
        **state,
        "restaurant_context":  ctx.to_prompt_context() if ctx else "Info unavailable.",
        "restaurant_name":     ctx.name if ctx else "the restaurant",
        "restaurant_tone":     ctx.conversation_tone if ctx else "friendly",
        "day_context":         _get_day_context(),
        "season_context":      _get_season(),
        "upcoming_occasions":  _get_upcoming_occasions(),
    }


# ── Node 2: Load recent posts ─────────────────────────────────────────────────

def load_recent_posts(state: ContentState) -> ContentState:
    try:
        from db import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as db:
            rows = db.execute(text(
                "SELECT caption FROM posts WHERE status='published' ORDER BY created_at DESC LIMIT 10"
            )).fetchall()
            topics = [r[0][:80] for r in rows if r[0]]
    except Exception as e:
        print(f"WARNING [Content Agent]: Could not load recent posts: {e}")
        topics = []
    return {**state, "recent_post_topics": topics}


# ── Node 3: Analyse image ─────────────────────────────────────────────────────

def analyse_image(state: ContentState) -> ContentState:
    if state["mode"] != "image" or not state.get("image_url"):
        return {**state, "image_description": None}
    try:
        resp = requests.get(state["image_url"], timeout=10)
        resp.raise_for_status()
        b64 = base64.b64encode(resp.content).decode("utf-8")
        ct = resp.headers.get("content-type", "image/jpeg")
        media_type = "image/png" if "png" in ct else "image/webp" if "webp" in ct else "image/jpeg"

        vision_llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.5,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            max_tokens=400,
        )
        result = vision_llm.invoke([
            SystemMessage(content=(
                f"You are analysing a photo for {state['restaurant_name']}. "
                "Describe what you see: dish, plating, colours, textures, mood, lighting, setting. "
                "Be specific and evocative — this description will be used to write a social media caption."
            )),
            HumanMessage(content=[
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}", "detail": "high"}},
                {"type": "text", "text": f"Owner note: {state.get('owner_idea') or 'No additional context.'}"},
            ])
        ])
        return {**state, "image_description": result.content.strip()}
    except Exception as e:
        print(f"WARNING [Content Agent]: Image analysis failed: {e}")
        return {**state, "image_description": f"Image provided. Owner note: {state.get('owner_idea', '')}"}


# ── Node 4: Pick content strategy ────────────────────────────────────────────

def pick_content_strategy(state: ContentState) -> ContentState:
    recent = "\n".join(state.get("recent_post_topics", [])) or "No recent posts yet."
    occasions = ", ".join(state.get("upcoming_occasions", [])) or "None this week."

    result = llm_precise.invoke([
        SystemMessage(content=f"""You are the content strategist for {state['restaurant_name']}.

RESTAURANT INFO:
{state['restaurant_context']}

CONTEXT:
- {state['day_context']}
- Season: {state['season_context']}
- Upcoming occasions: {occasions}
- Recent posts (DO NOT repeat these themes): {recent}

CONTENT PILLARS — rotate through these, avoid the most recently used:
- food: Spotlight a dish with sensory description
- experience: Vibe, ambiance, occasions
- offers: Sunday Brunch, events, seasonal specials
- behind_the_scenes: Wood fire, kitchen, chefs, craft

OWNER INPUT: {state.get('owner_idea') or 'None — choose the best option.'}
IMAGE DESCRIPTION: {state.get('image_description') or 'No image.'}

Reply in EXACTLY this format (no other text):
PILLAR: [food|experience|offers|behind_the_scenes]
DISH_OR_THEME: [specific dish OR general theme]
ANGLE: [one sentence creative direction]
LABEL: [short label like "Lamb Chops Spotlight" or "Sunday Brunch Vibes"]
"""),
        HumanMessage(content="Pick the best strategy."),
    ])

    parsed = {}
    for line in result.content.strip().split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            parsed[k.strip()] = v.strip()

    pillar = parsed.get("PILLAR", "food")
    if pillar not in CONTENT_PILLARS:
        pillar = "food"

    return {
        **state,
        "chosen_pillar":        pillar,
        "chosen_dish":          parsed.get("DISH_OR_THEME"),
        "content_angle":        parsed.get("ANGLE", ""),
        "content_pillar_label": parsed.get("LABEL", pillar.replace("_", " ").title()),
    }


# ── Node 5: Generate captions ─────────────────────────────────────────────────

def generate_captions(state: ContentState) -> ContentState:
    tone_map = {
        "professional": "warm and professional",
        "friendly":     "warm, friendly, conversational",
        "casual":       "casual, fun, relatable",
    }
    tone = tone_map.get(state["restaurant_tone"], "warm and friendly")
    occasions = ", ".join(state.get("upcoming_occasions", [])) or ""
    image_ctx = f"\nIMAGE DESCRIPTION: {state['image_description']}" if state.get("image_description") else ""

    lang = state.get("language", "auto")
    lang_instruction = (
        "Detect language from the owner's idea and write in that language. Default to English if no idea."
        if lang == "auto" else f"Write in {lang}."
    )

    base = f"""You are writing social media content for {state['restaurant_name']}.

TONE: {tone}
PILLAR: {state['chosen_pillar']} — {state['content_pillar_label']}
ANGLE: {state['content_angle']}
DISH/THEME: {state.get('chosen_dish', 'general')}{image_ctx}
OWNER IDEA: {state.get('owner_idea') or 'Use your creative judgment.'}
DAY: {state['day_context']}
SEASON: {state['season_context']}
OCCASIONS: {occasions}
LANGUAGE: {lang_instruction}

RESTAURANT INFO:
{state['restaurant_context']}
"""

    ig = llm.invoke([
        SystemMessage(content=base),
        HumanMessage(content="""Write an INSTAGRAM caption.
- First line is a scroll-stopping hook
- 3-5 lines total
- Sensory and evocative — make them taste/feel it
- 1-2 emojis woven in naturally
- Soft CTA at the end (visit, DM to reserve, link in bio)
- NO hashtags — those come separately
- Max 150 words
- Casual and warm"""),
    ])

    fb = llm.invoke([
        SystemMessage(content=base),
        HumanMessage(content="""Write a FACEBOOK caption.
- Slightly more descriptive and story-driven than Instagram
- 4-6 lines total
- More context about the dish/experience
- Warm but slightly more formal
- Clear CTA (reserve a table, visit us, call us)
- NO hashtags
- Max 200 words"""),
    ])

    return {
        **state,
        "caption_instagram": ig.content.strip(),
        "caption_facebook":  fb.content.strip(),
    }


# ── Node 5b: Generate image (LLM prompt → DALL-E 3) ──────────────────────────

def generate_image(state: ContentState) -> ContentState:
    """
    LLM writes a rich DALL-E prompt using the full restaurant context +
    content strategy, then DALL-E 3 generates the image.
    Skipped entirely if the user already provided an image.
    """

    # Skip if user uploaded their own image
    if state.get("user_provided_image"):
        print("INFO [Image Gen]: User provided image — skipping generation.")
        return {**state, "generated_image_url": None, "image_prompt": None}

    # ── Step 1: LLM writes the DALL-E prompt ─────────────────────────────────
    try:
        prompt_result = llm_precise.invoke([
            SystemMessage(content=f"""You are the visual director for {state['restaurant_name']}'s social media team.
You write detailed, cinematic image generation prompts for DALL-E 3.

Your prompts result in stunning, professional food and restaurant photography that stops the scroll.

RESTAURANT CONTEXT:
{state['restaurant_context']}

TODAY: {state['day_context']}
SEASON: {state['season_context']}
UPCOMING OCCASIONS: {', '.join(state.get('upcoming_occasions', [])) or 'None'}
"""),
            HumanMessage(content=f"""Write a DALL-E 3 prompt for this post:

Content pillar: {state['chosen_pillar']}
Dish / subject: {state.get('chosen_dish', 'signature dish')}
Creative angle: {state.get('content_angle', '')}
Post theme: {state['content_pillar_label']}
Caption mood (Instagram): {state.get('caption_instagram', '')[:200]}

Instructions:
- Describe the exact dish, plating style, garnishes, colours, textures
- Specify lighting (golden hour, warm tungsten, soft diffused, candle, etc.)
- Specify camera angle (overhead flat-lay, 45-degree hero shot, macro close-up, etc.)
- Describe the background and table setting to match the restaurant's brand
- Include seasonal and occasion cues if relevant
- Match the mood of the caption above
- End EVERY prompt with this exact sentence: "No text overlays, no watermarks, no people, photorealistic DSLR food photography."
- Output ONLY the prompt text, nothing else, no preamble, no labels"""),
        ])

        dalle_prompt = prompt_result.content.strip()
        print(f"INFO [Image Gen]: DALL-E prompt generated ({len(dalle_prompt)} chars)")

    except Exception as e:
        print(f"WARNING [Image Gen]: Prompt generation failed: {e}")
        return {**state, "generated_image_url": None, "image_prompt": None}

    # ── Step 2: DALL-E 3 generates the image ─────────────────────────────────
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.images.generate(
            model="dall-e-3",
            prompt=dalle_prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        generated_url = response.data[0].url
        print(f"INFO [Image Gen]: Image generated successfully → {generated_url[:60]}...")

        return {
            **state,
            "generated_image_url": generated_url,
            "image_prompt":        dalle_prompt,
        }

    except Exception as e:
        print(f"WARNING [Image Gen]: DALL-E generation failed: {e}")
        # Return the prompt even if image failed — useful for debugging
        return {
            **state,
            "generated_image_url": None,
            "image_prompt":        dalle_prompt,
        }


# ── Node 6: Generate hashtags ─────────────────────────────────────────────────

def generate_hashtags(state: ContentState) -> ContentState:
    result = llm_precise.invoke([
        SystemMessage(content=f"""You generate Instagram hashtags for {state['restaurant_name']}.
Restaurant context: {state['restaurant_context'][:600]}
Content: {state['content_pillar_label']} — {state.get('chosen_dish', '')}
Upcoming occasions: {', '.join(state.get('upcoming_occasions', []))}
"""),
        HumanMessage(content="""Generate hashtags in EXACTLY this format (no other text):

BRAND: #Firebelly #FirebellyDelhi #WoodFired (3-5 brand hashtags)
NICHE: #ButterChickenRisotto #WoodFiredFood #ModernIndian (8-10 niche hashtags)
DISCOVERY: #DelhiEats #DelhiRestaurants #LodhiColony #FoodiesOfDelhi #IndiaEats (8-12 discovery hashtags)

Replace the examples with real hashtags for this restaurant and content.
Only output three lines starting with BRAND:, NICHE:, DISCOVERY:"""),
    ])

    brand, niche, discovery = [], [], []
    for line in result.content.strip().split("\n"):
        line = line.strip()
        if line.startswith("BRAND:"):
            brand = [t for t in line.replace("BRAND:", "").split() if t.startswith("#")]
        elif line.startswith("NICHE:"):
            niche = [t for t in line.replace("NICHE:", "").split() if t.startswith("#")]
        elif line.startswith("DISCOVERY:"):
            discovery = [t for t in line.replace("DISCOVERY:", "").split() if t.startswith("#")]

    return {**state, "hashtags_brand": brand, "hashtags_niche": niche, "hashtags_discovery": discovery}


# ── Node 7: Suggest posting time ─────────────────────────────────────────────

def suggest_posting_time(state: ContentState) -> ContentState:
    now = datetime.now()
    day = now.strftime("%A")
    pillar = state["chosen_pillar"]

    schedule = {
        "food":              {"Monday": "12:00", "Tuesday": "13:00", "Wednesday": "12:30", "Thursday": "18:00", "Friday": "17:00", "Saturday": "10:30", "Sunday": "10:00"},
        "experience":        {"Monday": "19:00", "Tuesday": "19:30", "Wednesday": "18:30", "Thursday": "18:00", "Friday": "16:00", "Saturday": "14:00", "Sunday": "17:00"},
        "offers":            {"Monday": "10:00", "Tuesday": "11:00", "Wednesday": "10:00", "Thursday": "09:30", "Friday": "10:00", "Saturday": "09:00", "Sunday": "08:30"},
        "behind_the_scenes": {"Monday": "12:00", "Tuesday": "14:00", "Wednesday": "13:00", "Thursday": "15:00", "Friday": "11:00", "Saturday": "11:00", "Sunday": "14:00"},
    }

    reasons = {
        "food":              {"Monday": "Lunch hour inspiration", "Tuesday": "Post-lunch scroll", "Wednesday": "Mid-week food mood", "Thursday": "Pre-weekend dinner planning", "Friday": "Weekend dinner excitement", "Saturday": "Brunch and lunch planning", "Sunday": "Sunday brunch prime time"},
        "experience":        {"Monday": "Evening aspirational scroll", "Tuesday": "Evening relaxation", "Wednesday": "Weekend planning begins", "Thursday": "Weekend anticipation peak", "Friday": "TGIF — highest engagement", "Saturday": "Weekend afternoon peak", "Sunday": "Sunday evening reflection"},
        "offers":            {"Monday": "Week planning window", "Tuesday": "Mid-morning discovery", "Wednesday": "Hump day value posts", "Thursday": "Pre-weekend planning", "Friday": "Friday morning reach peak", "Saturday": "Early decision window", "Sunday": "Brunch decision time"},
        "behind_the_scenes": {"Monday": "Lunchtime curiosity", "Tuesday": "Afternoon engagement", "Wednesday": "Mid-week discovery", "Thursday": "Afternoon scroll", "Friday": "Friday morning high reach", "Saturday": "Weekend morning engagement", "Sunday": "Sunday afternoon"},
    }

    pillar_schedule = schedule.get(pillar, schedule["food"])
    pillar_reasons  = reasons.get(pillar, reasons["food"])
    time_str = pillar_schedule.get(day, "12:00")
    reason   = pillar_reasons.get(day, "Peak engagement window")

    # Boost for occasions
    occasions = state.get("upcoming_occasions", [])
    if occasions and any("today" in o or "tomorrow" in o for o in occasions):
        time_str = "09:00"
        reason = f"Early post to ride the {occasions[0]} wave"

    h, m = int(time_str.split(":")[0]), int(time_str.split(":")[1])
    dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if dt <= now:
        dt += timedelta(days=1)

    return {**state, "suggested_time": dt.isoformat(), "suggested_time_reason": reason}


# ── Build graph ───────────────────────────────────────────────────────────────

def build_content_graph():
    g = StateGraph(ContentState)
    g.add_node("load_restaurant_context", load_restaurant_context)
    g.add_node("load_recent_posts",       load_recent_posts)
    g.add_node("analyse_image",           analyse_image)
    g.add_node("pick_content_strategy",   pick_content_strategy)
    g.add_node("generate_captions",       generate_captions)
    g.add_node("generate_image",          generate_image)       # NEW
    g.add_node("generate_hashtags",       generate_hashtags)
    g.add_node("suggest_posting_time",    suggest_posting_time)

    g.set_entry_point("load_restaurant_context")
    g.add_edge("load_restaurant_context", "load_recent_posts")
    g.add_edge("load_recent_posts",       "analyse_image")
    g.add_edge("analyse_image",           "pick_content_strategy")
    g.add_edge("pick_content_strategy",   "generate_captions")
    g.add_edge("generate_captions",       "generate_image")     # NEW
    g.add_edge("generate_image",          "generate_hashtags")  # NEW (was captions→hashtags)
    g.add_edge("generate_hashtags",       "suggest_posting_time")
    g.add_edge("suggest_posting_time",    END)

    return g.compile()


_content_graph = None

def get_content_graph():
    global _content_graph
    if _content_graph is None:
        _content_graph = build_content_graph()
    return _content_graph


# ── Public interface ──────────────────────────────────────────────────────────

def generate_content(
    mode: str,
    restaurant_id: str = TENANT_ID,
    owner_idea: str | None = None,
    image_url: str | None = None,
    language: str = "auto",
) -> dict:
    """
    Entry point called from FastAPI.
    mode: 'idea' | 'image' | 'surprise'
    """
    # If an image_url was passed in, user provided the image — don't generate one
    user_provided_image = image_url is not None

    result = get_content_graph().invoke({
        "restaurant_id":        restaurant_id,
        "mode":                 mode,
        "owner_idea":           owner_idea,
        "image_url":            image_url,
        "language":             language,
        "user_provided_image":  user_provided_image,
        "recent_post_topics":   [],
        "restaurant_context":   "",
        "restaurant_name":      "",
        "restaurant_tone":      "friendly",
        "day_context":          "",
        "season_context":       "",
        "upcoming_occasions":   [],
        "chosen_pillar":        "",
        "chosen_dish":          None,
        "content_angle":        "",
        "content_pillar_label": "",
        "image_description":    None,
        "caption_instagram":    "",
        "caption_facebook":     "",
        "hashtags_brand":       [],
        "hashtags_niche":       [],
        "hashtags_discovery":   [],
        "suggested_time":       "",
        "suggested_time_reason": "",
        "generated_image_url":  None,
        "image_prompt":         None,
    })

    all_tags = result["hashtags_brand"] + result["hashtags_niche"] + result["hashtags_discovery"]

    return {
        # Captions
        "caption_instagram":     result["caption_instagram"],
        "caption_facebook":      result["caption_facebook"],

        # Hashtags — all formats
        "hashtags":              all_tags,                         # flat list for frontend chips
        "hashtags_brand":        result["hashtags_brand"],
        "hashtags_niche":        result["hashtags_niche"],
        "hashtags_discovery":    result["hashtags_discovery"],
        "hashtags_all":          " ".join(all_tags),

        # Schedule — nested object that frontend expects
        "suggested_schedule": {
            "datetime":     result["suggested_time"],
            "datetime_str": _format_datetime(result["suggested_time"]),
            "reason":       result["suggested_time_reason"],
            "pillar":       result["chosen_pillar"],
        },

        # Strategy metadata
        "chosen_pillar":         result["chosen_pillar"],
        "content_pillar_label":  result["content_pillar_label"],
        "content_theme":         result["content_pillar_label"],   # alias for frontend
        "chosen_dish":           result.get("chosen_dish"),
        "content_angle":         result.get("content_angle"),
        "image_description":     result.get("image_description"),

        # Image generation
        "generated_image_url":   result.get("generated_image_url"),
        "image_prompt":          result.get("image_prompt"),
    }