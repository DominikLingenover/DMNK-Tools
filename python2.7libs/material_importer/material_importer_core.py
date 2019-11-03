import hou
import os
import struct
import re
import sys
import icons

from name_list import *

from PySide2.QtCore import *
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtUiTools import *

# Stylesheets
CLGRP_STYLE = """
QGroupBox::indicator {
    width: 12px;
    height: 12px;
}
QGroupBox::indicator:unchecked {
    image: url(:icons/collapsed.svg);
}
QGroupBox::indicator:checked {
    image: url(:icons/opened.svg);
}
"""

# Relevant paths 
scriptpath = os.path.dirname(__file__)
dmnk_path = hou.getenv("DMNK")
configpath = dmnk_path + "/config/material_importer_config"

# Initiliaze variables
engine = None
input_slots = None
get_network = None
mat_builder_node = None

# Name list
texType_names = {
    'diffuse': ["diffuse", "diff", "albedo", "color", "col", "alb", "dif", "basecolor"],
    'ao': ["ao", "ambientocclusion", "ambient_occlusion", "cavity"],
    'spec': ["specular", "spec", "s", "refl", "reflectivity"],
    'rough': ["roughness", "rough", "r"],
    'gloss': ["gloss", "g", "glossiness"],
    'metal': ["metal", "metalness", "m", "metallic"],
    'opc': ["transparency", "t", "opacity", "o"],
    'emissive': ["emission", "emissive"],
    'normal': ["normal", "nrm", "nrml", "n", "norm_ogl", "normalbump"],
    'bump': ["bump", "bmp", "height", "h"],
    'displ': ["displacement", "displace", "disp"]
}

