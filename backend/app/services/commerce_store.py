"""Rich single-shop commerce dataset — the shared knowledge base the upgraded
intelligence features and the Copilot reason over.

Deterministically generated (seeded) so tests/CI reproduce exactly. Models the
entities the Đề bài care about and their relationships: Product ↔ SKU ↔ Brand ↔
Category ↔ Promotion ↔ Content/Creator ↔ Sales, plus competitors. This is demo
data standing in for a real seller DB; every field is plausible for a
small/medium Vietnamese fashion & cosmetics shop.
"""

from __future__ import annotations

import random
from functools import lru_cache

Category = str  # "Thời trang" | "Mỹ phẩm" | "Phụ kiện"

# --- brand + product vocabulary per category ------------------------------- #
_CATALOG_SPEC: dict[str, dict] = {
    "Thời trang": {
        "brands": ["Local Brand HANOI", "Coolmate", "YODY", "Routine", "IVY moda"],
        "items": [
            ("Áo thun cotton unisex", (180000, 320000), {"chất liệu": "cotton", "form": "rộng"}),
            ("Áo khoác dù 2 lớp", (280000, 520000), {"chất liệu": "dù", "form": "regular"}),
            ("Váy hoa nhí midi", (250000, 450000), {"chất liệu": "voan", "form": "xoè"}),
            ("Đầm suông linen", (320000, 600000), {"chất liệu": "linen", "form": "suông"}),
            ("Quần jean ống rộng", (300000, 550000), {"chất liệu": "denim", "form": "ống rộng"}),
            ("Áo sơ mi oversize", (220000, 400000), {"chất liệu": "kate", "form": "oversize"}),
            ("Hoodie nỉ bông", (280000, 480000), {"chất liệu": "nỉ", "form": "rộng"}),
            ("Chân váy tennis", (190000, 350000), {"chất liệu": "poly", "form": "chữ A"}),
            ("Áo croptop gân", (120000, 250000), {"chất liệu": "gân", "form": "ôm"}),
            ("Quần short kaki", (160000, 300000), {"chất liệu": "kaki", "form": "regular"}),
            ("Blazer linen", (450000, 850000), {"chất liệu": "linen", "form": "regular"}),
            ("Áo len tăm cổ lọ", (260000, 460000), {"chất liệu": "len", "form": "ôm"}),
        ],
    },
    "Mỹ phẩm": {
        "brands": ["NUDESTIX", "Bourjois", "Laneige", "Cocoon", "The Ordinary"],
        "items": [
            ("Serum Vitamin C 15%", (280000, 720000), {"loại": "serum", "công dụng": "sáng da"}),
            ("Kem chống nắng SPF50", (150000, 320000), {"loại": "kcn", "spf": "50"}),
            ("Son tint lì velvet", (150000, 350000), {"loại": "son", "finish": "lì"}),
            ("Toner cấp ẩm", (120000, 300000), {"loại": "toner", "công dụng": "cấp ẩm"}),
            ("Sữa rửa mặt dịu nhẹ", (110000, 260000), {"loại": "srm", "da": "nhạy cảm"}),
            ("Mặt nạ ngủ dưỡng ẩm", (180000, 650000), {"loại": "mask", "công dụng": "cấp ẩm"}),
            ("Cushion che khuyết điểm", (250000, 550000), {"loại": "cushion", "finish": "căng bóng"}),
            ("Retinol 0.5%", (220000, 480000), {"loại": "serum", "công dụng": "chống lão hoá"}),
            ("Tẩy trang dầu", (130000, 290000), {"loại": "tẩy trang", "da": "mọi loại"}),
            ("Kem dưỡng ẩm ban đêm", (200000, 450000), {"loại": "kem dưỡng", "công dụng": "phục hồi"}),
            ("Mascara làm dày mi", (160000, 330000), {"loại": "mascara", "finish": "dày"}),
            ("Niacinamide 10%", (180000, 360000), {"loại": "serum", "công dụng": "giảm thâm"}),
        ],
    },
    "Phụ kiện": {
        "brands": ["Bag House", "Casio VN", "Local Studio", "Daily Basics", "OEM"],
        "items": [
            ("Túi tote canvas", (120000, 250000), {"chất liệu": "canvas", "kiểu": "tote"}),
            ("Túi đeo chéo da PU", (200000, 420000), {"chất liệu": "da pu", "kiểu": "đeo chéo"}),
            ("Balo laptop chống nước", (300000, 650000), {"chất liệu": "poly", "kiểu": "balo"}),
            ("Ví cầm tay nữ", (150000, 320000), {"chất liệu": "da pu", "kiểu": "ví"}),
            ("Kính mát gọng vuông", (180000, 400000), {"kiểu": "vuông", "chống": "uv400"}),
            ("Đồng hồ dây da", (350000, 900000), {"dây": "da", "kiểu": "classic"}),
            ("Mũ bucket", (90000, 200000), {"chất liệu": "kaki", "kiểu": "bucket"}),
            ("Thắt lưng da", (160000, 350000), {"chất liệu": "da", "kiểu": "bản nhỏ"}),
            ("Vòng tay charm", (80000, 180000), {"chất liệu": "thép", "kiểu": "charm"}),
            ("Tất cổ trung combo", (60000, 130000), {"chất liệu": "cotton", "kiểu": "combo"}),
            ("Khăn lụa vuông", (110000, 240000), {"chất liệu": "lụa", "kiểu": "vuông"}),
            ("Kẹp tóc ngọc trai", (50000, 120000), {"chất liệu": "ngọc trai", "kiểu": "kẹp"}),
        ],
    },
}

