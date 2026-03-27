"""
Firebelly AI Chatbot — ai_reply.py
------------------------------------
Two separate AI personalities:
  - EMBER  → DMs (private, helpful, full info, conversational)
  - BLAZE  → Comments (public, short, witty, brand-voice, no private info)
"""

import os
import requests
from datetime import datetime

# ---------------------------------------------------------------------------
# FIREBELLY RESTAURANT KNOWLEDGE BASE (swap with CMS fetch later)
# ---------------------------------------------------------------------------
FIREBELLY_KNOWLEDGE = """
RESTAURANT: Firebelly
TAGLINE: Wood-fired flavours, warm hearts.

LOCATION:
  Address: 47, Ground Floor, Meherchand Market, Lodhi Colony, New Delhi – 110003
  Landmark: Opposite Lodhi Garden Gate No. 2

HOURS:
  Monday–Thursday: 12:00 PM – 11:00 PM
  Friday–Saturday: 12:00 PM – 12:00 AM (Midnight)
  Sunday: 11:00 AM – 10:30 PM (Sunday Brunch available)
  Kitchen closes 45 minutes before closing time.

CUISINE: Modern Indian with wood-fired cooking techniques.

MENU HIGHLIGHTS:
  Starters:
    - Firebelly Signature Chicken Wings (wood-fired, 3 sauces) — ₹595
    - Burrata & Heirloom Tomato Salad — ₹645
    - Dal Chawal Arancini (crispy risotto balls, makhani dip) — ₹425
    - Smoked Mushroom Tikka — ₹395

  Mains:
    - Wood-Fired Lamb Chops (rosemary jus, saffron potato) — ₹1,495
    - Butter Chicken Risotto (most-loved fusion dish) — ₹795
    - Paneer Makhani Ravioli — ₹695
    - 28-Day Aged Firebelly Burger (double patty, truffle fries) — ₹895

  Wood-Fired Pizzas:
    - Spicy Nduja & Burrata — ₹795
    - Tandoori Paneer Pizza — ₹695
    - Prawn Aglio Olio Pizza — ₹845

  Desserts:
    - Gulab Jamun Cheesecake — ₹425
    - Warm Chocolate Fondant (vanilla ice cream) — ₹395
    - Mango Kulfi Tart (seasonal) — ₹375

  Sunday Brunch (11 AM – 4 PM):
    - All-you-can-eat with free-flow mocktails — ₹1,499 per person
    - Alcoholic free-flow add-on — ₹799 extra

DRINKS:
  - Full bar: cocktails, mocktails, wine, craft beer
  - Signature: "The Firebelly" (mango, chilli, gin) — ₹595
  - Non-alcoholic: Fresh juices, lassi bar, specialty teas — ₹195–₹295

RESERVATIONS:
  - WhatsApp: +91 98765 43210 (preferred)
  - Phone: +91 11 4567 8900
  - Online: Dineout or EazyDiner (search "Firebelly Lodhi")
  - Walk-ins welcome but reservations recommended on weekends
  - Groups of 10+: Call directly for private dining

DELIVERY & TAKEAWAY:
  - Delivery via Zomato and Swiggy (select items only)
  - Takeaway available — call ahead: +91 11 4567 8900
  - Delivery radius: 7 km from Lodhi Colony

PRIVATE DINING & EVENTS:
  - Private dining room: 8–20 guests
  - Full venue buyout: 80–120 guests
  - Contact: events@firebelly.in

PARKING:
  - Street parking on Meherchand Market Road
  - Valet parking Friday & Saturday evenings (₹100)

DIETARY:
  - Vegetarian: ~40% of menu, clearly marked
  - Vegan: Several options, ask staff
  - Gluten-free: Available on request
  - No pork on the menu

AMBIANCE:
  - Warm rustic-industrial interiors with open wood-fire kitchen
  - Outdoor garden seating (weather permitting)
  - Smart casual dress code (no flip-flops)
"""

# ---------------------------------------------------------------------------
# ESCALATION KEYWORDS (DMs only)
# ---------------------------------------------------------------------------
ESCALATION_KEYWORDS = [
    "complaint", "refund", "food poisoning", "manager", "legal",
    "worst experience", "disgusting", "rude staff", "health department",
    "consumer forum", "harassed", "sick", "horrible"
]

ESCALATION_RESPONSE = (
    "I'm so sorry to hear that — this is absolutely not the experience we want for you. "
    "Our management team will personally reach out to you very shortly. "
    "Could you share your contact number or email so we can make this right? 🙏"
)

UNKNOWN_RESPONSE = (
    "Great question! I want to make sure you get the most accurate answer — "
    "WhatsApp us at +91 98765 43210 and we'll get back to you right away! 😊"
)


# ===========================================================================
# EMBER — DM PERSONALITY
# Private, conversational, full info, helpful
# ===========================================================================
EMBER_SYSTEM_PROMPT = f"""You are Ember, the friendly digital host for Firebelly restaurant in New Delhi.
You respond to private Direct Messages from customers on Facebook and Instagram.

YOUR PERSONALITY:
- Warm, welcoming, genuine — like a great restaurant host
- Helpful and solution-focused
- Naturally upsell where it fits (e.g. mention Sunday Brunch when relevant) — never pushy
- Use sensory language when describing food
- Conversational, like texting a friend

YOUR RULES:
1. Respond in the same language the customer used (Hindi/Hinglish/English)
2. Keep replies under 100 words
3. For reservations, always give WhatsApp (+91 98765 43210) as first option
4. If you don't know the answer: "Great question! Let me get our team to reach out — could you share your number or email?"
5. NEVER make up information. Only use the knowledge base below.
6. Do NOT use bullet points — write like a human texts
7. On Instagram be slightly more casual; on Facebook slightly more formal

FIREBELLY KNOWLEDGE BASE:
{FIREBELLY_KNOWLEDGE}

TODAY: {datetime.now().strftime("%A, %B %d, %Y")}
"""


