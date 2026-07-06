"""EventBus — 组件间解耦通信"""

import logging
import weakref
from typing import Callable, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """事件对象"""
    type: str
    data: Any = None
    source: Any = None


class EventBus:
    """全局事件总线，组件间通过事件通信，避免直接引用

    使用弱引用存储处理器，避免内存泄漏。
    当处理器所属对象被销毁时，弱引用自动失效。
    """

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

    _instance: Optional['EventBus'] = None

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
        """注册事件处理器（弱引用）

        handler 通常是绑定方法（如 self._on_xxx），
        使用弱引用避免 EventBus 阻止对象被回收。
        """
        # 尝试获取绑定方法的 self 对象用于弱引用
        if hasattr(handler, '__self__'):
            # 绑定方法：弱引用 self，保存方法名
            ref = weakref.ref(handler.__self__)
            method_name = handler.__func__.__name__
            self._handlers[event_type].append(('bound', ref, method_name))
        else:
            # 普通函数：直接存储（无法弱引用）
            self._handlers[event_type].append(('func', handler))

    def off(self, event_type: str, handler: Callable) -> None:
        """移除事件处理器"""
        if hasattr(handler, '__self__'):
            ref_obj = handler.__self__
            method_name = handler.__func__.__name__
            self._handlers[event_type] = [
                h for h in self._handlers[event_type]
                if not (h[0] == 'bound' and h[2] == method_name and h[1]() is ref_obj)
            ]
        else:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type]
                if not (h[0] == 'func' and h[1] is handler)
            ]

    def emit(self, event_type: str, data: Any = None, source: Any = None) -> None:
        """触发事件"""
        event = Event(type=event_type, data=data, source=source)
        # 清理失效的弱引用
        alive = []
        for handler_entry in self._handlers.get(event_type, []):
            if handler_entry[0] == 'bound':
                ref, method_name = handler_entry[1], handler_entry[2]
                obj = ref()
                if obj is not None:
                    try:
                        getattr(obj, method_name)(event)
                    except Exception as e:
                        logger.error(f"Error in handler for {event_type}: {e}")
                    alive.append(handler_entry)
                # else: 对象已被回收，跳过
            else:
                # 普通函数
                try:
                    handler_entry[1](event)
                except Exception as e:
                    logger.error(f"Error in handler for {event_type}: {e}")
                alive.append(handler_entry)
        self._handlers[event_type] = alive

    def clear(self, event_type: Optional[str] = None) -> None:
        """清除事件处理器"""
        if event_type:
            self._handlers[event_type].clear()
        else:
            self._handlers.clear()
