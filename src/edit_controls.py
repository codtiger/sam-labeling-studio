from enum import Enum

from src.utils import MaskData


class Actions(Enum):
    NONE = 0
    MASK_CREATE = 1
    MASK_MOVED = 2
    MASK_DELETED = 3
    NEXT_IMAGE = 4
    PREV_IMAGE = 5
    LABEL_CHANGE = 6


class EditManager:
    def __init__(
        self,
        set_actions: list[Actions],
        state_dict: dict = {},
        latest_assigned_ids: dict = {},
    ):
        """
        Edit options(undo, redo, cut, copy, paste) data management and control
        set_actions: List[Actions]
            Set of permissible actions this class keeps track of
        state_dict: dict
            Dictionary of states. Mostly keeping `last` things happening.
            e.g. `last_action`, `last_state`, `last_object`
            Can evolve with time to keep track of more things
        last_assigned_ids: dict
            Last id of objects created. Used to track for copying objects, removing or             cutting them
        """
        self.set_actions = set_actions
        self.state_dict = state_dict
        self.latest_assigned_ids = latest_assigned_ids
        self.clipboard = None

    def update_state(self, action, state, obj):
        if action:
            self.state_dict["last_action"] = action
        if state:
            self.state_dict["last_state"] = state
        if obj:
            self.state_dict["last_object"] = obj

    def undo(self):
        pass

    def redo(self):
        pass

    def cut(self):
        pass

    def copy(self):
        obj = self.state_dict.get("last_object", None)
        if isinstance(obj, MaskData):
            self.clipboard = obj

    def paste(self, **kwargs):
        if isinstance(self.clipboard, MaskData):
            if pointer := kwargs.get("pointer", None):
                new_points = [
                    [
                        coord[0] + pointer.x() - self.clipboard.center.x(),
                        coord[1] + pointer.y() - self.clipboard.center.y(),
                    ]
                    for coord in self.clipboard.points
                ]
            else:
                new_points = self.clipboard.points
            obj_copy = MaskData(
                mask_id=self.latest_assigned_ids["mask"] + 1,
                points=new_points,
                label=self.clipboard.label,
                center=self.clipboard.center,
            )
            self.latest_assigned_ids["mask"] += 1
            return obj_copy
