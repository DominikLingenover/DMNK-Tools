node = kwargs['node']
if node:
    node_parm_templ_grp = node.parmTemplateGroup()
    view_folder = node_parm_templ_grp.find("stdswitcher3_2")
    
    if view_folder:
        prob_cb = "kwargs['node'].parmTuple('dmnk_helper_parm').set(kwargs['node'].parmTuple('res').eval())"
        new_parm = hou.ToggleParmTemplate("dmnk_enable_prop_scaling", "Proportional Scaling", script_callback=prob_cb, script_callback_language=hou.scriptLanguage.Python)
        node_parm_templ_grp.insertAfter("resMenu", new_parm)

        res_parm = node_parm_templ_grp.find("res")
        res_parm.setScriptCallbackLanguage(hou.scriptLanguage.Python)
        res_parm.setScriptCallback("import dmnknodeutils as nu; nu.calc_cam_res(kwargs)")
        
        hidden_helper_parm = hou.FloatParmTemplate("dmnk_helper_parm", "Helper Parm", 2, is_hidden=True)
        node_parm_templ_grp.append(hidden_helper_parm)

        node_parm_templ_grp.replace("res", res_parm)

        node.setParmTemplateGroup(node_parm_templ_grp)