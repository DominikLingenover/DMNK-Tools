import hou
import os
import shutil
import re

from PySide2 import QtCore
from PySide2 import QtWidgets
from PySide2 import QtGui
from PySide2 import QtUiTools

scriptpath = os.path.dirname(__file__)
asset_checker_path = hou.getenv("dmnk")
settings_path = asset_checker_path + "/config/asset_checker_config"
version = "2.00"

# Icons
missing_Icon = hou.qt.Icon("BUTTONS_list_delete")
found_Icon = hou.qt.Icon("SCENEGRAPH_loaded_on")
reload_Icon = hou.qt.Icon("BUTTONS_reload")
options_Icon = hou.qt.Icon("BUTTONS_gear_mini")
file_Chooser_Icon = hou.qt.Icon("BUTTONS_chooser_file")

# UI Elements
_status = None
_options_B = None
_options_Box = None
_search_Path = None
_open_File_Dialog = None
_reload_B = None
_asset_List = None 
_relink_B = None
_copy_B = None
_texPath_input = None
_geoPath_input = None
_simPath_input = None
_config_Box = None
_variable_Name = None
_only_missing_CB = None
_include_out_CB = None
_make_archive_B = None

# Initialize Variables
isConfigOpen = 0
isOptionsOpen = 0
_missing_Textures_Index_List = []
_all_Files_List = []
_amount_Missing_Textures = 0
_amount_files_relinked = 0
_amount_files_copied = 0

tex_extensions = (".pic", ".pic.Z", ".picZ", ".pic.gz", ".picgz", ".rat", ".tbf", ".dsm",
                  ".picnc", ".piclc", ".rgb", ".rgba", ".sgi", ".tif", ".tif3", ".tif16", 
                  ".tif32", ".tiff", ".yuv", ".pix", ".als", ".cin", ".kdk", ".jpg", ".jpeg",
                  ".exr", ".png", ".psd", ".psb", ".si", ".tga", ".vst", ".vtg", ".rla", ".rla16",
                  ".rlb", ".rlb16", ".bmp", ".hdr", ".ptx", ".ptex", ".ies", ".qtl")

geo_extensions = (".geo", ".bgeo", ".geo.gz", ".geogz", ".bgeo.gz", ".bgeogz", ".geo.sc",
                  ".geosc", ".bgeo.sc", ".bgeosc", ".poly", ".bpoly", ".d", ".rib", ".GoZ",
                  ".bgeo.lzma", ".bgeo.bz2", ".pmap", ".geo.lzma", ".off",
                  ".igs", ".ply", ".obj", ".pdb", ".lw", ".lwo", ".geo.bz2", ".bstl", ".eps",
                  ".ai", ".stl", ".dxf", ".abc", ".fbx")

sim_extensions = (".sim", ".vdb")

