# Redshift Texture Manager
# Originally created by Dominik Lingenover

import hou
import os
import subprocess
import threading
import math
import time
import Queue

from PySide2.QtCore import *
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtUiTools import *

# Get path to this script
scriptpath = os.path.dirname(__file__)
dmnk_path = hou.getenv("dmnk")
configpath = dmnk_path + "/config/rs_tex_manager_config"

# Find redshiftTextureProcessor.exe
try:
    texProcessorPath = hou.getenv(
        "REDSHIFT_COREDATAPATH") + "/bin/" + "redshiftTextureProcessor.exe"
except:
    texProcessorPath = "C:/ProgramData/Redshift/bin/redshiftTextureProcessor.exe"
    if not os.path.exists(texProcessorPath):
        print "WARNING: Couldn't find 'redshiftTextureProcessor.exe' !"

# UI Elements
treeview = None

# Command Line Options for redshiftTextureProcessor.exe
force_linear = None
force_sRGB = None
texture_type = ["", "-p", "-isphere", "-ihemisphere",
                "-imirrorball", "-iangularmap", "-ocolor", "-oalpha"]

# Initializing Variables for certain functions
# Extensions to look for when importing images
extensions = (".jpg", ".exr", ".tga", ".png", "tif", ".hdr")
images_dict = {}  # The main dictionary that holds texture path and command line options
get_tex_amount = 0  # Amount of textures for progress bar
p = None  # Holds the subprocess

# Icons
missing_Icon = hou.qt.Icon("BUTTONS_list_delete")
found_Icon = hou.qt.Icon("SCENEGRAPH_loaded_on")


