"""
agents/reply_agent.py
----------------------
LangGraph-powered reply agent for Facebook and Instagram DMs and comments.

Graph flow:
  load_context → classify_intent → route →
    [ember_dm | blaze_comment | escalate | book_table]
  → save_memory → return reply

Two personas:
  Ember — private DMs: full knowledge, conversational, can book tables
  Blaze — public comments: short, punchy, brand voice, no private info
"""

import os
from typing import TypedDict, Literal, Annotated
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from config.restaurant_config import get_restaurant_context, RestaurantContext
from config.cms_client import TENANT_ID
from tools.cms_tools import CMS_TOOLS
from tools.memory_tools import (
    get_conversation_history,
    get_customer_profile,
    save_message,
    update_customer_profile,
    format_customer_context,
)

# ── LLM ──────────────────────────────────────────────────────────────────────
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.75,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)

llm_with_tools = llm.bind_tools(CMS_TOOLS)

# ── Graph State ───────────────────────────────────────────────────────────────

class ReplyState(TypedDict):
    # Input
    restaurant_id: str
    platform: str           # 'facebook' | 'instagram'
    interaction_type: str   # 'message' | 'comment'
    customer_id: str
    customer_name: str | None
    message: str

    # Loaded context
    restaurant_context: str      # formatted restaurant info from CMS
    customer_context: str        # memory / profile summary
    conversation_history: list   # prior messages

    # Routing
    intent: str             # reservation | menu | hours | complaint | general | off_topic
    escalate: bool

    # Output
    reply: str
    ai_persona: str         # 'ember' | 'blaze'
    confidence: str


# ── Escalation keywords ───────────────────────────────────────────────────────
ESCALATION_KEYWORDS = [
    "complaint", "refund", "food poisoning", "manager", "legal",
    "worst experience", "disgusting", "rude staff", "health department",
    "consumer forum", "harassed", "sick", "horrible", "unacceptable"
]

ESCALATION_REPLY = (
    "I'm so sorry to hear that — this is absolutely not the experience we want for you. "
    "Our management team will personally reach out to you very shortly. "
    "Could you share your contact number or email so we can make this right? 🙏"
)


# ── Node 1: Load context ──────────────────────────────────────────────────────

def load_context(state: ReplyState) -> ReplyState:
    """Load restaurant config from CMS and customer memory from DB."""
    restaurant_id = state.get("restaurant_id", TENANT_ID)

    # Restaurant context from CMS
    ctx = get_restaurant_context(restaurant_id)
    restaurant_context = ctx.to_prompt_context() if ctx else "Restaurant info unavailable."

    # Customer memory
    profile = get_customer_profile(
        platform=state["platform"],
        customer_id=state["customer_id"],
        restaurant_id=restaurant_id,
    )
    customer_context = format_customer_context(profile)

    # Conversation history (for DMs only — comments don't have threads)
    history = []
    if state["interaction_type"] == "message":
        history = get_conversation_history(
            platform=state["platform"],
            customer_id=state["customer_id"],
            restaurant_id=restaurant_id,
        )

    return {
        **state,
        "restaurant_context": restaurant_context,
        "customer_context": customer_context,
        "conversation_history": history,
        "escalate": False,
    }


# ── Node 2: Classify intent ───────────────────────────────────────────────────

def classify_intent(state: ReplyState) -> ReplyState:
    """Quickly classify what the customer wants — used for routing."""

    # Fast escalation check before hitting the LLM
    msg_lower = state["message"].lower()
    if any(kw in msg_lower for kw in ESCALATION_KEYWORDS):
        return {**state, "intent": "complaint", "escalate": True}

    classifier = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    result = classifier.invoke([
        SystemMessage(content=(
            "Classify the customer message into exactly one of these intents:\n"
            "reservation, menu, hours, complaint, general, off_topic\n\n"
            "reservation = wants to book a table\n"
            "menu = asking about food, drinks, prices, dietary\n"
            "hours = asking about opening times, location\n"
            "complaint = expressing dissatisfaction, bad experience\n"
            "general = greeting, general enquiry about the restaurant\n"
            "off_topic = has nothing to do with the restaurant\n\n"
            "Reply with ONLY the intent word, nothing else."
        )),
        HumanMessage(content=state["message"]),
    ])

    intent = result.content.strip().lower()
    if intent not in ["reservation", "menu", "hours", "complaint", "general", "off_topic"]:
        intent = "general"

    return {**state, "intent": intent, "escalate": intent == "complaint"}


