"""
Firebelly AI DM Chatbot — ai_reply.py
--------------------------------------
Drop this file into your /backend folder alongside main.py.
It handles all AI reply generation using OpenAI GPT-4o.
Restaurant data is currently dummy data — swap with CMS fetch later.
"""

import os
import json
import requests
from datetime import datetime

# ---------------------------------------------------------------------------
# FIREBELLY RESTAURANT KNOWLEDGE BASE (Dummy Data — replace with CMS later)
# ---------------------------------------------------------------------------
FIREBELLY_KNOWLEDGE = """
RESTAURANT: Firebelly
TAGLINE: Wood-fired flavours, warm hearts.

LOCATION:
  Address: 47, Ground Floor, Meherchand Market, Lodhi Colony, New Delhi – 110003
  Landmark: Opposite Lodhi Garden Gate No. 2
  Google Maps: https://maps.app.goo.gl/firebelly (placeholder)

HOURS:
  Monday–Thursday: 12:00 PM – 11:00 PM
  Friday–Saturday: 12:00 PM – 12:00 AM (Midnight)
  Sunday: 11:00 AM – 10:30 PM (Sunday Brunch available)
  Note: Kitchen closes 45 minutes before closing time.

CUISINE: Modern Indian with wood-fired cooking techniques. Think tandoor-meets-global.

MENU HIGHLIGHTS:
  Starters:
    - Firebelly Signature Chicken Wings (wood-fired, 3 sauces) — ₹595
    - Burrata & Heirloom Tomato Salad — ₹645
    - Dal Chawal Arancini (crispy risotto balls, makhani dip) — ₹425
    - Smoked Mushroom Tikka — ₹395
  
  Mains:
    - Wood-Fired Lamb Chops (rosemary jus, saffron potato) — ₹1,495
    - Butter Chicken Risotto (our most-loved fusion dish) — ₹795
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
  
  Sunday Brunch Special (11 AM – 4 PM):
    - All-you-can-eat brunch with free-flow mocktails — ₹1,499 per person
    - Free-flow alcoholic beverages add-on — ₹799 extra

DRINKS:
  - Full bar with cocktails, mocktails, wine, and craft beer
  - Signature cocktail: "The Firebelly" (mango, chilli, gin) — ₹595
  - Non-alcoholic: Fresh juices, lassi bar, specialty teas — ₹195–₹295

RESERVATIONS:
  - WhatsApp: +91 98765 43210 (preferred for quick booking)
  - Phone: +91 11 4567 8900
  - Online: via Dineout or EazyDiner (search "Firebelly Lodhi")
  - Walk-ins welcome but reservations strongly recommended on weekends
  - For groups of 10+: Call directly for private dining arrangements

DELIVERY & TAKEAWAY:
  - Delivery via Zomato and Swiggy (select items only — pizza, burgers, starters)
  - Full menu NOT available for delivery (wood-fired dishes best eaten fresh)
  - Takeaway available — call ahead: +91 11 4567 8900
  - Delivery radius: 7 km from Lodhi Colony

PRIVATE DINING & EVENTS:
  - Private dining room available for 8–20 guests
  - Full venue buyout for 80–120 guests
  - Customised menus available for corporate events, birthdays, anniversaries
  - Contact: events@firebelly.in

PARKING:
  - Street parking available on Meherchand Market Road
  - Valet parking on Friday & Saturday evenings (₹100 charge)

DIETARY OPTIONS:
  - Vegetarian: Clearly marked on menu, ~40% of menu is vegetarian
  - Vegan: Several options available, ask staff for modifications
  - Gluten-free: Available on request for most dishes
  - No pork on the menu

AMBIANCE:
  - Warm, rustic-industrial interiors with an open wood-fire kitchen
  - Outdoor seating in a garden area (weather permitting)
  - Great for: dates, family dinners, work lunches, celebrations
  - Dress code: Smart casual (no flip-flops or beachwear)

CONTACT:
  - Instagram: @firebellyrestaurant
  - Facebook: facebook.com/firebellyrestaurant
  - Email: hello@firebelly.in
  - Phone: +91 11 4567 8900
"""

