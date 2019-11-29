import hou, os, sys, icons, numpy

from PySide2.QtCore import *
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtUiTools import *

scriptpath = os.path.dirname(__file__)
dmnk_path = hou.getenv("dmnk")
configpath = dmnk_path + "/config/samples_editor_config"

button_dict = None
mats = None
lights = None
rop = None
bundle_list = None

# STYLESHEETS
custom_style = """
QTreeWidget { border: none; outline: none; border-radius: 5px; } 
QTreeWidget::item:!selected, QTreeWidget::item:selected { border: none; }
QTreeWidget::branch:has-siblings:!adjoins-item { border-image: url(:/resources/branch-vline.svg) 0; }
QTreeView::branch:has-siblings:adjoins-item { border-image: url(:/resources/branch-more.svg) 0; }
QTreeView::branch:!has-children:!has-siblings:adjoins-item { border-image: url(:/resources/branch-end.svg) 0; }
QTreeView::branch:has-children:!has-siblings:closed,
QTreeView::branch:closed:has-children:has-siblings { margin: 4px; border-image: none; image: url(:/resources/collapsed.svg);}
QTreeView::branch:open:has-children:!has-siblings,
QTreeView::branch:open:has-children:has-siblings { margin: 4px; border-image: none; image: url(:/resources/opened.svg); }
QGroupBox::indicator:unchecked { image: url(:/resources/collapsed.svg); }
QGroupBox::indicator:checked { image: url(:/resources/opened.svg); }
"""

