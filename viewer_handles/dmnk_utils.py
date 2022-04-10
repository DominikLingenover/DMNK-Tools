"""
Description:    Guide for the  poor man's move tool demo.
Author:         marcb
Date Created:   April 2, 2020 - 10:33:07
"""

import math

import hou
import resourceutils as ru
import viewerhandle.utils as hu

SIZE = 1.0
SCALE = 150.0

AXIS_LENGTH = SIZE*0.75
AXIS_RAD = 0.015

ARROW_TIP = 0
ARROW_BASE = 0.02
ARROW_HEIGHT = 0.15
ARROW_OFFSET = ARROW_HEIGHT/2        

ARROW_L = 0.1
ARROW_W = 0.05
ANCHOR_SIZE = 0.07

SPH_RAD = 0.05
PIVOT_SIZE = SPH_RAD*2.6

TILE_POS = AXIS_LENGTH*0.75
TILE_SIZE = PIVOT_SIZE*0.75

RING_SIZE = SIZE

X = "X"
Y = "Y"
Z = "Z"
XZ = "XZ"
YZ = "YZ"
XY = "XY"
XYZ = "XYZ"
    
PLANE_XZ = hou.Vector3(0,1,0)
PLANE_YZ = hou.Vector3(1,0,0)
PLANE_XY = hou.Vector3(0,0,1)
PLANE_XYZ = hou.Vector3(1,1,1)    
    
PLANE = 0
PLANE_LABEL = 1
    
PLANES = {XZ:PLANE_XZ, YZ:PLANE_YZ, XY:PLANE_XY, XYZ:PLANE_XYZ}
    
RING_ORIENT = {PLANE_XZ:2,PLANE_YZ:0,PLANE_XY:1}
    
XCOLOR = (1,0,0,1)
YCOLOR = (0,1,0,1)
ZCOLOR = (0,0,1,1)    
HLIGHT_COLOR = [1,1,0,.7]    

