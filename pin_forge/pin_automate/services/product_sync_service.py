"""Stub ProductSyncService used during development/startup.

The real implementation may contact external stores. This lightweight
stub provides the expected API so imports succeed while running
management commands like `makemigrations`.
"""

class ProductSyncService:
    @staticmethod
    def sync(store):
        """No-op stub for syncing products from a store."""
        # In the real implementation this would enqueue or run sync logic.
        return None
