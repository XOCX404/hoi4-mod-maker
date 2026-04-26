"""
DeleteCountryCommand — 删除国家, 支持 undo (恢复 country 数据 + 所有 state owner).
"""

from __future__ import annotations

import copy

from commands.base import Command


class DeleteCountryCommand(Command):
    """删除一个国家. 同时清理所有指向它的 state owner. undo 时完整恢复."""

    label = "删除国家"

    def __init__(self, country_mgr, tag: str) -> None:
        self._country_mgr = country_mgr
        self._tag = tag.upper()[:3]
        self._snapshot = None  # CountryData 快照
        self._owned_state_ids: list[int] = []

    def execute(self) -> None:
        c = self._country_mgr.countries.get(self._tag)
        if c is None:
            return
        self._snapshot = copy.deepcopy(c)
        # 记录该国拥有的所有 state, undo 时重新分配
        self._owned_state_ids = [
            sid for sid, t in self._country_mgr._state_owner.items() if t == self._tag
        ]
        # remove_country 内部会清理 _state_owner
        self._country_mgr.remove_country(self._tag)

    def undo(self) -> None:
        if self._snapshot is None:
            return
        self._country_mgr._countries[self._tag] = self._snapshot
        for sid in self._owned_state_ids:
            self._country_mgr._state_owner[sid] = self._tag
