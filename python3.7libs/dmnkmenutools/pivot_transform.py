import hou

def pivot_cb(kwargs, btn):
    node = kwargs["node"]

    if node.type().name() == "xform":
        bbox = node.geometry().boundingBox()
    else:
        bbox = node.displayNode().geometry().boundingBox()

    if btn == "center":
        node.setParms({
            "p": bbox.center()
        })
    elif btn == "xmax":
        node.setParms({
            "px": bbox.maxvec()[0]
        })
    elif btn == "xmin":
        node.setParms({
            "px": bbox.minvec()[0]
        })
    elif btn == "ymax":
        node.setParms({
            "py": bbox.maxvec()[1]
        })
    elif btn == "ymin":
        node.setParms({
            "py": bbox.minvec()[1]
        })
    elif btn == "zmax":
        node.setParms({
            "pz": bbox.maxvec()[2]
        })
    elif btn == "zmin":
        node.setParms({
            "pz": bbox.minvec()[2]
        })
    
def pt_already_exists(kwargs):
    node = kwargs['node']
    node_parm_templ_grp = node.parmTemplateGroup()
    temp = node_parm_templ_grp.find("dmnk_pivot_transform")

    if temp == None:
        return False
    else:
        return True

def add_pivot_transform(kwargs):
    node = kwargs['node']
    node_parm_templ_grp = node.parmTemplateGroup()

    if pt_already_exists(kwargs):
        node_parm_templ_grp.remove("dmnk_pivot_transform")
        node.setParmTemplateGroup(node_parm_templ_grp)
        return

    if node.type().name() == "xform":
        transform_folder = node_parm_templ_grp.find("parmgroup_pivotxform")
    else:
        transform_folder = node_parm_templ_grp.find("stdswitcher4")

    dmnk_pivot_folder = hou.FolderParmTemplate("dmnk_pivot_transform", "DMNK Pivot")
    center_btn_callback = "import dmnkmenutools.pivot_transform as pt; pt.pivot_cb(kwargs, 'center')"
    center_btn = hou.ButtonParmTemplate("dmnk_pivot_center", "CENTER", join_with_next=True, script_callback=center_btn_callback, script_callback_language=hou.scriptLanguage.Python)

    xmax_btn_callback = "import dmnkmenutools.pivot_transform as pt; pt.pivot_cb(kwargs, 'xmax')"
    xmax_btn = hou.ButtonParmTemplate("dmnk_pivot_xmax", "X MAX", join_with_next=True, script_callback=xmax_btn_callback, script_callback_language=hou.scriptLanguage.Python)

    xmin_btn_callback = "import dmnkmenutools.pivot_transform as pt; pt.pivot_cb(kwargs, 'xmin')"
    xmin_btn = hou.ButtonParmTemplate("dmnk_pivot_xmin", "X MIN", join_with_next=True, script_callback=xmin_btn_callback, script_callback_language=hou.scriptLanguage.Python)

    ymax_btn_callback = "import dmnkmenutools.pivot_transform as pt; pt.pivot_cb(kwargs, 'ymax')"
    ymax_btn = hou.ButtonParmTemplate("dmnk_pivot_ymax", "Y MAX", join_with_next=True, script_callback=ymax_btn_callback, script_callback_language=hou.scriptLanguage.Python)

    ymin_btn_callback = "import dmnkmenutools.pivot_transform as pt; pt.pivot_cb(kwargs, 'ymin')"
    ymin_btn = hou.ButtonParmTemplate("dmnk_pivot_ymin", "Y MIN", join_with_next=True, script_callback=ymin_btn_callback, script_callback_language=hou.scriptLanguage.Python)

    zmax_btn_callback = "import dmnkmenutools.pivot_transform as pt; pt.pivot_cb(kwargs, 'zmax')"
    zmax_btn = hou.ButtonParmTemplate("dmnk_pivot_zmax", "Z MAX", join_with_next=True, script_callback=zmax_btn_callback, script_callback_language=hou.scriptLanguage.Python)

    zmin_btn_callback = "import dmnkmenutools.pivot_transform as pt; pt.pivot_cb(kwargs, 'zmin')"
    zmin_btn = hou.ButtonParmTemplate("dmnk_pivot_zmin", "Z MIN", join_with_next=True, script_callback=zmin_btn_callback, script_callback_language=hou.scriptLanguage.Python)

    uselessparm = hou.FloatParmTemplate("dmnk_uselessparm", "", is_hidden=True, num_components=1)

    dmnk_pivot_folder.addParmTemplate(center_btn)
    dmnk_pivot_folder.addParmTemplate(xmax_btn)
    dmnk_pivot_folder.addParmTemplate(xmin_btn)
    dmnk_pivot_folder.addParmTemplate(ymax_btn)
    dmnk_pivot_folder.addParmTemplate(ymin_btn)
    dmnk_pivot_folder.addParmTemplate(zmax_btn)
    dmnk_pivot_folder.addParmTemplate(zmin_btn)
    dmnk_pivot_folder.addParmTemplate(uselessparm)

    node_parm_templ_grp.appendToFolder(transform_folder, dmnk_pivot_folder)
    node.setParmTemplateGroup(node_parm_templ_grp)