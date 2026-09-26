"""Domain exceptions raised by the core layer; their messages are safe to show to MCP clients."""


class ShopError(Exception):
    """Base class for expected, user-facing errors."""


class InvalidInputError(ShopError):
    """A tool argument is well-typed but semantically invalid (e.g. start date after end date)."""


class CustomerNotFoundError(ShopError):
    """No customer matches the given email."""
