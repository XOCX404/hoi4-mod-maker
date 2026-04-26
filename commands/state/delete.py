"""
DeleteStateCommand — 删除 State, 支持 undo (恢复 provinces / owner / 所有属性).
"""

from __future__ import annotations

import copy

from commands.base import Command


class DeleteStateCommand(Command):
    """删除一个 State, 同时清理 country_mgr 里指向它的 owner 引用. undo 时完整恢复."""

    label = "删除 State"

    def __init__(self, state_mgr, country_mgr, sid: int) -> None:
        self._state_mgr = state_mgr
        self._country_mgr = country_mgr
        self._sid = sid
        self._snapshot = None  # StateData 快照
        self._owner_tag = ""

    def execute(self) -> None:
        state = self._state_mgr.get_state(self._sid)
        if state is None:
            return
        # 完整快照: 用 copy.deepcopy 因为 StateData 含 list/dict 嵌套
        self._snapshot = copy.deepcopy(state)
        if self._country_mgr is not None:
            self._owner_tag = self._country_mgr.get_owner_of_state(self._sid)
            if self._owner_tag:
                self._country_mgr.assign_state(self._sid, "")
        self._state_mgr.delete_state(self._sid)

    def undo(self) -> None:
        if self._snapshot is None:
            return
        # 写回 _states + 重建反向索引
        self._state_mgr._states[self._sid] = self._snapshot
        for pid in self._snapshot.provinces:
            self._state_mgr._province_to_state[pid] = self._sid
        if self._owner_tag and self._country_mgr is not None:
            self._country_mgr.assign_state(self._sid, self._owner_tag)
