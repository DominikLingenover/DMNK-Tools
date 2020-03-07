import hou
import os
import re
import icons

from PySide2 import QtCore
from PySide2 import QtWidgets
from PySide2 import QtGui
from PySide2 import QtUiTools

scriptpath = os.path.dirname(__file__)
asset_checker_path = hou.getenv("dmnk")
settings_path = asset_checker_path + "/config/speedtree_importer_config"
version = "2.00"

# Name lists + regex filter
extensions = (".jpg", ".exr", ".tga", ".png", "tif", ".hdr")
ao_names = ["ao", "ambientocclusion", "ambient_occlusion", "cavity"]
nml_names = ["normal", "nrm", "nrml", "n", "norm_ogl", "normalbump"]
opc_names = ["transparency", "t", "opacity", "o", "alpha"]
gloss_names = ["gloss", "g", "glossiness"]
diff_names = ["diffuse", "diff", "albedo", "color", "col", "alb", "dif", "diffuseColor"]
sss_names = ["subsurfacecolor", "subsurfaceamount", "sss"]
rough_names = ["roughness", "rough", "r"]
spec_names = ["specular", "spec", "s", "refl", "reflectivity"]
all_names = ao_names + nml_names + opc_names + gloss_names + diff_names + sss_names + rough_names + spec_names
regex_filter = "[/_.]*(?:SubsurfaceAmount|Gloss|SubsurfaceColor|Opacity|Alpha|AO|Normal|\\b)(?=.jpg|.exr|.png|.tif)"

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

# Initialize variables
geo_node = None
mat_builder_node = None

