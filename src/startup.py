from .project import StartupDialog, ProjectCreateDialog

def get_or_create_project(parent=None):
    startup_dialog = StartupDialog(parent)
    startup_dialog.exec()
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