class Guide(object):
    """
    Encapsulates the move tool guides implementation.
    """    
    
    def __init__(self, handle):
        self.handle = handle
        self.dbg = hu.DebugAid(handle)
        self.xform_aid = self.handle.xform_aid
        self.handle_dragger = handle.handle_dragger
        self.scene_viewer = handle.scene_viewer
        self.drag_values = None
        self.drag_line = None
        self.setDragPlane(XYZ)
        self.plane_rot = hou.Matrix4(1)
        self.drag_rotate = None
        self.drag_scaling = None
        self.drag_scaling_pivot = None
        self.drag_trans_plane = None

        self.cum_delta_pos = hou.Vector3()
        self.text1_pos = hou.Vector3()
        self.text2_pos = hou.Vector3()
        self.arrow_scale = 1.0
        self.ui_guides = False
        
        self.sop_cat = hou.sopNodeTypeCategory()

        self.color_options = ru.ColorOptions(self.scene_viewer)
        self.pick_color = self.color_options.colorFromName("PickedHandleColor")
        self.text_color = self.color_options.colorFromName("HandleDeltaTextColor")
        self.plane_color = self.color_options.colorFromName("GridColor", alpha_name="GridLineAlpha")
        self.line_color = self.color_options.colorFromName("GridColor")
        self.createDrawables()
        self.createGeometries()
        self.assignGeometries()
                
    def show(self, value):
        self.plane_dim.show(value)
        self.text1.show(value)
        self.text2.show(value)
        self.guide_line.show(value)
        self.dim_line1.show(value)
        self.dim_line2.show(value)
        self.dim_arrow1.show(value)
        self.dim_arrow2.show(value)
        self.ring_hlight.show(value)
               
    def draw(self, draw_handle):
        if self.ui_guides:
            # These dimension guides will draw only if 
            # they are diplayed
            self.plane_dim.draw(draw_handle)
            self.text1.draw(draw_handle)
            self.text2.draw(draw_handle)
            self.guide_line.draw(draw_handle)
            self.dim_line1.draw(draw_handle)
            self.dim_line2.draw(draw_handle)
            self.dim_arrow1.draw(draw_handle)
            self.dim_arrow2.draw(draw_handle)
            self.anchor_rot.draw(draw_handle)

        if self.drag_rotate:
            self.ring_hlight.draw(draw_handle)

    def updateTransform(self, s=None, r=None, t=None):
        """ Update the handle transform and return a proper guide 
            transform.
        """
        xform = self.xform_aid.updateTransform(s, r, t)        
        
        # the handle scaling is not needed for the guides/gadgets
        try:
            sinv = hou.hmath.buildScale(self.xform_aid.parm3("scale")).inverted()
            xform = sinv*xform
        except:
            pass
        return xform
    
    def setDragPlane(self, plane_name):
        try:
            self.drag_plane = (PLANES[plane_name], plane_name)
            return True
        except:
            pass
        return False            

    def dragPlaneLabel(self):
        return self.drag_plane[PLANE_LABEL]
        
    def dragPlane(self):
        return self.drag_plane[PLANE]

    def setUIGuides(self, value):
        self.ui_guides = value
        
    def startDragPivot(self, ui_event, hpos):           
        
        if self.dragPlaneLabel() not in [PLANE_XYZ]:
            self.show(True)
            self.plane_rot = hou.Matrix4(1)
            self.handle_dragger.startDragAlongPlane(ui_event, hpos, self.drag_plane[PLANE])
        else:
            self.text1.show(True)
            self.guide_line.show(True)    
            self.handle_dragger.startDrag(ui_event, hpos)
            
        self.cum_delta_pos = hou.Vector3()

    def startDragTransPlane(self, ui_event, hpos, plane):
        self.show(True)
        self.plane_rot = hou.hmath.buildRotate(self.updateTransform().extractRotates())        
        self.handle_dragger.startDragAlongPlane(ui_event, hpos, plane * self.plane_rot)
        self.cum_delta_pos = hou.Vector3()
        self.drag_trans_plane = plane
       
    def startDragLine(self, ui_event, hpos, axis_dir):
        self.drag_line = axis_dir
        
        # show guide
        self.text1.show(True)
        self.guide_line.show(True)

        self.handle_dragger.startDragAlongLine(ui_event, hpos, self.drag_line)        
        self.cum_delta_pos = hou.Vector3()

    def startDragRotate(self, ui_event, ring_orient, ring_radius, hpos, rot_axis, horient):                    
        self.drag_rotate = True
        self.ring_orient = ring_orient
        self.ring_radius = ring_radius
        self.start_orient = horient
        self.handle_pos = hpos
        self.start_end_angle = None
                
        rot_axis *= self.start_orient
        self.handle_dragger.startDragRotate(ui_event, self.handle_pos, self.ring_radius, 
            rot_axis, self.start_orient)
        self.start_rotate_pos = self.handle_dragger.startRotatePosition()
        
        # rotate the start rotate pos around the handle orientation to compute begin angle.
        start_rotate_pos = self.start_rotate_pos
        start_rotate_pos *= self.start_orient.inverted()
        start_rotate_pos += self.handle_pos
        
        if self.ring_orient == 0:
            # XY plane
            cx = self.handle_pos[0]
            cy = self.handle_pos[1]
            x = start_rotate_pos[0]
            y = start_rotate_pos[1]
            self.begin_angle = math.degrees(math.atan2(y-cy, x-cx))
        elif self.ring_orient == 1:
            # YZ plane
            cy = self.handle_pos[1]
            cx = self.handle_pos[2]
            y = start_rotate_pos[1]
            x = start_rotate_pos[2]        
            self.begin_angle = math.degrees(math.atan2(y-cy, cx-x))
        elif self.ring_orient == 2:
            # ZX plane
            cx = self.handle_pos[0]
            cy = self.handle_pos[2]                        
            x = start_rotate_pos[0]
            y = start_rotate_pos[2]                    
            self.begin_angle = math.degrees(math.atan2(cy-y, x-cx))
               
        # create a geometry for the ring highlighter
        hlight_geo = createRingHighlightGeometry(self.sop_cat, self.ring_radius, self.ring_orient, 
            self.begin_angle, self.begin_angle)
        self.ring_hlight.setGeometry(hlight_geo)
        
        xform = self.updateTransform()
        self.ring_hlight.setTransform(xform)
        self.ring_hlight.show(True)

        # position the anchor at the start of the angle
        anchor_pos = self.start_rotate_pos
        anchor_pos *= self.start_orient.inverted()
        self.anchor_rot.setTransform(hou.hmath.buildTranslate(anchor_pos) * xform)
        self.anchor_rot.show(True)
        
        # rotation text
        self.total_angle = 0.0        
        self.text1.show(True)

    def startDragScaling(self, ui_event, hpos, scaling_value, axis_dir, scaling_axis):
        
        self.drag_scaling = True
        self.scaling_axis = scaling_axis

        self.handle_dragger.startDragAlongLine(ui_event, hpos, axis_dir)
        start_pos = self.handle_dragger.startPosition()

        self.setGeoPoint(self.geo_dim_line1_points[0], start_pos)

        text_pos = self.xform_aid.toScreen(start_pos)
        self.text1.setParams({"translate":text_pos})

        if scaling_value == 0:
            scaling_value = 1

        self.start_scaling_value = scaling_value
        self.scaling_value = scaling_value        
        self.text1.setParams({"text":"1.0x"})
                        
    def startDragScalingPivot(self, ui_event, hpos):
        self.drag_scaling_pivot = True

        self.handle_dragger.startDrag(ui_event, hpos)

        self.scaling_value = 0.0
        self.text1.setParams({"text":""})

        self.cum_delta_pos = hou.Vector3()
        
    def drag(self, ui_event):
        self.drag_values = self.handle_dragger.drag(ui_event)
        try:
            self.cum_delta_pos += self.drag_values["delta_position"]
        except:
            pass

        return self.drag_values

    def endDrag(self):
        self.handle_dragger.endDrag()                   
        self.show(False)
        self.anchor_rot.show(False)
        self.drag_line = None
        self.drag_rotate = None
        self.drag_values = None
        self.drag_scaling = None
        self.drag_scaling_pivot = None
        self.drag_trans_plane = None

    def update(self):
        if not self.handle_dragger:
            return
                           
        if self.drag_rotate and self.drag_values:
            self.updateRotatePos()
        elif self.drag_scaling:
            self.updateScaling()
        elif self.drag_scaling_pivot:
            self.updateScalingPivot()
        elif self.drag_trans_plane:
            self.updatePlanePos(self.drag_trans_plane)            
        elif self.drag_plane[PLANE] == PLANE_XYZ or self.drag_line:
            self.updateAxisPos()
        elif self.drag_plane[PLANE] in [PLANE_XY, PLANE_YZ, PLANE_XZ]:
            self.updatePlanePos(self.drag_plane[PLANE])                    
        else:
            raise
            
        self.makeGuidesDirty()            

    def updateAxisPos(self):
        """
        Draw a dim line between the start pivot and the new absolute
        position (abs_pos), and display the distance between start pivot 
        and pos.
        """               
        start_pos = self.handle_dragger.startPosition()                                     
        abs_pos = start_pos + self.cum_delta_pos
        
        # dim line1 geo which will blend with the axis
        self.setGeoPoint(self.geo_dim_line1_points[0], start_pos)
        self.setGeoPoint(self.geo_dim_line1_points[1], abs_pos)        
                
        # dimension text 
        delta = abs_pos-start_pos
        mv = "%6.3f" % (math.fabs(delta.length()))
        
        # place the text at mid point between dragger origin 
        # pos and current pos
        dist = start_pos.distanceTo(abs_pos)/2.0
        pos = start_pos + dist*delta.normalized()        
        
        text_pos = self.xform_aid.toScreen(pos)        
        self.text1.setParams({"translate":text_pos, "text": mv})
        
    def updateRotatePos(self):
        """ Update the rotation guide.
        """        
        # Compute the guide end angle 
        end_angle = hou.hmath.radToDeg(self.drag_values["angle"])
        angle = (end_angle % 360 + 360) % 360
        if end_angle < 0.0:
            angle = (360.0 - angle) * -1
        end_angle = angle
                
        if math.fabs(end_angle) < 360.0: 
            end_angle += self.begin_angle
        else:
            end_angle = self.begin_angle
                        
        hlight_geo = createRingHighlightGeometry(self.sop_cat, self.ring_radius, self.ring_orient, 
            self.begin_angle, end_angle)
        self.ring_hlight.setGeometry(hlight_geo)
                
        # show current angle text
        pos = self.drag_values["rotate_position"] 
        pos *= self.start_orient.inverted()
        pos *= self.updateTransform()        
        text_pos = self.xform_aid.toScreen(pos)
        self.text1.setParams({"translate":text_pos})
        
        self.total_angle += hou.hmath.radToDeg(self.drag_values["delta_angle"])                        
        self.text1.setParams({"text":"%6.3f"%(self.total_angle)})

    def updateScaling(self):    
        if not self.drag_values:
            return
                
        delta_pos = self.drag_values["delta_position"]
        abs_pos = self.drag_values["position"]
    
        # update the guide line geometry
        self.setGeoPoint(self.geo_dim_line1_points[1], abs_pos)        
        self.guide_line.show(True)

        self.text1.show(True)        

        # update text
        text_pos = self.xform_aid.toScreen(abs_pos)
        self.text1.setParams({"translate":text_pos})
        self.scaling_value += delta_pos[self.scaling_axis]                    
        scale_change = self.scaling_value / self.start_scaling_value
        self.text1.setParams({"text":"%4.2fx"%(scale_change)})

    def updateScalingPivot(self):
        if not self.drag_values:
            return

        # update text
        delta_pos = self.drag_values["delta_position"]
        delta_value = delta_pos[0]
        abs_pos = self.drag_values["position"]        
        
        text_pos = self.xform_aid.toScreen(abs_pos)
        self.scaling_value += delta_value
        self.text1.setParams({"translate":text_pos,
            "text":"%4.2fx"%(self.scaling_value)})
        self.text1.show(True)

    def updatePlanePos(self, active_plane):
        """ Update the position based on the selected plane type.
        abs_pos: the handle absolute position
        active_plane: plane used for translating `pos`
        """
        obj_world_inv = self.xform_aid.objectWorldTransform().inverted()
        rotm4 = self.plane_rot
        xform = rotm4 * hou.hmath.buildScale(self.xform_aid.transform().extractScales())                
        
        start_pos = self.handle_dragger.startPosition()
        abs_pos = start_pos + self.cum_delta_pos
        rot_start_pos = start_pos * rotm4.inverted()
        rot_delta_pos = self.cum_delta_pos * rotm4.inverted()
        
        # plane guide 
        plane_pos = [
            hou.Vector3(rot_start_pos),
            hou.Vector3(rot_start_pos),
            hou.Vector3(rot_start_pos),
            hou.Vector3(rot_start_pos)]
        
        # dimension guide lines
        dim_pos = [
            hou.Vector3(rot_start_pos),
            hou.Vector3(rot_start_pos),
            hou.Vector3(rot_start_pos)]
        
        # arrows
        arrow_pos = [
            hou.Vector3(rot_start_pos),
            hou.Vector3(rot_start_pos)]
        
        # text position
        text_dim_pos = [
            hou.Vector3(rot_start_pos),
            hou.Vector3(rot_start_pos)]
        text_dim_val = ["",""]
        
        if active_plane == PLANE_XZ:
            plane_pos[1][0] += rot_delta_pos[0]
            plane_pos[2][0] += rot_delta_pos[0]
            plane_pos[2][2] += rot_delta_pos[2]
            plane_pos[3][2] += rot_delta_pos[2]
                            
            dim_pos[1][0] += rot_delta_pos[0]
            dim_pos[2][2] += rot_delta_pos[2]

            arrow_pos[0][0] += rot_delta_pos[0]            
            rot = 90 if abs_pos[0] < start_pos[0] else -90
            arrow_offset = ARROW_OFFSET if abs_pos[0] < start_pos[0]-ARROW_OFFSET else -ARROW_OFFSET
            
            self.dim_arrow1.setParams({"rotate":(0,0,rot)})
            self.dim_arrow1.setParams({"translate":(arrow_offset,0,0)})
            
            arrow_pos[1][2] += rot_delta_pos[2]
            rot = -90 if abs_pos[2] < start_pos[2] else 90
            arrow_offset = ARROW_OFFSET if abs_pos[2] < start_pos[2]-ARROW_OFFSET else -ARROW_OFFSET
            
            self.dim_arrow2.setParams({"rotate":(rot,0,0)})
            self.dim_arrow2.setParams({"translate":(0,0,arrow_offset)})

            text_dim_pos[0][0] += rot_delta_pos[0]/2
            text_dim_val[0] = "%6.3f" % (math.fabs(abs_pos[0]-start_pos[0]))
            text_dim_pos[1][2] += rot_delta_pos[2]/2
            text_dim_val[1] = "%6.3f" % (math.fabs(abs_pos[2]-start_pos[2]))
            
        elif active_plane == PLANE_XY:
            plane_pos[1][1] += rot_delta_pos[1]            
            plane_pos[2][0] += rot_delta_pos[0]
            plane_pos[2][1] += rot_delta_pos[1]
            plane_pos[3][0] += rot_delta_pos[0]

            dim_pos[1][0] += rot_delta_pos[0]
            dim_pos[2][1] += rot_delta_pos[1]
            
            arrow_pos[0][0] += rot_delta_pos[0]
            rot = 90 if abs_pos[0] < start_pos[0] else -90        
            arrow_offset = ARROW_OFFSET if abs_pos[0] < start_pos[0]-ARROW_OFFSET else -ARROW_OFFSET
            
            self.dim_arrow1.setParams({"rotate":(0,0,rot)})
            self.dim_arrow1.setParams({"translate":(arrow_offset,0,0)})
            
            arrow_pos[1][1] += rot_delta_pos[1]
            rot = 180 if abs_pos[1] < start_pos[1] else 0
            arrow_offset = ARROW_OFFSET if abs_pos[1] < start_pos[1]-ARROW_OFFSET else -ARROW_OFFSET
            
            self.dim_arrow2.setParams({"rotate":(rot,0,0)})
            self.dim_arrow2.setParams({"translate":(0,arrow_offset,0)})

            text_dim_pos[0][0] += rot_delta_pos[0]/2
            text_dim_val[0] = "%6.3f" % (math.fabs(abs_pos[0]-start_pos[0]))
            text_dim_pos[1][1] += rot_delta_pos[1]/2
            text_dim_val[1] = "%6.3f" % (math.fabs(abs_pos[1]-start_pos[1]))
            
        elif active_plane == PLANE_YZ:
            plane_pos[1][2] += rot_delta_pos[2]            
            plane_pos[2][1] += rot_delta_pos[1]
            plane_pos[2][2] += rot_delta_pos[2]
            plane_pos[3][1] += rot_delta_pos[1]

            dim_pos[1][1] += rot_delta_pos[1]
            dim_pos[2][2] += rot_delta_pos[2]
            
            arrow_pos[0][1] += rot_delta_pos[1]
            rot = 180 if abs_pos[1] < start_pos[1] else 0
            arrow_offset = ARROW_OFFSET if abs_pos[1] < start_pos[1]-ARROW_OFFSET else -ARROW_OFFSET
            
            self.dim_arrow1.setParams({"rotate":(rot,0,0)})
            self.dim_arrow1.setParams({"translate":(0,arrow_offset,0)})
            
            arrow_pos[1][2] += rot_delta_pos[2]
            rot = -90 if abs_pos[2] < start_pos[2] else 90
            arrow_offset = ARROW_OFFSET if abs_pos[2] < start_pos[2]-ARROW_OFFSET else -ARROW_OFFSET
            
            self.dim_arrow2.setParams({"rotate":(rot,0,0)})
            self.dim_arrow2.setParams({"translate":(0,0,arrow_offset)})

            text_dim_pos[0][2] += rot_delta_pos[2]/2
            text_dim_val[0] = "%6.3f" % (math.fabs(abs_pos[2]-start_pos[2]))
            text_dim_pos[1][1] += rot_delta_pos[1]/2
            text_dim_val[1] = "%6.3f" % (math.fabs(abs_pos[1]-start_pos[1]))            
        else:
            raise
            
        # apply transform to plane points
        #dbg = hu.DebugAid(self.handle)
                
        for i, (plane_pt, pos) in enumerate(zip(self.plane_points, plane_pos)):        
            plane_pt.setPosition(pos * rotm4)
            
        # dim guide line
        self.setGeoPoint(self.geo_dim_line1_points[0], dim_pos[0] * rotm4)        
        self.setGeoPoint(self.geo_dim_line1_points[1], dim_pos[1] * rotm4)        
        self.setGeoPoint(self.geo_dim_line2_points[0], dim_pos[0] * rotm4)        
        self.setGeoPoint(self.geo_dim_line2_points[1], dim_pos[2] * rotm4)        
        
        # dim arrows 
        xform = hou.hmath.buildScale(self.updateTransform().extractScales())                
        xform *= hou.hmath.buildTranslate(arrow_pos[0])
        xform *= rotm4
        self.dim_arrow1.setTransform(xform)
        
        xform = hou.hmath.buildScale(self.updateTransform().extractScales())                
        xform *= hou.hmath.buildTranslate(arrow_pos[1])
        xform *= rotm4
        self.dim_arrow2.setTransform(xform)
        
        # dim text        
        text_pos = self.xform_aid.toScreen(text_dim_pos[0] * rotm4)
        self.text1.setParams({ "translate":text_pos, "text": text_dim_val[0] })
        text_pos = self.xform_aid.toScreen(text_dim_pos[1] * rotm4)
        self.text2.setParams({ "translate":text_pos, "text": text_dim_val[1] })
        
    def setGeoPoint(self, point, pos):        
        obj_world_inv = self.xform_aid.objectWorldTransform().inverted()
        point.setPosition(pos * obj_world_inv)            
        
    def createDrawables(self):
        """ Create all drawables used for drawing the guides.
        """
        # dimension plane
        scene_viewer = self.scene_viewer
        self.plane_dim = hou.GeometryDrawable(scene_viewer, hou.drawableGeometryType.Face, "plane")
        self.plane_dim.setParams( {"color1":self.plane_color})
        self.plane_dim.show(False)

        self.guide_line = hou.GeometryDrawable(scene_viewer, hou.drawableGeometryType.Line, "guide_line")
        self.guide_line.setParams({"color1":self.line_color})
        self.guide_line.show(False)
        
        # text dimension #1
        self.text1 = hou.TextDrawable(scene_viewer, "dim1")
        self.text1.setParams( {"color1":self.text_color} )
        self.text1.show(False)

        self.dim_line1 = hou.GeometryDrawable(scene_viewer, hou.drawableGeometryType.Line, "dim_line1")
        self.dim_line1.setParams({"color1":self.pick_color})
        self.dim_line1.show(False)

        self.dim_arrow1 = hou.GeometryDrawable(scene_viewer, hou.drawableGeometryType.Face, "dim_arrow1")
        self.dim_arrow1.setParams( {"color1":self.pick_color} )
        self.dim_arrow1.show(False)
        
        # text dimension #2
        self.text2 = hou.TextDrawable(scene_viewer, "dim2")
        self.text2.setParams( {"color1":self.text_color} )
        self.text2.show(False)
               
        self.dim_line2 = hou.GeometryDrawable(scene_viewer, hou.drawableGeometryType.Line, "dim_line2")
        self.dim_line2.setParams( {"color1":self.pick_color} )
        self.dim_line2.show(False)

        self.dim_arrow2 = hou.GeometryDrawable(scene_viewer, hou.drawableGeometryType.Face, "dim_arrow2")
        self.dim_arrow2.setParams( {"color1":self.pick_color} )
        self.dim_arrow2.show(False)

        # anchor rotation
        self.anchor_rot = hou.GeometryDrawable(scene_viewer, hou.drawableGeometryType.Face, "anchor rotation")        
        self.anchor_rot.setGeometry(createSphereGeometry(self.sop_cat))
        self.anchor_rot.setParams( {"color1":self.color_options.colorFromName("HandleColor")} )

        # ring highlighter
        self.ring_hlight = hou.GeometryDrawable(scene_viewer, hou.drawableGeometryType.Line, "ring_hl")
        self.ring_hlight.setParams( {"color1":HLIGHT_COLOR, "color2":self.pick_color, "line_width":3.0} )
        self.ring_hlight.show(False)
    
    def createGeometries(self):       
        """ Create the needs geometries for the drawables.
        """
        # dimension plane
        self.plane_geo = hou.Geometry()
        
        self.plane_points = []
        self.plane_points.append( self.plane_geo.createPoint() )
        self.plane_points.append( self.plane_geo.createPoint() )
        self.plane_points.append( self.plane_geo.createPoint() )
        self.plane_points.append( self.plane_geo.createPoint() )

        self.plane_poly = self.plane_geo.createPolygon()
        self.plane_poly.addVertex(self.plane_points[0])
        self.plane_poly.addVertex(self.plane_points[1])
        self.plane_poly.addVertex(self.plane_points[2])
        self.plane_poly.addVertex(self.plane_points[3])
        
        # dim line 1
        self.geo_dim_line1 = hou.Geometry()

        self.geo_dim_line1_points = []
        self.geo_dim_line1_points.append(self.geo_dim_line1.createPoint())
        self.geo_dim_line1_points.append(self.geo_dim_line1.createPoint())

        self.poly_dim_line1 = self.geo_dim_line1.createPolygon()
        self.poly_dim_line1.addVertex(self.geo_dim_line1_points[0])
        self.poly_dim_line1.addVertex(self.geo_dim_line1_points[1])
        self.poly_dim_line1.addVertex(self.geo_dim_line1_points[0])

        # dim line 2
        self.geo_dim_line2 = hou.Geometry()

        self.geo_dim_line2_points = []
        self.geo_dim_line2_points.append(self.geo_dim_line2.createPoint())
        self.geo_dim_line2_points.append(self.geo_dim_line2.createPoint())

        self.poly_dim_line2 = self.geo_dim_line2.createPolygon()
        self.poly_dim_line2.addVertex(self.geo_dim_line2_points[0])
        self.poly_dim_line2.addVertex(self.geo_dim_line2_points[1])
        self.poly_dim_line2.addVertex(self.geo_dim_line2_points[0])
        
        # dim line 1 arrow
        self.geo_dim_arrow1 = createArrowGeometry(self.sop_cat)

        # dim line 2 arrow
        self.geo_dim_arrow2 = createArrowGeometry(self.sop_cat)
            
    def assignGeometries(self):
        """ Assign the drawables with geometries.
        """
        self.plane_dim.setGeometry(self.plane_geo)
        self.guide_line.setGeometry(self.geo_dim_line1)
        self.dim_line1.setGeometry(self.geo_dim_line1)
        self.dim_line2.setGeometry(self.geo_dim_line2)
        self.dim_arrow1.setGeometry(self.geo_dim_arrow1)
        self.dim_arrow2.setGeometry(self.geo_dim_arrow2)
                
    def makeGuidesDirty(self):
        self.plane_geo.findPointAttrib("P").incrementDataId()
        self.geo_dim_line1.findPointAttrib("P").incrementDataId()
        self.geo_dim_line2.findPointAttrib("P").incrementDataId()
        self.plane_geo.incrementModificationCounter()
        self.geo_dim_line1.incrementModificationCounter()
        self.geo_dim_line2.incrementModificationCounter()
                
