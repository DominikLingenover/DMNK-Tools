import hou

def main():

    sceneViewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    # currentViewport = sceneViewer.curViewport()

    # newCam = currentViewport.defaultCamera()

    # flipbookSettings = sceneViewer.flipbookSettings().stash()
    # flipbookSettings.frameRange((hou.frame(), hou.frame()))
    # flipbookSettings.outputToMPlay(False)

    # flipbookSettings.output("C:/Users/Dominik/Desktop/Test.jpg")

    # sceneViewer.flipbook(sceneViewer.curViewport(), flipbookSettings)

    screenshot = sceneViewer.qtWindow().grab()
    screenshot.save("C:/Users/Dominik/Desktop/Test.jpg", "JPG", 95)