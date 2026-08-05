from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


IntentName = Literal[
    "product_search",
    "multi_product_search",
    "top_products",
    "lowest_price",
    "highest_price",
    "newest_products",
    "compare_products",
    "recommend_products",
    "greeting",
    "reset",
    "out_of_context",
]

ActionName = Literal["new_search", "modify", "reset"]
ResponseLanguage = Literal["english", "roman_urdu"]
ProductRelation = Literal[
    "none",
    "single",
    "multi_list",
    "ambiguous",
    "complementary",
]


class ShoppingFilters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    productType: str | None = None
    vendor: str | None = None
    minPrice: float | None = None
    maxPrice: float | None = None
    priceIntent: Literal["lower", "higher"] | None = None

    @field_validator("productType", "vendor", mode="before")
    @classmethod
    def clean_optional_text(cls, value):
        if value is None:
            return None
        clean_value = " ".join(str(value).strip().split())
        return clean_value or None


class ShoppingQueryPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: IntentName = "product_search"
    action: ActionName = "new_search"
    limit: int = Field(default=5, ge=1, le=20)
    responseLanguage: ResponseLanguage = "english"
    semanticQuery: str = ""
    comparisonTargets: list[str] = Field(default_factory=list, max_length=4)
    productTypes: list[str] = Field(default_factory=list, max_length=12)
    unresolvedProductTypes: list[str] = Field(default_factory=list, max_length=12)
    relation: ProductRelation = "none"
    filters: ShoppingFilters = Field(default_factory=ShoppingFilters)

    @field_validator("semanticQuery", mode="before")
    @classmethod
    def clean_semantic_query(cls, value):
        return " ".join(str(value or "").strip().split())[:300]

    @field_validator(
        "comparisonTargets",
        "productTypes",
        "unresolvedProductTypes",
        mode="before",
    )
    @classmethod
    def clean_string_list(cls, value):
        if not isinstance(value, list):
            return []

        result: list[str] = []
        seen: set[str] = set()

        for item in value:
            clean_item = " ".join(str(item or "").strip().split())
            key = clean_item.lower()
            if not clean_item or key in seen:
                continue
            seen.add(key)
            result.append(clean_item)

        return result