def createAxisGeometry(sop_cat, t=(0,0,0), r=(0,0,0)):
    verb = sop_cat.nodeVerb("tube")
    verb.setParms({
        "type" : 1,
        "rad": (AXIS_RAD, AXIS_RAD),
        "t": t,
        "r": r,
        "rows": 2,
        "cols": 30,
        "height":AXIS_LENGTH,
        "cap":True
    })
    geo = hou.Geometry()        
    verb.execute(geo, [])
    return geo

def createArrowGeometry(sop_cat, t=(0,0,0), r=(0,0,0)):
    verb = sop_cat.nodeVerb('tube')
    verb.setParms({
        "type" : 1,
        "rad": (ARROW_TIP, ARROW_BASE),
        "t": t,
        "r": r,
        "radscale": 2,
        "rows": 2,
        "cols": 10,
        "height":ARROW_HEIGHT,
        "cap":True
    })
    geo = hou.Geometry()        
    verb.execute(geo, [])
    return geo
          
def createSphereGeometry(sop_cat, rad=(SPH_RAD,SPH_RAD,SPH_RAD), t=(0,0,0), r=(0,0,0)):
    verb = sop_cat.nodeVerb('sphere')
    verb.setParms({
        "type" : 2,
        "t": t,
        "r": r,
        "rad":rad,
        "rows": 30,
        "cols": 30
    })
    geo = hou.Geometry()        
    verb.execute(geo, [])
    return geo

