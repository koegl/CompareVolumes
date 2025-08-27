import os, string

from typing import List

import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *

import RegistrationLib

#
# CompareVolumes
#

class CompareVolumes(ScriptedLoadableModule):
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    parent.title = "Compare Volumes"
    parent.categories = ["Wizards"]
    parent.dependencies = []
    parent.contributors = ["Steve Pieper (Isomics)"] # replace with "Firstname Lastname (Org)"
    parent.helpText = """
    """
    parent.helpText = string.Template("""
    This module helps organize layouts and volume compositing to help compare images

Please refer to <a href=\"$a/Documentation/$b.$c/Modules/CompareVolumes\"> the documentation</a>.

    """).substitute({ 'a':parent.slicerWikiUrl, 'b':slicer.app.majorVersion, 'c':slicer.app.minorVersion })
    parent.acknowledgementText = """
    This file was originally developed by Steve Pieper, Isomics, Inc.
    It was partially funded by NIH grant 3P41RR013218-12S1 and P41 EB015902 the
    Neuroimage Analysis Center (NAC) a Biomedical Technology Resource Center supported
    by the National Institute of Biomedical Imaging and Bioengineering (NIBIB).
    And this work is part of the "National Alliance for Medical Image
    Computing" (NAMIC), funded by the National Institutes of Health
    through the NIH Roadmap for Medical Research, Grant U54 EB005149.
    Information on the National Centers for Biomedical Computing
    can be obtained from http://nihroadmap.nih.gov/bioinformatics.
    This work is also supported by NIH grant 1R01DE024450-01A1
    "Quantification of 3D Bony Changes in Temporomandibular Joint Osteoarthritis"
    (TMJ-OA).
""" # replace with organization, grant and thanks.

#
# qCompareVolumesWidget
#

