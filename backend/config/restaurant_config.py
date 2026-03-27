"""
restaurant_config.py
---------------------
Loads and normalises restaurant data from the CMS into a clean
RestaurantContext object that every agent uses.

Usage:
    from config.restaurant_config import get_restaurant_context
    ctx = get_restaurant_context()   # uses TENANT_ID from .env
    ctx = get_restaurant_context("some-other-uuid")  # multi-tenant
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from config.cms_client import get_restaurant_config, get_menu, TENANT_ID


@dataclass
class OperatingHours:
    open: str
    close: str
    closed: bool


@dataclass
class MenuItem:
    id: str
    name: str
    description: str
    price_paise: int
    price_rupees: float
    is_vegetarian: bool
    is_vegan: bool
    is_gluten_free: bool
    spice_level: int
    is_available: bool
    image: str | None = None


@dataclass
class MenuCategory:
    id: str
    name: str
    description: str
    items: list[MenuItem] = field(default_factory=list)


@dataclass
class RestaurantContext:
    # Identity
    id: str
    name: str
    slug: str
    timezone: str

    # Contact
    address: str
    city: str
    state: str
    phone: str
    email: str

    # Hours
    operating_hours: dict[str, OperatingHours]  # keyed by day name
    kitchen_closing_time: str
    weekly_off: list[str]

    # Menu
    menu_categories: list[MenuCategory]
    menu_highlights: str
    total_menu_items: int

    # Service modes
    service_modes: list[str]          # dine_in, takeaway, delivery
    takeaway_available: bool
    delivery_available: bool
    delivery_radius_km: float

    # Reservations
    max_party_size: int
    advance_booking_days: int
    cancellation_policy: str
    no_show_policy: str

    # Social
    instagram_handle: str
    facebook_handle: str

    # AI personality (from voiceSettings — same tone for social)
    conversation_tone: str            # professional, friendly, casual
    languages: list[str]
    escalation_phone: str

    # Raw config (for anything not mapped above)
    raw: dict = field(default_factory=dict)

    # ── Computed helpers ──────────────────────────────────────────────────────

    def get_todays_hours(self) -> OperatingHours | None:
        day = datetime.now().strftime("%A").lower()  # monday, tuesday...
        return self.operating_hours.get(day)

    def is_open_now(self) -> bool:
        hours = self.get_todays_hours()
        if not hours or hours.closed:
            return False
        now = datetime.now().strftime("%H:%M")
        return hours.open <= now <= hours.close

    def get_menu_summary(self, max_items: int = 20) -> str:
        """
        Compact text summary of the menu for use in AI prompts.
        Avoids token bloat by limiting items per category.
        """
        lines = []
        for cat in self.menu_categories:
            lines.append(f"\n{cat.name.upper()}:")
            shown = [i for i in cat.items if i.is_available][:max_items]
            for item in shown:
                flags = []
                if item.is_vegetarian: flags.append("veg")
                if item.is_vegan: flags.append("vegan")
                if item.is_gluten_free: flags.append("GF")
                flag_str = f" ({', '.join(flags)})" if flags else ""
                lines.append(f"  - {item.name}{flag_str} — ₹{item.price_rupees:.0f}")
                if item.description:
                    lines.append(f"    {item.description[:80]}")
        return "\n".join(lines)

    def get_hours_summary(self) -> str:
        """Human-readable hours for AI prompts."""
        lines = []
        for day, hours in self.operating_hours.items():
            if hours.closed:
                lines.append(f"  {day.capitalize()}: Closed")
            else:
                lines.append(f"  {day.capitalize()}: {hours.open} – {hours.close}")
        return "\n".join(lines)

    def to_prompt_context(self) -> str:
        """
        Full formatted context string injected into every AI system prompt.
        This replaces the hardcoded FIREBELLY_KNOWLEDGE in ai_reply.py.
        """
        today_hours = self.get_todays_hours()
        today_str = (
            f"{today_hours.open} – {today_hours.close}"
            if today_hours and not today_hours.closed
            else "Closed today"
        )

        return f"""
RESTAURANT: {self.name}
LOCATION: {self.address}, {self.city}, {self.state}
CONTACT PHONE: {self.phone}
CONTACT EMAIL: {self.email}

TODAY'S HOURS: {today_str}
FULL WEEKLY HOURS:
{self.get_hours_summary()}
KITCHEN CLOSES: {self.kitchen_closing_time} before closing

SERVICES: {', '.join(self.service_modes)}
DELIVERY AVAILABLE: {'Yes' if self.delivery_available else 'No'}
{'DELIVERY RADIUS: ' + str(self.delivery_radius_km) + ' km' if self.delivery_available else ''}
TAKEAWAY: {'Available' if self.takeaway_available else 'Not available'}