# ── Node 3: Router ────────────────────────────────────────────────────────────

def route_message(state: ReplyState) -> Literal["escalate", "blaze_comment", "ember_dm"]:
    """Route to the right handler based on type and intent."""
    if state.get("escalate"):
        return "escalate"
    if state["interaction_type"] == "comment":
        return "blaze_comment"
    return "ember_dm"


# ── Node 4a: Escalation handler ───────────────────────────────────────────────

def escalate(state: ReplyState) -> ReplyState:
    """Handle complaints — warm empathetic reply, flag for human follow-up."""
    return {
        **state,
        "reply": ESCALATION_REPLY,
        "ai_persona": "ember",
        "confidence": "escalated",
    }


# ── Node 4b: Blaze — comment handler ─────────────────────────────────────────

def blaze_comment(state: ReplyState) -> ReplyState:
    """
    Short punchy public comment replies.
    No private info. Max 15 words. Brand voice.
    """
    platform_note = "Instagram" if state["platform"] == "instagram" else "Facebook"
    ctx = get_restaurant_context(state.get("restaurant_id", TENANT_ID))
    restaurant_name = ctx.name if ctx else "the restaurant"

    system = f"""You are Blaze, the witty public voice of {restaurant_name} on social media.
You reply to public {platform_note} comments.

RULES:
- Under 15 words maximum
- Never share phone numbers, addresses, or prices publicly
- For any detailed question: redirect to DMs — "Slide into our DMs! 📩"
- 1-2 emojis max
- Warm, fun, punchy — scroll-stopping
- Same language as the commenter

EXAMPLES:
- "Nice" → "Wood-fired nice 🔥 Come see for yourself!"
- "Looks amazing" → "Wait till you taste it 😏"
- "Do you have veg options?" → "Plenty! Slide into our DMs 📩"
- "What are your timings?" → "DM us and we'll send all the deets! 📩"
"""

    result = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=f"[Comment from {state.get('customer_name', 'someone')}]: {state['message']}"),
    ])

    return {
        **state,
        "reply": result.content.strip(),
        "ai_persona": "blaze",
        "confidence": "ai_generated",
    }


# ── Node 4c: Ember — DM handler ──────────────────────────────────────────────

def ember_dm(state: ReplyState) -> ReplyState:
    """
    Full conversational DM handler with tool access.
    Ember can fetch live menu, check availability, and book tables.
    """
    platform_note = "Instagram" if state["platform"] == "instagram" else "Facebook"
    ctx = get_restaurant_context(state.get("restaurant_id", TENANT_ID))
    restaurant_name = ctx.name if ctx else "the restaurant"
    tone = ctx.conversation_tone if ctx else "friendly"

    tone_map = {
        "professional": "warm and professional",
        "friendly": "warm, friendly, conversational",
        "casual": "casual and fun",
    }
    tone_desc = tone_map.get(tone, "warm and friendly")

    system = f"""You are Ember, the digital host for {restaurant_name} on {platform_note}.
You handle private Direct Messages from customers.

PERSONALITY: {tone_desc}. Like a great restaurant host — helpful, knowledgeable, genuine.
Naturally upsell where it fits. Use sensory language for food. Never pushy.

RULES:
1. Reply in the same language the customer used (Hindi/Hinglish/English)
2. Keep replies under 100 words — DMs are conversations
3. Use tools to get LIVE data: menu, hours, availability — never guess
4. For reservations: always confirm name, phone, date, time, party size before booking
5. If you don't know something: "Let me get our team to help — could you share your number?"
6. Do NOT use bullet points — write like a human texts
7. Instagram: slightly more casual. Facebook: slightly more formal.

CUSTOMER CONTEXT:
{state.get('customer_context', 'New customer.')}

RESTAURANT INFO:
{state.get('restaurant_context', '')}
"""

    # Build message list with conversation history
    messages = [SystemMessage(content=system)]
    for turn in state.get("conversation_history", []):
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        else:
            messages.append(AIMessage(content=turn["content"]))
    messages.append(HumanMessage(content=state["message"]))

    # Agentic loop — let Ember call tools if needed
    response = llm_with_tools.invoke(messages)

    # If tool calls were made, execute them and get final response
    if response.tool_calls:
        tool_node = ToolNode(CMS_TOOLS)
        tool_results = tool_node.invoke({"messages": messages + [response]})
        messages_with_tools = messages + [response] + tool_results["messages"]
        response = llm.invoke(messages_with_tools)

    return {
        **state,
        "reply": response.content.strip(),
        "ai_persona": "ember",
        "confidence": "ai_generated",
    }