class CompareVolumesWidget(ScriptedLoadableModuleWidget):

  def __init__(self, parent=None):
    ScriptedLoadableModuleWidget.__init__(self, parent)
    self.layerReveal = None

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Instantiate and connect widgets ...

    if self.developerMode:
      # reload and run specific tests
      scenarios = ("Three Volume", "View Watcher", "LayerReveal", "Optional VolumeID Mapping")
      for scenario in scenarios:
        button = qt.QPushButton("Reload and Test %s" % scenario)
        button.toolTip = "Reload this module and then run the %s self test." % scenario
        self.reloadCollapsibleButton.layout().addWidget(button)
        button.connect('clicked()', lambda s=scenario: self.onReloadAndTest(scenario=s))

    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # Volume order select
    #
    self.volumeOrderSelect = VolumeOrderSelect()
    parametersFormLayout.addRow("Volumes", self.volumeOrderSelect.widget)

    #
    # background volume selector
    #
    self.backgroundSelector = slicer.qMRMLNodeComboBox()
    self.backgroundSelector.nodeTypes = ( ("vtkMRMLVolumeNode"), "" )
    self.backgroundSelector.selectNodeUponCreation = True
    self.backgroundSelector.addEnabled = False
    self.backgroundSelector.removeEnabled = False
    self.backgroundSelector.noneEnabled = True
    self.backgroundSelector.showHidden = False
    self.backgroundSelector.showChildNodeTypes = True
    self.backgroundSelector.setMRMLScene( slicer.mrmlScene )
    self.backgroundSelector.setToolTip( "Common background - all lightbox panes will have this background and a different volume in each foreground." )
    parametersFormLayout.addRow("Common Background: ", self.backgroundSelector)

    #
    # label volume selector
    #
    self.labelSelector = slicer.qMRMLNodeComboBox()
    self.labelSelector.nodeTypes = ( ("vtkMRMLLabelMapVolumeNode"), "" )
    self.labelSelector.selectNodeUponCreation = True
    self.labelSelector.addEnabled = False
    self.labelSelector.removeEnabled = False
    self.labelSelector.noneEnabled = True
    self.labelSelector.showHidden = False
    self.labelSelector.showChildNodeTypes = True
    self.labelSelector.setMRMLScene( slicer.mrmlScene )
    self.labelSelector.setToolTip( "Common label - all lightbox panes will have this label on top." )
    parametersFormLayout.addRow("Common Label: ", self.labelSelector)

    #
    # Hot link and cursor
    #
    self.hotLinkWithCursorCheck = qt.QCheckBox()
    self.hotLinkWithCursorCheck.checked = True
    parametersFormLayout.addRow("Hot Link with Cursor", self.hotLinkWithCursorCheck)

    #
    # re-use some UI from LandmarkRegistration
    # - TODO: this makes odd circular dependency
    #   that may need to be refactored someday,
    #   but for now it works because this widget
    #   is a common depdency.
    #
    self.visualization = RegistrationLib.VisualizationWidget(None)
    self.visualization.groupBoxLayout.itemAt(3).widget().hide()
    self.visualization.groupBoxLayout.itemAt(2).widget().hide()
    parametersFormLayout.addRow(self.visualization.widget)
    self.visualization.connect("layoutRequested(mode,volumesToShow)", self.onLayoutRequested)
    self.visualization.layoutOption = self.visualization.layoutOptions[0]
    self.onCompareVolumes()
    RegistrationLib.zoom("Fit")

    #
    # Compare Button
    #
    self.compareVolumesButton = qt.QPushButton("Compare Checked Volumes")
    self.compareVolumesButton.setToolTip( "Make a set of slice views that show each of the currently checked volumes, with optional companion volumes, in the selected orientation." )
    parametersFormLayout.addRow(self.compareVolumesButton)
    self.compareVolumesButton.connect("clicked()", self.onCompareVolumes)

    #
    # Add layer reveal area
    #
    layerRevealCollapsibleButton = ctk.ctkCollapsibleButton()
    layerRevealCollapsibleButton.text = "Layer Reveal Cursor"
    self.layout.addWidget(layerRevealCollapsibleButton)
    layerRevealFormLayout = qt.QFormLayout(layerRevealCollapsibleButton)

    self.layerRevealCheck = qt.QCheckBox()
    layerRevealFormLayout.addRow("Layer Reveal Cursor", self.layerRevealCheck)
    self.layerRevealCheck.connect("toggled(bool)", self.onLayerRevealToggled)

    self.layerRevealScaleCheck = qt.QCheckBox()
    layerRevealFormLayout.addRow("Layer Reveal Cursor Scaled 2x", self.layerRevealScaleCheck)
    self.layerRevealScaleCheck.connect("toggled(bool)", self.onLayerRevealToggled)

    # Add vertical spacer
    self.layout.addStretch(1)

  def cleanup(self):
    self.volumeOrderSelect.cleanup()
    if self.layerReveal:
      self.layerReveal.cleanup()

  def onLayerRevealToggled(self):
    if self.layerReveal is not None:
      self.layerReveal.cleanup()
      self.layerReveal = None
    if self.layerRevealCheck.checked:
      self.layerReveal = RegistrationLib.LayerReveal(scale=self.layerRevealScaleCheck.checked)

  def onCompareVolumes(self):
    logic = RegistrationLib.CustomViewsLogic()
    volumeIDs = self.volumeOrderSelect.volumeIDs()
    volumeNodes = [slicer.mrmlScene.GetNodeByID(id) for id in volumeIDs]
    if self.visualization.layoutOption == 'Axi/Sag/Cor':
        viewers = logic.viewersPerVolume(
            volumeNodes=volumeNodes,
            background=self.backgroundSelector.currentNode(),
            label=self.labelSelector.currentNode(),
            opacity=self.visualization.fadeSlider.value,
            )
    else:
        viewers = logic.viewerPerVolume(
            volumeNodes=volumeNodes,
            orientation=self.visualization.layoutOption,
            background=self.backgroundSelector.currentNode(),
            label=self.labelSelector.currentNode(),
            opacity=self.visualization.fadeSlider.value,
            )
    
    # when no volumes are selected, viewers is None
    if not viewers:
      return

    for viewName in viewers.keys():
        sliceWidget = slicer.app.layoutManager().sliceWidget(viewName)
        compositeNode = sliceWidget.sliceLogic().GetSliceCompositeNode()
        compositeNode.SetLinkedControl(self.hotLinkWithCursorCheck.checked)
        compositeNode.SetHotLinkedControl(self.hotLinkWithCursorCheck.checked)
    crosshairNode = slicer.mrmlScene.GetSingletonNode("default", "vtkMRMLCrosshairNode")
    crossharMode = crosshairNode.ShowSmallBasic if self.hotLinkWithCursorCheck.checked else crosshairNode.NoCrosshair
    crosshairNode.SetCrosshairMode(crossharMode)

  def onLayoutRequested(self, mode: str, volumesToShow: List[str]) -> None:

    if mode not in self.visualization.layoutOptions:
      return

    self.visualization.layoutOption = mode
    self.onCompareVolumes()
    RegistrationLib.zoom("Fit")



