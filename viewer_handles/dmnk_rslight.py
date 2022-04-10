"""
Handle:         DMNK RSLight
Handle type:    dmnk_rslight
Description:    Custom Handle for RSLight
Author:         Dominik
Date Created:   March 19, 2022 - 11:45:39
"""


from imp import reload
import hou
import resourceutils as ru
import viewerhandle.utils as hu
import viewerstate.utils as su
import dmnk_utils as du
reload(du)

X_COLOR = (1, 0.2, 0.32, 1)
Y_COLOR = (0.55, 0.86, 0, 1)
Z_COLOR = (0.16, 0.56, 1, 1)

GADGET_PIVOT = "pivot"
GADGET_XAXIS = "xaxis"
GADGET_YAXIS = "yaxis"
GADGET_ZAXIS = "zaxis"
GADGET_XY_TRANS = "xytrans"
GADGET_YZ_TRANS = "yztrans"
GADGET_XZ_TRANS = "xztrans"
GADGET_XRING = "xring"
GADGET_YRING = "yring"
GADGET_ZRING = "zring"
GADGET_SCALEPIVOT = "scale_pivot"
GADGET_XSCALE = "xscale"
GADGET_YSCALE = "yscale"
GADGET_ZSCALE = "zscale"
GADGET_XY_SCALE = "xyscale"
GADGET_YZ_SCALE = "yzscale"
GADGET_XZ_SCALE = "xzscale"

GADGET_GROUPING_TRANS_ROT = "Translate/Rotate"
GADGET_GROUPING_TRANS = "Translate"
GADGET_GROUPING_ROT = "Rotate"
GADGET_GROUPING_SCALE = "Scale"

TILE_POS = du.AXIS_LENGTH*0.75

PARM_TX = "tx"
PARM_TY = "ty"
PARM_TZ = "tz"
PARM_RX = "rx"
PARM_RY = "ry"
PARM_RZ = "rz"
PARM_SX = "sx"
PARM_SY = "sy"
PARM_SZ = "sz"

LABEL_TX = "Translate X"
LABEL_TY = "Translate Y"
LABEL_TZ = "Translate Z"
LABEL_RX = "Rotate X"
LABEL_RY = "Rotate Y"
LABEL_RZ = "Rotate Z"
LABEL_SX = "Scale X"
LABEL_SY = "Scale Y"
LABEL_SZ = "Scale Z"

SCALE_SIZE = du.PIVOT_SIZE

XAXIS_DIR = hou.Vector3(1,0,0)
YAXIS_DIR = hou.Vector3(0,1,0)
ZAXIS_DIR = hou.Vector3(0,0,1)

AXIS_DIRS = {
    GADGET_XAXIS:XAXIS_DIR, GADGET_YAXIS:YAXIS_DIR, GADGET_ZAXIS:ZAXIS_DIR,
    GADGET_XSCALE:XAXIS_DIR, GADGET_YSCALE:YAXIS_DIR, GADGET_ZSCALE:ZAXIS_DIR
}
ROT_AXIS = {
    GADGET_XRING:XAXIS_DIR, GADGET_YRING:YAXIS_DIR, GADGET_ZRING:ZAXIS_DIR
}
RING_ORIENT = {
    GADGET_XRING:1, GADGET_YRING:2, GADGET_ZRING:0
}
SCALE_AXES = {
    GADGET_XSCALE:0, GADGET_YSCALE:1, GADGET_ZSCALE:2
}
SCALE_PARM = {
    GADGET_XAXIS:PARM_SX, GADGET_YAXIS:PARM_SY, GADGET_ZAXIS:PARM_SZ,
    GADGET_XSCALE:PARM_SX, GADGET_YSCALE:PARM_SY, GADGET_ZSCALE:PARM_SZ
}


