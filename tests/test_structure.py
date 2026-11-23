def test_domain_imports():
    from alive.domain.config import Config, Zone
    from alive.domain.orders import parse_orders
    from alive.domain.animation import AnimationEngine
    from alive.domain.geometry import Rect
    from alive.domain.contracts import AiReply, ProviderError, CommandRunner
