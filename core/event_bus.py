"""EventBus — 组件间解耦通信"""

from typing import Callable, Any
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Event:
    """事件对象"""
    type: str
    data: Any = None
    source: Any = None


class EventBus:
    """全局事件总线，组件间通过事件通信，避免直接引用"""

    # 事件类型常量
    FILE_OPENED = "file.opened"
    FILE_CLOSED = "file.closed"
    NODE_SELECTED = "node.selected"
    NODE_DOUBLE_CLICKED = "node.double_clicked"
    SLICE_CHANGED = "slice.changed"
    SPLIT_REQUESTED = "split.requested"
    TAB_CLOSE_REQUESTED = "tab.close.requested"
    PLUGIN_ACTIVATED = "plugin.activated"
    STATUS_MESSAGE = "status.message"
    ERROR_OCCURRED = "error.occurred"
    FOLDER_OPENED = "folder.opened"
    FOLDER_CLOSED = "folder.closed"
    FILE_TAB_ACTIVATED = "file.tab.activated"

    _instance: 'EventBus | None' = None
    _handlers: dict[str, list[Callable]] = field(default_factory=lambda: defaultdict(list))

    def __new__(cls) -> 'EventBus':
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers = defaultdict(list)
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'EventBus':
        """获取单例"""
        return cls()

    def on(self, event_type: str, handler: Callable) -> None:
        """注册事件处理器"""
        self._handlers[event_type].append(handler)

    def off(self, event_type: str, handler: Callable) -> None:
        """移除事件处理器"""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    def emit(self, event_type: str, data: Any = None, source: Any = None) -> None:
        """触发事件"""
        event = Event(type=event_type, data=data, source=source)
        for handler in self._handlers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                print(f"[EventBus] Error in handler for {event_type}: {e}")

    def clear(self, event_type: str | None = None) -> None:
        """清除事件处理器"""
        if event_type:
            self._handlers[event_type].clear()
        else:
            self._handlers.clear()