class SpeedTreeImporter(QtWidgets.QWidget):
    def __init__(self):
        super(SpeedTreeImporter, self).__init__(hou.qt.mainWindow())

        # Create UI
        self.create_ui()

    def create_ui(self):
        """
        Create UI.
        Assign functions to buttons and actions.
        """

        self.settings = QtCore.QSettings(settings_path, QtCore.QSettings.IniFormat)

        self.setWindowTitle('DMNK - SpeedTree Importer')
        self.setWindowFlags(QtCore.Qt.Dialog)
        self.resize(self.settings.value("size", QtCore.QSize(hou.ui.scaledSize(425), hou.ui.scaledSize(238))))
        self.move(self.settings.value("pos", QtCore.QPoint(0, 0)))

        # Layout
        loader = QtUiTools.QUiLoader()
        self.ui = loader.load(scriptpath + "/speedtree_importer_ui.ui")

        mainLayout = QtWidgets.QGridLayout()
        mainLayout.addWidget(self.ui)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(mainLayout)

        self.ui.settings.setStyleSheet(CLGRP_STYLE)
        
        # Get values from config
        self.ui.renderer_dropdown.setCurrentText(self.settings.value("renderer_dropdown", ""))
        self.ui.opc_as_stencil.setChecked(str(self.settings.value("opc_as_stencil", False)).lower() == 'true')
        self.ui.diff_is_linear.setChecked(str(self.settings.value("diff_is_linear", False)).lower() == 'true')
        self.ui.use_env.setChecked(str(self.settings.value("use_env", False)).lower() == 'true')
        self.ui.env.setText(self.settings.value("env", ""))

        # Connect functions to signals
        ## Config related signals
        self.ui.renderer_dropdown.currentIndexChanged.connect(self.updateConfig)
        self.ui.renderer_dropdown.currentIndexChanged.connect(self.updateEngine)
        self.ui.opc_as_stencil.toggled.connect(self.updateConfig)
        self.ui.diff_is_linear.toggled.connect(self.updateConfig)
        self.ui.use_env.toggled.connect(self.updateConfig)
        self.ui.env.editingFinished.connect(self.updateConfig)

        ## Open/close settings
        self.ui.settings.toggled.connect(self.open_settings)

        ## Main functions
        self.ui.node_jump.clicked.connect(self.jump_to_tree)
        self.ui.import_mat.clicked.connect(self.createGeo)

        if self.ui.use_env.isChecked() == False:
            self.ui.env.setDisabled(True)
        else:
            self.ui.env.setDisabled(False)

        self.updateEngine()

    def hideEvent(self, event):
        """
        When window is closed store position and size in config.
        """

        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())

    def updateConfig(self):
        """
        Updates the config when user inputs settings.
        """

        renderer_dropdown = self.ui.renderer_dropdown.currentText()
        opc_as_stencil = self.ui.opc_as_stencil.isChecked()
        diff_is_linear = self.ui.diff_is_linear.isChecked()
        use_env = self.ui.use_env.isChecked()
        env = self.ui.env.text()

        self.settings.setValue("renderer_dropdown", renderer_dropdown)
        self.settings.setValue("opc_as_stencil", opc_as_stencil)
        self.settings.setValue("diff_is_linear", diff_is_linear)
        self.settings.setValue("use_env", use_env)
        self.settings.setValue("env", env)

        if self.ui.use_env.isChecked() == False:
            self.ui.env.setDisabled(True)
        else:
            self.ui.env.setDisabled(False)

    def open_settings(self):
        if self.ui.settings.isChecked() == False:
            self.ui.settings.setMaximumSize(16777215, 30)
        else:
            self.ui.settings.setMaximumSize(16777215, 16777215)

    def updateEngine(self):
        # Render specific settings
        global engine
        global input_slots
        global node_names
        global parm_names
        engine = self.ui.renderer_dropdown.currentText()

        if engine == 'Arnold':
            input_slots = {
                'diffuse': 1,
                'ao': 0,
                'transl_weight': 17,
                'transl_color': 18,
                'spec': 5,
                'rough': 6,
                'gloss': 6,
                'opc': 38,
                'normal': 39,
                'bump': 39,
            }
            node_names = {
                'mat_builder': 'arnold_materialbuilder',
                'material': 'arnold::standard_surface',
                'material_name': 'standard_surface2',
                'material_out': 'OUT_material',
                'texture_node': 'arnold::image',
                'cc': 'arnold::color_correct',
                'bump': 'arnold::normal_map'
            }
            parm_names = {
                'brdf_type': [None, None],
                'transl_weight': 'subsurface',
                'roughness': 'specular_roughness',
                'tex_filename': 'filename',
                'gamma': [None, None]
            }

        elif engine == 'Octane':
            self.ui.diff_is_linear.setDisabled(False)
            
            input_slots = {
                'diffuse': 2,
                'ao': None,
                'transl_weight': None,
                'transl_color': None,
                'spec': 4,
                'rough': 6,
                'gloss': 6,
                'opc': 28,
                'normal': 32,
                'bump': 31,
            }
            node_names = {
                'mat_builder': 'octane_vopnet',
                'material': 'octane::NT_MAT_UNIVERSAL',
                'material_name': 'NT_MAT_UNIVERSAL1',
                'material_out': 'octane_material1',
                'texture_node': 'octane::NT_TEX_IMAGE',
                'texture_node_greyscale': 'octane::NT_TEX_FLOATIMAGE',
                'cc': 'octane::NT_TEX_COLORCORRECTION',
            }
            parm_names = {
                'brdf_type': ['brdf', "2"],
                'transl_weight': None,
                'roughness': 'roughness',
                'tex_filename': 'A_FILENAME',
                'gamma': ['gamma', 1],
            }

        elif engine == 'Redshift':
            self.ui.diff_is_linear.setDisabled(False)
            self.ui.opc_as_stencil.setDisabled(False)

            input_slots = {
                'diffuse': 0,
                'ao': 1,
                'transl_weight': 4,
                'transl_color': 3,
                'spec': 5,
                'rough': 7,
                'gloss': 7,
                'opc': 47,
                'normal': 49,
                'bump': 49,
            }
            node_names = {
                'mat_builder': 'redshift_vopnet',
                'material': 'redshift::Material',
                'material_name': 'Material1',
                'material_out': 'redshift_material1',
                'texture_node': 'redshift::TextureSampler',
                'cc': 'redshift::RSColorCorrection',
                'bump': 'redshift::BumpMap',
            }
            parm_names = {
                'brdf_type': ['refl_brdf', "1"],
                'transl_weight': 'transl_weight',
                'roughness': 'refl_roughness',
                'tex_filename': 'tex0',
                'gamma': ['tex0_gammaoverride', '1']
            }

        elif engine == 'Renderman':
            input_slots = {
                'diffuse': 1,
                'ao': 2,
                'transl_weight': 7,
                'transl_color': 8,
                'spec': 10,
                'rough': 14,
                'gloss': 14,
                'opc': 94,
                'normal': 92,
                'bump': 92,
            }
            node_names = {
                'mat_builder': 'pxrmaterialbuilder',
                'material': 'pxrsurface::22',
                'material_name': 'pxrdisney1',
                'material_out': 'output_collect',
                'texture_node': 'pxrtexture::22',
                'cc': 'pxrcolorcorrect::22',
                'bump': 'pxrnormalmap::22'
            }
            parm_names = {
                'brdf_type': ['specularModelType', "1"],
                'transl_weight': 'diffuseTransmitGain',
                'roughness': 'specularRoughness',
                'tex_filename': 'filename',
                'gamma': [None, None]
            }

        elif engine == 'VRay':
            self.ui.diff_is_linear.setDisabled(False)
            
            input_slots = {
                'diffuse': 0,
                'ao': None,
                'transl_weight': None,
                'transl_color': None,
                'spec': 5,
                'rough': 6,
                'gloss': 6,
                'opc': 2,
                'normal': None,
                'bump': None,
            }
            node_names = {
                'mat_builder': 'vray_vop_material',
                'material': 'VRayNodeBRDFVRayMtl',
                'material_name': 'VRay_BRDF',
                'material_out': 'vray_material_output1',
                'texture_node': 'VRayNodeMetaImageFile',
                'cc': 'VRayNodeColorCorrection',
                'bump': 'VRayNodeBRDFBump'
            }
            parm_names = {
                'brdf_type': [None, None],
                'transl_weight': None,
                'roughness': 'reflect_glossiness',
                'tex_filename': 'BitmapBuffer_file',
                'gamma': ['BitmapBuffer_color_space', '0']
            }
        
        if engine not in  ['Redshift', 'VRay']:
            self.ui.opc_as_stencil.setDisabled(True)

        if engine not in ['Octane', 'Redshift', 'VRay']:
            self.ui.diff_is_linear.setDisabled(True)

    def createGeo(self):
        global geo_node
        global matnet

        # Get Geometry
        get_Mesh_File = hou.ui.selectFile(
            title="Select Mesh File",
            file_type=hou.fileType.Geometry,
            pattern=("*.bgeo, *.abc, *.obj, *.fbx"))

        get_Mesh_File_Ext = get_Mesh_File[-3:]
        get_Mesh_File_Abs = hou.expandString(get_Mesh_File)

        # Create 'geo' and 'matnet' node
        geo_node = hou.node("/obj").createNode("geo")
        matnet = geo_node.createNode("matnet", "Materials")

        # Get primitive groups depending on mesh file type
        if get_Mesh_File_Ext == "abc":
            abc_Node = geo_node.createNode("alembic")
            abc_Node.parm("fileName").set(get_Mesh_File)
            abc_Node.parm("loadmode").set(1)
            abc_Node.parm("polysoup").set(0)

            # unpack_Node = abc_Node.createOutputNode("unpack")

            mat_assign_node = abc_Node.createOutputNode("material")

            prim_groups = self.get_prim_grps(abc_Node)
        
        elif get_Mesh_File_Ext == "obj" or get_Mesh_File_Ext == "fbx":
            file_Node = geo_node.createNode("file")
            file_Node.parm("file").set(get_Mesh_File)

            clean_Node = file_Node.createOutputNode("clean")
            clean_Node.parm("dodelgroups").set("1")
            clean_Node.parm("deldegengeo").set("0")

            partition_Node = clean_Node.createOutputNode("partition")
            partition_Node.parm("rule").set("$MAT")

            mat_assign_node = partition_Node.createOutputNode("material")

            prim_groups = self.get_prim_grps(partition_Node)
        else:
            file_Node = geo_node.createNode("file")
            file_Node.parm("file").set(get_Mesh_File)

            mat_assign_node = file_Node.createOutputNode("material")

            prim_groups = self.get_prim_grps(file_Node)

        # Set flags to last node
        mat_assign_node.setDisplayFlag(True)
        mat_assign_node.setRenderFlag(True)

        textures = self.get_Textures(get_Mesh_File_Abs)

        self.create_Materials(geo_node, matnet, mat_assign_node, prim_groups, textures[0], textures[1])

    def jump_to_tree(self):
        try:
            get_network = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.NetworkEditor)
            if QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
                get_network.setPwd(matnet)
            else:
                get_network.setPwd(geo_node)
        except:
            print("No Node found.")

    def get_prim_grps(self, primgrp_Node):
        """
        Return primitive groups.
        """ 
        
        x = primgrp_Node.geometry()
        get_Groups = x.primGroups()
        return get_Groups

    def get_Textures(self, mesh_File_Path):
        """
        Find textures from mesh file path and return texture list.
        """

        tex_list = []
        for (dirpath, dirnames, filenames) in os.walk(os.path.dirname(mesh_File_Path)):
            for files in filenames:
                if files.endswith(extensions):
                    tex_list.append(files)

        if self.ui.use_env.isChecked() == True:
            try:
                env_path = hou.getenv(self.ui.env.text()[1:])
                env_path = self.convert_backslash(env_path)
                dirpath = dirpath.replace(env_path, self.ui.env.text())
            except:
                pass

        tex_list = ["/" + x for x in tex_list]

        return tex_list, dirpath

    def create_Materials(self, geo_node, matnet, mat_assign_node, prim_groups, tex_list, dirpath):
        # Texture list with lowercase names for easier comparison
        tex_list_lower = [x.lower() for x in tex_list]

        # Get all opacity textures
        opc_list = []
        for tex in tex_list:
            is_opc = re.search(r"(?i)(alpha|opacity|opc)", tex)
            if is_opc != None:
                opc_list.append(tex)

        for index, x in enumerate(prim_groups):
            global mat_builder_node

            opc_exists = False
            rough_exists = False
            ao_exists = False
            diffuse_exists = False
            spec_exists = False
            normal_exists = False
            transl_weight_exists = False
            transl_color_exists = False
            ao_node = None
            diffuse_node = None

            # Remove unnecessary names from prim group
            getMatSG = re.findall(r"(?i)_*(?:matsg|mat)_*", x.name())
            prim_group = x.name()

            if len(getMatSG) > 0:
                for i, word in enumerate(getMatSG):
                    prim_group = prim_group.replace(getMatSG[i], "")

            # Find leaf and leaf variations
            is_leaf = re.search(r"(?i)leaf", prim_group)
            is_leaf_variation = re.search(r"v\d", prim_group)
                    
            # Create Material Builder inside Matnet
            mat_builder_node = matnet.createNode(node_names['mat_builder'], prim_group)
            mat_out_node = hou.node("/obj/%s/Materials/%s/%s" % (geo_node.name(), prim_group, node_names['material_out']))

            if engine == 'VRay':
                # VRay requires a different setup for backlight translucency
                if is_leaf != None:
                    twoside_mat_node = mat_builder_node.createNode("VRayNodeMtl2Sided")
                    front_mat_node = hou.node("/obj/%s/Materials/%s/VRay_BRDF" % (geo_node.name(), prim_group))
                    back_mat_node = mat_builder_node.createNode(node_names['material'])

                    twoside_mat_node.setInput(0, front_mat_node)
                    twoside_mat_node.setInput(1, back_mat_node)
                    mat_out_node.setInput(0, twoside_mat_node)

                else:
                    mat_node = hou.node("/obj/%s/Materials/%s/VRay_BRDF" % (geo_node.name(), prim_group))
                    mat_out_node.setInput(0, mat_node)

            else:
                mat_node = mat_builder_node.createNode(node_names['material'])
                mat_out_node.setInput(0, mat_node)

                if engine == 'Renderman':
                    mat_node.parm("specularFresnelMode").set("1")
                    mat_node.setParms({"diffuseColorr": 1, "diffuseColorg": 1, "diffuseColorb": 1})
                    mat_node.setParms({"specularEdgeColorr": 1, "specularEdgeColorg": 1, "specularEdgeColorb": 1})

                    if is_leaf != None:
                        mat_node.parm("diffuseDoubleSided").set("1")

            # Set BRDF to GGX
            if engine in ['Redshift', 'Octane', 'Renderman']:
                mat_node.parm(parm_names['brdf_type'][0]).set(parm_names['brdf_type'][1])

            # Set 'Diffuse' transmission type for leafs in Octane for backlight translucency
            if engine == 'Octane':
                if is_leaf != None:
                    mat_node.parm("transmissionType").set("1")

            # Get relative path to materials and populate 'Material' SOP with materials assigned to approriate prim group
            mat_rel_path = mat_assign_node.relativePathTo(mat_builder_node)
            mat_assign_node.parm("num_materials").set(len(prim_groups))
            mat_assign_node.parm("group%s" % str(index+1)).set(x.name())
            mat_assign_node.parm("shop_materialpath%s" % str(index+1)).set(mat_rel_path)

            # Iterate through textures
            if is_leaf_variation != None:
                base_prim_group = prim_group[:-3] #  Base prim group to get missing texture types for leaf variation

                for tex in tex_list:
                    find_leaf_variation_tex = re.search(r"(?i)(?:" + prim_group + r")" + regex_filter, tex)

                    if find_leaf_variation_tex != None:
                        x = tex[:-4]
                        tex_type = x.split("_")[-1]
                        tex_type = tex_type.lower()

                        # Determine if tex_type is diffuse
                        if tex_type not in all_names:
                            tex_type = "diffuse"

                        # Prevent creation of opacity texture node for Redshift
                        if engine == 'Redshift':
                            if tex_type not in opc_names:
                                tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)

                        else:
                            tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                            tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)

                        self.adjust_gamma(tex_node, tex_type) #  Set linear or sRGB Gamma

                        if tex_type in diff_names:
                            diffuse_exists = True
                            diffuse_node = tex_node

                            if engine == 'VRay':
                                if ao_exists == True:
                                    multiply_node = mat_builder_node.createNode("VRayNodeTexRGBMultiplyMax")
                                    multiply_node.setInput(0, diffuse_node)
                                    multiply_node.setInput(1, ao_node)
                                    mat_node.setInput(input_slots['diffuse'], multiply_node)
                                else:
                                    mat_node.setInput(input_slots['diffuse'], tex_node)

                            elif engine == 'Octane':
                                if ao_exists == True:
                                    diffuse_node.setInput(0, ao_node)
                                
                                mat_node.setInput(input_slots['diffuse'], tex_node)

                            else:
                                mat_node.setInput(input_slots['diffuse'], tex_node)

                            if prim_group.lower() + "_subsurfacecolor.png" not in tex_list_lower:
                                transl_color_exists = True

                                cc_node = mat_builder_node.createNode(node_names['cc'])
                                cc_node.setInput(0, tex_node)

                                transl_color_node = cc_node

                                if engine == 'Octane':
                                    multiply_node = mat_builder_node.createNode("octane::NT_TEX_MULTIPLY")
                                    multiply_node.setInput(0, cc_node)

                                    if transl_weight_exists == True:
                                        multiply_node.setInput(1, transl_weight_node)
                                    else:
                                        multiply_node.parm("texture2").set(0.3)

                                    transl_color_node = multiply_node

                                    mat_node.setInput(input_slots['transl_color'], multiply_node)

                                elif engine == 'VRay':
                                    back_mat_node.setInput(0, cc_node)

                                else:
                                    mat_node.setInput(input_slots['transl_color'], cc_node)

                        elif tex_type in ao_names:
                            ao_exists = True
                            ao_node = tex_node

                            if engine == 'VRay':
                                if diffuse_exists == True:
                                    multiply_node = mat_builder_node.createNode("VRayNodeTexRGBMultiplyMax")
                                    multiply_node.setInput(0, diffuse_node)
                                    multiply_node.setInput(1, tex_node)
                                    mat_node.setInput(0, multiply_node)

                            elif engine == 'Octane':
                                if diffuse_exists == True:
                                    diffuse_node.setInput(0, tex_node)

                            else:
                                mat_node.setInput(input_slots['ao'], tex_node)
                            
                        elif tex_type == "subsurfacecolor":
                            if engine == 'Octane':
                                transl_color_exists = True
                                transl_color_node = tex_node
                                if transl_weight_exists == True:
                                    tex_node.setInput(0, transl_weight_node)

                                mat_node.setInput(0, tex_node)

                            elif engine == 'VRay':
                                back_mat_node.setInput(0, tex_node)
                            
                            else:
                                mat_node.setInput(input_slots['transl_color'], tex_node)

                        elif tex_type == "subsurfaceamount":
                            transl_weight_exists = True

                            if engine == 'Octane':
                                transl_weight_node = tex_node
                                if transl_color_exists == True:
                                    if prim_group.lower() + "_subsurfacecolor.png" not in tex_list_lower:
                                        transl_color_node.setInput(1, tex_node)
                                    else:
                                        transl_color_node.setInput(0, tex_node)

                            elif engine == 'VRay':
                                twoside_mat_node.setInput(2, tex_node)

                            else:
                                mat_node.setInput(input_slots['transl_weight'], tex_node)

                        elif tex_type in spec_names:
                            spec_exists = True
                            mat_node.setInput(input_slots['spec'], tex_node)

                        elif tex_type in gloss_names:
                            rough_exists = True
                            mat_node.parm(parm_names['roughness']).set(1)
                
                            if engine == 'Redshift':
                                mat_node.parm("refl_isGlossiness").set("1")
                                mat_node.setInput(input_slots['gloss'], tex_node)

                            elif engine == 'Arnold':
                                invert_node = mat_builder_node.createNode("arnold::color_correct")
                                invert_node.setInput(0, tex_node)
                                invert_node.parm("invert").set("1")
                                mat_node.setInput(input_slots['gloss'], invert_node)

                            elif engine == 'Renderman':
                                invert_node = mat_builder_node.createNode("pxrinvert::22")
                                invert_node.setInput(0, tex_node)
                                mat_node.setInput(input_slots['gloss'], invert_node)

                            elif engine == 'Octane':
                                tex_node.parm("invert").set("1")
                                mat_node.setInput(input_slots['gloss'], tex_node)

                            else:
                                mat_node.setInput(input_slots['gloss'], tex_node)

                        elif tex_type in rough_names:
                            rough_exists = True
                            mat_node.parm(parm_names['roughness']).set(1)

                            if engine == 'VRay':
                                mat_node.parm("option_use_roughness").set("1")

                            mat_node.setInput(input_slots['rough'], tex_node)

                        elif tex_type in opc_names:
                            opc_exists = True

                            if engine == 'Redshift':
                                if self.ui.opc_as_stencil.isChecked() == True:
                                    sprite_node = mat_builder_node.createNode("redshift::Sprite", tex_type)
                                    sprite_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                                    sprite_node.setInput(0, mat_node)
                                    mat_out_node.setInput(0, sprite_node)

                                else:
                                    tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                    tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                                    mat_node.setInput(47, tex_node)

                            elif engine == 'Renderman':
                                mat_node.setInput(input_slots['opc'], tex_node, 1)
                            
                            else:
                                # tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                # tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                                mat_node.setInput(input_slots['opc'], tex_node)

                                if engine == 'VRay':
                                    back_mat_node.setInput(input_slots['opc'], tex_node)

                                    if self.ui.opc_as_stencil.isChecked() == True:
                                        twoside_mat_node.parm("opacity_mode").set("1")
                                        back_mat_node.parm("opacity_mode").set("1")

                        elif tex_type in nml_names:
                            normal_exists = True
                            if engine in ['Arnold', 'Redshift', 'Renderman']:
                                normal_node = mat_builder_node.createNode(node_names['bump'])
                                normal_node.setInput(1, tex_node)
                                mat_node.setInput(input_slots['normal'], normal_node)

                                if engine == 'Redshift':
                                    normal_node.parm("inputType").set("1")

                            elif engine == 'Octane':
                                mat_node.setInput(input_slots['normal'], tex_node)

                            elif engine == 'Renderman':
                                normal_node = mat_builder_node.createNode("pxrnormalmap:22")
                                mat_node.setInput(input_slots['normal'], tex_node)

                            elif engine == 'VRay':
                                normal_node = mat_builder_node.createNode(node_names['bump'])

                                if is_leaf != None:
                                    normal_node.setInput(0, twoside_mat_node)
                                else:
                                    normal_node.setInput(0, mat_node)

                                normal_node.parm("map_type").set("1")
                                normal_node.setInput(3, tex_node)

                                mat_out_node.setInput(0, normal_node)

                        
                for tex in tex_list:
                    find_base_leaf_tex = re.search(r"(?i)(?:" + base_prim_group + r")" + regex_filter, tex)

                    if find_base_leaf_tex != None:
                        x = tex[:-4]
                        tex_type = x.split("_")[-1]
                        tex_type = tex_type.lower()

                        if tex_type not in all_names or tex_type == "subsurfacecolor":
                            pass

                        if tex_type in ao_names and ao_exists == False:
                            tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                            tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)

                            ao_exists = True
                            ao_node = tex_node

                            if engine == 'VRay':
                                if diffuse_exists == True:
                                    multiply_node = mat_builder_node.createNode("VRayNodeTexRGBMultiplyMax")
                                    multiply_node.setInput(0, diffuse_node)
                                    multiply_node.setInput(1, tex_node)
                                    mat_node.setInput(0, multiply_node)

                            elif engine == 'Octane':
                                if diffuse_exists == True:
                                    diffuse_node.setInput(0, tex_node)

                            else:
                                mat_node.setInput(input_slots['ao'], tex_node)

                        elif tex_type in spec_names and spec_exists == False:
                            spec_exists = True
                            tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                            tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)

                            mat_node.setInput(input_slots['spec'], tex_node)

                        elif tex_type in gloss_names and rough_exists == False:
                            rough_exists = True
                            mat_node.parm(parm_names['roughness']).set(1)

                            tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                            tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)

                            if engine == 'Redshift':
                                mat_node.parm("refl_isGlossiness").set("1")
                                mat_node.setInput(input_slots['gloss'], tex_node)

                            elif engine == 'Arnold':
                                invert_node = mat_builder_node.createNode("arnold::color_correct")
                                invert_node.setInput(0, tex_node)
                                invert_node.parm("invert").set("1")
                                mat_node.setInput(input_slots['gloss'], invert_node)

                            elif engine == 'Renderman':
                                invert_node = mat_builder_node.createNode("pxrinvert::22")
                                invert_node.setInput(0, tex_node)
                                mat_node.setInput(input_slots['gloss'], invert_node)

                            elif engine == 'Octane':
                                tex_node.parm("invert").set("1")
                                mat_node.setInput(input_slots['gloss'], tex_node)

                            else:
                                mat_node.setInput(input_slots['gloss'], tex_node)

                        elif tex_type in rough_names and rough_exists == False:
                            rough_exists = True
                            mat_node.parm(parm_names['roughness']).set(1)

                            tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                            tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                            
                            if engine == 'VRay':
                                mat_node.parm("option_use_roughness").set("1")

                            mat_node.setInput(input_slots['rough'], tex_node)

                        elif tex_type in opc_names and opc_exists == False:
                            opc_exists = True

                            if engine == 'Redshift':
                                if self.ui.opc_as_stencil.isChecked() == True:
                                    sprite_node = mat_builder_node.createNode("redshift::Sprite", tex_type)
                                    sprite_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                                    sprite_node.setInput(0, mat_node)
                                    mat_out_node.setInput(0, sprite_node)
                                else:
                                    tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                    tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                                    mat_node.setInput(47, tex_node)

                            elif engine == 'Renderman':
                                mat_node.setInput(input_slots['opc'], tex_node, 1)

                            else:
                                tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                                mat_node.setInput(input_slots['opc'], tex_node)

                                if engine == 'VRay':
                                    back_mat_node.setInput(input_slots['opc'], tex_node)

                                    if self.ui.opc_as_stencil.isChecked() == True:
                                        mat_node.parm("opacity_mode").set("1")

                        elif tex_type in nml_names and normal_exists == False:
                            normal_exists = True
                            tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                            tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                            
                            if engine in ['Arnold', 'Redshift', 'Renderman']:
                                normal_node = mat_builder_node.createNode(node_names['bump'])
                                normal_node.setInput(1, tex_node)
                                mat_node.setInput(input_slots['normal'], normal_node)

                                if engine == 'Redshift':
                                    normal_node.parm("inputType").set("1")

                            elif engine == 'Octane':
                                mat_node.setInput(input_slots['normal'], tex_node)

                            elif engine == 'Renderman':
                                mat_node.setInput(input_slots['normal'], tex_node)

                            elif engine == 'VRay':
                                normal_node = mat_builder_node.createNode(node_names['bump'])

                                if is_leaf != None:
                                    normal_node.setInput(0, twoside_mat_node)
                                else:
                                    normal_node.setInput(0, mat_node)
                                    
                                normal_node.parm("map_type").set("1")
                                normal_node.setInput(3, tex_node)

                                mat_out_node.setInput(0, normal_node)

                        elif tex_type == "subsurfaceamount" and transl_weight_exists == False:
                            tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                            tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)

                            if engine == 'Octane':
                                transl_weight_node = tex_node
                                if transl_color_exists == True:
                                    if prim_group.lower() + "_subsurfacecolor.png" not in tex_list_lower:
                                        transl_color_node.setInput(1, tex_node)
                                    else:
                                        transl_color_node.setInput(0, tex_node)

                            elif engine == 'VRay':
                                twoside_mat_node.setInput(2, tex_node)

                            else:
                                mat_node.setInput(input_slots['transl_weight'], tex_node)

                        self.adjust_gamma(tex_node, tex_type) #  Set linear or sRGB Gamma

                        if rough_exists == False:
                            mat_node.parm(parm_names['roughness']).set(0.2)

                        if transl_weight_exists == False:
                            if engine == 'VRay':
                                    twoside_mat_node.setParms({"translucency_texr": 0.3, "translucency_texg": 0.3, "translucency_texb": 0.3})
                            elif engine != 'Octane':
                                mat_node.parm(parm_names['transl_weight']).set(0.3)

            else:
                for tex in tex_list:
                    if engine == 'VRay':
                        if is_leaf != None:
                            mat_node = front_mat_node

                    find_tex = re.search(r"(?i)(?:" + prim_group + r")" + regex_filter, tex)

                    if find_tex != None:
                        x = tex[:-4]
                        tex_type = x.split("_")[-1]
                        tex_type = tex_type.lower()

                        if tex_type not in all_names:
                            tex_type = "diffuse"

                        # Prevent creation of opacity texture node for Redshift
                        if engine == 'Redshift':
                            if tex_type not in opc_names:
                                tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)

                        else:
                            tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                            tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)

                        self.adjust_gamma(tex_node, tex_type) #  Set linear or sRGB Gamma

                        if tex_type in diff_names:
                            diffuse_exists = True
                            diffuse_node = tex_node

                            if engine == 'VRay':
                                if ao_exists == True:
                                    multiply_node = mat_builder_node.createNode("VRayNodeTexRGBMultiplyMax")
                                    multiply_node.setInput(0, diffuse_node)
                                    multiply_node.setInput(1, ao_node)
                                    mat_node.setInput(input_slots['diffuse'], multiply_node)
                                else:
                                    mat_node.setInput(input_slots['diffuse'], tex_node)
                            
                            elif engine == 'Octane':
                                if ao_exists == True:
                                    diffuse_node.setInput(0, ao_node)
                                
                                mat_node.setInput(input_slots['diffuse'], tex_node)

                            else:
                                mat_node.setInput(input_slots['diffuse'], tex_node)

                            if is_leaf != None:
                                if prim_group.lower() + "_subsurfacecolor.png" not in tex_list_lower:
                                    transl_color_exists = True

                                    cc_node = mat_builder_node.createNode(node_names['cc'])
                                    cc_node.setInput(0, tex_node)

                                    transl_color_node = cc_node

                                    if engine == 'Octane':
                                        multiply_node = mat_builder_node.createNode("octane::NT_TEX_MULTIPLY")
                                        multiply_node.setInput(0, cc_node)

                                        if transl_weight_exists == True:
                                            multiply_node.setInput(1, transl_weight_node)
                                        else:
                                            multiply_node.parm("texture2").set(0.3)

                                        transl_color_node = multiply_node

                                        mat_node.setInput(input_slots['transl_color'], multiply_node)

                                    elif engine == 'VRay':
                                        back_mat_node.setInput(0, cc_node)

                                    else:
                                        mat_node.setInput(input_slots['transl_color'], cc_node)

                        elif tex_type in ao_names:
                            ao_exists = True
                            ao_node = tex_node

                            if engine == 'VRay':
                                if diffuse_exists == True:
                                    multiply_node = mat_builder_node.createNode("VRayNodeTexRGBMultiplyMax")
                                    multiply_node.setInput(0, diffuse_node)
                                    multiply_node.setInput(1, tex_node)
                                    mat_node.setInput(0, multiply_node)
                            
                            elif engine == 'Octane':
                                if diffuse_exists == True:
                                    diffuse_node.setInput(0, tex_node)

                            else:
                                mat_node.setInput(input_slots['ao'], tex_node)

                        elif tex_type == "subsurfacecolor":
                            if engine == 'Octane':
                                transl_color_exists = True
                                transl_color_node = tex_node
                                
                                if transl_weight_exists == True:
                                    tex_node.setInput(0, transl_weight_node)

                                mat_node.setInput(0, tex_node)

                            elif engine == 'VRay':
                                if is_leaf != None:
                                    back_mat_node.setInput(0, tex_node)
                            
                            else:
                                mat_node.setInput(input_slots['transl_color'], tex_node)

                        elif tex_type == "subsurfaceamount":
                            transl_weight_exists = True

                            if engine == 'Octane':
                                transl_weight_node = tex_node
                                if transl_color_exists == True:
                                    if prim_group.lower() + "_subsurfacecolor.png" not in tex_list_lower:
                                        transl_color_node.setInput(1, tex_node)
                                    else:
                                        transl_color_node.setInput(0, tex_node)

                            elif engine == 'VRay':
                                twoside_mat_node.setInput(2, tex_node)

                            else:
                                mat_node.setInput(input_slots['transl_weight'], tex_node)

                        elif tex_type in spec_names:
                            mat_node.setInput(input_slots['spec'], tex_node)

                        elif tex_type in gloss_names:
                            rough_exists = True
                            mat_node.parm(parm_names['roughness']).set(1)
                
                            if engine == 'Redshift':
                                mat_node.parm("refl_isGlossiness").set("1")
                                mat_node.setInput(input_slots['gloss'], tex_node)

                            elif engine == 'Arnold':
                                invert_node = mat_builder_node.createNode("arnold::color_correct")
                                invert_node.setInput(0, tex_node)
                                invert_node.parm("invert").set("1")
                                mat_node.setInput(input_slots['gloss'], invert_node)

                            elif engine == 'Renderman':
                                invert_node = mat_builder_node.createNode("pxrinvert::22")
                                invert_node.setInput(0, tex_node)
                                mat_node.setInput(input_slots['gloss'], invert_node)

                            elif engine == 'Octane':
                                tex_node.parm("invert").set("1")
                                mat_node.setInput(input_slots['gloss'], tex_node)

                            else:
                                mat_node.setInput(input_slots['gloss'], tex_node)

                        elif tex_type in rough_names:
                            rough_exists = True
                            mat_node.parm(parm_names['roughness']).set(1)

                            if engine == 'VRay':
                                mat_node.parm("option_use_roughness").set("1")

                            mat_node.setInput(input_slots['rough'], tex_node)

                        elif tex_type in opc_names:
                            opc_exists = True

                            if engine == 'Redshift':
                                if self.ui.opc_as_stencil.isChecked() == True:
                                    sprite_node = mat_builder_node.createNode("redshift::Sprite", tex_type)
                                    sprite_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                                    sprite_node.setInput(0, mat_node)
                                    mat_out_node.setInput(0, sprite_node)

                                else:
                                    tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                    tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                                    mat_node.setInput(47, tex_node)

                            elif engine == 'Renderman':
                                mat_node.setInput(input_slots['opc'], tex_node, 1)
                            
                            else:
                                # tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                # tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                                mat_node.setInput(input_slots['opc'], tex_node)

                                if engine == 'VRay':
                                    if is_leaf != None:
                                        back_mat_node.setInput(input_slots['opc'], tex_node)

                                        if self.ui.opc_as_stencil.isChecked() == True:
                                            front_mat_node.parm("opacity_mode").set("1")
                                            back_mat_node.parm("opacity_mode").set("1")

                                    else:
                                        if self.ui.opc_as_stencil.isChecked() == True:
                                            mat_node.parm("opacity_mode").set("1")
                        
                        elif tex_type in nml_names:
                            normal_exists = True
                            if engine in ['Arnold', 'Redshift', 'Renderman']:
                                normal_node = mat_builder_node.createNode(node_names['bump'])
                                normal_node.setInput(1, tex_node)
                                mat_node.setInput(input_slots['normal'], normal_node)

                                if engine == 'Redshift':
                                    normal_node.parm("inputType").set("1")
                                elif engine == 'Arnold':
                                    normal_node.parm("color_to_signed").set("0")

                            elif engine == 'Octane':
                                mat_node.setInput(input_slots['normal'], tex_node)

                            elif engine == 'VRay':
                                normal_node = mat_builder_node.createNode(node_names['bump'])

                                if is_leaf != None:
                                    normal_node.setInput(0, twoside_mat_node)
                                else:
                                    normal_node.setInput(0, mat_node)
                                    
                                normal_node.parm("map_type").set("1")
                                normal_node.setInput(3, tex_node)

                                mat_out_node.setInput(0, normal_node)
                        
                        if is_leaf != None:
                            if transl_weight_exists == False:
                                if engine == 'VRay':
                                    twoside_mat_node.setParms({"translucency_texr": 0.3, "translucency_texg": 0.3, "translucency_texb": 0.3})

                                elif engine == 'Octane':
                                    try:
                                        transl_color_node.parm("power").set(0.3)
                                    except:
                                        pass

                                elif engine != 'Octane':
                                    mat_node.parm(parm_names['transl_weight']).set(0.3)
                
            # User input if no opc texture could be found for a leaf texture
            if opc_exists == False and is_leaf != None:
                get_opc_tex = hou.ui.selectFromList(
                    opc_list,
                    exclusive=True,
                    title="Select Opacity Texture",
                    message="Texture for " + prim_group + " not found",
                    clear_on_cancel=True)
                    
                if len(get_opc_tex) < 1:
                    pass

                else:
                    get_base_name = opc_list[get_opc_tex[0]]
                    get_Type = get_base_name[:-4].split("_")[-1]
                    get_Ext = get_base_name[-4:]
                    get_base_name = get_base_name.replace(get_Type, "")[:-4]

                    for tex_type in all_names:
                        tex = get_base_name + tex_type + get_Ext

                        if tex.lower() in tex_list_lower:
                            index = tex_list_lower.index(tex.lower())
                            tex = tex_list[index]

                            if tex_type in ao_names and ao_exists == False:
                                tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                tex_node.parm(parm_names['tex_filename']).set(dirpath + "/" + tex)

                                ao_exists = True
                                ao_node = tex_node

                                if engine == 'VRay':
                                    if diffuse_exists == True:
                                        multiply_node = mat_builder_node.createNode("VRayNodeTexRGBMultiplyMax")
                                        multiply_node.setInput(0, diffuse_node)
                                        multiply_node.setInput(1, tex_node)
                                        mat_node.setInput(0, multiply_node)
                                
                                elif engine == 'Octane':
                                    if diffuse_exists == True:
                                        diffuse_node.setInput(0, tex_node)

                                else:
                                    mat_node.setInput(input_slots['ao'], tex_node)

                            elif tex_type in spec_names and spec_exists == False:
                                tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                tex_node.parm(parm_names['tex_filename']).set(dirpath + "/" + tex)

                                spec_exists = True
                                mat_node.setInput(input_slots['spec'], tex_node)
                            
                            elif tex_type in gloss_names and rough_exists == False:
                                tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                tex_node.parm(parm_names['tex_filename']).set(dirpath + "/" + tex)

                                rough_exists = True
                                mat_node.parm(parm_names['roughness']).set(1)
                
                                if engine == 'Redshift':
                                    mat_node.parm("refl_isGlossiness").set("1")
                                    mat_node.setInput(input_slots['gloss'], tex_node)

                                elif engine == 'Arnold':
                                    invert_node = mat_builder_node.createNode("arnold::color_correct")
                                    invert_node.setInput(0, tex_node)
                                    invert_node.parm("invert").set("1")
                                    mat_node.setInput(input_slots['gloss'], invert_node)

                                elif engine == 'Renderman':
                                    invert_node = mat_builder_node.createNode("pxrinvert::22")
                                    invert_node.setInput(0, tex_node)
                                    mat_node.setInput(input_slots['gloss'], invert_node)

                                elif engine == 'Octane':
                                    tex_node.parm("invert").set("1")
                                    mat_node.setInput(input_slots['gloss'], tex_node)

                                else:
                                    mat_node.setInput(input_slots['gloss'], tex_node)

                            elif tex_type in rough_names and rough_exists == False:
                                tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                tex_node.parm(parm_names['tex_filename']).set(dirpath + "/" + tex)

                                rough_exists = True
                                mat_node.parm(parm_names['roughness']).set(1)

                                if engine == 'VRay':
                                    mat_node.parm("option_use_roughness").set("1")

                                mat_node.setInput(input_slots['rough'], tex_node)

                            elif tex_type in opc_names:
                                opc_exists = True

                                if engine == 'Redshift':
                                    if self.ui.opc_as_stencil.isChecked() == True:
                                        sprite_node = mat_builder_node.createNode("redshift::Sprite", tex_type)
                                        sprite_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                                        sprite_node.setInput(0, mat_node)
                                        mat_out_node.setInput(0, sprite_node)

                                    else:
                                        tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                        tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                                        mat_node.setInput(47, tex_node)

                                elif engine == 'Renderman':
                                    tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                    tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                                    mat_node.setInput(input_slots['opc'], tex_node, 1)
                                
                                else:
                                    tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                    tex_node.parm(parm_names['tex_filename']).set(dirpath + tex)
                                    mat_node.setInput(input_slots['opc'], tex_node)

                                    if engine == 'VRay':
                                        if is_leaf != None:
                                            back_mat_node.setInput(input_slots['opc'], tex_node)

                                            if self.ui.opc_as_stencil.isChecked() == True:
                                                twoside_mat_node.parm("opacity_mode").set("1")
                                                back_mat_node.parm("opacity_mode").set("1")

                                        else:
                                            if self.ui.opc_as_stencil.isChecked() == True:
                                                mat_node.parm("opacity_mode").set("1")

                            elif tex_type in nml_names and normal_exists == False:
                                tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                tex_node.parm(parm_names['tex_filename']).set(dirpath + "/" + tex)
                                
                                normal_exists = True
                                if engine in ['Arnold', 'Redshift', 'Renderman']:
                                    normal_node = mat_builder_node.createNode(node_names['bump'])
                                    normal_node.setInput(1, tex_node)
                                    mat_node.setInput(input_slots['normal'], normal_node)

                                    if engine == 'Redshift':
                                        normal_node.parm("inputType").set("1")

                                    elif engine == 'Arnold':
                                        normal_node.parm("color_to_signed").set("0")

                                elif engine == 'Octane':
                                    mat_node.setInput(input_slots['normal'], tex_node)

                                elif engine == 'Renderman':
                                    mat_node.setInput(input_slots['normal'], tex_node)

                                elif engine == 'VRay':
                                    normal_node = mat_builder_node.createNode(node_names['bump'])

                                    if is_leaf != None:
                                        normal_node.setInput(0, twoside_mat_node)
                                    else:
                                        normal_node.setInput(0, mat_node)

                                    normal_node.parm("map_type").set("1")
                                    normal_node.setInput(3, tex_node)

                                    mat_out_node.setInput(0, normal_node)

                            elif tex_type == 'subsurfaceamount':
                                tex_node = mat_builder_node.createNode(node_names['texture_node'], tex_type)
                                tex_node.parm(parm_names['tex_filename']).set(dirpath + "/" + tex)
                                
                                transl_weight_exists = True

                                if engine == 'Octane':
                                    transl_weight_node = tex_node
                                    if transl_color_exists == True:
                                        if prim_group.lower() + "_subsurfacecolor.png" not in tex_list_lower:
                                            transl_color_node.setInput(1, tex_node)
                                        else:
                                            transl_color_node.setInput(0, tex_node)

                                elif engine == 'VRay':
                                    twoside_mat_node.setInput(2, tex_node)

                                else:
                                    mat_node.setInput(input_slots['transl_weight'], tex_node)

                            self.adjust_gamma(tex_node, tex_type) #  Set linear or sRGB Gamma

            # Set roughness values if no roughness texture was found
            if is_leaf != None and rough_exists == False:
                mat_node.parm(parm_names['roughness']).set("0.2")
            elif is_leaf == None and rough_exists == False:
                mat_node.parm(parm_names['roughness']).set("0.8")

            # Collapse nodes
            for node in mat_builder_node.children():
                node.setDetailMediumFlag(True)

            mat_builder_node.layoutChildren()
            self.createOGL(mat_builder_node, mat_node)

        # Layout
        matnet.layoutChildren()
        geo_node.layoutChildren()
        geo_node.moveToGoodPosition()

    def adjust_gamma(self, tex_node, tex_type):
        if self.ui.diff_is_linear.isChecked() == True:
            try:
                tex_node.parm(parm_names['gamma'][0]).set(parm_names['gamma'][1])
            except:
                pass
        else:
            if tex_type not in ['diffuse', 'subsurfacecolor'] and tex_type in all_names:
                try:
                    tex_node.parm(parm_names['gamma'][0]).set(parm_names['gamma'][1])
                except:
                    pass
    
    def convert_backslash(self, path):
        """
        Convert backslash to forwardslash.
        """

        return path.replace("\\", "/")
        
    def createOGL(self, material_builder, material):
        """This function creates all OGL tags needed on the RS Material Builder and
        links them to the appropriate parameters inside the builder"""

        # Get paths to RS Material Builder and RS Uber Material
        material_path = material_builder.relativePathTo(material)
        material_builder_path = material_builder.name()
        material_builder_children = material_builder.children()

        filepath_parm = parm_names['tex_filename']

        # Initialize paths
        diffuse_path = ""
        ao_path = ""
        normal_path = ""
        rough_path = ""
        gloss_path = ""
        spec_path = ""
        opc_path = ""

        for i in range(len(material_builder_children)):
            if str(material_builder_children[i]) in diff_names:
                diffuse_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) in ao_names:
                ao_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) in nml_names:
                normal_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) in rough_names:
                rough_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) in gloss_names:
                gloss_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) in spec_names:
                spec_path = material_builder.relativePathTo(material_builder_children[i])
            elif str(material_builder_children[i]) in opc_names:
                opc_path = material_builder.relativePathTo(material_builder_children[i])

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

        ogl_template_item1 = hou.FloatParmTemplate("ogl_emit", "Emission", 3, naming_scheme = hou.parmNamingScheme.RGBA)
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

        ogl_template_item1 = hou.ToggleParmTemplate("ogl_use_specmap", "Use Specular Map", default_value = False)
        ogl_template_folder2.addParmTemplate(ogl_template_item1)

        ogl_template_item1 = hou.StringParmTemplate("ogl_specmap", "Specular Map", 1, file_type = hou.fileType.Image, string_type = hou.stringParmType.FileReference)
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
                material_builder.parm("ogl_tex1").set("`chs('"+diffuse_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_texuvset1").set("`chs('"+diffuse_path+"/tspace_id')`", hou.exprLanguage.Hscript)

            material_builder.parm("ogl_specr").setExpression("ch('"+material_path+"/refl_colorr')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_specg").setExpression("ch('"+material_path+"/refl_colorg')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_specb").setExpression("ch('"+material_path+"/refl_colorb')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_spec_intensity").setExpression("ch('"+material_path+"/refl_weight')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_rough").setExpression("ch('"+material_path+"/refl_roughness')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_ior").setExpression("ch('"+material_path+"/refl_ior')", hou.exprLanguage.Hscript)

            if len(spec_path) > 0:
                material_builder.parm("ogl_use_specmap").set(1)
                material_builder.parm("ogl_specmap").set("`chs('"+spec_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            if len(rough_path) > 0:
                material_builder.parm("ogl_roughmap").set("`chs('"+rough_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            elif len(gloss_path) > 0:
                material_builder.parm("ogl_invertroughmap").set(1)
                material_builder.parm("ogl_roughmap").set("`chs('"+gloss_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            if len(normal_path) > 0:
                material_builder.parm("ogl_normalmap").set("`chs('"+normal_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_normalmap_scale").setExpression("ch(BumpMap1/scale)")
                material_builder.parm("ogl_normalflipy").setExpression("ch(BumpMap1/flipY)")

            if len(opc_path) > 0:
                material_builder.parm("ogl_use_alpha_transparency").set(1)
                material_builder.parm("ogl_use_opacitymap").set(1)
                material_builder.parm("ogl_opacitymap").set("`chs('"+opc_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_transparency").set(0)

        elif engine == 'VRay':
            material_builder.parm("ogl_diffr").setExpression("ch('"+material_path+"/diffuser')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffg").setExpression("ch('"+material_path+"/diffuseg')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffb").setExpression("ch('"+material_path+"/diffuseb')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diff_rough").setExpression("ch('"+material_path+"/roughness')", hou.exprLanguage.Hscript)

            if len(diffuse_path) > 0:
                material_builder.parm("ogl_tex1").set("`chs('"+diffuse_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_texuvset1").set("`chs('"+diffuse_path+"/UVWGenMayaPlace2dTexture_uv_set_name')`", hou.exprLanguage.Hscript)

            material_builder.parm("ogl_specr").setExpression("ch('"+material_path+"/reflectr')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_specg").setExpression("ch('"+material_path+"/reflectg')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_specb").setExpression("ch('"+material_path+"/reflectb')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_rough").setExpression("ch('"+material_path+"/reflect_glossiness')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_ior").setExpression("ch('"+material_path+"/refract_ior')", hou.exprLanguage.Hscript)

            if len(spec_path) > 0:
                material_builder.parm("ogl_use_specmap").set(1)
                material_builder.parm("ogl_specmap").set("`chs('"+spec_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            if len(rough_path) > 0:
                material_builder.parm("ogl_roughmap").set("`chs('"+rough_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            elif len(gloss_path) > 0:
                material_builder.parm("ogl_invertroughmap").set(1)
                material_builder.parm("ogl_roughmap").set("`chs('"+gloss_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            if len(normal_path) > 0:
                material_builder.parm("ogl_normalmap").set("`chs('"+normal_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_normalmap_scale").setExpression("ch(VRayNodeBRDFBump1/bump_tex_mult)")

            if len(opc_path) > 0:
                material_builder.parm("ogl_use_alpha_transparency").set(1)
                material_builder.parm("ogl_use_opacitymap").set(1)
                material_builder.parm("ogl_opacitymap").set("`chs('"+opc_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_transparency").set(0)

        elif engine == 'Octane':
            material_builder.parm("ogl_diffr").setExpression("ch('"+material_path+"/albedor')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffg").setExpression("ch('"+material_path+"/albedog')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffb").setExpression("ch('"+material_path+"/albedob')", hou.exprLanguage.Hscript)

            if len(diffuse_path) > 0:
                material_builder.parm("ogl_tex1").set("`chs('"+diffuse_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            material_builder.parm("ogl_spec_intensity").setExpression("ch('"+material_path+"/specular')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_rough").setExpression("ch('"+material_path+"/roughness')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_ior").setExpression("ch('"+material_path+"/index4')", hou.exprLanguage.Hscript)

            if len(spec_path) > 0:
                material_builder.parm("ogl_use_specmap").set(1)
                material_builder.parm("ogl_specmap").set("`chs('"+spec_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            if len(rough_path) > 0:
                material_builder.parm("ogl_roughmap").set("`chs('"+rough_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            elif len(gloss_path) > 0:
                material_builder.parm("ogl_invertroughmap").set(1)
                material_builder.parm("ogl_roughmap").set("`chs('"+gloss_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            if len(normal_path) > 0:
                material_builder.parm("ogl_normalmap").set("`chs('"+normal_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_normalmap_scale").setExpression("chs('"+normal_path+"/power')")

            if len(opc_path) > 0:
                material_builder.parm("ogl_use_alpha_transparency").set(1)
                material_builder.parm("ogl_use_opacitymap").set(1)
                material_builder.parm("ogl_opacitymap").set("`chs('"+opc_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_transparency").set(0)

        elif engine == 'Renderman':
            material_builder.parm("ogl_diffr").setExpression("ch('"+material_path+"/diffuseColorr')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffg").setExpression("ch('"+material_path+"/diffuseColorg')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffb").setExpression("ch('"+material_path+"/diffuseColorb')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diff_intensity").setExpression("ch('"+material_path+"/diffuseGain')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diff_rough").setExpression("ch('"+material_path+"/diffuseRoughness')", hou.exprLanguage.Hscript)

            if len(diffuse_path) > 0:
                material_builder.parm("ogl_tex1").set("`chs('"+diffuse_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            material_builder.parm("ogl_spec_intensity").setExpression("ch('"+material_path+"/specularEdgeColorr')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_rough").setExpression("ch('"+material_path+"/specularRoughness')", hou.exprLanguage.Hscript)

            if len(spec_path) > 0:
                material_builder.parm("ogl_use_specmap").set(1)
                material_builder.parm("ogl_specmap").set("`chs('"+spec_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            if len(rough_path) > 0:
                material_builder.parm("ogl_roughmap").set("`chs('"+rough_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            elif len(gloss_path) > 0:
                material_builder.parm("ogl_invertroughmap").set(1)
                material_builder.parm("ogl_roughmap").set("`chs('"+gloss_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            if len(normal_path) > 0:
                material_builder.parm("ogl_normalmap").set("`chs('"+normal_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_normalmap_scale").setExpression("ch(pxrnormalmap1/bumpScale)")
                material_builder.parm("ogl_normalflipy").setExpression("ch(pxrnormalmap1/flipY)")
                material_builder.parm("ogl_normalflipx").setExpression("ch(pxrnormalmap1/flipX)")

            if len(opc_path) > 0:
                material_builder.parm("ogl_use_alpha_transparency").set(1)
                material_builder.parm("ogl_use_opacitymap").set(1)
                material_builder.parm("ogl_opacitymap").set("`chs('"+opc_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_transparency").set(0)

        elif engine == 'Arnold':
            material_builder.parm("ogl_diffr").setExpression("ch('"+material_path+"/base_colorr')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffg").setExpression("ch('"+material_path+"/base_colorg')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diffb").setExpression("ch('"+material_path+"/base_colorb')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diff_intensity").setExpression("ch('"+material_path+"/base')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_diff_rough").setExpression("ch('"+material_path+"/diffuse_roughness')", hou.exprLanguage.Hscript)

            if len(diffuse_path) > 0:
                material_builder.parm("ogl_tex1").set("`chs('"+diffuse_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_texuvset1").set("uv")

            material_builder.parm("ogl_specr").setExpression("ch('"+material_path+"/specular_colorr')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_specg").setExpression("ch('"+material_path+"/specular_colorg')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_specb").setExpression("ch('"+material_path+"/specular_colorb')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_spec_intensity").setExpression("ch('"+material_path+"/specular')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_rough").setExpression("ch('"+material_path+"/specular_roughness')", hou.exprLanguage.Hscript)
            material_builder.parm("ogl_ior").setExpression("ch('"+material_path+"/specular_IOR')", hou.exprLanguage.Hscript)

            if len(spec_path) > 0:
                material_builder.parm("ogl_use_specmap").set(1)
                material_builder.parm("ogl_specmap").set("`chs('"+spec_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            if len(rough_path) > 0:
                material_builder.parm("ogl_roughmap").set("`chs('"+rough_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            elif len(gloss_path) > 0:
                material_builder.parm("ogl_invertroughmap").set(1)
                material_builder.parm("ogl_roughmap").set("`chs('"+gloss_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)

            if len(normal_path) > 0:
                material_builder.parm("ogl_normalmap").set("`chs('"+normal_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_normalmap_scale").setExpression("ch(normal_map1/strength)")
                material_builder.parm("ogl_normalflipy").setExpression("ch(normal_map1/invert_y)")

            if len(opc_path) > 0:
                material_builder.parm("ogl_use_alpha_transparency").set(1)
                material_builder.parm("ogl_use_opacitymap").set(1)
                material_builder.parm("ogl_opacitymap").set("`chs('"+opc_path+"/"+filepath_parm+"')`", hou.exprLanguage.Hscript)
                material_builder.parm("ogl_transparency").set(0)

_SpeedTreeImporter = None

def show():
    global _SpeedTreeImporter
    if _SpeedTreeImporter is None:
        _SpeedTreeImporter = SpeedTreeImporter()
    _SpeedTreeImporter.show()