RESERVATION INFO:
  Max party size: {self.max_party_size}
  Advance booking: up to {self.advance_booking_days} days
  Cancellation policy: {self.cancellation_policy}

SOCIAL MEDIA:
  Instagram: @{self.instagram_handle}
  Facebook: {self.facebook_handle}

MENU:
{self.get_menu_summary()}

MENU HIGHLIGHTS: {self.menu_highlights}
""".strip()


# ── Factory function ──────────────────────────────────────────────────────────

def get_restaurant_context(restaurant_id: str = TENANT_ID) -> RestaurantContext | None:
    """
    Load and return a RestaurantContext from the CMS.
    Returns None if the restaurant is not found or CMS is unreachable.
    """
    raw = get_restaurant_config(restaurant_id)
    if not raw:
        print(f"ERROR: Could not load config for restaurant {restaurant_id}")
        return None

    menu_raw = get_menu(restaurant_id) or {}

    # ── Parse menu (None-safe) ───────────────────────────────────────────────
    categories = []
    for cat in (menu_raw.get("menu") or []):
        if not cat: continue
        items = []
        for item in (cat.get("items") or []):
            if not item: continue
            items.append(MenuItem(
                id=item.get("id", ""),
                name=item.get("name", ""),
                description=item.get("description", ""),
                price_paise=item.get("price", 0),
                price_rupees=item.get("price", 0) / 100,
                is_vegetarian=item.get("isVegetarian", False),
                is_vegan=item.get("isVegan", False),
                is_gluten_free=item.get("isGlutenFree", False),
                spice_level=item.get("spiceLevel", 0),
                is_available=item.get("isAvailable", True),
                image=item.get("image"),
            ))
        categories.append(MenuCategory(
            id=cat.get("id", ""),
            name=cat.get("name", ""),
            description=cat.get("description", ""),
            items=items,
        ))

    # ── Parse hours (None-safe) ──────────────────────────────────────────────
    hours_raw = (raw.get("hoursAndPolicies") or {}).get("operatingHours") or {}
    hours = {}
    for day, h in (hours_raw or {}).items():
        if h:
            hours[day.lower()] = OperatingHours(
                open=h.get("open", ""),
                close=h.get("close", ""),
                closed=h.get("closed", False),
            )

    # ── Parse everything else (all None-safe) ────────────────────────────────
    restaurant  = raw.get("restaurant") or {}
    profile     = raw.get("businessProfile") or {}
    hours_pol   = raw.get("hoursAndPolicies") or {}
    res_rules   = raw.get("reservationRules") or {}
    order_rules = raw.get("orderingRules") or {}
    menu_seat   = raw.get("menuAndSeating") or {}
    voice       = raw.get("voiceSettings") or {}
    social      = (raw.get("socialSettings") or {}).get("handles") or {}

    return RestaurantContext(
        id=restaurant.get("id", restaurant_id),
        name=restaurant.get("name", ""),
        slug=restaurant.get("slug", ""),
        timezone=restaurant.get("timezone", "Asia/Kolkata"),

        address=profile.get("address", ""),
        city=profile.get("city", ""),
        state=profile.get("state", ""),
        phone=profile.get("contactPhone", ""),
        email=profile.get("contactEmail", ""),

        operating_hours=hours,
        kitchen_closing_time=hours_pol.get("kitchenClosingTime", "45 minutes before closing"),
        weekly_off=hours_pol.get("weeklyOff", []),

        menu_categories=categories,
        menu_highlights=menu_seat.get("menuHighlights", ""),
        total_menu_items=menu_raw.get("totalItems", 0),

        service_modes=restaurant.get("serviceModes", []),
        takeaway_available=menu_seat.get("takeawayAvailable", False),
        delivery_available=menu_seat.get("deliveryAvailable", False),
        delivery_radius_km=menu_seat.get("deliveryRadius", 0),

        max_party_size=res_rules.get("maxPartySize", 10),
        advance_booking_days=res_rules.get("advanceBookingDays", 7),
        cancellation_policy=res_rules.get("cancellationPolicy", ""),
        no_show_policy=res_rules.get("noShowPolicy", ""),

        instagram_handle=social.get("instagram", ""),
        facebook_handle=social.get("facebook", ""),

        conversation_tone=voice.get("conversationTone", "friendly"),
        languages=voice.get("languages", ["en"]),
        escalation_phone=voice.get("escalationNumber", ""),

        raw=raw,
    )