"""AI Sales Assistant service.

Provides LLM-powered conversational sales assistant.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.core.context import tenant_query
from app.models import Product, StockCount

logger = logging.getLogger(__name__)


@dataclass
class AIContext:
    tenant_id: int
    customer_id: Optional[int] = None
    conversation_id: Optional[int] = None
    platform: Optional[str] = None
    product_id: Optional[int] = None
    language: str = "ar"


@dataclass
class AIResponse:
    text: str
    language: str = "ar"
    action: Optional[str] = None
    action_data: Optional[dict] = None
    confidence: float = 0.0


class BaseAIProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], context: AIContext) -> str:
        ...


class MockAIProvider(BaseAIProvider):
    """Mock AI provider for testing and when no LLM credentials are available."""

    def chat(self, messages: list[dict], context: AIContext) -> str:
        last_msg = messages[-1]["content"] if messages else ""
        lower = last_msg.lower()

        if any(w in lower for w in ["price", "prix", "كم", "ثمن"]):
            return json.dumps({"action": "lookup_product", "confidence": 0.9})
        if any(w in lower for w in ["order", "commande", "طلب", "أريد"]):
            return json.dumps({"action": "collect_order_info", "confidence": 0.85})
        if any(w in lower for w in ["stock", "available", "متوفر"]):
            return json.dumps({"action": "check_stock", "confidence": 0.9})
        return json.dumps({"action": "reply", "text": "Thank you for your interest! How can I help you?", "confidence": 0.5})


class OpenAIProvider(BaseAIProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def chat(self, messages: list[dict], context: AIContext) -> str:
        import httpx
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages, "temperature": 0.3},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def get_ai_provider() -> BaseAIProvider:
    from app.config import get_settings
    settings = get_settings()
    provider = settings.AI_PROVIDER.lower()
    if provider == "openai":
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, falling back to mock provider")
            return MockAIProvider()
        return OpenAIProvider(api_key=api_key, model=settings.OPENAI_MODEL)
    return MockAIProvider()


SYSTEM_PROMPT = """You are a helpful sales assistant for an Algerian e-commerce business.
You can help customers in Arabic, French, English, and Algerian Darija.

You have access to the following tools/actions:
- lookup_product: Look up product information by name
- check_stock: Check stock availability for a product
- collect_order_info: Collect customer information for an order
- create_order: Create an order with collected information
- reply: Send a reply message

Always respond in JSON format with these fields:
{"action": "...", "text": "...", "confidence": 0.0-1.0, "action_data": {...}}

Never invent product information. Always look up products from the database.
Respect stock availability - never promise items that are out of stock.
Collect: customer name, phone, wilaya, commune, product, variant, quantity before creating an order.
"""


class AIAssistant:
    def __init__(self, db: Session, provider: Optional[BaseAIProvider] = None):
        self.db = db
        self.provider = provider or get_ai_provider()

    def _get_products_context(self, tenant_id: int, search: str = "") -> list[dict]:
        q = tenant_query(self.db, Product, tenant_id).filter(Product.status == "active")
        if search:
            q = q.filter(Product.name.ilike(f"%{search}%"))
        products = q.limit(10).all()
        return [
            {
                "id": p.id, "name": p.name, "price": p.price,
                "stock": p.stock, "sku": p.sku,
                "sizes": p.sizes or [], "colors": p.colors or [],
                "status": p.status,
            }
            for p in products
        ]

    def _get_stock_info(self, tenant_id: int, product_id: int) -> dict:
        stock = tenant_query(self.db, StockCount, tenant_id).filter(
            StockCount.product_id == product_id
        ).first()
        return {
            "product_id": product_id,
            "quantity": stock.quantity if stock else 0,
            "available": stock.quantity > 0 if stock else False,
        }

    def _build_system_message(self, context: AIContext, products: list[dict]) -> str:
        products_str = json.dumps(products, ensure_ascii=False) if products else "[]"
        return (
            f"{SYSTEM_PROMPT}\n\n"
            f"Context:\n"
            f"- Tenant ID: {context.tenant_id}\n"
            f"- Platform: {context.platform or 'unknown'}\n"
            f"- Language: {context.language}\n"
            f"- Customer ID: {context.customer_id or 'unknown'}\n\n"
            f"Available products:\n{products_str}\n"
        )

    def process_message(
        self,
        tenant_id: int,
        content: str,
        conversation_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        platform: Optional[str] = None,
    ) -> AIResponse:
        products = self._get_products_context(tenant_id, content)

        context = AIContext(
            tenant_id=tenant_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            platform=platform,
        )

        messages = [
            {"role": "system", "content": self._build_system_message(context, products)},
            {"role": "user", "content": content},
        ]

        try:
            raw_response = self.provider.chat(messages, context)
            parsed = json.loads(raw_response) if raw_response.startswith("{") else {"action": "reply", "text": raw_response}
            return AIResponse(
                text=parsed.get("text", ""),
                language=parsed.get("language", context.language),
                action=parsed.get("action"),
                action_data=parsed.get("action_data"),
                confidence=parsed.get("confidence", 0.5),
            )
        except Exception as e:
            logger.error("AI processing error: %s", e)
            return AIResponse(text="I apologize, I'm having trouble processing your request. Please try again.", confidence=0.0)
