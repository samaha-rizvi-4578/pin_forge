"""Stub AIContentService used during development/startup."""

class AIContentService:
    @staticmethod
    def generate_product_content(product):
        """Return a simple placeholder AI-generated product content."""
        return {
            "title": getattr(product, "title", "Generated Title"),
            "description": getattr(product, "description", "Generated description."),
        }
