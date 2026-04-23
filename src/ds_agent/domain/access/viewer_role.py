from typing import Final, Literal

ViewerRole = Literal["owner", "viewer"]
VIEWER_ROLES: Final[tuple[ViewerRole, ...]] = ("owner", "viewer")
