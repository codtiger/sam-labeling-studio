from typing import Optional

from PyQt6.QtGui import QIcon
from .project import StartupDialog, Project


def get_or_create_project(parent=None, icon: Optional[QIcon] = None) -> Optional[Project]:
    startup_dialog = StartupDialog(parent)
    if icon:
        startup_dialog.setWindowIcon(icon)
        startup_dialog.setWindowTitle("Sam Labeling Studio")
    if startup_dialog.exec():
        print ("dfdf")
        proj = startup_dialog.get_selected_project()
        if proj:
            return proj
        else:
            return None

    # select = ProjectSelectDialog(parent)
    # if select.exec():
    #     proj = select.get_selected_project()
    #     if proj:
    #         return proj
    # create = ProjectCreateDialog(parent)
    # if create.exec():
    #     proj = create.get_project()
    #     proj.save()
    #     return proj
    return None