class SamplesEditor(QWidget):
    def __init__(self):
        super(SamplesEditor, self).__init__(hou.qt.mainWindow())

        # Create UI
        self.createUi()

    def createUi(self):
        # Initialize settings
        self.settings = QSettings(configpath, QSettings.IniFormat)

        self.setWindowTitle('DMNK - Samples Editor')
        self.setWindowFlags(Qt.Dialog)
        self.resize(self.settings.value("size", QSize(hou.ui.scaledSize(800), hou.ui.scaledSize(500))))
        self.move(self.settings.value("pos", QPoint(0, 0)))

        # Load UI
        loader = QUiLoader()
        self.ui = loader.load(scriptpath + '/samples_editor_ui.ui')

        margin = hou.ui.scaledSize(0)
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.ui)
        mainLayout.setContentsMargins(margin, margin, margin, margin)
        mainLayout.setSpacing(margin)
        self.setLayout(mainLayout)

        rop_chooser = hou.qt.NodeChooserButton()
        rop_chooser.setNodeChooserFilter(hou.nodeTypeFilter.Rop) 
        self.ui.horizontalLayout.addWidget(rop_chooser)
        rop_chooser.nodeSelected.connect(self.onNodeSelected)

        # Set Stylesheets
        self.ui.mat_treewidget.setStyleSheet(custom_style)
        self.ui.light_treewidget.setStyleSheet(custom_style)
        self.ui.rop_box.setStyleSheet(custom_style)
        self.ui.mat_box.setStyleSheet(custom_style)
        self.ui.light_box.setStyleSheet(custom_style)
        self.ui.splitter.setStyleSheet( "QSplitter:handle { background: none; }")

        # Set material and Light list minimum size
        min_size = hou.ui.scaledSize(150)
        self.ui.mat_treewidget.setMinimumSize(min_size, 0)
        self.ui.light_treewidget.setMinimumSize(min_size, 0)

        # Button dict that maps the doubling QPushButton to the corresponding QLineEdit and sample parameter
        global button_dict
        button_dict = {
            self.ui.prog_passes_double: [self.ui.prog_passes, "ProgressiveRenderingNumPasses"],
            self.ui.min_samples_double: [self.ui.min_samples, "UnifiedMinSamples"],
            self.ui.max_samples_double: [self.ui.max_samples, "UnifiedMaxSamples"],
            self.ui.bf_samples_double: [self.ui.bf_samples, "BruteForceGINumRays"],
            self.ui.refl_samples_double: [self.ui.refl_samples, "refl_samples"],
            self.ui.refr_samples_double: [self.ui.refr_samples, "refr_samples"],
            self.ui.ss_samples_double: [self.ui.ss_samples, "ss_samples"],
            self.ui.sss_samples_double: [self.ui.sss_samples, "ms_samples"],
            self.ui.coating_samples_double: [self.ui.coating_samples, "coat_samples"],
            self.ui.light_samples_double: [self.ui.light_samples, "RSL_samples"],
            self.ui.vol_samples_double: [self.ui.vol_samples, "RSL_volumeSamples"],
            self.ui.shadow_samples_double: [self.ui.shadow_samples, "SAMPLINGOVERRIDES_numShadowSamples"]
        }

        # Samples dict that maps the QLineEdit to the corresponding sample parameter
        global samples_dict
        samples_dict = {
            self.ui.prog_passes: ["ProgressiveRenderingNumPasses", None],
            self.ui.min_samples: ["UnifiedMinSamples", None],
            self.ui.max_samples: ["UnifiedMaxSamples", None],
            self.ui.AET: ["UnifiedAdaptiveErrorThreshold", [0, 1]],
            self.ui.refl_depth: ["MaxTraceDepthReflection", [0, 63]],
            self.ui.refr_depth: ["MaxTraceDepthRefraction", [0, 63]],
            self.ui.combined_depth: ["MaxTraceDepthCombined", [0, 63]],
            self.ui.transp_depth: ["MaxTraceDepthTransparency", [0, 255]],
            self.ui.bf_samples: ["BruteForceGINumRays", None],
            self.ui.refl_samples: ["refl_samples", None],
            self.ui.refr_samples: ["refr_samples", None],
            self.ui.ss_samples: ["ss_samples", None],
            self.ui.sss_samples: ["ms_samples", None],
            self.ui.coating_samples: ["coat_samples", None],
            self.ui.light_samples: ["RSL_samples", None],
            self.ui.vol_samples: ["RSL_volumeSamples", None],
            self.ui.shadow_samples: ["SAMPLINGOVERRIDES_numShadowSamples", None]
        }

        # Set all ROP parameter labels to a uniform minimum size to align all elements properly
        label_width = QSize(hou.ui.scaledSize(144), hou.ui.scaledSize(0))
        self.ui.prog_passes_label.setMinimumSize(label_width)
        self.ui.min_samples_label.setMinimumSize(label_width)
        self.ui.max_samples_label.setMinimumSize(label_width)
        self.ui.bf_samples_label.setMinimumSize(label_width)

        # Connect all doubling QPushButtons to the double_samples function
        self.ui.prog_passes_double.clicked.connect(lambda: self.double_samples("ROP", self.ui.prog_passes_double))
        self.ui.min_samples_double.clicked.connect(lambda: self.double_samples("ROP", self.ui.min_samples_double))
        self.ui.max_samples_double.clicked.connect(lambda: self.double_samples("ROP", self.ui.max_samples_double))
        self.ui.bf_samples_double.clicked.connect(lambda: self.double_samples("ROP", self.ui.bf_samples_double))

        self.ui.refl_samples_double.clicked.connect(lambda: self.double_samples("MAT", self.ui.refl_samples_double))
        self.ui.refr_samples_double.clicked.connect(lambda: self.double_samples("MAT", self.ui.refr_samples_double))
        self.ui.ss_samples_double.clicked.connect(lambda: self.double_samples("MAT", self.ui.ss_samples_double))
        self.ui.sss_samples_double.clicked.connect(lambda: self.double_samples("MAT", self.ui.sss_samples_double))
        self.ui.coating_samples_double.clicked.connect(lambda: self.double_samples("MAT", self.ui.coating_samples_double))
        self.ui.light_samples_double.clicked.connect(lambda: self.double_samples("LIGHT", self.ui.light_samples_double))
        self.ui.vol_samples_double.clicked.connect(lambda: self.double_samples("LIGHT", self.ui.vol_samples_double))
        self.ui.shadow_samples_double.clicked.connect(lambda: self.double_samples("LIGHT", self.ui.shadow_samples_double))

        # Connect all QLineEdits to the proper update samples function
        self.ui.prog_passes.editingFinished.connect(lambda: self.update_rop_samples(rop, self.ui.prog_passes))
        self.ui.min_samples.editingFinished.connect(lambda: self.update_rop_samples(rop, self.ui.min_samples))
        self.ui.max_samples.editingFinished .connect(lambda: self.update_rop_samples(rop, self.ui.max_samples))
        self.ui.AET.editingFinished.connect(lambda: self.update_rop_samples(rop, self.ui.AET))
        self.ui.bf_samples.editingFinished.connect(lambda: self.update_rop_samples(rop, self.ui.bf_samples))
        self.ui.refl_depth.editingFinished.connect(lambda: self.update_rop_samples(rop, self.ui.refl_depth))
        self.ui.refr_depth.editingFinished.connect(lambda: self.update_rop_samples(rop, self.ui.refr_depth))
        self.ui.combined_depth.editingFinished.connect(lambda: self.update_rop_samples(rop, self.ui.combined_depth))
        self.ui.transp_depth.editingFinished.connect(lambda: self.update_rop_samples(rop, self.ui.transp_depth))

        self.ui.refl_samples.editingFinished.connect(lambda: self.update_samples(self.ui.refl_samples, self.ui.mat_treewidget, mats))
        self.ui.refr_samples.editingFinished.connect(lambda: self.update_samples(self.ui.refr_samples, self.ui.mat_treewidget, mats))
        self.ui.ss_samples.editingFinished.connect(lambda: self.update_samples(self.ui.ss_samples, self.ui.mat_treewidget, mats))
        self.ui.sss_samples.editingFinished.connect(lambda: self.update_samples(self.ui.sss_samples, self.ui.mat_treewidget, mats))
        self.ui.coating_samples.editingFinished.connect(lambda: self.update_samples(self.ui.coating_samples, self.ui.mat_treewidget, mats))

        self.ui.light_samples.editingFinished.connect(lambda: self.update_samples(self.ui.light_samples, self.ui.light_treewidget, lights))
        self.ui.vol_samples.editingFinished.connect(lambda: self.update_samples(self.ui.vol_samples, self.ui.light_treewidget, lights))
        self.ui.shadow_samples.editingFinished.connect(lambda: self.update_samples(self.ui.shadow_samples, self.ui.light_treewidget, lights))

        # Connect the click signal of items in the mat or light list to the insert samples function
        self.ui.mat_treewidget.itemClicked.connect(self.insert_mat_samples)
        self.ui.light_treewidget.itemClicked.connect(self.insert_light_samples)

        # Connect the expanding and collapsing of QTreeWidget items to the corresponding functions
        self.ui.light_treewidget.itemCollapsed.connect(lambda: self.collapse_items(self.ui.light_treewidget))
        self.ui.mat_treewidget.itemCollapsed.connect(lambda: self.collapse_items(self.ui.mat_treewidget))
        self.ui.light_treewidget.itemExpanded.connect(lambda: self.expand_items(self.ui.light_treewidget))
        self.ui.mat_treewidget.itemExpanded.connect(lambda: self.expand_items(self.ui.mat_treewidget))

        # Connect the toggling of the QGroupBoxes to the open_settings function
        self.ui.rop_box.toggled.connect(lambda: self.open_settings(self.ui.rop_box))
        self.ui.mat_box.toggled.connect(lambda: self.open_settings(self.ui.mat_box))
        self.ui.light_box.toggled.connect(lambda: self.open_settings(self.ui.light_box))

        # Parse the scene to get all lights and mats
        self.parse_scene()

    def hideEvent(self, event):
        """
        When window is closed store position and size in config.
        """

        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
    
    def open_settings(self, widget):
        if widget.isChecked() == False:
            widget.setMaximumSize(16777215, 20)
        else:
            widget.setMaximumSize(16777215, 16777215)

    def onNodeSelected(self, node):
        try:
            global rop
            rop = node
            prog_passes = rop.parm("ProgressiveRenderingNumPasses").eval()
            uni_min_samples = rop.parm("UnifiedMinSamples").eval()
            uni_max_samples = rop.parm("UnifiedMaxSamples").eval()
            aet = rop.parm("UnifiedAdaptiveErrorThreshold").eval()
            bf_samples = rop.parm("BruteForceGINumRays").eval()
            refl_depth = rop.parm("MaxTraceDepthReflection").eval()
            refr_depth = rop.parm("MaxTraceDepthRefraction").eval()
            combined_depth = rop.parm("MaxTraceDepthCombined").eval()
            transp_depth = rop.parm("MaxTraceDepthTransparency").eval()

            # Set ROP sample QLineEdit text to the evaluated samples value
            self.ui.prog_passes.setText(str(prog_passes))
            self.ui.min_samples.setText(str(uni_min_samples))
            self.ui.max_samples.setText(str(uni_max_samples))
            self.ui.AET.setText(str(round(aet, 3)))
            self.ui.bf_samples.setText(str(bf_samples))
            self.ui.refl_depth.setText(str(refl_depth))
            self.ui.refr_depth.setText(str(refr_depth))
            self.ui.combined_depth.setText(str(combined_depth))
            self.ui.transp_depth.setText(str(transp_depth))
            
            self.ui.rop.setText(node.path())
        except:
            sys.exit()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F5:
            self.parse_scene()
            try:
                self.onNodeSelected(hou.node(self.ui.rop.text()))
            except: pass

    def expand_items(self, widget):
        if QGuiApplication.keyboardModifiers() == Qt.ShiftModifier:
            for i in range(widget.topLevelItemCount()):
                item = widget.topLevelItem(i)
                try:
                    item.setExpanded(True)
                except: pass

    def collapse_items(self, widget):
        if QGuiApplication.keyboardModifiers() == Qt.ShiftModifier:
            for i in range(widget.topLevelItemCount()):
                item = widget.topLevelItem(i)
                try:
                    item.setExpanded(False)
                except: pass

    def insert_mat_samples(self, item, column):
        for node in mats:
            if item.text(0) == node.path():
                for i in range(len(mats[node])):
                    sample_parm = mats[node][i][0]
                    ui_samples = mats[node][i][1]
                    amount_samples = node.parm(sample_parm).eval()

                    ui_samples.setText(str(amount_samples))

    def insert_light_samples(self, item, column):
        for node in lights:
            if item.text(0) == node.path():
                for i in range(len(lights[node])):
                    sample_parm = lights[node][i][0]
                    ui_samples = lights[node][i][1]

                    try:
                        amount_samples = node.parm(sample_parm).eval()
                    except:
                        amount_samples = None

                    ui_samples.setText("")
                    ui_samples.setDisabled(False)

                    if amount_samples != None:
                        ui_samples.setText(str(amount_samples))
                    else:
                        ui_samples.setDisabled(True)

    def double_samples(self, node_type, btn):
        if node_type == "ROP":
            mats_lights = None
        elif node_type == "MAT":
            mats_lights = mats
            widget = self.ui.mat_treewidget
        elif node_type == "LIGHT":
            mats_lights = lights
            widget = self.ui.light_treewidget

        if mats_lights == None:
            nodes = [rop]
        else:
            sel_items = widget.selectedItems()
            bundle_list_names = [x.name() for x in bundle_list]
            node_paths = [x.path() for x in mats_lights.keys()]
            nodes = []

            for item in sel_items:
                if item.text(0) in bundle_list_names:
                    i = bundle_list_names.index(item.text(0))
                    nodes_temp = bundle_list[i].nodes()

                    for node in nodes_temp:
                        if node.type().name() == "redshift_vopnet":
                            get_childs = node.children()
                            for child in get_childs:
                                if child.type().name() == "redshift::Material":
                                    nodes.append(child)

                elif item.text(0) in node_paths:
                    i = node_paths.index(item.text(0))
                    nodes.append(mats_lights.keys()[i])

        for node in nodes:
            ui_samples = button_dict[btn][0]
            sample_parm = button_dict[btn][1]

            if btn == self.ui.shadow_samples_double:
                if node.type().name() == 'rslightsun':
                    sample_parm = "PhysicalSun1_" + sample_parm
                elif node.type().name() == 'rslight':
                    sample_parm = "Light1_" + sample_parm

            try:
                cur_val = node.parm(sample_parm).eval()

                if QGuiApplication.keyboardModifiers() == Qt.ShiftModifier:
                    if cur_val > 1:
                        new_val = cur_val / 2
                    else:
                        pass
                else:
                    new_val = cur_val * 2

                ui_samples.setText(str(new_val))
                node.parm(sample_parm).set(new_val)
            except: pass

    def update_samples(self, sample, treewidget, mats_lights):
        sel_items = treewidget.selectedItems()
        bundle_list_names = [x.name() for x in bundle_list]
        for item in sel_items:
            if item.text(0) in bundle_list_names:
                i = bundle_list_names.index(item.text(0))
                nodes = bundle_list[i].nodes()

            else:
                nodes = []
                for node in mats_lights.keys():
                    if item.text(0) == node.path():
                        nodes.append(node)

            for node in nodes:
                sample_parm = samples_dict[sample][0]

                if sample == self.ui.shadow_samples:
                    if node.type().name() == 'rslightsun':
                        sample_parm = "PhysicalSun1_" + sample_parm
                    elif node.type().name() == 'rslight':
                        sample_parm = "Light1_" + sample_parm

                try:
                    amount_samples = int(float(sample.text()))
                except: break 

                try:
                    node.parm(sample_parm).set(amount_samples)
                except: pass

    def update_rop_samples(self, rop, sample):
        rop_parm = samples_dict[sample][0]
        minmax = samples_dict[sample][1]
        if sample == self.ui.AET:
            amount_samples = numpy.clip(float(sample.text()), minmax[0], minmax[1])
        else:
            if minmax != None:
                amount_samples = numpy.clip(int(float(sample.text())), minmax[0], minmax[1])
            else:
                amount_samples = int(float(sample.text()))
            
        rop.parm(rop_parm).set(amount_samples)

        self.onNodeSelected(hou.node(self.ui.rop.text()))

    def add_items(self, mat_light_list, widget_type):
        bundles = hou.nodeBundles()
        temp_mat_light_list = []

        global bundle_list
        bundle_list = []
        for bundle in bundles:
            has_bundle = False
            bundle_list.append(bundle)
            if len(bundle.nodes()) < 1:
                    pass
            else:
                for i in mat_light_list:
                    if i in bundle.nodes() or i.parent() in bundle.nodes():
                        if has_bundle == False:
                            item = QTreeWidgetItem(widget_type, [bundle.name()])
                            has_bundle = True
                        if i not in temp_mat_light_list:
                            child = QTreeWidgetItem(item, [i.path()])
                            temp_mat_light_list.append(i)

        for i in mat_light_list:
            if i not in temp_mat_light_list:
                item = QTreeWidgetItem(widget_type, [i.path()])
                temp_mat_light_list.append(i)

    def parse_scene(self):
        self.ui.mat_treewidget.clear()
        self.ui.light_treewidget.clear()
        obj_net = hou.node("obj")
        mat_net = hou.node("mat")
        out_net = hou.node("out")
        shop_net = hou.node("shop")

        global mats
        global lights
        mats = {}
        lights = {}
        node_list = []

        def recurse(node):
            if node.type().name() in ["redshift::Material", "rslight", "rslightdome::2.0", "rslighties", "rslightportal", "rslightsun"]:
                node_list.append(node)
            else:
                try:
                    get_childs = node.children()
                    if get_childs:
                        for child in get_childs:
                            recurse(child)
                except: pass

        for network in [obj_net, mat_net, out_net]:
            recurse(network)

        for node in node_list:
            node_type = node.type().name()
            if node_type == "redshift::Material":
                mats[node] = [["refl_samples", self.ui.refl_samples], ["refr_samples", self.ui.refr_samples], ["ss_samples", self.ui.ss_samples], ["ms_samples", self.ui.sss_samples], ["coat_samples", self.ui.coating_samples]]

            elif node_type in ["rslight", "rslightdome::2.0", "rslightportal"]:
                lights[node] = [["RSL_samples", self.ui.light_samples], ["RSL_volumeSamples", self.ui.vol_samples], ["Light1_SAMPLINGOVERRIDES_numShadowSamples", self.ui.shadow_samples]]
            
            elif node_type == "rslighties":
                lights[node] = [["RSL_samples", self.ui.light_samples], ["RSL_volumeSamples", self.ui.vol_samples], ["SAMPLINGOVERRIDES_numShadowSamples", self.ui.shadow_samples]]

            elif node_type == "rslightsun":
                lights[node] = [["RSL_samples", self.ui.light_samples], ["RSL_volumeSamples", self.ui.vol_samples], ["PhysicalSun1_SAMPLINGOVERRIDES_numShadowSamples", self.ui.shadow_samples]]

        self.add_items(mats, self.ui.mat_treewidget)
        self.add_items(lights, self.ui.light_treewidget)

_SamplesEditor = None

def show():
    global _SamplesEditor
    if _SamplesEditor is None:
        _SamplesEditor = SamplesEditor()
    _SamplesEditor.show()