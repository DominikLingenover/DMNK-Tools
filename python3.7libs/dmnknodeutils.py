import hou

def calc_cam_res(kwargs):
    node = kwargs['node']
    if node.parm("dmnk_enable_prop_scaling").eval() == True:
        parm = kwargs['parm_name']
        new_resx = int(kwargs['script_value0'])
        new_resy = int(kwargs['script_value1'])
        old_resx = node.parm("dmnk_helper_parmx").eval()
        old_resy = node.parm("dmnk_helper_parmy").eval()

        if new_resx == old_resx:
            node.parm("resx").set(int(new_resy * (old_resx / old_resy)))
        else:
            node.parm("resy").set(int(new_resx / (old_resx / old_resy)))

        node.parm("dmnk_helper_parmx").set(node.parm("resx").eval())
        node.parm("dmnk_helper_parmy").set(node.parm("resy").eval())