class TextureImporter(QWidget):
    def __init__(self):
        super(TextureImporter, self).__init__(hou.qt.mainWindow())
        
        # Create UI
        self.createUi()

    def createUi(self):
        self.settings = QSettings(configpath, QSettings.IniFormat)

        self.setWindowTitle('DMNK - Material Importer')
        self.setWindowFlags(Qt.Dialog)
        self.resize(self.settings.value("size", QSize(hou.ui.scaledSize(800), hou.ui.scaledSize(500))))
        self.move(self.settings.value("pos", QPoint(0, 0)))

        loader = QUiLoader()
        self.ui = loader.load(scriptpath + '/material_importer_ui_2.ui')

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.ui)
        mainLayout.setContentsMargins(0,0,0,0)
        self.setLayout(mainLayout)

        self.ui.env.setDisabled(True)
        self.ui.use_env.toggled.connect(self.toggleEnvVar)

        self.ui.settings.setStyleSheet(CLGRP_STYLE)

        self.updateEngine()

        # Config
        self.ui.pref_exr.setChecked(str(self.settings.value("pref_exr", False)).lower() == 'true')
        self.ui.pref_metal.setChecked(str(self.settings.value("pref_metal", False)).lower() == 'true')
        self.ui.cc_on_diff.setChecked(str(self.settings.value("diff_on_cc", False)).lower() == 'true')
        self.ui.auto_triplanar.setChecked(str(self.settings.value("auto_triplanar", False)).lower() == 'true')
        self.ui.enable_udim.setChecked(str(self.settings.value("enable_udim", False)).lower() == 'true')
        self.ui.opc_as_stencil.setChecked(str(self.settings.value("opc_as_stencil", False)).lower() == 'true')
        self.ui.height_is_displ.setChecked(str(self.settings.value("height_is_displ", False)).lower() == 'true')
        self.ui.man_tex_sel.setChecked(str(self.settings.value("man_tex_sel", False)).lower() == 'true')
        self.ui.apply_to_sel_obj.setChecked(str(self.settings.value("apply_to_sel_obj", False)).lower() == 'true')
        self.ui.use_env.setChecked(str(self.settings.value("use_env", False)).lower() == 'true')
        self.ui.diff_is_linear.setChecked(str(self.settings.value("diff_is_linear", False)).lower() == 'true')
        self.ui.env.setText(self.settings.value("env", ""))
        self.ui.renderer_dropdown.setCurrentText(self.settings.value("renderer_dropdown", ""))

        self.ui.pref_exr.toggled.connect(self.updateConfig)
        self.ui.pref_metal.toggled.connect(self.updateConfig)
        self.ui.cc_on_diff.toggled.connect(self.updateConfig)
        self.ui.auto_triplanar.toggled.connect(self.updateConfig)
        self.ui.enable_udim.toggled.connect(self.updateConfig)
        self.ui.opc_as_stencil.toggled.connect(self.updateConfig)
        self.ui.height_is_displ.toggled.connect(self.updateConfig)
        self.ui.man_tex_sel.toggled.connect(self.updateConfig)
        self.ui.apply_to_sel_obj.toggled.connect(self.updateConfig)
        self.ui.use_env.toggled.connect(self.updateConfig)
        self.ui.diff_is_linear.toggled.connect(self.updateConfig)
        self.ui.env.editingFinished.connect(self.updateConfig)
        self.ui.renderer_dropdown.currentIndexChanged.connect(self.updateConfig)
        self.ui.renderer_dropdown.currentIndexChanged.connect(self.updateEngine)

        self.ui.settings.toggled.connect(self.open_settings)
        self.ui.material_jump.clicked.connect(self.jump_to_mat)

        # Tooltips
        self.ui.pref_exr.setToolTip("If EXR textures are found they are used over any other file type. \
                                     \nAutomatically falls back to other file types if no EXR texture was found.")

        self.ui.pref_metal.setToolTip("Automatically falls back to Specular textures if no Metalness texture can be found.")

        self.ui.enable_udim.setToolTip("Enables the UDIM workflow.\
                                        \nThis option is necessary when working with UDIM textures.")

        self.ui.height_is_displ.setToolTip("Height textures are used as Displacement instead of Bump.")

        self.ui.opc_as_stencil.setToolTip("Opacity textures are used in a RS Stencil node.\
                                           \nThis is a Redshift only option.")

        self.ui.diff_is_linear.setToolTip("Enable this to linearize Diffuse textures.\
                                           \nOnly relevant for Redshift and Octane.")

        self.ui.cc_on_diff.setToolTip("Creates a Color Correction for the Diffuse texture.")

        self.ui.auto_triplanar.setToolTip("Automatically creates a network with a Tri-Planar setup.")

        self.ui.man_tex_sel.setToolTip("This option allows you to manually select the textures you want to import.")

        self.ui.apply_to_sel_obj.setToolTip("Applies the shader to all selected objects after it was created.")

        self.ui.use_env.setToolTip("When enabled you can specify an environment variable like $HIP to create relative paths.\
                                    \nYour textures have to be in the directory that the variable points to.")

        self.ui.import_mat.setToolTip("Starts the import process.")

        # Main function
        self.ui.import_mat.clicked.connect(self.loadImages)

    def hideEvent(self, event):
        """
        When window is closed store position and size in config.
        """

        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
    
    def helpEvent(self, event, view, option, index):
        print "Test"
        print event

    def updateEngine(self):
        global engine
        global input_slots
        engine = self.ui.renderer_dropdown.currentText()

        if engine == 'Arnold':
            input_slots = {
                'diffuse': 1,
                'ao': 0,
                'spec': 5,
                'rough': 6,
                'gloss': 6,
                'metal': 3,
                'opc': 38,
                'emissive': 37,
                'normal': 39,
                'bump': 39
            }
        
        elif engine == 'Octane':
            self.ui.use_vertex_displ.setDisabled(False)
            input_slots = {
                'diffuse': 2,
                'spec': 4,
                'rough': 6,
                'gloss': 6,
                'metal': 3,
                'opc': 0,
                'emissive': 36,
                'normal': 32,
                'bump': 31,
                'displ': 33
            }

        elif engine == 'Redshift':
            self.ui.opc_as_stencil.setDisabled(False)

            input_slots = {
                'diffuse': 0,
                'ao': 1,
                'spec': 5,
                'rough': 7,
                'gloss': 7,
                'metal': 14,
                'opc': 47,
                'emissive': 48,
                'normal': 49,
                'bump': 49
            }
        
        elif engine == 'Renderman':
            input_slots = {
                'diffuse': 0,
                'spec': 5,
                'rough': 7,
                'gloss': 7,
                'metal': 4,
                'opc': 14,
                'emissive': 1,
                'normal': 13,
                'bump': 13
            }

        elif engine == 'VRay':
            input_slots = {
                'diffuse': 0,
                'spec': 5,
                'rough': 6,
                'gloss': 6,
                'metal': 9,
                'opc': 2,
                'emissive': 3,
            }
        
        if engine != 'Redshift':
            self.ui.opc_as_stencil.setDisabled(True)

        if engine != 'Octane':
            self.ui.use_vertex_displ.setDisabled(True)

    def updateConfig(self):
        pref_exr = self.ui.pref_exr.isChecked()
        pref_metal = self.ui.pref_metal.isChecked()
        cc_on_diff = self.ui.cc_on_diff.isChecked()
        auto_triplanar = self.ui.auto_triplanar.isChecked()
        enable_udim = self.ui.enable_udim.isChecked()
        opc_as_stencil = self.ui.opc_as_stencil.isChecked()
        height_is_displ = self.ui.height_is_displ.isChecked()
        man_tex_sel = self.ui.man_tex_sel.isChecked()
        apply_to_sel_obj = self.ui.apply_to_sel_obj.isChecked()
        use_env = self.ui.use_env.isChecked()
        diff_is_linear = self.ui.diff_is_linear.isChecked()
        env = self.ui.env.text()
        renderer_dropdown = self.ui.renderer_dropdown.currentText()

        self.settings.setValue("pref_exr", pref_exr)
        self.settings.setValue("pref_metal", pref_metal)
        self.settings.setValue("cc_on_diff", cc_on_diff)
        self.settings.setValue("auto_triplanar", auto_triplanar)
        self.settings.setValue("enable_udim", enable_udim)
        self.settings.setValue("opc_as_stencil", opc_as_stencil)
        self.settings.setValue("height_is_displ", height_is_displ)
        self.settings.setValue("man_tex_sel", man_tex_sel)
        self.settings.setValue("apply_to_sel_obj", apply_to_sel_obj)
        self.settings.setValue("use_env", use_env)
        self.settings.setValue("diff_is_linear", diff_is_linear)
        self.settings.setValue("env", env)
        self.settings.setValue("renderer_dropdown", renderer_dropdown)

    def createOGL(self, material_builder, material):
        """This function creates all OGL tags needed on the RS Material Builder and
        links them to the appropriate parameters inside the builder"""

        # Get paths to RS Material Builder and RS Uber Material
        material_path = material_builder.relativePathTo(material)
        material_builder_path = material_builder.name()
        material_builder_children = material_builder.children()

        # Initialize paths
        diffuse_path = ""
        ao_path = ""
        normal_path = ""
        bump_path = ""
        displ_path = ""
        rough_path = ""
        gloss_path = ""
        metal_path = ""
        spec_path = ""
        opc_path = ""
        emission_path = ""

        for i in range(len(material_builder_children)):
            if str(material_builder_children[i]) == 'diffuse':
                diffuse_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) == 'ao':
                ao_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) == 'normal':
                normal_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) == 'bump':
                bump_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) == 'displ':
                displ_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) == 'rough':
                rough_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) == 'gloss':
                gloss_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) == 'metal':
                metal_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) == 'spec':
                spec_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) == 'opc':
                opc_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) == 'emission':
                emission_path = material_builder.relativePathTo(material_builder_children[i])

        # Initiliaze the template group for the spare parameters on RS Material Builder
        ogl_template_group = hou.ParmTemplateGroup()

        if engine == 'Redshift':
            # 'Settings' folder with 'Material ID'
            ogl_template_folder1 = hou.FolderParmTemplate("Redshift_SHOP_parmSwitcher3", "Settings", folder_type = hou.folderType.Tabs)
            ogl_template_item1 = hou.IntParmTemplate("RS_matprop_ID", "Material ID", 1)
            ogl_template_folder1.addParmTemplate(ogl_template_item1)
            ogl_template_group.append(ogl_template_folder1)

            # 'OpenGL' folder with OGL tags
            ogl_template_folder1 = hou.FolderParmTemplate("Redshift_SHOP_parmSwitcher3_1", "OpenGL", folder_type = hou.folderType.Tabs)

            ogl_template_folder2 = hou.FolderParmTemplate("f_Global", "Global", folder_type = hou.folderType.Tabs)

            ogl_template_item1 = hou.ToggleParmTemplate("ogl_light", "Use Lighting")
            ogl_template_folder2.addParmTemplate(ogl_template_item1)

            ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_geo_color", "Enable Geometry Color")
            ogl_template_folder2.addParmTemplate(ogl_template_item1)

            ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_packed_color", "Enable Packed Color")
            ogl_template_folder2.addParmTemplate(ogl_template_item1)

            ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_diffuse_map_alpha", "Use Diffuse Map Alpha")
            ogl_template_folder2.addParmTemplate(ogl_template_item1)

            ogl_template_item1 = hou.ToggleParmTemplate("ogl_enablelight", "Enable Light in Viewport")
            ogl_template_folder2.addParmTemplate(ogl_template_item1)

            ogl_template_folder1.addParmTemplate(ogl_template_folder2)

        else:
            ogl_template_folder1 = hou.FolderParmTemplate("f_OpenGL", "OpenGL", folder_type = hou.folderType.Tabs)

        #------------------------

        ogl_template_folder2 = hou.FolderParmTemplate("f_Diffuse", "Diffuse", folder_type = hou.folderType.Tabs)

        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_diff", "Enable Diffuse", default_value = True)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_diff", "Diffuse", 3, naming_scheme = hou.parmNamingScheme.RGBA)
        ogl_template_item1.setConditional(hou.parmCondType.HideWhen, "{ ogl_use_diff == 0 }")
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_diff_intensity", "Diffuse Intensity", 1, min = 0.0, max = 1.0, default_value = ([1]))
        ogl_template_item1.setConditional(hou.parmCondType.HideWhen, "{ ogl_use_diff == 0 }")
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_diff_rough", "Diffuse Roughness", 1, min = 0.0, max = 1.0)
        ogl_template_item1.setConditional(hou.parmCondType.HideWhen, "{ ogl_use_diff == 0 }")
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_folder3 = hou.FolderParmTemplate("ogl_numtex", "Diffuse Texture Layers", folder_type=hou.folderType.MultiparmBlock, default_value=1)
        ogl_template_folder3.setConditional(hou.parmCondType.HideWhen, "{ ogl_use_diff == 0 }")
        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_tex#", "Use Diffuse Map #", default_value=True)
        ogl_template_folder3.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_tex#", "Diffuse Map #", 1, file_type = hou.fileType.Image, string_type = hou.stringParmType.FileReference)
        ogl_template_folder3.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_texuvset#", "UV Set", 1, default_value = (["uv"]), string_type = hou.stringParmType.Regular, menu_items=(["uv","uv2","uv3","uv4","uv5","uv6","uv7","uv8"]), menu_labels=(["uv","uv2","uv3","uv4","uv5","uv6","uv7","uv8"]), menu_type=hou.menuType.StringReplace)
        ogl_template_folder3.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_tex_min_filter#", "Minification Filter", 1, default_value=(["GL_LINEAR_MIPMAP_LINEAR"]), string_type=hou.stringParmType.Regular, menu_items=(["GL_NEAREST","GL_LINEAR","GL_NEAREST_MIPMAP_NEAREST","GL_LINEAR_MIPMAP_NEAREST","GL_NEAREST_MIPMAP_LINEAR","GL_LINEAR_MIPMAP_LINEAR"]), menu_labels=(["No filtering (very poor)","Bilinear (poor)","No filtering, Nearest Mipmap (poor)","Bilinear, Nearest Mipmap (okay)","No filtering, Blend Mipmaps (good)","Trilinear (best)"]), menu_type=hou.menuType.Normal)
        ogl_template_item1.hide(1)
        ogl_template_folder3.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_tex_mag_filter#", "Magnification Filter", 1, default_value=(["GL_NEAREST"]), string_type=hou.stringParmType.Regular, menu_items=(["GL_NEAREST","GL_LINEAR"]), menu_labels=(["No filtering","Bilinear"]), menu_type=hou.menuType.Normal)
        ogl_template_item1.hide(1)
        ogl_template_folder3.addParmTemplate(ogl_template_item1)
        ogl_template_folder2.addParmTemplate(ogl_template_folder3)
        ogl_template_folder1.addParmTemplate(ogl_template_folder2)

        # #------------------------

        ogl_template_folder2 = hou.FolderParmTemplate("f_specular", "Specular", folder_type = hou.folderType.Tabs)

        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_spec", "Enable Specular", default_value=True)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_spec", "Specular", 3, naming_scheme = hou.parmNamingScheme.RGBA)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_spec_intensity", "Specular Intensity", 1, default_value = ([1]), min = 0.0, max = 1.0)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_rough", "Roughness", 1, min = 0.0, max = 1.0)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_spec_model", "Specular Model", 1, default_value=(["ggx"]), string_type=hou.stringParmType.Regular, menu_items=(["phong","blinn","ggx"]), menu_labels=(["Phong","Blinn","GGX"]), menu_type=hou.menuType.Normal)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_ior", "Index of Refraction", 1, default_value = ([1.5]), min = 0.0, max = 3.0)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_metallic", "Metallic", 1, default_value = ([0]), min = 0.0, max = 1.0)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_specmap", "Use Specular Map", default_value = False)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_specmap", "Specular Map", 1, file_type = hou.fileType.Image, string_type = hou.stringParmType.FileReference)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_metallicmap", "Use Metallic Map", default_value = True)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_metallicmap", "Metallic Map", 1, file_type = hou.fileType.Image, string_type = hou.stringParmType.FileReference)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_roughmap", "Use Roughness Map", default_value = True)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_roughmap", "Roughness Map", 1, file_type = hou.fileType.Image, string_type = hou.stringParmType.FileReference)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.ToggleParmTemplate("ogl_invertroughmap", "Invert Roughness Map", default_value = False)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)
        ogl_template_folder1.addParmTemplate(ogl_template_folder2)

        #------------------------

        ogl_template_folder2 = hou.FolderParmTemplate("f_normal", "Normal Map", folder_type = hou.folderType.Tabs)
        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_normalmap", "Enable Normal Map", default_value=True)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_normalmap", "Normal Map", 1, file_type = hou.fileType.Image, string_type = hou.stringParmType.FileReference)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_normalmap_type", "Normal Map Type", 1, default_value=(["uvtangent"]), string_type=hou.stringParmType.Regular, menu_items=(["uvtangent","world","object"]), menu_labels=(["Tangent Space","World Space","Object Space"]), menu_type=hou.menuType.Normal)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_normalmap_scale", "Normal Scale", 1, default_value = ([1]), min = -2.0, max = 2.0)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.ToggleParmTemplate("ogl_normalflipx", "Flip Normal Map X", default_value = False)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.ToggleParmTemplate("ogl_normalflipy", "Flip Normal Map Y", default_value = True)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)
        ogl_template_folder1.addParmTemplate(ogl_template_folder2)

        #------------------------

        ogl_template_folder2 = hou.FolderParmTemplate("f_bump", "Bump Map", folder_type = hou.folderType.Tabs)
        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_bumpmap", "Enable Bump Map", default_value=False)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_bumpmap", "Bump Map", 1, file_type = hou.fileType.Image, string_type = hou.stringParmType.FileReference)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_bumpscale", "Bump Scale", 1, default_value = ([1]), min = -2.0, max = 2.0)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)
        ogl_template_folder1.addParmTemplate(ogl_template_folder2)

        #------------------------

        ogl_template_folder2 = hou.FolderParmTemplate("f_opacity", "Opacity Map", folder_type = hou.folderType.Tabs)
        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_alpha_transparency", "Enable Alpha and Transparency", default_value=False)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_alpha", "Alpha", 1)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_transparency", "Transparency", 1)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_opacitymap", "Enable Opacity Map", default_value=False)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_opacitymap", "Opacity Map", 1, file_type = hou.fileType.Image, string_type = hou.stringParmType.FileReference)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)
        ogl_template_folder1.addParmTemplate(ogl_template_folder2)

        #------------------------

        ogl_template_folder2 = hou.FolderParmTemplate("f_emission", "Emission", folder_type = hou.folderType.Tabs)
        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_emit", "Enable Emission", default_value=False)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_emit", "Emission", 3, naming_scheme = hou.parmNamingScheme.RGBA)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_emissionmap", "Enable Emission Map", default_value=False)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_emissionmap", "Emission Map", 1, file_type = hou.fileType.Image, string_type = hou.stringParmType.FileReference)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)
        ogl_template_folder1.addParmTemplate(ogl_template_folder2)

        #------------------------

        ogl_template_folder2 = hou.FolderParmTemplate("f_coat", "Coat", folder_type = hou.folderType.Tabs)
        ogl_template_item1 = hou.FloatParmTemplate("ogl_coat_intensity", "Coat Intensity", 1,  default_value=([0]))
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_coat_rough", "Coat Roughness", 1,  default_value=([0]))
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_coat_model", "Coat Specular Model", 1, default_value=(["ggx"]), string_type=hou.stringParmType.Regular, menu_items=(["phong","blinn","ggx"]), menu_labels=(["Phong","Blinn","GGX"]), menu_type=hou.menuType.Normal)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_coat_intensity_map", "Use Coat Intensity Map", default_value=False)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_coat_intensity_map", "Coat Intensity Map", 1, file_type = hou.fileType.Image, string_type = hou.stringParmType.FileReference)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_coat_intensity_comp", "Coat Intensity Channel", 1, default_value=(["0"]), string_type=hou.stringParmType.Regular, menu_items=(["0","1","2","3","4"]), menu_labels=(["Luminance","Red","Green","Blue","Alpha"]), menu_type=hou.menuType.Normal)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_coat_roughness_map", "Use Coat Roughness Map", default_value=False)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_coat_roughness_map", "Coat Roughness Map", 1, file_type = hou.fileType.Image, string_type = hou.stringParmType.FileReference)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_coat_roughness_comp", "Coat Roughness Channel", 1, default_value=(["0"]), string_type=hou.stringParmType.Regular, menu_items=(["0","1","2","3","4"]), menu_labels=(["Luminance","Red","Green","Blue","Alpha"]), menu_type=hou.menuType.Normal)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)
        ogl_template_folder1.addParmTemplate(ogl_template_folder2)

        #------------------------

        ogl_template_folder2 = hou.FolderParmTemplate("f_Displ", "Displacement", folder_type = hou.folderType.Tabs)
        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_displacemap", "Use Displacement Map", default_value=False)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_displacemap", "Displacement Map", 1, file_type = hou.fileType.Image, string_type = hou.stringParmType.FileReference)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_displacescale", "Displace Scale", 1,  default_value=([0]))
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.FloatParmTemplate("ogl_displaceoffset", "Displace Offset", 1,  default_value=([0]), min = -2.0, max = 2.0)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)
        ogl_template_folder1.addParmTemplate(ogl_template_folder2)

        ogl_template_group.append(ogl_template_folder1)
        material_builder.setParmTemplateGroup(ogl_template_group, rename_conflicting_parms=True)

        if engine == 'Redshift':
            material_builder.parm("RS_matprop_ID").setExpression("ch('redshift_material1/RS_matprop_ID')", hou.exprLanguage.Hscript)

            material_builder.parm("ogl_diffr").setExpression("ch('"+material_path+"/diffuse_colorr')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffg").setExpression("ch('"+material_path+"/diffuse_colorg')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffb").setExpression("ch('"+material_path+"/diffuse_colorb')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diff_intensity").setExpression("ch('"+material_path+"/diffuse_weight')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diff_rough").setExpression("ch('"+material_path+"/diffuse_roughness')", hou.exprLanguage.Hscript)

            if len(diffuse_path) > 0:
                material_builder.parm("ogl_tex1").set("`chs('"+diffuse_path+"/tex0')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_texuvset1").set("`chs('"+diffuse_path+"/tspace_id`')", hou.exprLanguage.Hscript)

            material_builder.parm("ogl_specr").setExpression("ch('"+material_path+"/refl_colorr')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_specg").setExpression("ch('"+material_path+"/refl_colorg')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_specb").setExpression("ch('"+material_path+"/refl_colorb')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_spec_intensity").setExpression("ch('"+material_path+"/refl_weight')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_rough").setExpression("ch('"+material_path+"/refl_roughness')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_ior").setExpression("ch('"+material_path+"/refl_ior')", hou.exprLanguage.Hscript)

            if len(normal_path) > 0:
                material_builder.parm("ogl_normalmap").set("`chs('"+normal_path+"/tex0`')", hou.exprLanguage.Hscript)

            if len(metal_path) > 0:
                material_builder.parm("ogl_metallicmap").set("`chs('"+metal_path+"/tex0`')", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_metallic").setExpression("ch('"+material_path+"/refl_metalness')", hou.exprLanguage.Hscript)
            elif len(spec_path) > 0:
                material_builder.parm("ogl_use_metallicmap").set(0)
                material_builder.parm("ogl_use_specmap").set(1)
                material_builder.parm("ogl_specmap").set("`chs('"+spec_path+"/tex0`')", hou.exprLanguage.Hscript)

            if len(rough_path) > 0:
                material_builder.parm("ogl_roughmap").set("`chs('"+rough_path+"/tex0`')", hou.exprLanguage.Hscript)
            elif len(gloss_path) > 0:
                material_builder.parm("ogl_invertroughmap").set(1)
                material_builder.parm("ogl_roughmap").set("`chs('"+gloss_path+"/tex0`')", hou.exprLanguage.Hscript)

            if len(bump_path) > 0:
                material_builder.parm("ogl_use_bumpmap").set(1)
                material_builder.parm("ogl_use_normalmap").set(0)
                material_builder.parm("ogl_bumpmap").set("`chs('"+bump_path+"/tex0`')", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_bumpscale").setExpression("ch(BumpMap1/scale)")
            elif len(normal_path) > 0:
                material_builder.parm("ogl_normalmap").set("`chs('"+normal_path+"/tex0`')", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_normalmap_scale").setExpression("ch(BumpMap1/scale)")
                material_builder.parm("ogl_normalflipy").setExpression("ch(BumpMap1/flipY)")

            if len(opc_path) > 0:
                material_builder.parm("ogl_use_alpha_transparency").set(1)
                material_builder.parm("ogl_use_opacitymap").set(1)
                material_builder.parm("ogl_opacitymap").set("`chs('"+opc_path+"/tex0`')", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_transparency").set(0)

            if len(emission_path) > 0:
                material_builder.parm("ogl_use_emit").set(1)
                material_builder.parm("ogl_use_emissionmap").set(1)
                material_builder.parm("ogl_emissionmap").set("`chs('"+emission_path+"/tex0`')", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_emitr").set(1)
                material_builder.parm("ogl_emitg").set(1)
                material_builder.parm("ogl_emitb").set(1)

            material_builder.parm("ogl_coat_intensity").setExpression("chs('"+material_path+"/coat_weight')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_coat_rough").setExpression("chs('"+material_path+"/coat_roughness')", hou.exprLanguage.Hscript)

            if len(displ_path) > 0:
                material_builder.parm("ogl_use_displacemap").set(1)
                material_builder.parm("ogl_displacemap").set("`chs('"+displ_path+"/tex0`')", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_displacescale").setExpression("ch('Displacement1/scale')", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_displaceoffset").setExpression("ch('Displacement1/oldrange_min')", hou.exprLanguage.Hscript)

        elif engine == 'VRay':
            material_builder.parm("ogl_diffr").setExpression("ch('"+material_path+"/diffuser')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffg").setExpression("ch('"+material_path+"/diffuseg')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffb").setExpression("ch('"+material_path+"/diffuseb')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diff_rough").setExpression("ch('"+material_path+"/roughness')", hou.exprLanguage.Hscript)

            if len(diffuse_path) > 0:
                material_builder.parm("ogl_tex1").set("`chs('"+diffuse_path+"/BitmapBuffer_file')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_texuvset1").set("`chs('"+diffuse_path+"/UVWGenMayaPlace2dTexture_uv_set_name')`", hou.exprLanguage.Hscript)

            material_builder.parm("ogl_specr").setExpression("ch('"+material_path+"/reflectr')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_specg").setExpression("ch('"+material_path+"/reflectg')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_specb").setExpression("ch('"+material_path+"/reflectb')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_rough").setExpression("ch('"+material_path+"/reflect_glossiness')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_ior").setExpression("ch('"+material_path+"/refract_ior')", hou.exprLanguage.Hscript)

            if len(normal_path) > 0:
                material_builder.parm("ogl_normalmap").set("`chs('"+normal_path+"/BitmapBuffer_file')`", hou.exprLanguage.Hscript)

            if len(metal_path) > 0:
                material_builder.parm("ogl_metallicmap").set("`chs('"+metal_path+"/BitmapBuffer_file')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_metallic").setExpression("ch('"+material_path+"/metalness')", hou.exprLanguage.Hscript)
            elif len(spec_path) > 0:
                material_builder.parm("ogl_use_metallicmap").set(0)
                material_builder.parm("ogl_use_specmap").set(1)
                material_builder.parm("ogl_specmap").set("`chs('"+spec_path+"/BitmapBuffer_file')`", hou.exprLanguage.Hscript)

            if len(rough_path) > 0:
                material_builder.parm("ogl_roughmap").set("`chs('"+rough_path+"/BitmapBuffer_file')`", hou.exprLanguage.Hscript)
            elif len(gloss_path) > 0:
                material_builder.parm("ogl_invertroughmap").set(1)
                material_builder.parm("ogl_roughmap").set("`chs('"+gloss_path+"/BitmapBuffer_file')`", hou.exprLanguage.Hscript)

            if len(bump_path) > 0:
                material_builder.parm("ogl_use_bumpmap").set(1)
                material_builder.parm("ogl_use_normalmap").set(0)
                material_builder.parm("ogl_bumpmap").set("`chs('"+bump_path+"/BitmapBuffer_file')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_bumpscale").setExpression("ch(VRayNodeBRDFBump1/scale)")
            elif len(normal_path) > 0:
                material_builder.parm("ogl_normalmap").set("`chs('"+normal_path+"/BitmapBuffer_file')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_normalmap_scale").setExpression("ch(VRayNodeBRDFBump1/bump_tex_mult)")
                # material_builder.parm("ogl_normalflipy").setExpression("ch(BumpMap1/flipY)")

            if len(opc_path) > 0:
                material_builder.parm("ogl_use_alpha_transparency").set(1)
                material_builder.parm("ogl_use_opacitymap").set(1)
                material_builder.parm("ogl_opacitymap").set("`chs('"+opc_path+"/BitmapBuffer_file')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_transparency").set(0)

            if len(emission_path) > 0:
                material_builder.parm("ogl_use_emit").set(1)
                material_builder.parm("ogl_use_emissionmap").set(1)
                material_builder.parm("ogl_emissionmap").set("`chs('"+emission_path+"/BitmapBuffer_file')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_emitr").set(1)
                material_builder.parm("ogl_emitg").set(1)
                material_builder.parm("ogl_emitb").set(1)

            # material_builder.parm("ogl_coat_intensity").setExpression("chs('"+material_path+"/coat_weight')", hou.exprLanguage.Hscript)
            # material_builder.parm("ogl_coat_rough").setExpression("chs('"+material_path+"/coat_roughness')", hou.exprLanguage.Hscript)

            if len(displ_path) > 0:
                material_builder.parm("ogl_use_displacemap").set(1)
                material_builder.parm("ogl_displacemap").set("`chs('"+displ_path+"/BitmapBuffer_file')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_displacescale").setExpression("ch(VRayNodeGeomDisplacedMesh1/displacement_amount)", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_displaceoffset").setExpression("ch(VRayNodeGeomDisplacedMesh1/displacement_shift)", hou.exprLanguage.Hscript)

        elif engine == 'Octane':
            material_builder.parm("ogl_diffr").setExpression("ch('"+material_path+"/albedor')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffg").setExpression("ch('"+material_path+"/albedog')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffb").setExpression("ch('"+material_path+"/albedob')", hou.exprLanguage.Hscript)
            # material_builder.parm("ogl_diff_intensity").setExpression("ch('"+material_path+"/diffuse_weight')", hou.exprLanguage.Hscript)
            # material_builder.parm("ogl_diff_rough").setExpression("ch('"+material_path+"/diffuse_roughness')", hou.exprLanguage.Hscript)

            if len(diffuse_path) > 0:
                material_builder.parm("ogl_tex1").set("`chs('"+diffuse_path+"/A_FILENAME`')", hou.exprLanguage.Hscript)
                # material_builder.parm("ogl_texuvset1").setExpression("chs('"+diffuse_path+"/tspace_id')", hou.exprLanguage.Hscript)

            # material_builder.parm("ogl_specr").setExpression("ch('"+material_path+"/refl_colorr')", hou.exprLanguage.Hscript)
            # material_builder.parm("ogl_specg").setExpression("ch('"+material_path+"/refl_colorg')", hou.exprLanguage.Hscript)
            # material_builder.parm("ogl_specb").setExpression("ch('"+material_path+"/refl_colorb')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_spec_intensity").setExpression("ch('"+material_path+"/specular')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_rough").setExpression("ch('"+material_path+"/roughness')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_ior").setExpression("ch('"+material_path+"/index4')", hou.exprLanguage.Hscript)

            if len(normal_path) > 0:
                material_builder.parm("ogl_normalmap").set("`chs('"+normal_path+"/A_FILENAME`')", hou.exprLanguage.Hscript)

            if len(metal_path) > 0:
                material_builder.parm("ogl_metallicmap").set("`chs('"+metal_path+"/A_FILENAME`')", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_metallic").setExpression("ch('"+material_path+"/metallic')", hou.exprLanguage.Hscript)
            elif len(spec_path) > 0:
                material_builder.parm("ogl_use_metallicmap").set(0)
                material_builder.parm("ogl_use_specmap").set(1)
                material_builder.parm("ogl_specmap").set("`chs('"+spec_path+"/A_FILENAME`')", hou.exprLanguage.Hscript)

            if len(rough_path) > 0:
                material_builder.parm("ogl_roughmap").set("`chs('"+rough_path+"/A_FILENAME`')", hou.exprLanguage.Hscript)
            elif len(gloss_path) > 0:
                material_builder.parm("ogl_invertroughmap").set(1)
                material_builder.parm("ogl_roughmap").set("`chs('"+gloss_path+"/A_FILENAME`')", hou.exprLanguage.Hscript)

            if len(bump_path) > 0:
                material_builder.parm("ogl_use_bumpmap").set(1)
                material_builder.parm("ogl_use_normalmap").set(0)
                material_builder.parm("ogl_bumpmap").set("`chs('"+bump_path+"/A_FILENAME`')", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_bumpscale").setExpression("chs('"+bump_path+"/power')")
            elif len(normal_path) > 0:
                material_builder.parm("ogl_normalmap").set("`chs('"+normal_path+"/A_FILENAME`')", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_normalmap_scale").setExpression("chs('"+normal_path+"/power')")
                # material_builder.parm("ogl_normalflipy").setExpression("ch(BumpMap1/flipY)")

            if len(opc_path) > 0:
                material_builder.parm("ogl_use_alpha_transparency").set(1)
                material_builder.parm("ogl_use_opacitymap").set(1)
                material_builder.parm("ogl_opacitymap").set("`chs('"+opc_path+"/A_FILENAME`')", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_transparency").set(0)

            if len(emission_path) > 0:
                material_builder.parm("ogl_use_emit").set(1)
                material_builder.parm("ogl_use_emissionmap").set(1)
                material_builder.parm("ogl_emissionmap").set("`chs('"+emission_path+"/A_FILENAME`')", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_emitr").set(1)
                material_builder.parm("ogl_emitg").set(1)
                material_builder.parm("ogl_emitb").set(1)

            # material_builder.parm("ogl_coat_intensity").setExpression("chs('"+material_path+"/coat_weight')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_coat_rough").setExpression("ch('"+material_path+"/coatingRoughness')", hou.exprLanguage.Hscript)

            if len(displ_path) > 0:
                material_builder.parm("ogl_use_displacemap").set(1)
                material_builder.parm("ogl_displacemap").set("`chs('"+displ_path+"/A_FILENAME`')", hou.exprLanguage.Hscript)
                if self.ui.use_vertex_displ.isChecked() == True:
                    material_builder.parm("ogl_displacescale").setExpression("ch(NT_VERTEX_DISPLACEMENT1/amount)", hou.exprLanguage.Hscript)
                    material_builder.parm("ogl_displaceoffset").setExpression("ch(NT_VERTEX_DISPLACEMENT1/black_level)", hou.exprLanguage.Hscript)
                else:
                    material_builder.parm("ogl_displacescale").setExpression("ch(NT_DISPLACEMENT1/amount)", hou.exprLanguage.Hscript)
                    material_builder.parm("ogl_displaceoffset").setExpression("ch(NT_DISPLACEMENT1/black_level)", hou.exprLanguage.Hscript)

        elif engine == 'Renderman':
            if self.ui.auto_triplanar.isChecked() == True:
                filepath_parm = "filename0"
            else:
                filepatH_parm = "filename"

            material_builder.parm("ogl_diffr").setExpression("ch('"+material_path+"/baseColorr')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffg").setExpression("ch('"+material_path+"/baseColorg')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffb").setExpression("ch('"+material_path+"/baseColorb')", hou.exprLanguage.Hscript)
            # material_builder.parm("ogl_diff_intensity").setExpression("ch('"+material_path+"/diffuse_weight')", hou.exprLanguage.Hscript)
            # material_builder.parm("ogl_diff_rough").setExpression("ch('"+material_path+"/diffuse_roughness')", hou.exprLanguage.Hscript)

            if len(diffuse_path) > 0:
                material_builder.parm("ogl_tex1").set("`chs('"+diffuse_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                # material_builder.parm("ogl_texuvset1").setExpression("chs('"+diffuse_path+"/tspace_id')", hou.exprLanguage.Hscript)

            # material_builder.parm("ogl_specr").setExpression("ch('"+material_path+"/refl_colorr')", hou.exprLanguage.Hscript)
            # material_builder.parm("ogl_specg").setExpression("ch('"+material_path+"/refl_colorg')", hou.exprLanguage.Hscript)
            # material_builder.parm("ogl_specb").setExpression("ch('"+material_path+"/refl_colorb')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_spec_intensity").setExpression("ch('"+material_path+"/specular')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_rough").setExpression("ch('"+material_path+"/roughness')", hou.exprLanguage.Hscript)
            # material_builder.parm("ogl_ior").setExpression("ch('"+material_path+"/index4')", hou.exprLanguage.Hscript)

            if len(metal_path) > 0:
                material_builder.parm("ogl_metallicmap").set("`chs('"+metal_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_metallic").setExpression("ch('"+material_path+"/metallic')", hou.exprLanguage.Hscript)
            elif len(spec_path) > 0:
                material_builder.parm("ogl_use_metallicmap").set(0)
                material_builder.parm("ogl_use_specmap").set(1)
                material_builder.parm("ogl_specmap").set("`chs('"+spec_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            if len(rough_path) > 0:
                material_builder.parm("ogl_roughmap").set("`chs('"+rough_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
            elif len(gloss_path) > 0:
                material_builder.parm("ogl_invertroughmap").set(1)
                material_builder.parm("ogl_roughmap").set("`chs('"+gloss_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            if len(bump_path) > 0:
                material_builder.parm("ogl_use_bumpmap").set(1)
                material_builder.parm("ogl_use_normalmap").set(0)
                material_builder.parm("ogl_bumpmap").set("`chs('"+bump_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                # material_builder.parm("ogl_bumpscale").setExpression("chs('"+bump_path+"/power')")
            elif len(normal_path) > 0:
                material_builder.parm("ogl_normalmap").set("`chs('"+normal_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                # material_builder.parm("ogl_normalmap_scale").setExpression("chs('"+normal_path+"/power')")
                # material_builder.parm("ogl_normalflipy").setExpression("ch(BumpMap1/flipY)")

            if len(opc_path) > 0:
                material_builder.parm("ogl_use_alpha_transparency").set(1)
                material_builder.parm("ogl_use_opacitymap").set(1)
                material_builder.parm("ogl_opacitymap").set("`chs('"+opc_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_transparency").set(0)

            if len(emission_path) > 0:
                material_builder.parm("ogl_use_emit").set(1)
                material_builder.parm("ogl_use_emissionmap").set(1)
                material_builder.parm("ogl_emissionmap").set("`chs('"+emission_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_emitr").set(1)
                material_builder.parm("ogl_emitg").set(1)
                material_builder.parm("ogl_emitb").set(1)

            material_builder.parm("ogl_coat_intensity").setExpression("chs('"+material_path+"/clearcoat')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_coat_rough").setExpression("1 - ch('"+material_path+"/clearcoatGloss')", hou.exprLanguage.Hscript)

            if len(displ_path) > 0:
                material_builder.parm("ogl_use_displacemap").set(1)
                material_builder.parm("ogl_displacemap").set("`chs('"+displ_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_displacescale").setExpression("ch(pxrdisplace1/dispAmount)", hou.exprLanguage.Hscript)
                # material_builder.parm("ogl_displaceoffset").setExpression("ch(pxrdisplace1/black_level)", hou.exprLanguage.Hscript)

    def createShaders(self, tex_paths, sel_Node):
        global get_network
        global mat_builder_node
        get_network = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.NetworkEditor)

        if engine != None:
            if engine == 'Arnold':
                mat_builder_node = hou.node("/mat").createNode("arnold_materialbuilder")
                mat_node = mat_builder_node.createNode("arnold::standard_surface")
                mat_out_node = hou.node("/mat/%s/OUT_material" % mat_builder_node.name())
                mat_node.parm("specular_roughness").set("1")
                mat_out_node.setInput(0, mat_node)

                if self.ui.auto_triplanar.isChecked() == True:
                    matrix = mat_builder_node.createNode("arnold::matrix_transform")
                    

                for imageType in tex_paths:
                    tex_node = mat_builder_node.createNode("arnold::image", imageType)
                    tex_node.parm("filename").set(tex_paths[imageType])

                    if self.ui.auto_triplanar.isChecked() == True:
                        triplanar_node = mat_builder_node.createNode("arnold::uv_projection")
                        triplanar_node.setInput(0, tex_node)
                        triplanar_node.setInput(5, matrix)

                        if imageType == 'normal':
                            normal_node = mat_builder_node.createNode("arnold::normal_map")
                            normal_node.setInput(0, triplanar_node)
                            mat_node.setInput(input_slots[imageType], normal_node)

                        elif imageType == 'bump':
                            bump_node = mat_builder_node.createNode("arnold::bump2d")
                            bump_node.setInput(0, triplanar_node)
                            mat_node.setInput(input_slots[imageType], bump_node)

                        elif imageType == 'displ':
                            mat_out_node.setInput(1, triplanar_node)

                        elif imageType == 'gloss':
                            invert_node = mat_builder_node.createNode("arnold::color_correct")
                            invert_node.parm("invert").set("1")
                            invert_node.setInput(0, tex_node)
                            triplanar_node.setInput(0, invert_node)
                            mat_node.setInput(input_slots[imageType], triplanar_node)

                        elif imageType == 'diffuse' and self.ui.cc_on_diff.isChecked():
                            cc_node = mat_builder_node.createNode("arnold::color_correct")
                            cc_node.setInput(0, tex_node)
                            triplanar_node.setInput(0, cc_node)
                            mat_node.setInput(input_slots[imageType], triplanar_node)

                        else:
                            mat_node.setInput(input_slots[imageType], triplanar_node)

                    else:
                        if imageType == 'normal':
                            normal_node = mat_builder_node.createNode("arnold::normal_map")
                            normal_node.setInput(0, tex_node)
                            mat_node.setInput(input_slots[imageType], normal_node)

                        elif imageType == 'bump':
                            bump_node = mat_builder_node.createNode("arnold::bump2d")
                            bump_node.setInput(0, tex_node)
                            mat_node.setInput(input_slots[imageType], bump_node)

                        elif imageType == 'displ':
                            mat_out_node.setInput(1, tex_node)

                        elif imageType == 'gloss':
                            invert_node = mat_builder_node.createNode("arnold::color_correct")
                            invert_node.parm("invert").set("1")
                            invert_node.setInput(0, tex_node)
                            mat_node.setInput(input_slots[imageType], invert_node)

                        elif imageType == 'diffuse' and self.ui.cc_on_diff.isChecked():
                            cc_node = mat_builder_node.createNode("arnold::color_correct")
                            cc_node.setInput(0, tex_node)
                            mat_node.setInput(input_slots[imageType], cc_node)

                        else:
                            mat_node.setInput(input_slots[imageType], triplanar_node)
            
            elif engine =='Octane':
                mat_builder_node = hou.node("/mat").createNode("octane_vopnet")
                mat_node = mat_builder_node.createNode("octane::NT_MAT_UNIVERSAL")
                mat_out_node = hou.node("/mat/%s/octane_material1" % mat_builder_node.name())
                mat_node.parm("roughness").set("1")
                mat_out_node.setInput(0, mat_node)

                diffuse_exists = False
                ao_exists = False

                rgb_types = ('diffuse', 'normal', 'emissive')

                if self.ui.auto_triplanar.isChecked() == True:
                    transform_node = mat_builder_node.createNode("octane::NT_TRANSFORM_2D")
                    triplanar_projection_node = mat_builder_node.createNode("octane::NT_PROJ_TRIPLANAR")

                if self.ui.cc_on_diff.isChecked() == True:
                    cc_node = mat_builder_node.createNode("octane::NT_TEX_COLORCORRECTION")

                for imageType in tex_paths:
                    if imageType in rgb_types:
                        tex_node = mat_builder_node.createNode("octane::NT_TEX_IMAGE", imageType)
                    else:
                        tex_node = mat_builder_node.createNode("octane::NT_TEX_FLOATIMAGE", imageType)

                    tex_node.parm("A_FILENAME").set(tex_paths[imageType])

                    if self.ui.auto_triplanar.isChecked() == True:
                        triplanar_node = mat_builder_node.createNode("octane::NT_TEX_TRIPLANAR")
                        for i in range(3, 9):
                            triplanar_node.setInput(i, tex_node)
                        
                        tex_node.setInput(4, transform_node)
                        tex_node.setInput(5, triplanar_projection_node)
                        
                        if imageType == 'normal':
                            mat_node.setInput(input_slots[imageType], triplanar_node)

                        elif imageType == 'bump':
                            mat_node.setInput(input_slots[imageType], triplanar_node)

                        elif imageType == 'displ':
                            if self.ui.use_vertex_displ.isChecked() == True:
                                displ_node = mat_builder_node.createNode("octane::NT_VERTEX_DISPLACEMENT")
                            else:
                                displ_node = mat_builder_node.createNode("octane::NT_DISPLACEMENT")

                            displ_node.setInput(0, triplanar_node)
                            mat_node.setInput(input_slots[imageType], displ_node)

                        elif imageType == 'gloss':
                            tex_node.parm("invert").set("1")
                            mat_node.setInput(input_slots[imageType], triplanar_node)

                        elif imageType == 'diffuse':
                            diffuse_exists = True
                            diffuse_node = tex_node

                            if ao_exists == True:
                                tex_node.setInput(0, ao_node)

                            if self.ui.cc_on_diff.isChecked() == True:
                                cc_node.setInput(0, tex_node)
                                diffuse_node = cc_node
                                for i in range(3, 9):
                                    triplanar_node.setInput(i, cc_node)
                            else:
                                for i in range(3, 9):
                                    triplanar_node.setInput(i, tex_node)

                            mat_node.setInput(input_slots[imageType], triplanar_node)

                        elif imageType == 'ao':
                            ao_exists = True
                            ao_node = triplanar_node

                            if diffuse_exists == True:
                                diffuse_node.setInput(0, triplanar_node)

                        else:
                            mat_node.setInput(input_slots[imageType], triplanar_node)

                    else:
                        if imageType == 'normal':
                            mat_node.setInput(input_slots[imageType], tex_node)

                        elif imageType == 'bump':
                            mat_node.setInput(input_slots[imageType], tex_node)

                        elif imageType == 'displ':
                            if self.ui.use_vertex_displ.isChecked() == True:
                                displ_node = mat_builder_node.createNode("octane::NT_VERTEX_DISPLACEMENT")
                            else:
                                displ_node = mat_builder_node.createNode("octane::NT_DISPLACEMENT")

                            displ_node.setInput(0, tex_node)
                            mat_node.setInput(input_slots[imageType], displ_node)

                        elif imageType == 'gloss':
                            tex_node.parm("invert").set("1")
                            mat_node.setInput(input_slots[imageType], tex_node)

                        elif imageType == 'ao':
                            ao_exists = True
                            ao_node = tex_node

                            if diffuse_exists == True:
                                diffuse_node.setInput(0, tex_node)

                        elif imageType == 'diffuse':
                            diffuse_exists = True
                            diffuse_node = tex_node

                            if ao_exists == True:
                                tex_node.setInput(0, ao_node)

                            if self.ui.cc_on_diff.isChecked() == True:
                                diffuse_node = cc_node
                                cc_node.setInput(0, tex_node)
                                mat_node.setInput(input_slots[imageType], cc_node)

                            else:
                                mat_node.setInput(input_slots[imageType], tex_node)

                        else:
                            mat_node.setInput(input_slots[imageType], tex_node)
                    
                    if self.ui.diff_is_linear.isChecked() == True:
                        tex_node.parm("gamma").set("1")
                    
                    elif imageType != 'diffuse':
                        tex_node.parm("gamma").set("1")

            elif engine == 'Redshift':
                mat_builder_node = hou.node("/mat").createNode("redshift_vopnet")
                mat_node = mat_builder_node.createNode("redshift::Material")
                mat_out_node = hou.node("/mat/%s/redshift_material1" % mat_builder_node.name())
                mat_node.parm("refl_roughness").set("1")
                mat_node.parm("refl_brdf").set("1")
                mat_node.parm("refl_fresnel_mode").set("2")
                mat_out_node.setInput(0, mat_node)

                if self.ui.auto_triplanar.isChecked() == True:
                    scale_node = mat_builder_node.createNode("redshift::RSVectorMaker", "Scale")
                    offset_node = mat_builder_node.createNode("redshift::RSVectorMaker", "Offset")
                    rotation_node = mat_builder_node.createNode("redshift::RSVectorMaker", "Rotation")
                    scale_node.parm("x").set("1")
                    scale_node.parm("y").set("1")
                    scale_node.parm("z").set("1")
                    offset_node.parm("x").set("0")
                    offset_node.parm("y").set("0")
                    offset_node.parm("z").set("0")
                    rotation_node.parm("x").set("0")
                    rotation_node.parm("y").set("0")
                    rotation_node.parm("z").set("0")

                if self.ui.cc_on_diff.isChecked() == True:
                    cc_node = mat_builder_node.createNode("redshift::RSColorCorrection")

                for imageType in tex_paths:
                    if imageType == "opacity" and self.ui.opc_as_stencil.isChecked() == True:
                        stencil_node = mat_builder_node.createNode("redshift::Sprite")
                        stencil_node.parm("tex0").set(tex_paths[imageType])
                        mat_out.setInput(0, stencil_node)
                        stencil_node.setInput(0, mat_node)
                    else:
                        tex_node = mat_builder_node.createNode("redshift::TextureSampler", imageType)
                        tex_node.parm("tex0").set(tex_paths[imageType])
                        if self.ui.auto_triplanar.isChecked() == True:
                            triplanar_node = mat_builder_node.createNode("redshift::TriPlanar")
                            triplanar_node.setInput(0, tex_node)
                            triplanar_node.setInput(4, scale_node)
                            triplanar_node.setInput(5, offset_node)
                            triplanar_node.setInput(6, rotation_node)

                            if imageType != "displ":
                                mat_node.setInput(input_slots[imageType], triplanar_node)

                            elif imageType == "normal" or imageType == "bump":
                                normal_node = mat_builder_node.createNode("redshift::BumpMap")
                                normal_node.setInput(0, triplanar_node)
                                mat_node.setInput(input_slots[imageType], normal_node)

                                if imageType == "normal":
                                    normal_node.parm("inputType").set("1")

                            elif imageType == "displ":
                                displ_node = mat_builder_node.createNode("redshift::Displacement")
                                displ_node.setInput(0, triplanar_node)
                                mat_out_node.setInput(1, displ_node)

                            elif imageType == "diffuse" and self.ui.cc_on_diff.isChecked() == True:
                                cc_node.setInput(0, tex_node)
                                triplanar_node.setInput(0, cc_node)
                                mat_node.setInput(0, triplanar_node)

                            elif imageType == "gloss":
                                mat_node.parm("refl_isGlossiness").set("1")

                        else:
                            if imageType == "displ":
                                displ_node = mat_builder_node.createNode("redshift::Displacement")
                                displ_node.setInput(0, tex_node)
                                mat_out_node.setInput(1, displ_node)

                            elif imageType == "diffuse" and self.ui.cc_on_diff.isChecked() == True:
                                cc_node.setInput(0, tex_node)
                                mat_node.setInput(input_slots[imageType], cc_node)

                            elif imageType == "normal" or imageType == "bump":
                                normal_node = mat_builder_node.createNode("redshift::BumpMap")
                                normal_node.setInput(0, tex_node)
                                mat_node.setInput(input_slots[imageType], normal_node)

                                if imageType == "normal":
                                    normal_node.parm("inputType").set("1")

                            elif imageType == "gloss":
                                mat_node.parm("refl_isGlossiness").set("1")

                            else:
                                mat_node.setInput(input_slots[imageType], tex_node)

                    if self.ui.diff_is_linear.isChecked() == True:
                        tex_node.parm("tex0_gammaoverride").set("1")

                    elif imageType != 'diffuse':
                        tex_node.parm("tex0_gammaoverride").set("1")

            elif engine == 'Renderman':
                mat_builder_node = hou.node("/mat").createNode("pxrmaterialbuilder")
                mat_node = mat_builder_node.createNode("pxrdisney::22")
                mat_out_node = hou.node("/mat/%s/output_collect" % mat_builder_node.name())
                mat_node.parm("roughness").set("1")
                mat_out_node.setInput(0, mat_node)

                triplanar = self.ui.auto_triplanar.isChecked()
                diffuse_exists = False
                ao_exists = False

                if triplanar == True:
                    triplanar_node = mat_builder_node.createNode("pxrroundcube::22")

                if self.ui.cc_on_diff.isChecked() == True:
                    cc_node = mat_builder_node.createNode("pxrcolorcorrect::22")

                for imageType in tex_paths:
                    if triplanar == True:
                        tex_node = mat_builder_node.createNode("pxrmultitexture::22", imageType)
                        tex_node.setInput(0, triplanar_node, 1)
                        tex_node.parm("filename0").set(tex_paths[imageType])
                    else:
                        tex_node = mat_builder_node.createNode("pxrtexture::22", imageType)
                        tex_node.parm("filename").set(tex_paths[imageType])

                    if imageType == "displ":
                        displ_node = mat_builder_node.createNode("pxrdisplace::22")
                        displ_node.setInput(1, tex_node)
                        mat_out_node.setInput(1, displ_node)

                    elif imageType == "gloss":
                        invert_node = mat_builder_node.createNode("pxrinvert::22")
                        invert_node.setInput(0, tex_node)
                        mat_node.setInput(input_slots[imageType], invert_node)

                    elif imageType == 'ao':
                        ao_exists = True
                        ao_node = tex_node

                        if diffuse_exists == True:
                            if triplanar == True:
                                diffuse_node.setInput(6, tex_node)
                            else:
                                diffuse_node.setInput(0, tex_node)

                    elif imageType == 'diffuse':
                        diffuse_exists = True
                        diffuse_node = tex_node

                        if ao_exists == True:
                            if triplanar == True:
                                tex_node.setInput(6, ao_node)
                            else:
                                tex_node.setInput(0, ao_node)

                        if self.ui.cc_on_diff.isChecked() == True:
                            diffuse_node = cc_node
                            cc_node.setInput(0, tex_node)
                            mat_node.setInput(input_slots[imageType], cc_node)

                        else:
                            mat_node.setInput(input_slots[imageType], tex_node)

                    else:
                        mat_node.setInput(input_slots[imageType], tex_node)

            elif engine == 'VRay':
                mat_builder_node = hou.node("/mat").createNode("vray_vop_material")
                mat_node = hou.node("/mat/%s/VRay_BRDF" % mat_builder_node.name())
                mat_out_node = hou.node("/mat/%s/vray_material_output1" % mat_builder_node.name())
                mat_out_node.setInput(0, mat_node)
                diffuse_exists = False
                ao_exists = False

                if self.ui.cc_on_diff.isChecked() == True:
                    cc_node = mat_builder_node.createNode("VRayNodeColorCorrection")

                for imageType in tex_paths:
                    tex_node = mat_builder_node.createNode("VRayNodeMetaImageFile", imageType)
                    tex_node.parm("BitmapBuffer_file").set(tex_paths[imageType])

                    if self.ui.auto_triplanar.isChecked() == True:
                        if imageType == 'ao':
                            pass
                        else:
                            triplanar_node = mat_builder_node.createNode("VRayNodeTexTriPlanar")
                            triplanar_node.setInput(0, tex_node)

                        if imageType == 'diffuse':
                            diffuse_exists = True
                            diffuse_node = tex_node

                            if self.ui.cc_on_diff.isChecked() == True:
                                diffuse_node = cc_node
                                cc_node.setInput(0, tex_node)

                            if ao_exists == True:
                                multiply_node = mat_builder_node.createNode("VRayNodeTexRGBMultiplyMax")
                                multiply_node.setInput(0, diffuse_node)
                                multiply_node.setInput(1, ao_node)
                                
                                triplanar_node.setInput(0, multiply_node)

                            mat_node.setInput(input_slots[imageType], triplanar_node)

                        elif imageType == 'ao':
                            ao_exists = True
                            ao_node = tex_node

                            if diffuse_exists == True:
                                get_triplanar_node = diffuse_node.outputConnections()[0].outputNode()
                                multiply_node = mat_builder_node.createNode("VRayNodeTexRGBMultiplyMax")
                                multiply_node.setInput(0, diffuse_node)
                                multiply_node.setInput(1, tex_node)
                                get_triplanar_node.setInput(0, multiply_node)
                                # mat_node.setInput(input_slots[imageType], get_triplanar_node)

                        elif imageType == 'rough':
                            mat_node.parm("option_use_roughness").set("1")
                            mat_node.setInput(input_slots[imageType], triplanar_node)

                        elif imageType == 'bump' or imageType == 'normal':
                            bump_node = mat_builder_node.createNode("VRayNodeBRDFBump")
                            bump_node.setInput(0, mat_node)

                            if imageType == 'normal':
                                bump_node.parm("map_type").set("1")
                                bump_node.setInput(3, triplanar_node)
                            else:
                                bump_node.setInput(2, triplanar_node)

                            mat_out_node.setInput(0, bump_node)

                        elif imageType == "displ":
                            displ_node = mat_builder_node.createNode("VRayNodeGeomDisplacedMesh")
                            displ_node.setInput(0, triplanar_node)
                            mat_out_node.setInput(1, displ_node)

                        else:
                            mat_node.setInput(input_slots[imageType], triplanar_node)
                        
                    else:
                        if imageType == 'diffuse':
                            diffuse_exists = True
                            diffuse_node = tex_node

                            if self.ui.cc_on_diff.isChecked() == True:
                                diffuse_node = cc_node
                                cc_node.setInput(0, tex_node)
                                mat_node.setInput(input_slots[imageType], cc_node)

                            if ao_exists == True:
                                multiply_node = mat_builder_node.createNode("VRayNodeTexRGBMultiplyMax")
                                multiply_node.setInput(0, diffuse_node)
                                multiply_node.setInput(1, ao_node)
                                mat_node.setInput(input_slots[imageType], multiply_node)
                            else:
                                mat_node.setInput(input_slots[imageType], tex_node)

                        elif imageType == 'ao':
                            ao_exists = True
                            ao_node = tex_node

                            if diffuse_exists == True:
                                multiply_node = mat_builder_node.createNode("VRayNodeTexRGBMultiplyMax")
                                multiply_node.setInput(0, diffuse_node)
                                multiply_node.setInput(1, tex_node)
                                mat_node.setInput(0, multiply_node)

                        elif imageType == 'bump' or imageType == 'normal':
                            bump_node = mat_builder_node.createNode("VRayNodeBRDFBump")
                            bump_node.setInput(0, mat_node)

                            if imageType == 'normal':
                                bump_node.parm("map_type").set("1")
                                bump_node.setInput(3, tex_node)
                            else:
                                bump_node.setInput(2, tex_node)

                            mat_out_node.setInput(0, bump_node)

                        elif imageType == 'rough':
                            mat_node.parm("option_use_roughness").set("1")
                            mat_node.setInput(input_slots[imageType], tex_node)

                        elif imageType == "displ":
                            displ_node = mat_builder_node.createNode("VRayNodeGeomDisplacedMesh")
                            displ_node.setInput(0, tex_node)
                            mat_out_node.setInput(1, displ_node)

                        else:
                            mat_node.setInput(input_slots[imageType], tex_node)

            for node in mat_builder_node.children():
                node.setDetailMediumFlag(True)

        if self.ui.apply_to_sel_obj.isChecked() == True:
            try:
                for i in sel_Node:
                    i.parm("shop_materialpath").set(mat_builder_node.path())
            except:
                pass

        # Layout
        mat_builder_node.layoutChildren()
        mat_builder_node.moveToGoodPosition()

        self.createOGL(mat_builder_node, mat_node)

    def loadImages(self):
        try:
            sel_Node = hou.selectedNodes()
        except:
            pass

        # Open file dialog to load diffuse texture
        initial_image = QFileDialog.getOpenFileName(filter='All Files (*.*);;OpenExr (*.exr);;HDR (*.hdr);;TIFF (*.tif);;PNG (*.png);;TGA (*.tga);;JPG (*.jpg)')
        initial_image = initial_image[0].encode('utf-8')
        initial_imageType = initial_image.split("/")[-1] #  Get file name only without path
        initial_imageType = "/" + initial_imageType      #  Add '/' to file name to avoid empty match from RegEx

        # Get all files from path of 'initial_image'
        initial_texList = []
        for (dirpath, dirnames, filenames) in os.walk(os.path.dirname(initial_image)):
                initial_texList.extend(filenames)
                break

        # Manual Selection
        if self.ui.man_tex_sel.isChecked() == True:
            tempTexList = []
            for tex in os.listdir(dirpath):
                if tex.endswith(extensions):
                    tempTexList.append(tex)
            initial_texList = self.showDialog(tempTexList, True)

        # Add '/' to file name to avoid empty match from RegEx and transform to lowercase
        for i in range(len(initial_texList)):
            initial_texList[i] = "/" + initial_texList[i].lower()

        # Create UDIM tag
        if self.ui.enable_udim.isChecked() == True:
            tempTexList = []
            for tex in initial_texList:
                findUdim = re.search(r"\d{4}", tex)
                if findUdim != None:
                    tex = tex.replace(findUdim.group(), "<udim>")
                    tempTexList.append(tex)

            initial_texList = list(dict.fromkeys(tempTexList))

        initial_texList = filter(None, initial_texList)

        # Get environment variable
        if self.ui.use_env.isChecked() == True:
            try:
                env_path = hou.getenv(self.ui.env.text()[1:])
                dirpath = dirpath.replace(env_path, self.ui.env.text())
            except:
                pass

        # Filter out files and create texture list
        h_names = ["height", "h"]
        texList = {}
        for tex in initial_texList:
            if tex.endswith(extensions):
                bFound = re.findall(r"(?i)(?<=[-_./])(" + regex_names + r")(?=[_.-])", tex)
                try:
                    bFound = bFound[0]
                except:
                    bFound = ""

                for imageType in texType_names:
                    get_names = texType_names[imageType]
                    if bFound in get_names:
                        if bFound in h_names and self.ui.height_is_displ.isChecked() == True:
                            texList.setdefault('disp', [])
                            texList['disp'].append(dirpath + tex)
                            # texList.setdefault('disp', ([], [names[4]['disp'][0], names[4]['disp'][1]]))
                            # texList[names[4]['disp'][2]][0].append(dirpath + tex)
                        else:
                            texList.setdefault(imageType, [])
                            texList[imageType].append(dirpath + tex)
                            # texList.setdefault(imageType[bFound][2], ([], [imageType[bFound][0], imageType[bFound][1]]))
                            # texList[imageType[bFound][2]][0].append(dirpath + tex)
                    else:
                        pass
            else:
                pass

        # Filter out low quality textures if possible ('prefer_exr')
        if self.ui.pref_exr.isChecked() == True:
            for texType in texList:
                if len(texList[texType]) > 1:
                    check_for_exr = None
                    check_for_exr = [x for x in texList[texType] if '.exr' in x]
                    if check_for_exr:
                        texList[texType] = []
                        texList[texType].extend(check_for_exr)
        
        # 
        count = {}

        for texType in texList:
            count.setdefault(texType, 0)
            if len(texList[texType]) > 1:
                count[texType] += len(texList[texType])
            else:
                count[texType] += 1

        normal_and_bump = False
        spec_and_metal = False
        if 'normal' in count and 'bump' in count:
            texList.pop('bump', None)
            count.pop('bump', None)

        if 'spec' in count and 'metal' in count:
            if self.ui.pref_metal.isChecked() == True:
                texList.pop('spec', None)
                count.pop('spec', None)
            elif self.ui.pref_metal.isChecked() == False:
                texList.pop('metal', None)
                count.pop('metal', None)

        if 'rough' in count and 'gloss' in count:
            texList.pop('gloss', None)
            count.pop('gloss', None)

        # Create final texture list
        for texType in texList:
            if count[texType] > 1:
                tempTexList = []
                for tex in texList[texType]:
                    tempTexList.append(tex)
                try:
                    tex = self.showDialog(tempTexList, False)[0]
                except:
                    break

            elif count[texType] == 1:
                tex = texList[texType][0]

            texList[texType] = tex
        
        self.createShaders(texList, sel_Node)

    def toggleEnvVar(self):
        if self.ui.use_env.isChecked():
            self.ui.env.setDisabled(False)
        else:
            self.ui.env.setDisabled(True)

    def showDialog(self, tempTexList, man_sel):
        loader = QUiLoader()
        ui = loader.load(scriptpath + "/texlist.ui")

        dialogLayout = QVBoxLayout()
        dialogLayout.addWidget(ui)

        texListDialog = hou.qt.Dialog()
        texListDialog.setLayout(dialogLayout)

        ui.buttonBox.accepted.connect(texListDialog.accept)
        ui.buttonBox.rejected.connect(texListDialog.reject)

        texListWidget = ui.listWidget
        if man_sel == True:
            texListWidget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for x in tempTexList:
            texListWidget.addItem(x)
        
        texListDialog.resize(hou.ui.scaledSize(600), hou.ui.scaledSize(300))

        texListDialog.exec_()

        items = texListWidget.selectedItems()

        newIniList = []
        for x in range(len(items)):
            newIniList.append(str(texListWidget.selectedItems()[x].text()))

        
        return newIniList

    def jump_to_mat(self):
        try:
            get_network.setPwd(mat_builder_node)
        except:
            print("No Material found.")
                
    def open_settings(self):
        if self.ui.settings.isChecked() == False:
            self.ui.settings.setMaximumSize(16777215, 30)
        else:
            self.ui.settings.setMaximumSize(16777215, 16777215)

_TextureImporter = None

def show():
    global _TextureImporter
    if _TextureImporter is None:
        _TextureImporter = TextureImporter()
    _TextureImporter.show()