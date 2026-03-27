"""
tools/cms_tools.py
-------------------
LangChain tools that agents call to fetch live restaurant data from the CMS.
Each tool is self-contained and returns clean text the LLM can use directly.
"""

import json
from datetime import datetime, timedelta
from langchain_core.tools import tool
from config.cms_client import (
    get_menu, get_availability, get_reservations,
    create_reservation, TENANT_ID
)
from config.restaurant_config import get_restaurant_context


# ── Tool 1: Get today's menu ──────────────────────────────────────────────────

@tool
def get_todays_menu(restaurant_id: str = TENANT_ID) -> str:
    """
    Fetch the current menu from the CMS.
    Returns a formatted text summary of all available dishes with prices.
    Use this when a customer asks about food, menu, dishes, prices, or dietary options.
    """
    ctx = get_restaurant_context(restaurant_id)
    if not ctx:
        return "Menu information is currently unavailable."
    return ctx.get_menu_summary()


@tool
def get_vegetarian_menu(restaurant_id: str = TENANT_ID) -> str:
    """
    Fetch only vegetarian items from the menu.
    Use when customer asks specifically about vegetarian or veg options.
    """
    data = get_menu(restaurant_id, is_vegetarian=True)
    if not data:
        return "Menu information is currently unavailable."

    lines = ["VEGETARIAN OPTIONS:"]
    for cat in data.get("menu", []):
        items = [i for i in cat.get("items", []) if i.get("isAvailable")]
        if not items:
            continue
        lines.append(f"\n{cat['name']}:")
        for item in items:
            vegan_tag = " (Vegan)" if item.get("isVegan") else ""
            lines.append(f"  - {item['name']}{vegan_tag} — ₹{item['price'] / 100:.0f}")
            if item.get("description"):
                lines.append(f"    {item['description'][:80]}")
    return "\n".join(lines)


@tool
def search_menu_item(query: str, restaurant_id: str = TENANT_ID) -> str:
    """
    Search for a specific dish or ingredient in the menu.
    Use when customer asks about a specific food item.
    Args:
        query: The dish name or ingredient to search for
    """
    data = get_menu(restaurant_id, search=query)
    if not data:
        return f"Could not find '{query}' in our menu."

    lines = [f"MENU SEARCH RESULTS FOR '{query}':"]
    found = False
    for cat in data.get("menu", []):
        for item in cat.get("items", []):
            if item.get("isAvailable"):
                found = True
                price = item["price"] / 100
                lines.append(f"  - {item['name']} — ₹{price:.0f}")
                if item.get("description"):
                    lines.append(f"    {item['description']}")
    if not found:
        return f"Sorry, we don't have '{query}' on our current menu."
    return "\n".join(lines)


# ── Tool 2: Restaurant info ───────────────────────────────────────────────────

@tool
def get_restaurant_info(restaurant_id: str = TENANT_ID) -> str:
    """
    Get complete restaurant information: location, hours, contact, services.
    Use when customer asks about location, timing, contact, parking, delivery etc.
    """
    ctx = get_restaurant_context(restaurant_id)
    if not ctx:
        return "Restaurant information is currently unavailable."
    return ctx.to_prompt_context()


@tool
def get_todays_hours(restaurant_id: str = TENANT_ID) -> str:
    """
    Get today's opening and closing hours.
    Use when customer asks 'are you open', 'what time do you close', 'timings' etc.
    """
    ctx = get_restaurant_context(restaurant_id)
    if not ctx:
        return "Hours information is currently unavailable."

    hours = ctx.get_todays_hours()
    day = datetime.now().strftime("%A")
    is_open = ctx.is_open_now()

    if not hours or hours.closed:
        return f"We are closed today ({day})."

    status = "We are currently OPEN" if is_open else "We are currently CLOSED"
    return (
        f"{status}.\n"
        f"Today ({day}): {hours.open} – {hours.close}\n"
        f"Kitchen closes at {ctx.kitchen_closing_time} before closing time."
    )


# ── Tool 3: Availability ──────────────────────────────────────────────────────

@tool
def check_table_availability(date: str, party_size: int, restaurant_id: str = TENANT_ID) -> str:
    """
    Check if tables are available for a given date and party size.
    Use when customer wants to book a table or asks about availability.
    Args:
        date: Date in YYYY-MM-DD format (use today's date if customer says 'today')
        party_size: Number of people
    """
    data = get_availability(restaurant_id, date=date, party_size=party_size)
    if not data:
        return "Availability information is currently unavailable. Please call us directly."

    available_slots = data.get("availableSlots", [])
    if not available_slots:
        return (
            f"Unfortunately we don't have availability for {party_size} people on {date}. "
            f"Please try a different date or contact us directly."
        )

    slots_text = ", ".join(available_slots[:6])
    return (
        f"Available time slots for {party_size} people on {date}:\n"
        f"{slots_text}\n"
        f"Would you like me to book one of these for you?"
    )


# ── Tool 4: Create reservation ────────────────────────────────────────────────

@tool
def book_table(
    customer_name: str,
    customer_phone: str,
    party_size: int,
    date: str,
    time: str,
    special_requests: str = "",
    restaurant_id: str = TENANT_ID,
) -> str:
    """
    Book a table reservation directly from a DM conversation.
    Only call this AFTER confirming all details with the customer.
    Args:
        customer_name: Full name of the customer
        customer_phone: Customer's phone number
        party_size: Number of people
        date: Date in YYYY-MM-DD format
        time: Time in HH:MM format
        special_requests: Any dietary needs or special occasions
    """
    result = create_reservation(
        restaurant_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        party_size=party_size,
        date=date,
        time=time,
        special_requests=special_requests,
    )

    if "error" in result:
        return (
            f"I wasn't able to complete the booking automatically. "
            f"Please WhatsApp us directly and we'll sort it out right away!"
        )

    reservation_id = result.get("id", "")
    return (
        f"Your table is booked! 🎉\n"
        f"Reservation confirmed for {customer_name}, party of {party_size} "
        f"on {date} at {time}.\n"
        f"Reference: {reservation_id}\n"
        f"We'll send a confirmation shortly. See you then!"
    )


# ── Tool 5: Analytics context ─────────────────────────────────────────────────

@tool
def get_reservation_summary(restaurant_id: str = TENANT_ID) -> str:
    """
    Get today's reservation summary for analytics context.
    Use in the analytics agent to understand current booking load.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    data = get_reservations(restaurant_id, date=today)
    if not data:
        return "No reservation data available."

    reservations = data.get("reservations", [])
    total = len(reservations)
    confirmed = sum(1 for r in reservations if r.get("status") == "confirmed")
    pending = sum(1 for r in reservations if r.get("status") == "pending")

    return (
        f"TODAY'S RESERVATIONS ({today}):\n"
        f"  Total: {total}\n"
        f"  Confirmed: {confirmed}\n"
        f"  Pending: {pending}\n"
    )


# ── All tools exported for agent use ─────────────────────────────────────────

CMS_TOOLS = [
    get_todays_menu,
    get_vegetarian_menu,
    search_menu_item,
    get_restaurant_info,
    get_todays_hours,
    check_table_availability,
    book_table,
    get_reservation_summary,
]