# ---------------------------------------------------------------------------
# SYSTEM PROMPT FOR THE AI
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = f"""You are Ember, the friendly and warm digital host for Firebelly restaurant in New Delhi.
Your job is to respond to customer DMs and comments on Facebook and Instagram.

YOUR PERSONALITY:
- Warm, welcoming, and genuine — like a great restaurant host
- Subtly enthusiastic about the food without being pushy
- Witty but never sarcastic
- Always helpful and solution-focused
- When mentioning food, make it sound genuinely delicious (use sensory language naturally)
- Lightly upsell where it feels natural — never forceful. For example, if someone asks about mains, mention Sunday Brunch as a great-value option

YOUR RULES:
1. Always respond in the same language the customer used (Hindi/Hinglish/English)
2. Keep replies concise — DMs should feel like a conversation, not a brochure
3. For reservations: always give the WhatsApp number (+91 98765 43210) as the primary option
4. If the question is irrelevant or nonsensical, gently redirect: ask what you can help them with regarding Firebelly
5. If a question is beyond your knowledge (e.g. specific dietary allergies, custom event quotes, legal/complaint matters): say "That's a great question — let me get our team to reach out to you directly! Could you share your phone number or email?"
6. NEVER make up information. Only use what is in the knowledge base below.
7. Keep replies under 120 words. Be natural, not robotic.
8. Do NOT use bullet points in DM replies — write like a human texts.
9. For platform context: on Instagram be slightly more casual; on Facebook slightly more formal.

FIREBELLY KNOWLEDGE BASE:
{FIREBELLY_KNOWLEDGE}

ESCALATION TRIGGER PHRASES (if customer says these, use the escalation response):
- complaint, refund, food poisoning, manager, legal, worst experience, disgusting, rude staff

TODAY'S DATE: {datetime.now().strftime("%A, %B %d, %Y")}
"""

ESCALATION_RESPONSE = (
    "I'm so sorry to hear that — this is absolutely not the experience we want for you. "
    "I'm flagging this to our management team right now and they'll personally reach out to you very shortly. "
    "Could you share your contact number or email so we can make this right? 🙏"
)

UNKNOWN_RESPONSE = (
    "That's a great question! I want to make sure you get the most accurate answer — "
    "let me connect you with our team who can help. Could you share your phone number or email? "
    "Alternatively, WhatsApp us directly at +91 98765 43210 and we'll get back to you right away! 😊"
)


# ---------------------------------------------------------------------------
# CORE FUNCTION: generate_ai_reply
# ---------------------------------------------------------------------------
def generate_ai_reply(
    message: str,
    platform: str = "instagram",
    sender_name: str = "there",
    conversation_history: list[dict] | None = None,
) -> dict:
    """
    Generate an AI reply for a given DM/comment.
    
    Args:
        message: The incoming customer message
        platform: 'facebook' or 'instagram'
        sender_name: Customer's name for personalisation
        conversation_history: Previous messages in this thread (list of {role, content})
    
    Returns:
        dict with keys: reply (str), escalate (bool), confidence (str)
    """
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openai_api_key:
        return {
            "reply": UNKNOWN_RESPONSE,
            "escalate": False,
            "confidence": "no_key",
            "error": "OPENAI_API_KEY not set in environment"
        }

    # Check for escalation triggers first
    escalation_keywords = [
        "complaint", "refund", "food poisoning", "manager", "legal",
        "worst experience", "disgusting", "rude staff", "health department",
        "consumer forum", "harassed"
    ]
    message_lower = message.lower()
    if any(kw in message_lower for kw in escalation_keywords):
        return {
            "reply": ESCALATION_RESPONSE,
            "escalate": True,
            "confidence": "escalated"
        }

    # Build message history
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Add prior conversation context if available
    if conversation_history:
        for turn in conversation_history[-6:]:  # last 3 exchanges max
            messages.append(turn)

    # Add platform context to the user message
    platform_note = "instagram" if platform == "instagram" else "facebook"
    user_message = (
        f"[Platform: {platform_note}] [Customer name: {sender_name}]\n"
        f"Customer message: {message}"
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
                "max_tokens": 200,
                "temperature": 0.75,
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
        }

    except requests.exceptions.Timeout:
        return {
            "reply": UNKNOWN_RESPONSE,
            "escalate": False,
            "confidence": "timeout",
            "error": "OpenAI request timed out"
        }
    except Exception as e:
        return {
            "reply": UNKNOWN_RESPONSE,
            "escalate": False,
            "confidence": "error",
            "error": str(e)
        }


# ---------------------------------------------------------------------------
# BATCH AUTO-REPLY: called from main.py webhook handler
# ---------------------------------------------------------------------------
def should_auto_reply(interaction_type: str, is_outgoing: bool) -> bool:
    """Only auto-reply to incoming DMs (messages), not comments or outgoing."""
    return interaction_type == "message" and not is_outgoing