_TRENDS = ["rising", "rising", "stable", "stable", "cooling", "cooling"]
_STOCK_STATUS = ["ok", "ok", "ok", "low", "out"]


def _slug(name: str, i: int) -> str:
    base = "".join(c for c in name.lower().replace(" ", "-") if c.isalnum() or c == "-")
    return f"{base[:24]}-{i:02d}"


@lru_cache(maxsize=1)
def _build() -> dict:
    rng = random.Random(303)
    products: list[dict] = []
    pid = 0
    for category, spec in _CATALOG_SPEC.items():
        brands = spec["brands"]
        for name, (lo, hi), attrs in spec["items"]:
            pid += 1
            price = int(round(rng.randint(lo, hi) / 1000) * 1000)
            cost = int(round(price * rng.uniform(0.42, 0.6) / 1000) * 1000)
            brand = brands[pid % len(brands)]
            trend = _TRENDS[pid % len(_TRENDS)]
            stock_status = _STOCK_STATUS[pid % len(_STOCK_STATUS)]
            daily = rng.randint(4, 30)
            stock = 0 if stock_status == "out" else (
                daily * rng.randint(1, 3) if stock_status == "low" else daily * rng.randint(15, 60))

            # 4-period sales history shaped by trend.
            base = rng.randint(120, 600)
            step = {"rising": 1.18, "cooling": 0.82, "stable": 1.0}[trend]
            noise = lambda: rng.uniform(0.95, 1.05)  # noqa: E731
            hist = []
            v = float(base)
            for _ in range(4):
                hist.append(int(v * noise()))
                v *= step
            sales_prev, sales_curr = hist[-2], hist[-1]

            # Optional promotion with a measured lift.
            promo = None
            if pid % 3 == 0:
                promo = {
                    "name": rng.choice(["Sale 11.11 -20%", "Freeship + tặng quà", "Flash sale cuối tuần -15%"]),
                    "discount_pct": rng.choice([10, 15, 20]),
                    "lift_pct": rng.choice([8, 14, 22, 30]),
                }

            # 1-2 competitors around our price.
            n_comp = 1 + (pid % 2)
            competitors = []
            comp_names = ["Shop " + c for c in ("BestPrice", "Mega Store", "Outlet VN", "Deal Zone")]
            for c in range(n_comp):
                cp = int(round(price * rng.uniform(0.82, 1.15) / 1000) * 1000)
                competitors.append({
                    "name": comp_names[(pid + c) % len(comp_names)],
                    "price_vnd": cp,
                    "discount_pct": rng.choice([0, 0, 10, 20, 30]),
                })

            products.append({
                "id": _slug(name, pid),
                "sku": f"{category[:2].upper()}-{brand[:3].upper()}-{pid:03d}",
                "name": name,
                "brand": brand,
                "category": category,
                "price_vnd": price,
                "cost_vnd": cost,
                "stock": stock,
                "stock_status": stock_status,
                "daily_sales": daily,
                "trend": trend,
                "attributes": attrs,
                "sales_history": hist,
                "sales_prev": sales_prev,
                "sales_curr": sales_curr,
                "promotion": promo,
                "competitors": competitors,
            })

    # --- creators with multi-campaign history (for Đề 4 correlation) --------- #
    creators: list[dict] = []
    creator_defs = [
        ("Hà Linh Official", "Mỹ phẩm", "livestream", 0.9),
        ("Chan Review", "Mỹ phẩm", "video", 0.6),
        ("Mai Beauty", "Mỹ phẩm", "post", 0.4),
        ("Trang Fashionista", "Thời trang", "video", 0.8),
        ("Style By An", "Thời trang", "livestream", 0.85),
        ("Daily Look", "Phụ kiện", "post", 0.5),
    ]
    for name, cat, ctype, eff in creator_defs:
        campaigns = []
        for m in (9, 10, 11, 12):
            views = rng.randint(20000, 180000)
            # sales correlate with views * creator efficiency (+noise) → measurable correlation
            sales = int(views * eff * rng.uniform(180, 320))
            campaigns.append({
                "month": m, "content_type": ctype, "views": views,
                "engagements": int(views * rng.uniform(0.03, 0.12)),
                "attributed_sales_vnd": sales,
            })
        creators.append({"creator": name, "category": cat, "campaigns": campaigns})

    # --- past operating decisions (for Đề 5) -------------------------------- #
    decisions = [
        {"kind": "ad", "description": "Đẩy ads TikTok tháng 12", "metric": "ROAS", "value": 5.1, "month": 12, "category": "Mỹ phẩm"},
        {"kind": "promo", "description": "Sale 11.11 giảm 20%", "metric": "ROAS", "value": 4.2, "month": 11, "category": "Thời trang"},
        {"kind": "promo", "description": "Freeship toàn shop", "metric": "sales_lift_pct", "value": 18.0, "month": 6, "category": "Phụ kiện"},
        {"kind": "price", "description": "Giảm giá 10% ngày thường", "metric": "ROAS", "value": 2.3, "month": None, "category": "Mỹ phẩm"},
        {"kind": "ad", "description": "Ads Facebook mùa hè", "metric": "ROAS", "value": 3.4, "month": 6, "category": "Thời trang"},
        {"kind": "inventory", "description": "Nhập sỉ áo khoác trước mùa lạnh", "metric": "sell_through_pct", "value": 92.0, "month": 10, "category": "Thời trang"},
        {"kind": "promo", "description": "Combo mua 2 tặng 1", "metric": "sales_lift_pct", "value": 25.0, "month": 8, "category": "Mỹ phẩm"},
        {"kind": "ad", "description": "Ads Tết Nguyên đán", "metric": "ROAS", "value": 4.8, "month": 1, "category": "Phụ kiện"},
    ]

    # --- customers (for churn / return / regret auto-analysis) -------------- #
    cust_names = [
        "Nguyễn Thu Hà", "Trần Minh Quân", "Lê Bảo Ngọc", "Phạm Gia Huy",
        "Vũ Khánh Linh", "Đặng Tuấn Anh", "Bùi Phương Thảo", "Hoàng Nhật Nam",
        "Đỗ Mỹ Duyên", "Ngô Thành Đạt",
    ]
    trends3 = ["declining", "stable", "growing"]
    customers: list[dict] = []
    for i, nm in enumerate(cust_names):
        prod = products[(i * 3) % len(products)]
        recency = rng.choice([5, 12, 20, 40, 65, 95, 140])
        customers.append({
            "id": f"C{i + 1:03d}",
            "name": nm,
            "recency_days": recency,
            "frequency_orders": rng.randint(1, 14),
            "sessions_last_month": rng.randint(0, 12),
            "cart_abandon_rate": round(rng.uniform(0.1, 0.9), 2),
            "trend": trends3[i % 3],
            "last_product": prod["name"],
            "last_category": prod["category"],
            "last_order_value_vnd": prod["price_vnd"],
            # signals for return/regret on the last order
            "reviews_read": rng.randint(0, 8),
            "is_first_purchase": recency > 90 or rng.random() < 0.3,
            "has_size_variants": prod["category"] == "Thời trang",
            "decision_seconds": rng.choice([15, 30, 45, 90, 180]),
            "revisits_before_buy": rng.randint(0, 4),
            "purchase_hour": rng.choice([9, 13, 18, 22, 23, 1]),
            "discount_driven": rng.random() < 0.5,
        })

    # --- pre-built shopping sessions (real journeys to test, not manual) ---- #
    sessions: list[dict] = [
        {"id": "S1", "label": "Săn serum — vừa thêm giỏ", "events": [
            {"type": "search", "category": "Mỹ phẩm", "query": "serum vitamin c"},
            {"type": "click", "category": "Mỹ phẩm"}, {"type": "view", "category": "Mỹ phẩm"},
            {"type": "livestream", "category": "Mỹ phẩm"}, {"type": "cart", "category": "Mỹ phẩm"}]},
        {"id": "S2", "label": "Lướt thời trang — chưa quyết", "events": [
            {"type": "search", "category": "Thời trang", "query": "váy hoa nhí"},
            {"type": "view", "category": "Thời trang"}, {"type": "view", "category": "Thời trang"},
            {"type": "click", "category": "Thời trang"}]},
        {"id": "S3", "label": "Mua xong — có thể cross-sell", "events": [
            {"type": "view", "category": "Mỹ phẩm"}, {"type": "cart", "category": "Mỹ phẩm"},
            {"type": "purchase", "category": "Mỹ phẩm"}]},
        {"id": "S4", "label": "Bỏ giỏ giữa chừng — nguy cơ rời", "events": [
            {"type": "click", "category": "Phụ kiện"}, {"type": "view", "category": "Phụ kiện"}]},
        {"id": "S5", "label": "Fan livestream thời trang", "events": [
            {"type": "livestream", "category": "Thời trang"}, {"type": "livestream", "category": "Thời trang"},
            {"type": "cart", "category": "Thời trang"}, {"type": "view", "category": "Thời trang"}]},
    ]

    return {"products": products, "creators": creators, "decisions": decisions,
            "customers": customers, "sessions": sessions}


