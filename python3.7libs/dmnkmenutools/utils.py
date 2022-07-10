import hou

def is_node_type(kwargs, type):
    return kwargs['node'].type().name() == type

def is_parm_type(kwargs, type):
    try:
        return kwargs['parm'].type().name() == type
    except:
        pass