import hou

def instance_from_node():
    sel_nodes = hou.selectedNodes()

    for node in sel_nodes:
        if node.type().name() == "geo":
            instance_node = node.parent().createNode("instance", node_name=node.name() + "_instance")
            instance_node.setParms({
                "instancepath": instance_node.relativePathTo(node),
                "ptinstance": 2
            })
            instance_node.moveToGoodPosition()

            node.setDisplayFlag(False)

def proxy_from_node():
    sel_nodes = hou.selectedNodes()

    for node in sel_nodes:
        if node.type().name() == "geo":
            display_node = node.displayNode()
            proxy_output_node = display_node.createOutputNode("Redshift_Proxy_Output")
            proxy_output_node.parm("execute").pressButton()
            
            proxy_loader_node = node.parent().createNode("geo")
            proxy_loader_node.createNode("redshift_proxySOP")
            proxy_loader_node.setParms({
                "RS_objprop_proxy_enable": 1,
                "RS_objprop_proxy_file": proxy_output_node.parm("RS_archive_file").eval()
            })
            
            node.setDisplayFlag(False)