class AssetChecker(QtWidgets.QWidget):
    def __init__(self):
        super(AssetChecker, self).__init__(hou.qt.mainWindow())

        # Create UI
        self.create_ui()

    def create_ui(self):
        """
        Create UI.
        Assign functions to buttons and actions.
        """

        self.settings = QtCore.QSettings(settings_path, QtCore.QSettings.IniFormat)

        self.setWindowTitle('DMNK - Asset Checker')
        self.setWindowFlags(QtCore.Qt.Dialog)
        self.resize(self.settings.value("size", QtCore.QSize(hou.ui.scaledSize(800), hou.ui.scaledSize(500))))
        self.move(self.settings.value("pos", QtCore.QPoint(0, 0)))

        # Layout
        loader = QtUiTools.QUiLoader()
        self.ui = loader.load(scriptpath + "/asset_checker_ui.ui")

        mainLayout = QtWidgets.QGridLayout()
        mainLayout.addWidget(self.ui)
        mainLayout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(mainLayout)

        # Variables
        global _status
        global _options_B
        global _options_Box
        global _search_Path
        global _open_File_Dialog
        global _reload_B
        global _asset_List
        global _relink_B
        global _copy_B
        global _texPath_input 
        global _geoPath_input
        global _config_Box
        global _variable_Name
        global _simPath_input
        global _only_missing_CB
        global _include_out_CB
        global _make_archive_B

        _status = self.ui.status
        _options_B = self.ui.options_B
        _options_Box = self.ui.options_Box
        _search_Path = self.ui.search_Path
        _open_File_Dialog = self.ui.open_File_Dialog
        _reload_B = self.ui.reload_B
        _asset_List = self.ui.asset_List
        _relink_B = self.ui.relink_B
        _copy_B = self.ui.copy_B
        _texPath_input = self.ui.tex_Path
        _geoPath_input = self.ui.geo_Path
        _simPath_input = self.ui.sim_Path
        _config_Box = self.ui.config_Box
        _variable_Name = self.ui.variable_Name
        _only_missing_CB = self.ui.only_missing_CB
        _include_out_CB = self.ui.include_out_CB
        _make_archive_B = self.ui.archive_B

        # Set Button Icons
        _reload_B.setIcon(QtGui.QIcon(reload_Icon))
        _reload_B.setIconSize(QtCore.QSize(24,24))

        _options_B.setIcon(QtGui.QIcon(options_Icon))
        _options_B.setIconSize(QtCore.QSize(24,24))

        _open_File_Dialog.setIcon(QtGui.QIcon(file_Chooser_Icon))
        _open_File_Dialog.setIconSize(QtCore.QSize(20,20))

        # Config
        _texPath_input.setText(self.settings.value("tex_Path", ""))
        _geoPath_input.setText(self.settings.value("geo_Path", ""))
        _simPath_input.setText(self.settings.value("sim_Path", ""))
        _search_Path.setText(self.settings.value("search_Path", ""))
        _variable_Name.setText(self.settings.value("var_Name", ""))
        _only_missing_CB.setChecked(str(self.settings.value("only_Missing_CB", False)).lower() == 'true')
        _include_out_CB.setChecked(str(self.settings.value("include_out", False)).lower() == 'true')

        _options_B.clicked.connect(self.open_options)
        _open_File_Dialog.clicked.connect(self.open_file_dialog)
        _open_File_Dialog.clicked.connect(self.updateConfig)
        _relink_B.clicked.connect(self.relink_paths)
        _copy_B.clicked.connect(self.copy_files_button)
        _texPath_input.editingFinished.connect(self.updateConfig)
        _geoPath_input.editingFinished.connect(self.updateConfig)
        _simPath_input.editingFinished.connect(self.updateConfig)
        _search_Path.editingFinished.connect(self.updateConfig)
        _variable_Name.editingFinished.connect(self.updateConfig)
        _reload_B.clicked.connect(self.parse_scene)
        _only_missing_CB.clicked.connect(self.updateConfig)
        _include_out_CB.clicked.connect(self.updateConfig)
        _make_archive_B.clicked.connect(self.make_archive)

        _asset_List.itemClicked.connect(self.jump_to_node)
        # Parse scene
        self.parse_scene()

    def updateConfig(self):
        """
        Updates the config when user inputs settings.
        """

        texPath = self.convert_backslash(_texPath_input.text())
        geoPath = self.convert_backslash(_geoPath_input.text())
        searchPath = self.convert_backslash(_search_Path.text())
        simPath = self.convert_backslash(_simPath_input.text())
        varName = _variable_Name.text()
        onlyMissing = _only_missing_CB.isChecked()
        includeOut = _include_out_CB.isChecked()

        self.settings.setValue("tex_Path", texPath)
        self.settings.setValue("geo_Path", geoPath)
        self.settings.setValue("sim_Path", simPath)
        self.settings.setValue("search_Path", searchPath)
        self.settings.setValue("var_Name", varName)
        self.settings.setValue("only_Missing_CB", onlyMissing)
        self.settings.setValue("include_out", includeOut)

    def hideEvent(self, event):
        """
        When window is closed store position and size in config.
        """

        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())

    def keyPressEvent(self, event):
        """
        Delete event to remove items from asset list.
        """

        if event.key() == QtCore.Qt.Key_Delete:
            if len(_asset_List.selectedItems()) > 0:
                try:
                    global _missing_Textures_Index_List
                    global _amount_Missing_Textures
                    global _all_Files_List
                    _missing_Textures_Index_List = []
                    _amount_Missing_Textures = 0

                    sel_Items = _asset_List.selectedItems()

                    for item in sel_Items:
                        x =  _asset_List.indexFromItem(item)
                        y = QtCore.QPersistentModelIndex(x)
                        if y.isValid():
                            _asset_List.removeRow(y.row())
                except:
                    pass

                for i in range(_asset_List.rowCount()):
                    # Updates the missing textures index list after deleting entries
                    item_Path = _asset_List.item(i, 2).text()
                    if not os.path.exists(item_Path):
                        _amount_Missing_Textures += 1
                        _missing_Textures_Index_List.append(i)
                status_text = "Status: Found - " + str(len(_all_Files_List)) + " | " + "Missing - " + str(_amount_Missing_Textures)
                _status.setText(status_text)
            else:
                pass
                
    def parse_scene(self):
        """
        '_all_Files_List structure':
        Index | Parm
        0     | Path to node
        1     | Path to file
        2     | Node parm
        3     | Is UDIM boolean
        4     | Is Sequence boolean
        5     | Index
        """

        global _missing_Textures_Index_List
        global _all_Files_List
        global _amount_Missing_Textures

        _asset_List.clearContents()

        all_Files = hou.fileReferences()
        _all_Files_List_temp = []
        _all_Files_List = {}
        _missing_Textures_Index_List = []
        _amount_Missing_Textures = 0

        for parm, filePath in all_Files:
            if parm != None:
                if _include_out_CB.isChecked() == False:
                    parm_parent = parm.node().parent().type().name()

                    if parm_parent != "out":
                        if parm_parent != "ropnet":
                            if filePath.endswith(tex_extensions) | filePath.endswith(geo_extensions) | filePath.endswith(sim_extensions):
                                _all_Files_List_temp.append((parm ,filePath))
                else:
                    if filePath.endswith(tex_extensions) | filePath.endswith(geo_extensions) | filePath.endswith(sim_extensions):
                        _all_Files_List_temp.append((parm ,filePath))

        for index, parm_tuple in enumerate(_all_Files_List_temp):
            parm = parm_tuple[0]
            file = parm_tuple[1]

            if parm != None:
                if file.endswith(tex_extensions) | file.endswith(geo_extensions) | file.endswith(sim_extensions):
                    nodePath = parm.node().path()
                    filePath = self.convert_backslash(file)

                    filePath_abs = hou.expandString(filePath)

                    _asset_List.setRowCount(len(_all_Files_List_temp))

                    filePath_item = QtWidgets.QTableWidgetItem()
                    filePath_item.setText(filePath)

                    nodePath_item = QtWidgets.QTableWidgetItem()
                    nodePath_item.setText(nodePath)

                    is_sequence = re.search(r"[$]F", filePath)
                    is_udim = re.search(r"<udim>", filePath)

                    _all_Files_List[index] = [nodePath, filePath, parm, is_udim, is_sequence, index]

                    if is_udim != None:
                        filePath_abs = filePath_abs.replace("<udim>", "1001")
                    else:
                        filePath_abs = hou.expandString(filePath)

                    filePath_abs_item = QtWidgets.QTableWidgetItem()
                    filePath_abs_item.setText(filePath_abs)

                    _asset_List.setItem(index, 0, filePath_item)
                    _asset_List.setItem(index, 2, filePath_abs_item)
                    _asset_List.setItem(index, 3, nodePath_item)

                    if not os.path.exists(filePath_abs):
                        _amount_Missing_Textures += 1
                        _missing_Textures_Index_List.append(index)
                        filePath_item.setIcon(QtGui.QIcon(missing_Icon))
                    else:
                        filePath_item.setIcon(QtGui.QIcon(found_Icon))

        status_text = "Status: Found - " + str(len(_all_Files_List)) + " | " + "Missing - " + str(_amount_Missing_Textures) + " | "

        _status.setText(status_text)

    def missing_texture_count(self):
        for row in range(_asset_List.rowCount()):
            pass

    def relink_paths(self):
        """
        Search the provided directory and all subdirectories and replace files.
        """
        global _amount_Missing_Textures
        global _missing_Textures_Index_List
        global _only_missing_CB
        global _amount_files_relinked

        _amount_Missing_Textures = 0
        _amount_files_relinked = 0

        search_Path = self.convert_backslash(hou.expandString(_search_Path.text()))

        if QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
            preview = False
            sel_Items = _asset_List.selectedItems()
            sel_row_list = []

            for item in sel_Items:
                sel_row_list.append(item.row())

            for root, dirs, files in os.walk(search_Path):
                if _only_missing_CB.isChecked() == True:
                    for index in _missing_Textures_Index_List:
                        if index in sel_row_list:
                            self.relink_path(index, root, preview)
                elif _only_missing_CB.isChecked() == False:
                    for i in range(_asset_List.rowCount()):
                        if i in sel_row_list:
                            self.relink_path(i, root, preview)

            _missing_Textures_Index_List = []
            for i in range(_asset_List.rowCount()):
            # Updates the missing textures index list after deleting entries
                item_Path = _asset_List.item(i, 2).text()
                if not os.path.exists(item_Path):
                    _amount_Missing_Textures += 1
                    _missing_Textures_Index_List.append(i)

        elif QtGui.QGuiApplication.keyboardModifiers() == (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier):
            preview = True
            sel_Items = _asset_List.selectedItems()
            sel_row_list = []

            for item in sel_Items:
                sel_row_list.append(item.row())

            for root, dirs, files in os.walk(search_Path):
                if _only_missing_CB.isChecked() == True:
                    for index in _missing_Textures_Index_List:
                        if index in sel_row_list:
                            self.relink_path(index, root, preview)
                elif _only_missing_CB.isChecked() == False:
                    for i in range(_asset_List.rowCount()):
                        if i in sel_row_list:
                            self.relink_path(i, root, preview)
        
        elif QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.ControlModifier:
            preview = True
            for root, dirs, files in os.walk(search_Path):
                if _only_missing_CB.isChecked() == True:
                    for index in _missing_Textures_Index_List:
                        self.relink_path(index, root, preview)
                elif _only_missing_CB.isChecked() == False:
                    for i in range(_asset_List.rowCount()):
                        self.relink_path(i, root, preview)

        else:
            preview = False

            for root, dirs, files in os.walk(search_Path):
                if _only_missing_CB.isChecked() == True:
                    for index in _missing_Textures_Index_List:
                        self.relink_path(index, root, preview)
                elif _only_missing_CB.isChecked() == False:
                    for i in range(_asset_List.rowCount()):
                        self.relink_path(i, root, preview)

            _missing_Textures_Index_List = []
            for i in range(_asset_List.rowCount()):
            # Updates the missing textures index list after deleting entries
                item_Path = _asset_List.item(i, 2).text()
                if not os.path.exists(item_Path):
                    _amount_Missing_Textures += 1
                    _missing_Textures_Index_List.append(i)

        status_text = "Status: Found - " + str(len(_all_Files_List)) + " | " + "Missing - " + str(_amount_Missing_Textures) + " | " + str(_amount_files_relinked) + " Files relinked!"

        _status.setText(status_text)

    def relink_path(self, index, root, preview):
        global _amount_Missing_Textures

        current_Path = _all_Files_List[index][1]
        current_Path_Abs = hou.expandString(current_Path)
        get_var = _search_Path.text().encode("utf-8")

        if _all_Files_List[index][3] != None:
            current_Path_Abs = current_Path_Abs.replace("<udim>", "1001")

        if _all_Files_List[index][4] != None:
            find_frame_var = re.findall(r"[$]F\d*", current_Path)

            if find_frame_var:
                determine_frame_length = find_frame_var[0][-1]

            try:
                if type(int(determine_frame_length)).__name__ == "int":
                    frame_length = int(determine_frame_length)
                else:
                    frame_length = 0
            except:
                frame_length = 0

        getVariable = current_Path.split("/")[0]

        filePath = root + "/" + current_Path_Abs.split("/")[-1]
        filePath = self.convert_backslash(filePath)

        if os.path.exists(filePath):
            global _amount_files_relinked
            _amount_files_relinked += 1

            file_path_abs = filePath
            if getVariable[0] == "$":
                    expand_var = hou.expandString(getVariable)
                    filePath = filePath.replace(expand_var, getVariable)

            if _all_Files_List[index][3] != None:
                filePath = filePath.replace("1001", "<udim>")

            if _all_Files_List[index][4] != None:
                if frame_length > 0:
                    filePath = filePath.replace(str(1).rjust(frame_length, '0'), find_frame_var[0].encode("utf-8"))
                else:
                    filePath = filePath.replace(str(1), "$F")

            if get_var[0] == "$":
                expand_var = self.convert_backslash(hou.expandString(get_var))
                filePath = filePath.replace(expand_var, get_var)

            new_path_item = QtWidgets.QTableWidgetItem()
            new_path_item.setText(filePath)
            

            if preview == False:
                _asset_List.setItem(index, 0, new_path_item)
                new_path_abs_item = QtWidgets.QTableWidgetItem()
                new_path_abs_item.setText(file_path_abs)
                _asset_List.setItem(index, 2, new_path_abs_item)

                _asset_List.item(index, 0).setIcon(QtGui.QIcon(found_Icon))

                _all_Files_List[index][2].set(filePath)
            else:
                _asset_List.setItem(index, 1, new_path_item)

    def copy_file_to_hip(self, file_path, last_segment, index, archive_path):
        global _variable_Name
        global _amount_files_copied

        if archive_path != "":
            var_path = archive_path

        else:
            if _variable_Name:
                var_path = hou.getenv(_variable_Name.text().replace("$", ""))
                if var_path == None:
                    var_path = self.convert_backslash(_variable_Name.text())

        tex_path = var_path + "/" + self.convert_backslash(_texPath_input.text())
        geo_path = var_path + "/" + self.convert_backslash(_geoPath_input.text())
        sim_path = var_path + "/" + self.convert_backslash(_simPath_input.text())

        if not os.path.exists(tex_path):
            os.makedirs(tex_path)
        
        if not os.path.exists(geo_path):
            os.makedirs(geo_path)

        if not os.path.exists(sim_path):
            os.makedirs(sim_path)

        if file_path.endswith(tex_extensions):
            dest_path = tex_path
            subdir = _texPath_input.text()

        elif file_path.endswith(geo_extensions):
            dest_path = geo_path
            subdir = _geoPath_input.text()

        elif file_path.endswith(sim_extensions):
            dest_path = sim_path
            subdir = _simPath_input.text()

        try:
            shutil.copy(file_path, dest_path)
            new_path = _variable_Name.text() + "/" + subdir + "/" + last_segment
            _asset_List.item(index, 0).setText(new_path)
            _all_Files_List[index][2].set(new_path)
            _amount_files_copied += 1
        except:
            pass

    def copy_files(self, index, archive_path):
        source_path = _asset_List.item(index, 0).text()
        source_path_abs = hou.expandString(source_path)

        if _all_Files_List[index][3] != None:
            i = 1001
            source_path_abs = source_path_abs.replace("<udim>", str(i))
            while True:
                source_path_abs = source_path_abs.replace(str(i-1), str(i))
                get_last_segment = source_path_abs.split("/")[-1]
                get_last_segment = get_last_segment.replace(str(i), "<udim>")

                if i == 1010:
                    break

                if not os.path.exists(source_path_abs):
                    break

                self.copy_file_to_hip(source_path_abs, get_last_segment, index, archive_path)
                
                i += 1

        elif _all_Files_List[index][4] != None:
            get_last_segment = source_path.split("/")[-1]
            get_first_segments_abs = source_path_abs.split("/")[:-1]
            get_first_segments_abs = "/".join(get_first_segments_abs)
            combine_paths = get_first_segments_abs + "/" + get_last_segment

            find_frame_var = re.findall(r"[$]F\d*", combine_paths)
            if find_frame_var:
                index_pos = combine_paths.index(find_frame_var[0])
                determine_frame_length = find_frame_var[0][-1]

            try:
                if type(int(determine_frame_length)).__name__ == "int":
                    frame_length = int(determine_frame_length)
                else:
                    frame_length = 0
            except:
                frame_length = 0

            if frame_length > 1:
                i = 1
                variable = find_frame_var[0].encode("utf-8")
                while True:
                    source_path_abs = combine_paths.replace(variable, str(i).rjust(frame_length, '0'))
                    if not os.path.exists(source_path_abs):
                        break

                    self.copy_file_to_hip(source_path_abs, get_last_segment, index, archive_path)

                    i += 1

            else:
                i = 1
                while True:
                    source_path_abs = combine_paths.replace("$F", str(i))
                    
                    if not os.path.exists(source_path_abs):
                        break

                    self.copy_file_to_hip(source_path_abs, get_last_segment, index, archive_path)

                    i += 1
        else:
            if os.path.exists(source_path_abs):
                get_last_segment = source_path_abs.split("/")[-1]

                self.copy_file_to_hip(source_path_abs, get_last_segment, index, archive_path)

    def copy_files_button(self):
        global _amount_files_copied
        _amount_files_copied = 0

        if QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
            sel_Items = _asset_List.selectedItems()
            sel_row_list = []

            for item in sel_Items:
                sel_row_list.append(item.row())

            for index in range(_asset_List.rowCount()):
                if index in sel_row_list:
                    self.copy_files(index, "")

        else:
            for index in range(_asset_List.rowCount()):
                self.copy_files(index, "")

        status_text = "Status: Found - " + \
                      str(len(_all_Files_List)) + \
                      " | " + \
                      "Missing - " + \
                      str(_amount_Missing_Textures) + \
                      " | " + \
                      str(_amount_files_copied) + \
                      " Files copied to: " + \
                      self.convert_backslash(hou.expandString(_variable_Name.text()))

        _status.setText(status_text)

    def make_archive(self):
        archive_destination = QtWidgets.QFileDialog.getExistingDirectory()
        hip_file = hou.hipFile.path()

        if archive_destination != "":
            for index in range(_asset_List.rowCount()):
                self.copy_files(index, archive_destination)

            try:
                shutil.copy(hip_file, archive_destination)
            except:
                pass        

    def open_file_dialog(self):
        selected_dir = QtWidgets.QFileDialog.getExistingDirectory()
        _search_Path.setText(selected_dir)

    def jump_to_node(self):
        if QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.AltModifier:
            current_row = _asset_List.currentRow()
            current_node_full = _asset_List.item(current_row, 3).text().encode("utf-8")
            current_node = "/".join(current_node_full.split("/")[:-1])

            get_network = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.NetworkEditor)
            get_network.setPwd(hou.node(current_node))
            hou.node(current_node_full).setCurrent(True, clear_all_selected=True)

    def open_options(self):
        global isOptionsOpen
        global isConfigOpen

        if QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
            if isConfigOpen > 0:
                _config_Box.setMaximumSize(0, 0)
                isConfigOpen -= 1
            else:
                _config_Box.setMaximumSize(16777215, 16777215)
                isConfigOpen += 1
        else:
            if isOptionsOpen > 0:
                _options_Box.setMaximumSize(0, 0)
                isOptionsOpen -= 1

            else:
                isOptionsOpen += 1
                _options_Box.setMaximumSize(16777215, 16777215)

    def convert_backslash(self, path):
        """
        Convert backslash to forwardslash.
        """

        return path.replace("\\", "/")

_AssetChecker = None

def show():
    global _AssetChecker
    if _AssetChecker is None:
        _AssetChecker = AssetChecker()
    _AssetChecker.show()