# --------------------------------------------------------------------------- #
# Public query helpers
# --------------------------------------------------------------------------- #
def all_products() -> list[dict]:
    return _build()["products"]


def all_creators() -> list[dict]:
    return _build()["creators"]


def all_decisions() -> list[dict]:
    return _build()["decisions"]


def all_customers() -> list[dict]:
    return _build()["customers"]


def all_sessions() -> list[dict]:
    return _build()["sessions"]


def categories() -> list[str]:
    return list(_CATALOG_SPEC.keys())


def brands(category: str | None = None) -> list[str]:
    seen: list[str] = []
    for p in all_products():
        if (category is None or p["category"] == category) and p["brand"] not in seen:
            seen.append(p["brand"])
    return seen


def find_product(query: str | None) -> dict | None:
    if not query:
        return None
    low = query.lower()
    for p in all_products():
        if p["id"] == low or p["sku"].lower() == low:
            return p
    for p in all_products():
        if p["name"].lower() in low or low in p["name"].lower():
            return p
    best, best_score = None, 0
    for p in all_products():
        toks = set(p["name"].lower().split())
        score = len(toks & set(low.split()))
        if score > best_score:
            best, best_score = p, score
    return best


def products_by_category(category: str) -> list[dict]:
    return [p for p in all_products() if p["category"] == category]


def products_by_brand(brand: str) -> list[dict]:
    return [p for p in all_products() if p["brand"] == brand]


def similar_products(product: dict, k: int = 5) -> list[dict]:
    """Rank other products by relatedness: same category (base) + same brand +
    price proximity + shared attribute values."""
    scored: list[tuple[float, dict]] = []
    p_attrs = set(product.get("attributes", {}).values())
    for q in all_products():
        if q["id"] == product["id"]:
            continue
        score = 0.0
        if q["category"] == product["category"]:
            score += 2.0
        if q["brand"] == product["brand"]:
            score += 1.5
        price_ratio = min(q["price_vnd"], product["price_vnd"]) / max(q["price_vnd"], product["price_vnd"])
        score += price_ratio  # 0..1, closer price → higher
        score += 0.5 * len(p_attrs & set(q.get("attributes", {}).values()))
        scored.append((score, q))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [q for _, q in scored[:k]]


def creators_for_category(category: str) -> list[dict]:
    return [c for c in all_creators() if c["category"] == category]