# ── Node 5: Save memory ───────────────────────────────────────────────────────

def save_memory(state: ReplyState) -> ReplyState:
    """Persist this conversation turn and update customer profile."""
    restaurant_id = state.get("restaurant_id", TENANT_ID)

    # Save incoming message
    save_message(
        platform=state["platform"],
        customer_id=state["customer_id"],
        role="user",
        content=state["message"],
        restaurant_id=restaurant_id,
    )

    # Save AI reply
    save_message(
        platform=state["platform"],
        customer_id=state["customer_id"],
        role="assistant",
        content=state["reply"],
        restaurant_id=restaurant_id,
    )

    # Update customer profile
    update_customer_profile(
        platform=state["platform"],
        customer_id=state["customer_id"],
        customer_name=state.get("customer_name"),
        sentiment="negative" if state.get("escalate") else "positive",
        topics=[state.get("intent", "general")],
        escalated=state.get("escalate", False),
        restaurant_id=restaurant_id,
    )

    return state


# ── Build the graph ───────────────────────────────────────────────────────────

def build_reply_graph() -> StateGraph:
    graph = StateGraph(ReplyState)

    # Add nodes
    graph.add_node("load_context",    load_context)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("escalate",        escalate)
    graph.add_node("blaze_comment",   blaze_comment)
    graph.add_node("ember_dm",        ember_dm)
    graph.add_node("save_memory",     save_memory)

    # Entry point
    graph.set_entry_point("load_context")

    # Edges
    graph.add_edge("load_context", "classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        route_message,
        {
            "escalate":     "escalate",
            "blaze_comment": "blaze_comment",
            "ember_dm":     "ember_dm",
        }
    )
    graph.add_edge("escalate",      "save_memory")
    graph.add_edge("blaze_comment", "save_memory")
    graph.add_edge("ember_dm",      "save_memory")
    graph.add_edge("save_memory",   END)

    return graph.compile()


# ── Singleton compiled graph ──────────────────────────────────────────────────
_reply_graph = None

def get_reply_graph():
    global _reply_graph
    if _reply_graph is None:
        _reply_graph = build_reply_graph()
    return _reply_graph


# ── Public interface (called from main.py) ────────────────────────────────────

def generate_reply(
    message: str,
    platform: str,
    interaction_type: str,
    customer_id: str,
    customer_name: str | None = None,
    restaurant_id: str = TENANT_ID,
) -> dict:
    """
    Main entry point. Called from FastAPI endpoints and webhook handlers.
    
    Returns:
        {reply, ai_persona, confidence, escalate, intent}
    """
    graph = get_reply_graph()

    result = graph.invoke({
        "restaurant_id": restaurant_id,
        "platform": platform,
        "interaction_type": interaction_type,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "message": message,
        # These get populated by the graph nodes:
        "restaurant_context": "",
        "customer_context": "",
        "conversation_history": [],
        "intent": "general",
        "escalate": False,
        "reply": "",
        "ai_persona": "",
        "confidence": "",
    })

    return {
        "reply":      result["reply"],
        "ai_persona": result["ai_persona"],
        "confidence": result["confidence"],
        "escalate":   result.get("escalate", False),
        "intent":     result.get("intent", "general"),
    }