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