class Handle(object):
    def __init__(self, **kwargs):
        """ Called when creating an instance of the handle.
        """
        self.__dict__.update(kwargs)
        self.initHandle(kwargs)

    def initHandle(self, kwargs):
        """ Initialize handle elements
        """

        self.handle_dragger = hou.ViewerHandleDragger("handle_dragger")

        self.current_pos = hou.Vector3()
        self.start_pos = hou.Vector3()
        self.dbg = hu.DebugAid(self)
        self.ring_radius = du.RING_SIZE

        self.scale = {}
        self.scaling = False

        self.xform_aid = hu.TransformAid(
            self, 
            parm_names={
                    "translate":    [PARM_TX,PARM_TY,PARM_TZ],
                    "rotate":       [PARM_RX,PARM_RY,PARM_RZ]
                }
            )

        sop_cat = hou.sopNodeTypeCategory()

        #####################################
        # Translate gadgets                 #
        #####################################
        self.xaxis = self._gadget(GADGET_XAXIS)
        if self.xaxis:
            axis_geo = du.createAxisGeometry(sop_cat, t=(du.AXIS_LENGTH/2,0,0), r=(0,0,-90))
            arrow_geo = du.createArrowGeometry(sop_cat, t=(du.AXIS_LENGTH,0,0), r=(0,0,-90))
            axis_geo.merge(arrow_geo)

            self.xaxis.setParams({"draw_color": (X_COLOR)})
            self.xaxis.setGeometry(axis_geo)

        self.yaxis = self._gadget(GADGET_YAXIS)
        if self.yaxis:
            axis_geo = du.createAxisGeometry(sop_cat, t=(0,du.AXIS_LENGTH/2,0))
            arrow_geo = du.createArrowGeometry(sop_cat, t=(0,du.AXIS_LENGTH,0))
            axis_geo.merge(arrow_geo)

            self.yaxis.setParams({"draw_color": (Y_COLOR)})
            self.yaxis.setGeometry(axis_geo)

        self.zaxis = self._gadget(GADGET_ZAXIS)
        if self.zaxis:
            axis_geo = du.createAxisGeometry(sop_cat, t=(0,0,du.AXIS_LENGTH/2), r=(90,0,0))
            arrow_geo = du.createArrowGeometry(sop_cat, t=(0,0,du.AXIS_LENGTH), r=(90,0,0))
            axis_geo.merge(arrow_geo)

            self.zaxis.setParams({"draw_color": (Z_COLOR)})
            self.zaxis.setGeometry(axis_geo)

        #####################################
        # Rotate gadgets                    #
        #####################################
        self.xring = self._gadget(GADGET_XRING)
        if self.xring:
            ring_geo = du.createRingGeometry(sop_cat, 1)

            self.xring.setParams({"draw_color": (X_COLOR)})
            self.xring.setGeometry(ring_geo)

        self.yring = self._gadget(GADGET_YRING)
        if self.yring:
            ring_geo = du.createRingGeometry(sop_cat, 2)

            self.yring.setParams({"draw_color": (Y_COLOR)})
            self.yring.setGeometry(ring_geo)

        self.zring = self._gadget(GADGET_ZRING)
        if self.zring:
            ring_geo = du.createRingGeometry(sop_cat, 0)

            self.zring.setParams({"draw_color": (Z_COLOR)})
            self.zring.setGeometry(ring_geo)
        #####################################

        # clipping sphere which is drawing in the depth 
        # buffer (glow minus matte) to hide part of the 
        # rings showing in the background.
        self.clipping = self.anchor_rot = hou.GeometryDrawable(self.scene_viewer, 
            hou.drawableGeometryType.Face, "clipping")
        rad = du.RING_SIZE/1.05
        sph = du.createSphereGeometry(hou.sopNodeTypeCategory(), rad=(rad,rad,rad))
        self.clipping.setGeometry(sph)
        self.clipping.setParams( {"highlight_mode": hou.drawableHighlightMode.Transparent} )
        

        # create the tool guides
        self.move_guide = du.Guide(self)
        self.move_guide.setUIGuides(True)

        gadgets = [
            self.xaxis, self.yaxis, self.zaxis,
            self.xring, self.yring, self.zring,
            self.clipping
        ]
        self.translate_rotate_group = [0,1,2,3,4,5,6]
        self.translate_group = [0,1,2]
        self.rotate_group = [3,4,5,6]

        grouping = [
            (GADGET_GROUPING_TRANS_ROT,self.translate_rotate_group),
            (GADGET_GROUPING_TRANS, self.translate_group),
            (GADGET_GROUPING_ROT, self.rotate_group)
        ]
        self.gadget_grouping = ru.DisplayGroup(self.scene_viewer, gadgets, grouping)
        self.gadget_grouping.showGroup(GADGET_GROUPING_TRANS_ROT, True)

    def onMouseEvent(self, kwargs):
        """ Handles pick events. Called when a handle gadget is picked and dragged.
        """
        ui_event = kwargs["ui_event"]
        reason = ui_event.reason()
        consumed = False
        gadget_name = self.handle_context.gadget()
        gadget = self._gadget(gadget_name)

        if not gadget:
            return False
        
        if reason == hou.uiEventReason.Start:
            self.start_pos = self.xform_aid.parm3("translate")

        if gadget_name in [GADGET_XAXIS, GADGET_YAXIS, GADGET_ZAXIS]:
            if reason == hou.uiEventReason.Start:
                # start dragging along an axis with the current guide tool
                hrot = self.xform_aid.parm3("rotate")

                axis_dir = AXIS_DIRS[gadget_name]
                axis_dir *= hou.hmath.buildRotate(hrot)

                self.move_guide.startDragLine(ui_event, self.start_pos, axis_dir)

                # Hide current grouping and show the pivot
                self.gadget_grouping.showCurrent(False)

                # show axis and arrow
                gadget.show(True)

            elif reason in [hou.uiEventReason.Changed, hou.uiEventReason.Active]:

                drag_values = self.move_guide.drag(ui_event)
                delta_pos = drag_values["delta_position"]

                # update the handle translate parameters
                self.xform_aid.addToParm3("translate", delta_pos)

                xform = gadget.transform() * hou.hmath.buildTranslate(delta_pos)
                gadget.setTransform(xform)

                if reason == hou.uiEventReason.Changed:
                    self.move_guide.endDrag()
                    self.gadget_grouping.showCurrent(True)

            consumed = True

        elif gadget_name in [GADGET_XRING,GADGET_YRING,GADGET_ZRING]:

            # Handle the ring gadgets for rotation
            hrot_axis = ROT_AXIS[gadget_name]
            ring_orient = RING_ORIENT[gadget_name]
            
            if reason == hou.uiEventReason.Start:
                self.start_orient = self.xform_aid.transform().extractRotationMatrix3()
                self.move_guide.startDragRotate(ui_event, ring_orient, self.ring_radius, self.start_pos, 
                    hrot_axis, self.start_orient)

                # Hide current grouping and show the pivot
                self.gadget_grouping.showCurrent(False) 
                gadget.show(True)
                                
            elif reason in [hou.uiEventReason.Changed, hou.uiEventReason.Active]:
                drag_values = self.move_guide.drag(ui_event)
                                
                orient = self.start_orient
                orient *= drag_values["delta_rotate_matrix"]
                rot = orient.extractRotates()

                self.xform_aid.setParm3("rotate", rot)
                
                if reason == hou.uiEventReason.Changed:
                    self.move_guide.endDrag()
                    self.gadget_grouping.showCurrent(True)
                    
            consumed = True
        
        return consumed

    def onDrawSetup(self, kwargs):
        """ Called before preforming drawing or picking or locating. 
        """
        # Scale the gadgets with a scale factor independent from the 
        # camera position.

        self.cacheViewportScale(self.current_pos)
        self.updateGadgetTransform()
        self.move_guide.update()   

    def onDraw(self, kwargs):
        """ Called when the handle needs to be drawn.
        """
        draw_handle = kwargs["draw_handle"]
        self._drawGadget(self.xaxis, draw_handle)
        self._drawGadget(self.yaxis, draw_handle)
        self._drawGadget(self.zaxis, draw_handle)
        self.clipping.draw(draw_handle)
        self._drawGadget(self.xring, draw_handle)
        self._drawGadget(self.yring, draw_handle)
        self._drawGadget(self.zring, draw_handle)

        if self.move_guide:
            self.move_guide.draw(draw_handle)
        

    def updateGadgetTransform(self):
        """ update the gadgets and drawables transform
        """
        # scales = [self.viewportScale()]*3
        origin = hou.Vector3()
        scale = self.handle_context.scaleFactor(origin)*250
        scales = [scale]*3
        
        # scale up the transform
        xform = self.xform_aid.updateTransform(s=[1,1,1])
        print(xform)
        
        # update the gadgets and drawables transform
        # self._transformGadget(self.pivot, xform)
        self._transformGadget(self.xaxis, xform)
        self._transformGadget(self.yaxis, xform)
        self._transformGadget(self.zaxis, xform)
        # self._transformGadget(self.xytrans, xform)
        # self._transformGadget(self.yztrans, xform)
        # self._transformGadget(self.xztrans, xform)

        self._transformGadget(self.xring, xform)
        self._transformGadget(self.yring, xform)
        self._transformGadget(self.zring, xform)
        
        self.clipping.setTransform(xform)

        # if self.handle_context.gadget() not in [GADGET_SCALEPIVOT, GADGET_XSCALE, GADGET_YSCALE, GADGET_ZSCALE]:
        #     self._transformGadget(self.xscale, xform)
        #     self._transformGadget(self.yscale, xform)
        #     self._transformGadget(self.zscale, xform)
        #     self._transformGadget(self.xyscale, xform)
        #     self._transformGadget(self.yzscale, xform)
        #     self._transformGadget(self.xzscale, xform)
        #     self._transformGadget(self.scale_pivot, xform)

    def cacheViewportScale(self, center):
        scale = self.handle_context.scaleFactor(center)*du.SCALE
        self.scale[self.scene_viewer.curViewport().name()] = scale
    
    def viewportScale(self):
        try:
            return self.scale[self.scene_viewer.curViewport().name()]
        except:
            msg = "Viewport scale value not set for %s." % self.scene_viewer.curViewport().name()
            self.scene_viewer.setPromptMessage(msg, hou.promptMessageType.Error)
        return 1.0
    
    def _gadget(self, gadget_name):
        """ Make sure to not throw if it fails as the gadget may not
            exist if its related handle parm has been disabled.
        """
        try:
            return self.handle_gadgets[gadget_name]
        except:
            return None

    def _drawGadget(self, gadget, draw_handle):
        """ Make sure to not throw if it fails as the gadget may not
            exist if its related handle parm has been disabled.
        """
        try:
            gadget.draw(draw_handle)
        except:
            pass

    def _transformGadget(self, gadget, xform):
        """ Make sure to not throw if it fails as the gadget may not
            exist if its related handle parm has been disabled.
        """
        try:
            gadget.setTransform(xform)
        except:
            pass