def createRingGeometry(sop_cat, orient):
    geo = hou.Geometry()

    circle1 = hou.Geometry()
    verb = sop_cat.nodeVerb("circle")
    verb.setParms({
        "type" : 1, 
        "orient":orient, 
        "divs":120, 
        "arc":0, 
        "rad":(RING_SIZE,RING_SIZE)})
    verb.execute(circle1, [])

    circle2 = hou.Geometry()
    verb2 = sop_cat.nodeVerb("circle")
    verb2.setParms({
        "type" : 1, 
        "orient": 0, 
        "divs": 30, 
        "arc":0, 
        "rad":(RING_SIZE*0.01,RING_SIZE*0.01)})
    verb2.execute(circle2, [])

    verb3 = sop_cat.nodeVerb("sweep::2.0")

    verb3.execute(geo, [circle1, circle2])
    

    return geo

def createBoxGeometry(sop_cat, t=(0,0,0), size=(PIVOT_SIZE,PIVOT_SIZE,PIVOT_SIZE)):        
    verb = sop_cat.nodeVerb("box")
    verb.setParms({
        "type" : 1, 
        "divrate":(2,2,2), 
        "size":size,
        "t": t })
    geo = hou.Geometry()        
    verb.execute(geo, [])
    return geo

def createTileGeometry(sop_cat, t=(0,0,0), r=(0,0,0), size=(TILE_SIZE, TILE_SIZE)):
    verb = sop_cat.nodeVerb("grid")
    verb.setParms({
        "type": 1, 
        "rows": 2, 
        "cols": 2, 
        "t": t,
        "r": r,
        "size": size
    })
    geo = hou.Geometry()
    verb.execute(geo, [])
    return geo

def createRingHighlightGeometry(sop_cat, rad, arc_plane, begin_angle, end_angle):        
    """ Creates the ring highligth guide for the rotation.
    """
    verb = sop_cat.nodeVerb("circle")        
    verb.setParms({
        "type":1, 
        "orient":arc_plane, 
        "divs":30, 
        "arc":1, 
        "rad":(rad,rad),
        "angle":(begin_angle,end_angle)})
    geo = hou.Geometry()
    verb.execute(geo, [])
    return geo