# ===========================================================================
# BLAZE — COMMENT PERSONALITY
# Public, short, witty, brand voice, NO private info
# ===========================================================================
BLAZE_SYSTEM_PROMPT = f"""You are Blaze, the witty and warm public voice of Firebelly restaurant on social media.
You reply to public comments on Firebelly's Instagram and Facebook posts.

YOUR PERSONALITY:
- Fun, punchy, on-brand
- Short and snappy — comments must stop the scroll
- Warm but never desperate or over-promotional
- 1–2 emojis max
- Playful wit is great — never sarcastic

YOUR RULES:
1. Keep replies under 15 words — short is everything in comments
2. NEVER share private info publicly (no phone numbers, addresses, or prices)
3. For any question needing details, redirect to DM: "Slide into our DMs! 📩"
4. Respond in the same language as the commenter
5. For compliments: acknowledge warmly, tease a dish
6. For questions: give a teaser, redirect to DMs
7. For one-word comments like "Nice" or fire emoji: reply fun and brand-relevant
8. NEVER make up information
9. Punchy only — no long sentences

GOOD EXAMPLES:
- "Nice" → "Wood-fired nice 🔥 Come see for yourself!"
- "Looks amazing" → "Wait till you taste it 😏"
- "Do you have veg options?" → "Plenty! Slide into our DMs for the full menu 📩"
- "Best restaurant!" → "You just made our whole kitchen smile 🙌"
- "What are your timings?" → "DM us and we'll send all the deets! 📩"
- "Nice ring" → "Our wood fire agrees 🔥"
- "Nice Insights" → "Glad you think so! Come experience it in person 🙌"

TODAY: {datetime.now().strftime("%A, %B %d, %Y")}
"""


# ---------------------------------------------------------------------------
# CORE FUNCTION: generate_ai_reply
# ---------------------------------------------------------------------------
def generate_ai_reply(
    message: str,
    platform: str = "instagram",
    sender_name: str = "there",
    interaction_type: str = "message",
    conversation_history: list[dict] | None = None,
) -> dict:
    """
    Generate an AI reply for a DM or comment.

    Args:
        message: The incoming message/comment text
        platform: 'facebook' or 'instagram'
        sender_name: Customer's name
        interaction_type: 'message' → Ember | 'comment' → Blaze
        conversation_history: Prior DM turns (ignored for comments)

    Returns:
        dict: reply, escalate, confidence, ai_persona
    """
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openai_api_key:
        return {
            "reply": UNKNOWN_RESPONSE,
            "escalate": False,
            "confidence": "no_key",
            "ai_persona": "none",
            "error": "OPENAI_API_KEY not set"
        }

    # Escalation check — DMs only
    if interaction_type == "message":
        message_lower = message.lower()
        if any(kw in message_lower for kw in ESCALATION_KEYWORDS):
            return {
                "reply": ESCALATION_RESPONSE,
                "escalate": True,
                "confidence": "escalated",
                "ai_persona": "ember"
            }

    # Pick persona based on interaction type
    if interaction_type == "comment":
        system_prompt = BLAZE_SYSTEM_PROMPT
        persona = "blaze"
        max_tokens = 60
        temperature = 0.85
    else:
        system_prompt = EMBER_SYSTEM_PROMPT
        persona = "ember"
        max_tokens = 180
        temperature = 0.75

    # Build message list
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history for DMs only
    if interaction_type == "message" and conversation_history:
        for turn in conversation_history[-6:]:
            messages.append(turn)

    platform_note = "instagram" if platform == "instagram" else "facebook"
    label = "Comment" if interaction_type == "comment" else "DM"
    user_message = (
        f"[Platform: {platform_note}] [{label} from: {sender_name}]\n{message}"
    )
    messages.append({"role": "user", "content": user_message})

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        reply_text = data["choices"][0]["message"]["content"].strip()

        return {
            "reply": reply_text,
            "escalate": False,
            "confidence": "ai_generated",
            "ai_persona": persona,
        }

    except requests.exceptions.Timeout:
        fallback = UNKNOWN_RESPONSE if interaction_type == "message" else "Thanks for the love! 🔥"
        return {"reply": fallback, "escalate": False, "confidence": "timeout", "ai_persona": persona}
    except Exception as e:
        fallback = UNKNOWN_RESPONSE if interaction_type == "message" else "Thanks for the love! 🔥"
        return {"reply": fallback, "escalate": False, "confidence": "error", "ai_persona": persona, "error": str(e)}


# ---------------------------------------------------------------------------
# HELPER
# ---------------------------------------------------------------------------
def should_auto_reply(interaction_type: str, is_outgoing: bool) -> bool:
    """Only auto-reply to incoming DMs. Comments handled separately when enabled."""
    return interaction_type == "message" and not is_outgoing