def createViewerHandleTemplate():
    """ Mandatory entry point to create and return the viewer handle 
        template to register. """

    handle_type = "dmnk_rslight"
    handle_label = "DMNK RSLight"
    handle_cat = [hou.objNodeTypeCategory()]

    template = hou.ViewerHandleTemplate(handle_type, handle_label, handle_cat)
    template.bindFactory(Handle)
    template.bindIcon("MISC_python")

    template.bindGadget(hou.drawableGeometryType.Face, GADGET_XAXIS, label=du.X, parms=[PARM_TX])
    template.bindGadget(hou.drawableGeometryType.Face, GADGET_YAXIS, label=du.Y, parms=[PARM_TY])
    template.bindGadget(hou.drawableGeometryType.Face, GADGET_ZAXIS, label=du.Z, parms=[PARM_TZ])
    template.bindGadget(hou.drawableGeometryType.Face, GADGET_XRING, label=du.X, parms=[PARM_RX])
    template.bindGadget(hou.drawableGeometryType.Face, GADGET_YRING, label=du.Y, parms=[PARM_RY])
    template.bindGadget(hou.drawableGeometryType.Face, GADGET_ZRING, label=du.Z, parms=[PARM_RZ])

    template.bindParameter(hou.parmTemplateType.Float, name=PARM_TX, label=LABEL_TX, min_limit=-10.0, max_limit=10.0, default_value=0.0)
    template.bindParameter(hou.parmTemplateType.Float, name=PARM_TY, label=LABEL_TY, min_limit=-10.0, max_limit=10.0, default_value=0.0)
    template.bindParameter(hou.parmTemplateType.Float, name=PARM_TZ, label=LABEL_TZ, min_limit=-10.0, max_limit=10.0, default_value=0.0)
    template.bindParameter(hou.parmTemplateType.Float, name=PARM_RX, label=LABEL_RX, min_limit=0, max_limit=360, default_value=0.0)
    template.bindParameter(hou.parmTemplateType.Float, name=PARM_RY, label=LABEL_RY, min_limit=0, max_limit=360, default_value=0.0)
    template.bindParameter(hou.parmTemplateType.Float, name=PARM_RZ, label=LABEL_RZ, min_limit=0, max_limit=360, default_value=0.0)

    template.exportParameters(
        [
            PARM_TX, PARM_TY, PARM_TZ,
            PARM_RX, PARM_RY, PARM_RZ,
        ]
    )

    return template