class VolumeOrderSelect:
    """Helper class to manage a list widget with a checkable
    and re-orderable item for each volume in the scene"""
    def __init__(self):
      self.widget = qt.QWidget()
      self.layout = qt.QVBoxLayout()
      self.widget.setLayout(self.layout)
      self.listWidget = qt.QListWidget()
      self.listWidget.setDragDropMode(qt.QAbstractItemView.InternalMove)
      self.layout.addWidget(self.listWidget)
      self.controlWiget = qt.QWidget()
      self.controlLayout = qt.QHBoxLayout()
      self.controlWiget.setLayout(self.controlLayout)
      self.selectAllButton = qt.QPushButton("Select all")
      self.unselectAllButton = qt.QPushButton("Unselect all")
      self.controlLayout.addWidget(self.selectAllButton)
      self.controlLayout.addWidget(self.unselectAllButton)
      self.layout.addWidget(self.controlWiget)
      self.selectAllButton.connect("clicked()", lambda state=qt.Qt.Checked: self.setCheckStates(state))
      self.unselectAllButton.connect("clicked()", lambda state=qt.Qt.Unchecked: self.setCheckStates(state))
      events = [slicer.mrmlScene.NodeAddedEvent,
                slicer.mrmlScene.NodeRemovedEvent,
                slicer.mrmlScene.NewSceneEvent]
      self.observations = []
      for event in events:
        self.observations.append(slicer.mrmlScene.AddObserver(event, self.refresh))
      self.refresh()

    def setCheckStates(self, state):
      listModel = self.listWidget.model()
      for row in range(listModel.rowCount()):
        item = self.listWidget.item(row)
        item.setCheckState(state)

    def cleanup(self):
      for observation in self.observations:
        slicer.mrmlScene.RemoveObserver(observation)

    def refresh(self, caller=None, event=None):
      """synchronize list items with current volume
      nodes in scene while retaining order and check state"""
      listModel = self.listWidget.model()
      # first, save the order and checkstate
      previousVolumeIDs = []
      previousCheckStates = []
      for row in range(listModel.rowCount()):
        item = self.listWidget.item(row)
        previousCheckStates.append(item.checkState())
        previousVolumeIDs.append(item.toolTip())
      # reset, and first add any of the previous volumes still in scene
      self.listWidget.clear()
      sceneVolumeNodes = list(slicer.util.getNodes('*VolumeNode*').values())
      sceneVolumeIDs = [node.GetID() for node in sceneVolumeNodes]
      volumeIDs = []
      volumeCheckStates = []
      for volumeIndex in range(len(previousVolumeIDs)):
        if previousVolumeIDs[volumeIndex] in sceneVolumeIDs:
          volumeIDs.append(previousVolumeIDs[volumeIndex])
          volumeCheckStates.append(previousCheckStates[volumeIndex])
      # add any new volumes that were here before
      for volumeID in sceneVolumeIDs:
        if volumeID not in volumeIDs:
          volumeIDs.append(volumeID)
          volumeCheckStates.append(qt.Qt.Checked)
      # add items
      for (volumeID,volumeCheckState) in zip(volumeIDs, volumeCheckStates):
        volumeNode = slicer.mrmlScene.GetNodeByID(volumeID)
        self.listWidget.addItem(volumeNode.GetName())
        item = self.listWidget.item(listModel.rowCount()-1)
        item.setToolTip(volumeID)
        item.setCheckState(volumeCheckState)

    def volumeIDs(self):
      volumeIDs = []
      listModel = self.listWidget.model()
      for row in range(listModel.rowCount()):
        item = self.listWidget.item(row)
        if item.checkState() == qt.Qt.Checked:
          volumeIDs.append(item.toolTip())
      return volumeIDs


class CompareVolumesTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self,scenario=None):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    if scenario == "Three Volume":
      self.test_CompareVolumes1()
    elif scenario == "View Watcher":
      self.test_CompareVolumes2()
    elif scenario == "LayerReveal":
      self.test_CompareVolumes3()
    elif scenario == "Optional VolumeID Mapping":
      self.test_CompareVolumes5()
    else:
      self.test_CompareVolumes1()
      self.test_CompareVolumes2()
      self.test_CompareVolumes3()
      self.test_CompareVolumes4()
      self.test_CompareVolumes5()

  def test_CompareVolumes1(self):
    """ Test modes with 3 volumes.
    """

    m = slicer.util.mainWindow()
    m.moduleSelector().selectModule('CompareVolumes')

    self.delayDisplay("Starting the test")

    # first with two volumes
    from SampleData import SampleDataLogic
    head = SampleDataLogic().downloadMRHead()
    brain = SampleDataLogic().downloadDTIBrain()
    logic = RegistrationLib.CustomViewsLogic()
    logic.viewerPerVolume()
    self.delayDisplay('Should be one row with two columns')
    logic.viewerPerVolume(volumeNodes=(brain,head), viewNames=('brain', 'head'))
    self.delayDisplay('Should be two columns, with names')

    # now with three volumes
    otherBrain = SampleDataLogic().downloadMRBrainTumor1()
    logic.viewerPerVolume()
    logic.viewerPerVolume(volumeNodes=(brain,head,otherBrain), viewNames=('brain', 'head','otherBrain'))
    self.delayDisplay('Should be one row with three columns')

    logic.viewerPerVolume(volumeNodes=(brain,head,otherBrain), viewNames=('brain', 'head','otherBrain'), orientation='Sagittal')
    self.delayDisplay('same thing in sagittal')

    logic.viewerPerVolume(volumeNodes=(brain,head,otherBrain), viewNames=('brain', 'head','otherBrain'), orientation='Coronal')
    self.delayDisplay('same thing in coronal')

    anotherHead = SampleDataLogic().downloadMRHead()
    logic.viewerPerVolume(volumeNodes=(brain,head,otherBrain,anotherHead), viewNames=('brain', 'head','otherBrain','anotherHead'), orientation='Coronal')
    self.delayDisplay('now four volumes, with three columns and two rows')


    logic.viewersPerVolume(volumeNodes=(brain,head))
    self.delayDisplay('now axi/sag/cor for two volumes')

    logic.viewersPerVolume(volumeNodes=(brain,head,otherBrain))
    self.delayDisplay('now axi/sag/cor for three volumes')

    self.delayDisplay('Test passed!')

  def test_CompareVolumes2(self):
    """
    Test modes with view watcher class.
    """

    m = slicer.util.mainWindow()
    m.moduleSelector().selectModule('CompareVolumes')

    self.delayDisplay("Starting View Watcher test")

    watcher = RegistrationLib.ViewWatcher()

    # first with two volumes
    from SampleData import SampleDataLogic
    head = SampleDataLogic().downloadMRHead()
    brain = SampleDataLogic().downloadDTIBrain()
    logic = RegistrationLib.CustomViewsLogic()
    logic.viewerPerVolume()
    self.delayDisplay('Should be one row with two columns')
    logic.viewerPerVolume(volumeNodes=(brain,head), viewNames=('brain', 'head'))
    self.delayDisplay('Should be two columns, with names')

    watcher.cleanup()

    self.delayDisplay('Test passed!')

  def test_CompareVolumes3(self):
    """
    Test LayerReveal

    From the python console:
slicer.util.mainWindow().moduleSelector().selectModule("CompareVolumes"); slicer.modules.CompareVolumesWidget.onReloadAndTest(scenario="LayerReveal"); reveal = LayerReveal()
    """

    self.delayDisplay("Starting LayerReveal test")

    # first with two volumes
    from SampleData import SampleDataLogic
    head = SampleDataLogic().downloadMRHead()
    dti = SampleDataLogic().downloadDTIBrain()
    tumor = SampleDataLogic().downloadMRBrainTumor1()
    logic = RegistrationLib.CustomViewsLogic()
    logic.viewerPerVolume()
    self.delayDisplay('Should be one row with two columns')
    logic.viewerPerVolume(volumeNodes=(dti,tumor,head),
                            background=dti, viewNames=('dti', 'tumor', 'head'))
    self.delayDisplay('Should be three columns, with dti in foreground')

    # the name of the view was givein the the call to viewerPerVolume above.
    # here we ask the layoutManager to give us the corresponding sliceWidget
    # from which we can get the interactorStyle so we can simulate events
    layoutManager = slicer.app.layoutManager()
    sliceWidget = layoutManager.sliceWidget('head')
    style = sliceWidget.sliceView().interactorStyle().GetInteractor()

    for scale in (False,True):
      for size in (100,400):
        # create a reveal cursor to test
        reveal = RegistrationLib.LayerReveal(width=size,height=size,scale=scale)
        reveal.processEvent(style, "EnterEvent")
        steps = 300
        for step in range(0,steps):
          t = step//float(steps)
          px = int(t * sliceWidget.width)
          py = int(t * sliceWidget.height)
          style.SetEventPosition(px,py)
          reveal.processEvent(style, "MouseMoveEvent")
        reveal.processEvent(style, "LeaveEvent")
        reveal.cleanup()
        self.delayDisplay(f'Scale {scale}, size {size}')


    self.delayDisplay('Should have just seen reveal cursor move through head view')

    self.delayDisplay('Test passed!')

  def test_CompareVolumes4(self):
    self.delayDisplay("Starting Hot Link Control test")

    slicer.mrmlScene.Clear(0)
    m = slicer.util.mainWindow()
    m.moduleSelector().selectModule('CompareVolumes')
    widget = slicer.modules.CompareVolumesWidget

    from SampleData import SampleDataLogic
    SampleDataLogic().downloadMRHead()
    SampleDataLogic().downloadDTIBrain()

    widget.compareVolumesButton.click()  # hot link default on

    left_slice_widget = slicer.app.layoutManager().sliceWidget('0_0')
    right_slice_widget = slicer.app.layoutManager().sliceWidget('0_1')
    left_slice_node = left_slice_widget.sliceLogic().GetSliceNode()
    right_slice_node = right_slice_widget.sliceLogic().GetSliceNode()

    self.assertAlmostEqual(left_slice_node.GetSliceOffset(), right_slice_node.GetSliceOffset())

    # changes to left slice should be reflected in the other
    left_offset_initial = left_slice_node.GetSliceOffset()
    left_slice_widget.interactorStyle().GetInteractor().MouseWheelForwardEvent()
    left_offset_new = left_offset_initial + left_slice_widget.sliceLogic().GetLowestVolumeSliceSpacing()[2]
    self.assertAlmostEqual(left_slice_node.GetSliceOffset(), left_offset_new)
    self.assertAlmostEqual(left_slice_node.GetSliceOffset(), right_slice_node.GetSliceOffset())

    widget.hotLinkWithCursorCheck.setChecked(False)
    widget.compareVolumesButton.click()

    self.assertAlmostEqual(left_slice_node.GetSliceOffset(), right_slice_node.GetSliceOffset())

    # changes to left slice are not reflected in the other
    right_offset_initial = right_slice_node.GetSliceOffset()
    left_offset_initial = left_slice_node.GetSliceOffset()
    right_slice_widget.interactorStyle().GetInteractor().MouseWheelForwardEvent()
    right_offset_new = right_offset_initial + right_slice_widget.sliceLogic().GetLowestVolumeSliceSpacing()[2]
    self.assertAlmostEqual(right_slice_node.GetSliceOffset(), right_offset_new)
    self.assertAlmostEqual(left_slice_node.GetSliceOffset(), left_offset_initial)

    self.delayDisplay('Test passed!')

  def test_CompareVolumes5(self):
    """
    Test viewerPerVolume and viewersPerVolume with optional mapping of volume IDs to view names.
    """

    slicer.mrmlScene.Clear(0)

    from SampleData import SampleDataLogic
    head = SampleDataLogic().downloadMRHead()
    dti = SampleDataLogic().downloadDTIBrain()

    logic = RegistrationLib.CustomViewsLogic()
    
    # Test viewerPerVolume with no common background
    _, volumeViewMapping = logic.viewerPerVolume([head, dti],
                                                 background=None,
                                                 returnVolumeViewMapping=True)

    correct_output = {
        'vtkMRMLScalarVolumeNode1': {
            'background': ['0_0']
        },
        'vtkMRMLDiffusionTensorVolumeNode1': {
            'background': ['0_1']
        }
    }
    self.assertEqual(volumeViewMapping, correct_output)

    # Test viewersPerVolume with no common background
    _, volumeViewMapping = logic.viewersPerVolume([head, dti],
                                                  background=None,
                                                  returnVolumeViewMapping=True)
    correct_output = {
        'vtkMRMLScalarVolumeNode1': {
            'background':
            ['MRHead-Axial', 'MRHead-Sagittal', 'MRHead-Coronal']
        },
        'vtkMRMLDiffusionTensorVolumeNode1': {
            'background':
            ['DTIBrain-Axial', 'DTIBrain-Sagittal', 'DTIBrain-Coronal']
        }
    }
    self.assertEqual(volumeViewMapping, correct_output)

    # Test viewerPerVolume with common background
    _, volumeViewMapping = logic.viewerPerVolume([head, dti],
                                                 background=head,
                                                 returnVolumeViewMapping=True)
    correct_output = {
        'vtkMRMLScalarVolumeNode1': {
            'background': ['0_0', '0_1'],
            'foreground': ['0_0']
        },
        'vtkMRMLDiffusionTensorVolumeNode1': {
            'foreground': ['0_1']
        }
    }
    self.assertEqual(volumeViewMapping, correct_output)

    # Test viewersPerVolume with common background
    _, volumeViewMapping = logic.viewersPerVolume([head, dti],
                                                  background=head,
                                                  returnVolumeViewMapping=True)
    correct_output = {
        'vtkMRMLScalarVolumeNode1': {
            'background': [
                'MRHead-Axial', 'MRHead-Sagittal', 'MRHead-Coronal',
                'DTIBrain-Axial', 'DTIBrain-Sagittal', 'DTIBrain-Coronal'
            ],
            'foreground':
            ['MRHead-Axial', 'MRHead-Sagittal', 'MRHead-Coronal']
        },
        'vtkMRMLDiffusionTensorVolumeNode1': {
            'foreground':
            ['DTIBrain-Axial', 'DTIBrain-Sagittal', 'DTIBrain-Coronal']
        }
    }
    self.assertEqual(volumeViewMapping, correct_output)

    self.delayDisplay('Test passed!')
