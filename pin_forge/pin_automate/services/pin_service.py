"""Stub PinGeneratorService used during development/startup."""

class PinGeneratorService:
    @staticmethod
    def generate(product, count=10):
        """Return a list of placeholder pins (dictionaries).

        The real implementation would generate image/content and post or
        queue pins. The stub returns simple dicts so callers can proceed.
        """
        try:
            n = int(count)
        except Exception:
            n = 10

        return [{"product_id": getattr(product, "id", None), "pin_index": i} for i in range(n)]