class RsTxMngr(QWidget):
    def __init__(self):
        super(RsTxMngr, self).__init__(hou.qt.mainWindow())

        self.createUi()

    def createUi(self):
        """
        Import the UI from Qt Designer and connect functions to buttons.
        """

        self.settings = QSettings(configpath, QSettings.IniFormat)

        self.setWindowTitle('DMNK - RS Tex Manager')
        self.setWindowFlags(Qt.Dialog)
        self.resize(self.settings.value("size", QSize(hou.ui.scaledSize(800), hou.ui.scaledSize(500))))
        self.move(self.settings.value("pos", QPoint(0, 0)))

        loader = QUiLoader()
        self.ui = loader.load(scriptpath + '/rs_tex_manager_ui.ui')

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.ui)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(mainLayout)

        global treeview
        treeview = self.ui.texList

        self.ui.texList.clicked.connect(self.get_options)
        self.ui.parseScene_B.clicked.connect(self.parse_scene)
        self.ui.pickImages_B.clicked.connect(self.pick_images)
        self.ui.pickDir_B.clicked.connect(self.pick_dir)
        self.ui.clearSel_B.clicked.connect(self.clear_sel)
        self.ui.clear_B.clicked.connect(self.clear_all)
        self.ui.fSRGB_CB.clicked.connect(self.update_options)
        self.ui.fLinear_CB.clicked.connect(self.update_options)
        self.ui.texType_DD.currentIndexChanged.connect(self.update_options)
        self.ui.convertSel_B.clicked.connect(self.converttex_sel)
        self.ui.convert_B.clicked.connect(self.converttex)

    def hideEvent(self, event):
        """
        When window is closed store position and size in config.
        """

        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())

    def parse_scene(self):
        """
        Goes through all file references and if a texture is found and it exists it is added to 'tex_list'
        Items in 'tex_list' are added to the 'QTreeWidget' and to the 'images_dict'
        """

        tex_list = []
        tex_parm_names = ["file", "fileName", "tex0", "env_map"]

        file_refs = hou.fileReferences()
        for parm, string in file_refs:
            if parm != None:
                if parm.name() in tex_parm_names:
                    tex = hou.expandString(string)
                    tex = self.convert_backslash(tex)
                    if tex.endswith(extensions):
                        if os.path.isfile(tex):
                            if tex not in images_dict.keys():
                                if tex not in tex_list:
                                    tex_list.append(tex)

        for tex in tex_list:
            # Add textures to QTreeWidget
            item = QTreeWidgetItem(treeview)
            item.setText(0, tex)

        self.append_tex_to_dict(tex_list)  # Add textures to 'images_dict'
        self.resetProgress()  # Reset progress bar to 0%
        self.check_status(tex_list)

    def pick_images(self):
        """
        Adds user picked images from a file dialog.
        """

        selected_images = QFileDialog.getOpenFileNames(
            filter="All Files (*.exr *.jpg *.tga *.png *.tif *.hdr)")
        selected_images = [x.encode("utf-8") for x in selected_images[0]]
        tex_list = []

        for image in selected_images:
            if image not in images_dict.keys():
                tex_list.append(image)
                item = QTreeWidgetItem(treeview)
                item.setText(0, image)

        self.append_tex_to_dict(tex_list)
        self.resetProgress()

    def pick_dir(self):
        """
        Adds all textures from a user picked directory.
        """

        selected_dir = QFileDialog.getExistingDirectory()
        tex_list = []
        for (dirpath, dirnames, filenames) in os.walk(selected_dir):
            for filename in filenames:
                if filename.endswith(extensions):
                    image = dirpath.encode("utf-8") + \
                        "/" + filename.encode("utf-8")
                    if image not in images_dict.keys():
                        tex_list.append(image)

        for image in tex_list:
            item = QTreeWidgetItem(treeview)
            item.setText(0, image)

        self.append_tex_to_dict(tex_list)
        self.resetProgress()

    def clear_sel(self):
        """
        Clears selected images in the QTreeWidget and also removes them from 'images_dict'
        """

        items = treeview.selectedItems()
        for item in items:
            tex = item.text(0)
            treeview.takeTopLevelItem(treeview.indexOfTopLevelItem(item))
            images_dict.pop(tex, None)
        self.resetProgress()

    def clear_all(self):
        """
        Clears all textures from QTreeWidget and 'images_dict'
        """

        treeview.clear()
        images_dict.clear()
        self.resetProgress()

    def convertfiles(self, tex_list):
        """
        Main function to convert the textures.
        It's a simple for loop that goes through each texture in 'tex_list' and opens a subprocess.
        """

        get_tex_amount = len(tex_list)
        tex_space = ""
        percentage = 0

        try:
            for tex in tex_list:
                # First check if user specified linear or sRGB texture space
                if images_dict[tex][0] == True:
                    tex_space = "-s"
                elif images_dict[tex][1] == True:
                    tex_space = "-l"

                # Calculate percentage for progress bar
                percentage += math.ceil(100.0 / get_tex_amount)
                if percentage > 100:
                    percentage = 100

                # Start measuring time
                start = time.time()

                # Open subprocess and start image conversion
                global p
                p = subprocess.call(texProcessorPath + " " + "\"" + tex + "\"" + " " +
                                    tex_space + " " + texture_type[images_dict[tex][2]], shell=True)

                # End measuring time
                end = time.time()

                # Update progress bar and print to console which texture finished converting + time.
                self.ui.progressBar.setValue(percentage)
                print "[RS_Tx_Mngr]     ", tex, "converted in ", round(
                    end-start, 2), "seconds."
        except:
            print("No Textures found!")

    def converttex(self):
        """
        The function assigned to the 'Convert' button.
        """

        tex_list = []
        tex_list.extend(images_dict.keys())
        t = threading.Thread(target=self.convertfiles,
                             name="rs_thread1", args=([tex_list]))
        t.start()

    def converttex_sel(self):
        """
        The function assigned to the 'Convert Selected' button.
        Gets user selected items and appends them to 'tex_list'.
        """

        items = treeview.selectedItems()
        tex_list = []
        for item in items:
            tex = item.text(0)
            tex_list.append(tex)

        t = threading.Thread(target=self.convertfiles,
                             name="rs_thread1", args=([tex_list]))
        t.start()

    def killprocess(self):
        """
        Clears the images_dict to stop the subprocess.
        I haven't found a better way to stop the subprocesses.
        """

        global images_dict
        images_dict.clear()

    def get_options(self):
        """
        The function assigned to a click event when the user selects one or multiple textures in the QTreeWidget.
        Displays the command line options associated with the selected texture.
        Currently doesn't show indication of varying options when multiple textures are selected.(Only last selected texture)
        """

        # Get currently selected item
        get_sel_item = treeview.currentItem()
        # Get texture path
        get_sel_item_text = get_sel_item.text(0)

        # Assign UI elements to variables
        force_srgb_cb = self.ui.fSRGB_CB
        force_linear_cb = self.ui.fLinear_CB
        textype_dd_1 = self.ui.texType_DD

        # Update UI elements
        force_srgb_cb.setChecked(images_dict[get_sel_item_text][0])
        force_linear_cb.setChecked(images_dict[get_sel_item_text][1])
        textype_dd_1.setCurrentIndex(images_dict[get_sel_item_text][2])

    def update_options(self):
        """
        Updates the 'images_dict' when user changes settings.
        This works for multiple textures!
        """
        
        items = treeview.selectedItems()
        try:
            force_sRGB = self.ui.fSRGB_CB.isChecked()
            force_linear = self.ui.fLinear_CB.isChecked()
            textype_index = self.ui.texType_DD.currentIndex()

            get_sel_item = treeview.currentItem()
            get_sel_item_text = get_sel_item.text(0)

            for item in items:
                images_dict[item.text(0)] = [force_sRGB,
                                             force_linear, textype_index]
        except:
            pass

    def convert_backslash(self, path):
        """
        Convert backslash to forwardslash.
        """

        return path.replace("\\", "/")

    def append_tex_to_dict(self, texlist):
        """
        Append the list of textures in 'texlist' to the 'images_dict' with default options.
        """

        for tex in texlist:
            images_dict[tex] = [False, False, 0]

    def append_tex_to_treewidget(self, texlist):
        """
        Append the list of textures in 'texlist' to the QTreeWidget.
        """
        for tex in texlist:
            item = QTreeWidgetItem(treeview)
            item.setText(0, tex)

    def resetProgress(self):
        """
        Reset the progress bar to 0%.
        """
        self.ui.progressBar.setValue(0)

    def check_status(self, tex_list):
        root = treeview.invisibleRootItem()
        item_count = root.childCount()

        for i in range(item_count):
            item = root.child(i)
            tex = item.text(0)
            tex = tex[:-3] + "rstexbin"
            if os.path.isfile(tex):
                item.setIcon(0, QIcon(found_Icon))
            else:
                item.setIcon(0, QIcon(missing_Icon))



_RsTxMngr = None

def show():
    global _RsTxMngr
    if _RsTxMngr is None:
        _RsTxMngr = RsTxMngr()
    _RsTxMngr.show()