# backend/app/models/request.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class TextQuery(BaseModel):
    """
    Represents a text-based search query
    (e.g., 'airports like Singapore Changi with indoor gardens').

    Supports flexible filters such as:
      - country: filter by country name
      - style: architectural style (e.g., glass, modern)
      - has_image: only include results with available images
    """
    query: str = Field(
        ...,
        min_length=1,
        description="Natural language text query used to find visually similar airports or scenes."
    )

    k: int = Field(
        1000,
        ge=1,
        le=10000,
        description="Number of results to return (default 1000, up to 10,000). Large values increase query time."
    )

    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional filters like {'country': 'India', 'style': 'glass', 'has_image': True}."
    )


class HybridTextQuery(TextQuery):
    """
    Hybrid multimodal search request that blends text and image embeddings.

    Allows weighted combination between text semantics and an optional image embedding.
    Example use:
      {
        'query': 'airports with bamboo ceiling design',
        'image_base64': '<base64 string>',
        'weight_text': 0.6,
        'weight_image': 0.4
      }
    """
    image_base64: Optional[str] = Field(
        default=None,
        description="Optional base64-encoded image input for hybrid similarity search."
    )

    weight_text: Optional[float] = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Relative weight for text embedding (default: 0.5)."
    )

    weight_image: Optional[float] = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Relative weight for image embedding (default: 0.5)."
    )
