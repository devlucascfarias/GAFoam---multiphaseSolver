import os
import sys
import re
import json
import signal
import psutil
import numpy as np
import pyqtgraph as pg
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QComboBox, QWidgetAction, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog, QTextEdit, QLabel,
    QMenuBar, QMenu, QAction, QLineEdit, QStatusBar, QDialog,
    QTableWidget, QTableWidgetItem, QMessageBox, QInputDialog
)
from PyQt5.QtCore import (
    QTimer, QProcess, Qt, QDir, QFileInfo, QProcessEnvironment
)
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5 import QtCore

from rate_calculator import calculate_increase_rate
from simulation_history import SimulationHistory

class OpenFOAMInterface(QWidget):
    """Interface moderna para interação com o OpenFOAM MultiphaseEuler."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("GAFoam — multiphaseEuler")
        self.resize(1000, 600)
        
        self.config_file = "config.json"
        self.config = self.load_config()
        
        self.init_paths()
        
        self.init_residual_data()
        
        self.mainVerticalLayout = QVBoxLayout(self)
        self.mainVerticalLayout.setContentsMargins(5, 5, 5, 5)
        
        self.apply_stylesheet()
        
        self.setupMenuBar()
        self.setupMainContentArea()
        self.setupStatusBar()
        
        self.systemMonitorTimer = QTimer(self)
        self.systemMonitorTimer.timeout.connect(self.updateSystemUsage)
        self.systemMonitorTimer.start(2000)
        
        self.setLayout(self.mainVerticalLayout)
        
        self.simulationHistory = SimulationHistory()

    def init_paths(self):
        """Inicializa os caminhos e configurações relacionadas a arquivos."""
        loaded_base_dir = self.config.get("baseDir", "") 
        if not loaded_base_dir or not os.path.isdir(loaded_base_dir):
            loaded_base_dir = os.getcwd() 
        self.baseDir = loaded_base_dir
        
        self.systemDir = os.path.join(self.baseDir, "system")
        self.unvFilePath = ""
        self.currentFilePath = ""
        self.currentOpenFOAMVersion = self.config.get("openFOAMVersion", "openfoam12")
        self.currentSolver = "multiphaseEuler"
        self.currentProcess = None
    
    def init_residual_data(self):
        """Inicializa estruturas de dados para os gráficos de resíduos."""
        self.residualData = {}
        self.timeData = []
        self.residualLines = {}
        self.colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2']
        self.maxCloudAlphaData = []
        self.maxCloudAlphaLine = None
    
    def apply_stylesheet(self):
        """Aplica o estilo global da aplicação."""
        # Definição do estilo integrado no código
        self.setStyleSheet("""
            /* Estilo geral */
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                color: #333;
                background-color: #f5f5f7;
            }
            
            /* Barra de menu */
            QMenuBar {
                background-color: #1e1e2e;
                color: #ffffff;
                padding: 6px;
                font-weight: bold;
                border-bottom: 1px solid #2a2a3a;
            }
            
            QMenuBar::item {
                background-color: transparent;
                padding: 8px 12px;
                border-radius: 2px;
                margin: 1px;
            }
            
            QMenuBar::item:selected {
                background-color: #3a7ca5;
                color: #ffffff;
            }
            
            QMenu {
                background-color: #2d2d3a;
                color: #ffffff;
                border: 1px solid #3a7ca5;
                border-radius: 2px;
                padding: 5px;
            }
            
            QMenu::item {
                background-color: transparent;
                padding: 6px 20px;
                border-radius: 2px;
            }
            
            QMenu::item:selected {
                background-color: #3a7ca5;
                color: #ffffff;
            }
            
            QMenu::separator {
                height: 1px;
                background-color: #3a7ca5;
                margin: 5px 0px;
            }
            
            /* Botões */
            QPushButton {
                background-color: #3a7ca5;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 2px;
                font-weight: bold;
                text-align: left;
            }
            
            QPushButton:hover {
                background-color: #2c5d80;
            }
            
            QPushButton:pressed {
                background-color: #1d3d54;
            }
            
            /* Terminal e Áreas de Texto */
            QTextEdit {
                background-color: #222236;
                color: #e0e0e0;
                border: 1px solid #333355;
                border-radius: 2px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                padding: 5px;
            }
            
            QLineEdit {
                background-color: #f0f0f0;
                color: #333;
                border: 1px solid #ddd;
                border-radius: 2px;
                padding: 8px;
            }
            
            /* ComboBox */
            QComboBox {
                background-color: #3a7ca5;
                color: white;
                border: none;
                border-radius: 2px;
                padding: 5px 10px;
                font-weight: bold;
                min-width: 120px;
            }
            
            QComboBox:hover {
                background-color: #2c5d80;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
            
            QComboBox QAbstractItemView {
                background-color: #2d2d3a;
                color: white;
                border: 1px solid #3a7ca5;
                selection-background-color: #3a7ca5;
                outline: none;
            }
            
            /* Status Bar */
            QStatusBar {
                background-color: #1e1e2e;
                color: white;
                border-top: 1px solid #3a7ca5;
                padding: 5px;
                font-weight: bold;
            }
            
            QStatusBar::item {
                border: none;
                border-right: 1px solid #3a7ca5;
                padding: 0px 10px;
            }
            
            /* Títulos de seção */
            QLabel[sectionTitle="true"] {
                background-color: #1e1e2e;
                color: #ffffff;
                padding: 8px 15px;
                border-radius: 2px;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #3a7ca5;
                margin-bottom: 5px;
            }
            
            /* Dialog */
            QDialog {
                background-color: #f5f5f7;
                border: 1px solid #ddd;
                border-radius: 6px;
            }
        """)
        
    
    def detectOpenFOAMVersions(self):
        versions = []
        openfoamDir = QDir("/opt")
        
        filters = ["openfoam*", "OpenFOAM*"]
        for dirName in openfoamDir.entryList(filters, QDir.Dirs | QDir.NoDotAndDotDot):
            versions.append(dirName)
        
        if not versions:
            versions.append("openfoam12")
            print("Warning: No OpenFOAM version found in /opt. Using fallback.")
        
        return versions
    
    def clearOldProcessorDirs(self):
        caseDir = QDir(self.baseDir)
        
        processorDirs = caseDir.entryList(["processor*"], QDir.Dirs | QDir.NoDotAndDotDot)
        for dirName in processorDirs:
            processorDir = QDir(caseDir.filePath(dirName))
            if processorDir.removeRecursively():
                self.outputArea.append(f"Removing old folder: {dirName}")

    def chooseUNV(self):
        unvFilePath, _ = QFileDialog.getOpenFileName(
            self,
            "Choose .unv File",
            "",
            "UNV Files (*.unv)"
        )
        
        if unvFilePath:
            self.unvFilePath = unvFilePath
            self.outputArea.append(f".unv file loaded: {unvFilePath}")
            self.meshPathLabel.setText(f"Mesh: {QFileInfo(unvFilePath).fileName()}")
        else:
            self.outputArea.append("No .unv file was selected.")    

    
    def chooseCase(self):
        casePath = QFileDialog.getExistingDirectory(
            self, 
            "Choose Case Folder", 
            self.baseDir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if casePath:
            required_dirs = ["0", "system", "constant"]
            if all(QDir(casePath).exists(dir_name) for dir_name in required_dirs):
                self.unvFilePath = casePath  
                self.baseDir = casePath  # Adiciona esta linha para sincronizar baseDir
                self.systemDir = os.path.join(self.baseDir, "system")
                self.config["baseDir"] = self.baseDir
                self.save_config()
                self.outputArea.append(f"Case folder selected: {casePath}")
                self.meshPathLabel.setText(f"Mesh: {QFileInfo(casePath).fileName()}")
                self.outputArea.append("Case loaded successfully.")
                # self.populateTreeView(casePath)  
            else:
                self.outputArea.append("Error: The selected folder does not contain the required directories (0, system, constant).")
        else:
            self.outputArea.append("No folder was selected.")
    
    def setupMenuBar(self):
        """Configura a barra de menu com design moderno."""
        self.menuBar = QMenuBar(self)
        
        # Aplica estilo adicional específico para o menu superior
        self.menuBar.setStyleSheet("""
            QMenuBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #2c3e50, stop:1 #1c2e40);
                color: #ecf0f1;
                padding: 8px;
                font-weight: bold;
                font-size: 11pt;
                border-bottom: 2px solid #3498db;
            }
            
            QMenuBar::item {
                background: transparent;
                padding: 10px 15px;
                margin: 0px 2px;
                border-radius: 3px;
            }
            
            QMenuBar::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #3498db, stop:1 #2980b9);
                color: white;
            }
            
            QMenuBar::item:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #2980b9, stop:1 #2980b9);
            }
            
            QMenu {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #3498db;
                border-radius: 3px;
                padding: 5px;
                margin-top: 2px;
            }
            
            QMenu::item {
                padding: 8px 25px 8px 15px;
                border-radius: 3px;
                margin: 2px 5px;
            }
            
            QMenu::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #3498db, stop:1 #2980b9);
                color: white;
            }
            
            QMenu::separator {
                height: 1px;
                background-color: #3498db;
                margin: 6px 10px;
            }
        """)
        
        # Menu Arquivo
        fileMenu = QMenu("Arquivo", self.menuBar)
        
        # Ações do menu arquivo
        importUNVAction = QAction(QIcon.fromTheme("document-open", QIcon()), "Carregar Arquivo .unv", self)
        importUNVAction.triggered.connect(self.chooseUNV)
        
        importCaseAction = QAction(QIcon.fromTheme("folder-open", QIcon()), "Carregar Caso", self)
        importCaseAction.triggered.connect(self.chooseCase)
        
        setBaseDirAction = QAction(QIcon.fromTheme("folder", QIcon()), "Definir Diretório Base", self)
        setBaseDirAction.triggered.connect(self.set_base_dir)
        
        fileMenu.addAction(importUNVAction)
        fileMenu.addAction(importCaseAction)
        fileMenu.addAction(setBaseDirAction)
        
        # Menu Terminal
        terminalMenu = QMenu("Terminal", self.menuBar)
        
        clearTerminalAction = QAction(QIcon.fromTheme("edit-clear", QIcon()), "Limpar Terminal", self)
        clearTerminalAction.triggered.connect(self.clearTerminal)
        
        terminalMenu.addAction(clearTerminalAction)
        
        # Menu OpenFOAM
        openfoamMenu = QMenu("OpenFOAM", self.menuBar)
        
        # ComboBox de versões do OpenFOAM
        self.versionComboBox = QComboBox(self)
        self.versionComboBox.addItems(self.detectOpenFOAMVersions())
        self.versionComboBox.setCurrentText(self.currentOpenFOAMVersion)
        self.versionComboBox.currentTextChanged.connect(self.setOpenFOAMVersion)
        
        versionAction = QWidgetAction(openfoamMenu)
        versionAction.setDefaultWidget(self.versionComboBox)
        openfoamMenu.addAction(versionAction)
        
        # Menu Histórico
        historyMenu = QMenu("Histórico", self.menuBar)
        
        viewHistoryAction = QAction(QIcon.fromTheme("document-properties", QIcon()), "Ver Histórico de Simulação", self)
        viewHistoryAction.triggered.connect(self.openSimulationHistory)
        
        historyMenu.addAction(viewHistoryAction)
        
        # Adicionar menus à barra
        self.menuBar.addMenu(fileMenu)
        self.menuBar.addMenu(terminalMenu)
        self.menuBar.addMenu(openfoamMenu)
        self.menuBar.addMenu(historyMenu)
        
        self.mainVerticalLayout.setMenuBar(self.menuBar)
    
    def setOpenFOAMVersion(self, version):
        self.currentOpenFOAMVersion = version
        self.outputArea.append(f"Selected version: {version}")
    
    def setupMainContentArea(self):
        """Configura o layout principal da aplicação com design moderno."""
        contentLayout = QHBoxLayout()
        
        # === PAINEL LATERAL (ESQUERDO) ===
        leftPanel = QWidget()
        leftPanel.setObjectName("leftPanel")
        leftPanel.setStyleSheet("""
            QWidget#leftPanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #2c3e50, stop:1 #1c2e40);
                border-radius: 2px;
                padding: 5px;
                margin: 5px;
            }
            
            QLabel {
                color: #ecf0f1;
                font-weight: bold;
            }
            
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                              stop:0 #3498db, stop:1 #2980b9);
                color: white;
                border: none;
                padding: 10px 16px;
                border-radius: 2px;
                font-weight: bold;
                text-align: left;
                margin: 3px 0px;
            }
            
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                              stop:0 #2980b9, stop:1 #2475a8);
                border-left: 3px solid #e74c3c;
            }
            
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                              stop:0 #2475a8, stop:1 #1f6591);
            }
        """)
        leftPanel.setFixedWidth(220)
        
        leftControlLayout = QVBoxLayout(leftPanel)
        leftControlLayout.setContentsMargins(10, 15, 10, 15)
        leftControlLayout.setSpacing(10)
        
        # Título do painel de controle
        controlLabel = QLabel("Simulation Control", leftPanel)
        controlLabel.setProperty("sectionTitle", "true")
        leftControlLayout.addWidget(controlLabel)
        
        # Botões de controle de simulação
        buttonStyle = """
            QPushButton {
                background-color: #3a7ca5;
                color: white;
                border: none;
                font-size: 12px;
                border-radius: 2px;
                text-align: left;
                margin: 2px 0px;
            }
            QPushButton:hover {
                background-color: #2c5d80;
                cursor: pointer;
            }
            QPushButton:pressed {
                background-color: #1d3d54;
            }
        """
        
        # Botões principais com ícones
        self.convertButton = QPushButton("convertMesh", leftPanel)
        self.convertButton.setStyleSheet(buttonStyle)
        self.convertButton.clicked.connect(self.convertMesh)
        leftControlLayout.addWidget(self.convertButton)
        
        self.checkMeshButton = QPushButton("checkMesh", leftPanel)
        self.checkMeshButton.setStyleSheet(buttonStyle)
        self.checkMeshButton.clicked.connect(self.checkMesh)
        leftControlLayout.addWidget(self.checkMeshButton)
        
        self.decomposeParButton = QPushButton("decomposePar", leftPanel)
        self.decomposeParButton.setStyleSheet(buttonStyle)
        self.decomposeParButton.clicked.connect(self.decomposePar)
        leftControlLayout.addWidget(self.decomposeParButton)
        
        self.reconstructButton = QPushButton("Reconstruct", leftPanel)
        self.reconstructButton.setStyleSheet(buttonStyle)
        self.reconstructButton.clicked.connect(self.reconstructPar)
        leftControlLayout.addWidget(self.reconstructButton)
        
        self.clearDecomposeButton = QPushButton("clearProcessors", leftPanel)
        self.clearDecomposeButton.setStyleSheet(buttonStyle)
        self.clearDecomposeButton.clicked.connect(self.clearDecomposedProcessors)
        leftControlLayout.addWidget(self.clearDecomposeButton)
        
        self.clearSimulationButton = QPushButton("clearSimulation", leftPanel)
        self.clearSimulationButton.setStyleSheet(buttonStyle)
        self.clearSimulationButton.clicked.connect(self.clearSimulation)
        leftControlLayout.addWidget(self.clearSimulationButton)
        
        self.setCoresButton = QPushButton("configureDecomposeParCores", leftPanel)
        self.setCoresButton.setStyleSheet(buttonStyle)
        self.setCoresButton.clicked.connect(self.configureDecomposeParCores)
        leftControlLayout.addWidget(self.setCoresButton)
        
        self.logButton = QPushButton("showSimulationLogs", leftPanel)
        self.logButton.setStyleSheet(buttonStyle)
        self.logButton.clicked.connect(self.showSimulationLogs)
        leftControlLayout.addWidget(self.logButton)
        
        # Espaço em branco no final
        leftControlLayout.addStretch()
        
        # === ÁREA PRINCIPAL (DIREITA) ===
        rightContentLayout = QVBoxLayout()
        rightContentLayout.setSpacing(10)
        
        # === CONTROLES DE SIMULAÇÃO ===
        controlPanel = QWidget()
        controlPanel.setObjectName("controlPanel")
        controlPanel.setStyleSheet("""
            QWidget#controlPanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                              stop:0 #2c3e50, stop:1 #1c2e40);
                border-radius: 2px;
                padding: 5px;
                margin: 5px;
            }
            
            QPushButton {
                border-radius: 2px;
            }
        """)
        
        controlPanelLayout = QHBoxLayout(controlPanel)
        controlPanelLayout.setContentsMargins(10, 10, 10, 10)
        controlPanelLayout.setSpacing(10)
        
        # Botões utilitários
        utilButtonStyle = """
            QPushButton {
                background-color: #3a7ca5;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 2px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2c5d80;
            }
        """
        
        self.runButton = QPushButton("Iniciar", controlPanel)
        self.runButton.setStyleSheet(utilButtonStyle)
        self.runButton.setToolTip("Iniciar Simulação")
        self.runButton.clicked.connect(self.runSimulation)
        
        self.pauseButton = QPushButton("Pausar", controlPanel)
        self.pauseButton.setStyleSheet(utilButtonStyle)
        self.pauseButton.setToolTip("Pausar Simulação")
        self.pauseButton.clicked.connect(self.pauseSimulation)
        
        self.resumeButton = QPushButton("Retomar", controlPanel)
        self.resumeButton.setStyleSheet(utilButtonStyle)
        self.resumeButton.setToolTip("Retomar Simulação")
        self.resumeButton.clicked.connect(self.resumeSimulation)
        
        self.restartButton = QPushButton("Reiniciar", controlPanel)
        self.restartButton.setStyleSheet(utilButtonStyle)
        self.restartButton.setToolTip("Reiniciar Simulação")
        self.restartButton.clicked.connect(self.restartSimulation)
        self.restartButton.clicked.connect(self.clearResidualPlot)
        
        self.stopButton = QPushButton("Parar", controlPanel)
        self.stopButton.setStyleSheet(utilButtonStyle)
        self.stopButton.setToolTip("Parar Simulação")
        self.stopButton.clicked.connect(self.stopSimulation)
        
        controlPanelLayout.addWidget(self.runButton)
        controlPanelLayout.addWidget(self.pauseButton)
        controlPanelLayout.addWidget(self.resumeButton)
        controlPanelLayout.addWidget(self.restartButton)
        controlPanelLayout.addWidget(self.stopButton)
        
        # Botões utilitários
        utilButtonStyle = """
            QPushButton {
                background-color: #3a7ca5;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 2px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2c5d80;
            }
        """
        
        self.openParaviewButton = QPushButton("ParaView", controlPanel)
        self.openParaviewButton.setStyleSheet(utilButtonStyle)
        self.openParaviewButton.setToolTip("Abrir no ParaView")
        self.openParaviewButton.clicked.connect(self.openParaview)
        
        self.calculateRateButton = QPushButton("Calcular Δy", controlPanel)
        self.calculateRateButton.setStyleSheet(utilButtonStyle)
        self.calculateRateButton.setToolTip("Calcular taxa de crescimento")
        self.calculateRateButton.clicked.connect(self.openRateCalculationDialog)
        
        self.fluidPropertiesButton = QPushButton("Propriedades", controlPanel)
        self.fluidPropertiesButton.setStyleSheet(utilButtonStyle)
        self.fluidPropertiesButton.setToolTip("Calcular propriedades do fluido")
        self.fluidPropertiesButton.clicked.connect(self.openFluidPropertiesDialog)
        
        controlPanelLayout.addWidget(self.openParaviewButton)
        controlPanelLayout.addWidget(self.calculateRateButton)
        controlPanelLayout.addWidget(self.fluidPropertiesButton)
        controlPanelLayout.addStretch()
        
        rightContentLayout.addWidget(controlPanel)
        
        # === ÁREA DO TERMINAL ===
        terminalLayout = QVBoxLayout()

        
        self.outputArea = QTextEdit(self)
        self.outputArea.setReadOnly(True)
        self.outputArea.setMinimumHeight(200)
        self.outputArea.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a2e;
                color: #e0e0e0;
                border: 1px solid #3498db;
                border-radius: 2px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                padding: 8px;
                selection-background-color: #3498db;
                selection-color: white;
            }
            
            QScrollBar:vertical {
                border: none;
                background: #2c3e50;
                width: 12px;
                margin: 15px 0 15px 0;
                border-radius: 6px;
            }
            
            QScrollBar::handle:vertical {
                background: #3498db;
                min-height: 30px;
                border-radius: 6px;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
        terminalLayout.addWidget(self.outputArea)
        
        # Campo de entrada de comandos
        self.terminalInput = QLineEdit(self)
        self.terminalInput.setPlaceholderText(">> Digite um comando e pressione Enter")
        self.terminalInput.setStyleSheet("""
            QLineEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #3498db;
                border-radius: 2px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                selection-background-color: #3498db;
            }
            
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
        """)
        self.terminalInput.returnPressed.connect(self.executeTerminalCommand)
        terminalLayout.addWidget(self.terminalInput)
        
        rightContentLayout.addLayout(terminalLayout)
        
        # === ÁREA DE VISUALIZAÇÃO ===
        visualizationLayout = QHBoxLayout()
        
        # === GRÁFICO DE RESÍDUOS ===
        residualLayout = QVBoxLayout()
        
        plot_title = QLabel("Gráfico de Resíduos", self)
        plot_title.setProperty("sectionTitle", "true")
        plot_title.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                              stop:0 #2c3e50, stop:1 #3498db);
                color: #ecf0f1;
                padding: 10px 15px;
                border-radius: 2px;
                font-weight: bold;
                font-size: 13px;
                border-left: 5px solid #e74c3c;
                margin-bottom: 5px;
            }
        """)
        residualLayout.addWidget(plot_title)
        
        # Configuração do gráfico
        self.graphWidget = pg.PlotWidget()
        self.graphWidget.setBackground('#1a1a2e')
        self.graphWidget.setLabel('left', 'Resíduos', color='#ecf0f1')
        self.graphWidget.setLabel('bottom', 'Tempo', color='#ecf0f1')
        self.graphWidget.setLogMode(y=True)
        self.graphWidget.showGrid(x=True, y=True, alpha=0.3)
        self.graphWidget.addLegend(brush='#2c3e50', pen='#3498db', labelTextColor='#ecf0f1')
        
        # Configurações de estilo adicional para o gráfico
        plotStyle = """
            color: #ecf0f1;
            background-color: #1a1a2e;
            border: 1px solid #3498db;
            border-radius: 2px;
            padding: 5px;
            selection-background-color: #3498db;
        """
        residualLayout.addWidget(self.graphWidget)
        
        # Controles do gráfico
        graphControlLayout = QHBoxLayout()
        
        controlButtonStyle = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                              stop:0 #3498db, stop:1 #2980b9);
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 2px;
                font-weight: bold;
                font-size: 11px;
                text-align: center;
            }
            
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                              stop:0 #2980b9, stop:1 #2475a8);
            }
            
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                              stop:0 #2475a8, stop:1 #1f6591);
            }
        """
        
        self.clearPlotButton = QPushButton("Limpar Gráfico", self)
        self.clearPlotButton.setStyleSheet(controlButtonStyle)
        self.clearPlotButton.clicked.connect(self.clearResidualPlot)
        
        self.toggleScaleButton = QPushButton("Alternar Escala", self)
        self.toggleScaleButton.setStyleSheet(controlButtonStyle)
        self.toggleScaleButton.clicked.connect(self.toggleLogScale)
        
        self.exportPlotDataButton = QPushButton("Exportar Dados", self)
        self.exportPlotDataButton.setStyleSheet(controlButtonStyle)
        self.exportPlotDataButton.clicked.connect(self.exportPlotData)
        
        graphControlLayout.addWidget(self.clearPlotButton)
        graphControlLayout.addWidget(self.toggleScaleButton)
        graphControlLayout.addWidget(self.exportPlotDataButton)
        
        residualLayout.addLayout(graphControlLayout)
        
        # Adicionar painéis ao layout de visualização
        visualizationLayout.addLayout(residualLayout, 1)  # Toda a largura para o gráfico
        
        rightContentLayout.addLayout(visualizationLayout)
        
        # Adicionar os painéis principal e lateral ao layout do conteúdo
        contentLayout.addWidget(leftPanel)
        contentLayout.addLayout(rightContentLayout, 1)
        
        self.mainVerticalLayout.addLayout(contentLayout, 1)

    def toggleLogScale(self):
        """Toggles between linear and logarithmic scale on the Y-axis."""
        current = self.graphWidget.getViewBox().getState()['logMode'][1]
        self.graphWidget.setLogMode(y=not current)
        scale_type = "logarithmic" if not current else "linear"
        self.outputArea.append(f"{scale_type.capitalize()} scale activated", 2000)

    def exportPlotData(self):
        """Exports the plot data to a CSV file."""
        if not self.timeData:
            self.outputArea.append("No data to export", 2000)
            return
            
        fileName, _ = QFileDialog.getSaveFileName(
            self, "Save Residual Data", "", "CSV Files (*.csv)"
        )
        
        if fileName:
            with open(fileName, 'w') as f:
                header = "Time," + ",".join(self.residualData.keys())
                f.write(header + "\n")
                
                for i, time in enumerate(self.timeData):
                    line = f"{time}"
                    for var in self.residualData:
                        if i < len(self.residualData[var]):
                            value = self.residualData[var][i]
                            line += f",{value if value is not None else ''}"
                        else:
                            line += ","
                    f.write(line + "\n")
                    
            self.outputArea.append(f"Data exported to {fileName}")
        
    def onTreeViewDoubleClicked(self, index):
        """Abre a janela de edição de arquivos ao clicar em um arquivo na árvore."""
        item = self.treeModel.itemFromIndex(index)
        if item and not item.hasChildren(): 
            filePath = item.data(Qt.UserRole)
            if filePath:
                fileEditorWindow = FileEditorWindow(self.baseDir, self)
                fileEditorWindow.populateTreeView(self.baseDir)  
                fileEditorWindow.show()

                file = QtCore.QFile(filePath)
                if file.open(QtCore.QIODevice.ReadOnly | QtCore.QIODevice.Text):
                    fileEditorWindow.currentFilePath = filePath
                    fileEditorWindow.fileEditor.setPlainText(str(file.readAll(), 'utf-8'))
                    file.close()
    
    def setupStatusBar(self):
        """Configura a barra de status com design moderno."""
        self.statusBar = QStatusBar(self)
        
        # Estilo para os labels da barra de status
        labelStyle = """
            QLabel {
                background-color: transparent;
                color: #ecf0f1;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 11px;
            }
        """
        
        # Informações do mesh
        self.meshPathLabel = QLabel("Malha: Nenhuma", self.statusBar)
        self.meshPathLabel.setStyleSheet(labelStyle)
        
        # Solver atual
        self.solverLabel = QLabel(f"Solver: {self.currentSolver}", self.statusBar)
        self.solverLabel.setStyleSheet(labelStyle)
        
        # Uso da CPU
        self.cpuUsageLabel = QLabel("CPU: --%", self.statusBar)
        self.cpuUsageLabel.setStyleSheet(labelStyle)
        
        # Uso de memória
        self.memUsageLabel = QLabel("Memória: --%", self.statusBar)
        self.memUsageLabel.setStyleSheet(labelStyle)
        
        # Adiciona os widgets à barra de status
        self.statusBar.addPermanentWidget(self.solverLabel, 1)
        self.statusBar.addPermanentWidget(self.meshPathLabel, 1)
        self.statusBar.addPermanentWidget(self.cpuUsageLabel)
        self.statusBar.addPermanentWidget(self.memUsageLabel)
        
        self.mainVerticalLayout.addWidget(self.statusBar)
    
    def updateSystemUsage(self):
        try:
            with open('/proc/stat', 'r') as f:
                lines = f.readlines()
                if lines:
                    values = lines[0].split()[1:]
                    if len(values) >= 4:
                        user, nice, system, idle = map(int, values[:4])
                        total = user + nice + system + idle
                        
                        if hasattr(self, 'lastTotal') and hasattr(self, 'lastIdle'):
                            deltaTotal = total - self.lastTotal
                            deltaIdle = idle - self.lastIdle
                            
                            if deltaTotal > 0 and self.lastTotal > 0:
                                cpuUsage = 100 * (deltaTotal - deltaIdle) / deltaTotal
                                self.cpuUsageLabel.setText(f"CPU: {int(cpuUsage)}%")
                        
                        self.lastTotal = total
                        self.lastIdle = idle
        except:
            pass
        
        storage = QtCore.QStorageInfo(QtCore.QDir.rootPath())
        memUsed = (storage.bytesTotal() - storage.bytesFree()) / (1024.0**3)
        memTotal = storage.bytesTotal() / (1024.0**3)
        memPercent = (memUsed / memTotal) * 100 if memTotal > 0 else 0
        
        self.memUsageLabel.setText(
            f"Memory: {int(memPercent)}% ({memUsed:.1f}G/{memTotal:.1f}G)"
        )
    
    def populateTreeView(self, casePath=None):
        """Função removida pois a visualização de árvore foi descontinuada."""
        pass
    
    def addDirectoryToTree(self, path, parent):
        """Função removida pois a visualização de árvore foi descontinuada."""
        pass
    
    def openParaview(self):
        if not self.baseDir:
            self.outputArea.append("Erro: Nenhum caso selecionado")
            return
        foam_file = os.path.join(self.baseDir, "foam.foam")
        if not os.path.exists(foam_file):
            # Cria o arquivo vazio se não existir
            with open(foam_file, "w") as f:
                pass
            self.outputArea.append(f"Arquivo {foam_file} criado automaticamente.")
        command = f"paraview --data={foam_file}"
        process = QProcess(self)
        process.start(command)
        if not process.waitForStarted():
            self.outputArea.append("Erro ao abrir o ParaView")
        else:
            self.outputArea.append("ParaView iniciado com sucesso")
    
    def checkMesh(self):
        if not self.baseDir or not os.path.exists(self.baseDir):
            self.outputArea.append("Erro: Nenhum caso selecionado ou diretório base inválido.")
            return

        controlDictPath = os.path.join(self.baseDir, "system", "controlDict")
        if not os.path.exists(controlDictPath):
            self.outputArea.append(f"Erro: Arquivo controlDict não encontrado em {controlDictPath}.")
            return

        self.outputArea.append("Executando checkMesh...")
        command = f'source /opt/{self.currentOpenFOAMVersion}/etc/bashrc && checkMesh'

        process = QProcess(self)
        process.setWorkingDirectory(self.baseDir)
        self.setupProcessEnvironment(process)
        self.connectProcessSignals(process)
        process.start("bash", ["-c", command])
    
    def convertMesh(self):
        if not self.unvFilePath:
            self.outputArea.append("Erro: Nenhum arquivo UNV selecionado")
            return

        self.outputArea.append("Convertendo malha para OpenFOAM...")
        command = f'source /opt/{self.currentOpenFOAMVersion}/etc/bashrc && ideasUnvToFoam {self.unvFilePath}'

        process = QProcess(self)
        process.setWorkingDirectory(self.baseDir)
        self.setupProcessEnvironment(process)
        self.connectProcessSignals(process)
        process.start("bash", ["-c", command])
    
    def parseResiduals(self, line):
        """
        Analisa a saída do terminal para capturar resíduos e tempos.
        """

        # Captura dados de profiling e envia para o painel dedicado
        if "ExecutionTime" in line or "ClockTime" in line:
            self.profilingLogs.append(line)

        # Captura informações de performance (número de iterações)
        if ("Solving for" in line) and ("Final residual" in line) and ("No Iterations" in line):
            parts = line.split(',')
            if len(parts) >= 3:
                iterations_part = parts[2].strip()
                if "No Iterations" in iterations_part:
                    iter_count = iterations_part.split()[-1]
                    solver_info = f"Solver performance: {iter_count} iterations"
                    self.profilingLogs.append(solver_info)

        # Captura o tempo atual (Time = x)
        current_time_match = re.search(r'Time = ([0-9.eE+-]+)', line)
        if current_time_match:
            current_time = float(current_time_match.group(1))
            if current_time not in self.timeData:
                self.timeData.append(current_time)
                if len(self.maxCloudAlphaData) < len(self.timeData):
                    self.maxCloudAlphaData.append(None)

        # Captura resíduos de qualquer solver (ex: DILUPBiCGStab, GAMG, DICPBiCGStab, etc.)
        residual_match = re.search(
            r'([A-Z]+[a-zA-Z]*)[:]*\s+Solving for ([a-zA-Z0-9_.]+), Initial residual = ([0-9.eE+-]+)',
            line
        )
        if residual_match:
            solver_name = residual_match.group(1)
            variable = residual_match.group(2)
            residual = float(residual_match.group(3))

            if variable not in self.residualData:
                self.residualData[variable] = []
                color_idx = len(self.residualData) % len(self.colors)
                pen = pg.mkPen(color=self.colors[color_idx], width=2)
                self.residualLines[variable] = self.graphWidget.plot(
                    [], [], name=variable, pen=pen
                )

            while len(self.residualData[variable]) < len(self.timeData) - 1:
                self.residualData[variable].append(None)

            self.residualData[variable].append(residual)
            self.updateResidualPlot(variable)

        # Captura max(cloud:alpha)
        max_alpha_match = re.search(r'Max cell volume fraction\s*=\s*([0-9.eE+-]+)', line)
        if max_alpha_match:
            value = float(max_alpha_match.group(1))
            if self.timeData:
                if len(self.maxCloudAlphaData) == len(self.timeData):
                    self.maxCloudAlphaData[-1] = value
                elif len(self.maxCloudAlphaData) < len(self.timeData):
                    while len(self.maxCloudAlphaData) < len(self.timeData) - 1:
                        self.maxCloudAlphaData.append(None)
                    self.maxCloudAlphaData.append(value)
                else:
                    self.maxCloudAlphaData = self.maxCloudAlphaData[:len(self.timeData)-1] + [value]
                self.updateMaxCloudAlphaPlot()

    def updateResidualPlot(self, variable):
        """
        Atualiza o gráfico de resíduos para uma variável específica.
        """
        if variable in self.residualLines:
            filtered_time_data = [t for t, r in zip(self.timeData, self.residualData[variable]) if r is not None]
            filtered_residual_data = [r for r in self.residualData[variable] if r is not None]

            if filtered_time_data and filtered_residual_data:
                self.residualLines[variable].setData(filtered_time_data, filtered_residual_data)

    def updateMaxCloudAlphaPlot(self):
        # Cria a linha se não existir
        if self.maxCloudAlphaLine is None:
            pen = pg.mkPen(color='r', width=2, style=Qt.DashLine)
            self.maxCloudAlphaLine = self.graphWidget.plot([], [], name='max(cloud:alpha)', pen=pen)
        # Plota apenas os pontos válidos
        times = [t for t, v in zip(self.timeData, self.maxCloudAlphaData) if v is not None]
        values = [v for v in self.maxCloudAlphaData if v is not None]
        self.maxCloudAlphaLine.setData(times, values)

    def clearResidualPlot(self):
        self.timeData = []
        self.residualData = {}
        self.graphWidget.clear()
        self.residualLines = {}
        self.maxCloudAlphaData = []
        self.maxCloudAlphaLine = None

    def connectProcessSignals(self, process):
        """
        Conecta os sinais do processo para capturar saída e atualizar resíduos.
        """
        def readOutput():
            while process.canReadLine():
                line = process.readLine().data().decode("utf-8").strip()
                self.outputArea.append(line)  
                self.parseResiduals(line)    

        def readError():
            while process.canReadLine():
                line = process.readLine().data().decode("utf-8").strip()
                self.outputArea.append(f"Erro: {line}")

        process.readyReadStandardOutput.connect(readOutput)
        process.readyReadStandardError.connect(readError)

        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.outputArea.append("Iniciando simulação...")
        
        if not self.unvFilePath:
            self.outputArea.append("Erro: Nenhum caso selecionado")
            return

        required_dirs = ["0", "system", "constant"]
        if not all(QDir(self.unvFilePath).exists(dir_name) for dir_name in required_dirs):
            self.outputArea.append("Erro: A pasta selecionada não contém os diretórios necessários (0, system, constant).")
            return

        if not self.currentSolver:
            self.outputArea.append("Erro: Nenhum solver selecionado")
            return

        self.clearResidualPlot()

        command = f'bash -l -c "source /opt/{self.currentOpenFOAMVersion}/etc/bashrc && mpirun -np 6 {self.currentSolver} -parallel"'

        self.outputArea.append(f"Iniciando simulação com {self.currentSolver}...")
        self.currentProcess = QProcess(self)
        self.setupProcessEnvironment(self.currentProcess)

        def finished(code):
            if code == 0:
                self.outputArea.append("Simulação concluída com sucesso.")
            else:
                self.outputArea.append(f"Simulação finalizada com código de erro: {code}")

        self.currentProcess.finished.connect(finished)
        self.connectProcessSignals(self.currentProcess)

        self.currentProcess.start("bash", ["-l", "-c", command])
        self.currentProcess.finished.connect(lambda: self.logSimulationCompletion(start_time))

    def logSimulationCompletion(self, start_time):
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "Finished" if self.currentProcess.exitCode() == 0 else "Interrupted"
        self.simulationHistory.add_entry(
            solver=self.currentSolver,
            case_path=self.unvFilePath,
            start_time=start_time,
            end_time=end_time,
            status=status
        )
        self.outputArea.append(f"Simulation {status}.")

    def reconstructPar(self):
        if not self.unvFilePath:
            self.outputArea.append("Error: No case selected.")
            return
        
        self.outputArea.append("Reconstruindo caso...")
        command = f'bash -l -c "source /opt/{self.currentOpenFOAMVersion}/etc/bashrc && reconstructPar"'
        
        self.currentProcess = QProcess(self)
        self.setupProcessEnvironment(self.currentProcess)
        self.currentProcess.setWorkingDirectory(self.baseDir)
        
        def finished(code):
            self.outputArea.append(f"Reconstrução finalizada com código {code}", 5000)
            self.currentProcess = None
        
        self.currentProcess.finished.connect(finished)
        self.connectProcessSignals(self.currentProcess)
        self.currentProcess.start(command)
    
    def decomposePar(self):
        if not self.unvFilePath:
            self.outputArea.append("Error: No case selected.")
            return

        required_dirs = ["0", "system", "constant"]
        if not all(QDir(self.unvFilePath).exists(dir_name) for dir_name in required_dirs):
            self.outputArea.append("Error: The selected folder does not contain the required directories (0, system, constant).")
            return

        self.outputArea.append("Starting decomposition...")
        command = f'source /opt/{self.currentOpenFOAMVersion}/etc/bashrc && decomposePar'

        self.currentProcess = QProcess(self)
        self.setupProcessEnvironment(self.currentProcess)
        self.currentProcess.setWorkingDirectory(self.baseDir)

        def finished(code):
            if code == 0:
                self.outputArea.append("Decomposition completed successfully.")
            else:
                self.outputArea.append(f"Decomposition finished with error code: {code}")

        self.currentProcess.finished.connect(finished)
        self.connectProcessSignals(self.currentProcess)
        self.currentProcess.start("bash", ["-c", command])
    
    def clearSimulation(self):
        caseDir = QDir(self.baseDir)
        timeDirs = caseDir.entryList(QDir.Dirs | QDir.NoDotAndDotDot)
        removedAny = False
        
        for dirName in timeDirs:
            try:
                timeValue = float(dirName)
                if timeValue > 0:
                    timeDir = QDir(caseDir.filePath(dirName))
                    if timeDir.removeRecursively():
                        self.outputArea.append(f"Removed time folder: {dirName}")
                        removedAny = True
            except ValueError:
                pass
        
        if removedAny:
            self.outputArea.append("Time folders removed successfully.")
        else:
            self.outputArea.append("No time folders found to remove.")

    def runSimulation(self):
        """Inicia a simulação após perguntar o tempo de execução e atualizar o controlDict."""
        if self.currentProcess and self.currentProcess.state() == QProcess.Running:
            self.outputArea.append("Outra simulação já está em execução. Pare-a antes de iniciar uma nova.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Tempo de Simulação")
        layout = QVBoxLayout(dialog)
        label = QLabel("Informe o tempo final da simulação (endTime):", dialog)
        timeInput = QLineEdit(dialog)
        timeInput.setPlaceholderText("Exemplo: 10 (deixe em branco para padrão)")
        okButton = QPushButton("OK", dialog)
        cancelButton = QPushButton("Cancelar", dialog)
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(okButton)
        buttonLayout.addWidget(cancelButton)
        layout.addWidget(label)
        layout.addWidget(timeInput)
        layout.addLayout(buttonLayout)
        dialog.setLayout(layout)

        def on_ok():
            dialog.accept()
        def on_cancel():
            dialog.reject()
        okButton.clicked.connect(on_ok)
        cancelButton.clicked.connect(on_cancel)

        if not dialog.exec_():
            self.outputArea.append("Execução da simulação cancelada pelo usuário.")
            return

        user_end_time = timeInput.text().strip()

        import os
        controlDict_path = os.path.join(self.baseDir, "system", "controlDict")
        if not os.path.exists(controlDict_path):
            self.outputArea.append("Erro: controlDict não encontrado.")
            return

        try:
            with open(controlDict_path, "r") as f:
                lines = f.readlines()

            new_lines = []
            for line in lines:
                if line.strip().startswith("endTime") and user_end_time:
                    new_lines.append(f"endTime         {user_end_time};\n")
                else:
                    new_lines.append(line)

            with open(controlDict_path, "w") as f:
                f.writelines(new_lines)

            self.outputArea.append("Arquivo controlDict atualizado com novo endTime.")
        except Exception as e:
            self.outputArea.append(f"Erro ao atualizar controlDict: {e}")
            return

        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.outputArea.append("Iniciando simulação...")

        if not self.unvFilePath:
            self.outputArea.append("Erro: Nenhum caso selecionado.")
            return

        caseDir = self.baseDir
        allrunPath = os.path.join(caseDir, "Allrun")
        if not os.path.exists(allrunPath):
            self.outputArea.append("Erro: Script Allrun não encontrado.")
            return

        if not os.access(allrunPath, os.X_OK):
            os.chmod(allrunPath, 0o755)

        command = f'source /opt/{self.currentOpenFOAMVersion}/etc/bashrc && cd {caseDir} && ./Allrun'
        self.currentProcess = QProcess(self)
        self.setupProcessEnvironment(self.currentProcess)
        self.currentProcess.setWorkingDirectory(caseDir)

        def finished(code):
            if code == 0:
                self.outputArea.append("Simulação finalizada com sucesso.")
            else:
                self.outputArea.append(f"Simulação finalizada com erro: {code}")
            self.logSimulationCompletion(start_time)

        self.currentProcess.finished.connect(finished)
        self.connectProcessSignals(self.currentProcess)
        self.currentProcess.start("bash", ["-c", command])
    
    def pauseSimulation(self):
        """Pausa a simulação em execução enviando o sinal SIGSTOP para todos os processos filhos."""
        if self.currentProcess and self.currentProcess.state() == QProcess.Running:
            pid = self.currentProcess.processId()
            if pid:
                try:
                    import psutil
                    parent = psutil.Process(pid)
                    # Pausa todos os filhos recursivamente
                    for child in parent.children(recursive=True):
                        child.suspend()
                    parent.suspend()
                    self.outputArea.append("Simulação pausada (todos os processos).")
                except Exception as e:
                    self.outputArea.append(f"Erro ao pausar a simulação: {e}")
            else:
                self.outputArea.append("Não foi possível obter o PID do processo para pausar.")
        else:
            self.outputArea.append("Nenhuma simulação em execução para pausar.")

    def resumeSimulation(self):
        """Retoma uma simulação pausada enviando o sinal SIGCONT para todos os processos filhos."""
        if self.currentProcess:
            pid = self.currentProcess.processId()
            if pid:
                try:
                    import psutil
                    parent = psutil.Process(pid)
                    # Retoma todos os filhos recursivamente
                    for child in parent.children(recursive=True):
                        child.resume()
                    parent.resume()
                    self.outputArea.append("Simulação retomada (todos os processos).")
                except Exception as e:
                    self.outputArea.append(f"Erro ao retomar a simulação: {e}")
            else:
                self.outputArea.append("Não foi possível obter o PID do processo para retomar.")
        else:
            self.outputArea.append("Nenhuma simulação para retomar.")

    def restartSimulation(self):
        """Reinicia a simulação."""
        # First, stop any existing simulation
        if self.currentProcess and self.currentProcess.state() == QProcess.Running:
            self.stopSimulation() # Ensure it's fully stopped
            # Wait a bit for the process to terminate if stopSimulation is asynchronous in effect
            # Or ensure stopSimulation is blocking or provides a callback/signal
            # For simplicity here, we assume stopSimulation effectively stops it before proceeding.

        # Clear necessary previous run data, e.g., processor directories, logs if needed
        # self.clearDecomposedProcessors() # Example, if you always want to clear these
        # self.clearOldProcessorDirs() # As per your existing method

        self.outputArea.append("Reiniciando a simulação...")
        # Re-run the simulation. This might be similar to runSimulation or a specific restart logic
        self.runSimulation() # Assuming runSimulation can handle starting fresh or from where it should

    def clearDecomposedProcessors(self):
        if not self.baseDir: 
            self.outputArea.append("Erro: Nenhum diretório base selecionado.")
            return

        caseDir = QDir(self.baseDir)
        processorDirs = caseDir.entryList(["processor*"], QDir.Dirs | QDir.NoDotAndDotDot)
        removedAny = False

        for dirName in processorDirs:
            processorDir = QDir(caseDir.filePath(dirName))
            if processorDir.removeRecursively():
                self.outputArea.append(f"Removendo pasta: {dirName}")
                removedAny = True

        if removedAny:
            self.outputArea.append("Pastas de decomposição removidas com sucesso.")
        else:
            self.outputArea.append("Nenhuma pasta de decomposição encontrada.")
    
    def stopSimulation(self):
        """Para o processo de simulação em execução e seus processos filhos."""
        if self.currentProcess and self.currentProcess.state() == QProcess.Running:
            self.outputArea.append("Parando a simulação...")
            
            pid = self.currentProcess.processId()
            
            try:
                parent = psutil.Process(pid)
                for child in parent.children(recursive=True): 
                    child.terminate()  
                parent.terminate()  
                gone, still_alive = psutil.wait_procs(parent.children(recursive=True), timeout=5)
                for p in still_alive:
                    p.kill()  
                parent.kill()
                self.outputArea.append("Simulação interrompida com sucesso.")
            except psutil.NoSuchProcess:
                self.outputArea.append("O processo já foi encerrado.")
            except Exception as e:
                self.outputArea.append(f"Erro ao encerrar o processo: {e}")
            
            from datetime import datetime
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            start_time = end_time  
            self.simulationHistory.add_entry(
                solver=self.currentSolver,
                case_path=self.unvFilePath,
                start_time=start_time,
                end_time=end_time,
                status="Interrompida"
            )
            self.outputArea.append("Simulação Interrompida.")
            
            self.currentProcess = None 
        else:
            self.outputArea.append("Nenhuma simulação em execução para parar.")

    def clearTerminal(self):
        self.outputArea.clear()
        self.outputArea.append("Terminal limpo.", 2000)

    def enableProfiling(self):
        import os
        # Verifica se o diretório base está selecionado e é válido
        if not self.baseDir or not os.path.isdir(self.baseDir):
            self.outputArea.append("Erro: Nenhum diretório base selecionado.")
            return
        required_dirs = ["0", "constant", "system"]
        if not all(os.path.isdir(os.path.join(self.baseDir, d)) for d in required_dirs):
            self.outputArea.append("Erro: O diretório base selecionado não contém as pastas 0, constant e system.")
            return
        controlDict_path = os.path.join(self.baseDir, "system", "controlDict")
        if not os.path.exists(controlDict_path):
            self.outputArea.append(f"Erro: controlDict não encontrado em {controlDict_path}.")
            return
        try:
            with open(controlDict_path, "r") as f:
                lines = f.readlines()
            
            # Remove blocos InfoSwitches e DebugSwitches existentes, se houver
            new_lines = []
            inside_info = False
            inside_debug = False
            
            for line in lines:
                if 'InfoSwitches' in line:
                    inside_info = True
                    continue
                elif 'DebugSwitches' in line:
                    inside_debug = True
                    continue
                
                if inside_info or inside_debug:
                    if '}' in line:
                        inside_info = False
                        inside_debug = False
                    continue
                
                new_lines.append(line)
            
            # Adiciona blocos InfoSwitches e DebugSwitches antes do final do arquivo
            insert_idx = len(new_lines)
            for i, line in enumerate(reversed(new_lines)):
                if '*****' in line:
                    insert_idx = len(new_lines) - i - 1
                    break
            
            # Adiciona InfoSwitches
            new_lines.insert(insert_idx, 'InfoSwitches\n')
            new_lines.insert(insert_idx+1, '{\n')
            new_lines.insert(insert_idx+2, '    time 1;\n')
            new_lines.insert(insert_idx+3, '}\n')
            new_lines.insert(insert_idx+4, '\n')
            
            # Adiciona DebugSwitches
            new_lines.insert(insert_idx+5, 'DebugSwitches\n')
            new_lines.insert(insert_idx+6, '{\n')
            new_lines.insert(insert_idx+7, '    // 0 = off, 1 = on\n')
            new_lines.insert(insert_idx+8, '    InfoSwitch          1;\n')
            new_lines.insert(insert_idx+9, '    TimeRegistry        1;  // Esta é a chave! Garante profiling detalhado.\n')
            new_lines.insert(insert_idx+10, '}\n')
            
            with open(controlDict_path, "w") as f:
                f.writelines(new_lines)
            
            self.outputArea.append("Profiling completo ativado no controlDict!")
            self.outputArea.append("- InfoSwitches { time 1; } adicionado")
            self.outputArea.append("- DebugSwitches { TimeRegistry 1; } adicionado")
            self.profilingLogs.append("Profiling detalhado ativado - TimeRegistry habilitado!")
            
        except Exception as e:
            self.outputArea.append(f"Erro ao ativar profiling: {e}")
    
    def editFile(self):
        """Abre um arquivo para edição no editor."""
        fileName, _ = QFileDialog.getOpenFileName(
            self,
            "Escolher Arquivo de Código",
            self.systemDir,
            "Todos os Arquivos (*);;Arquivos de Código (*.dict *.txt *.swp)"
        )
        if fileName:
            file = QtCore.QFile(fileName)
            if file.open(QtCore.QIODevice.ReadOnly | QtCore.QIODevice.Text):
                self.currentFilePath = fileName
                self.fileEditor.setPlainText(str(file.readAll(), 'utf-8'))
                file.close()
                self.outputArea.append(f"Arquivo de código aberto: {fileName}")
            else:
                self.outputArea.append("Erro ao abrir o arquivo para edição.")
        else:
            self.outputArea.append("Nenhum arquivo selecionado.")
    
    def saveFile(self):
        if not self.currentFilePath:
            self.outputArea.append("Nenhum arquivo carregado para salvar.")
            return
        
        file = QtCore.QFile(self.currentFilePath)
        if file.open(QtCore.QIODevice.WriteOnly | QtCore.QIODevice.Text):
            file.write(self.fileEditor.toPlainText().encode('utf-8'))
            file.close()
            self.outputArea.append(f"Arquivo salvo com sucesso: {self.currentFilePath}")
        else:
            self.outputArea.append("Erro ao salvar o arquivo.")
    
    def executeTerminalCommand(self):
        command = self.terminalInput.text()
        if command:
            self.outputArea.append(f"> {command}")
            self.terminalInput.clear()
            
            process = QProcess(self)
            self.setupProcessEnvironment(process)
            self.connectProcessSignals(process)
            
            process.setWorkingDirectory(self.baseDir)
            
            fullCommand = f'source /opt/{self.currentOpenFOAMVersion}/etc/bashrc && {command}'
            process.start("bash", ["-l", "-c", fullCommand])
            
    
    def setupProcessEnvironment(self, process):
        env = QProcessEnvironment.systemEnvironment()
        foam_dir = f"/opt/{self.currentOpenFOAMVersion}"
        env.insert("FOAM_RUN", foam_dir)
        env.insert("LD_LIBRARY_PATH", f"{foam_dir}/lib:{foam_dir}/platforms/linux64GccDPInt32Opt/lib")
        process.setProcessEnvironment(env)
    
    def connectProcessSignals(self, process):
        """Conecta os sinais do processo para capturar saída e atualizar resíduos."""
        def readOutput():
            while process.canReadLine():
                output = str(process.readLine(), 'utf-8').strip()
                self.outputArea.append(output)
                self.parseResiduals(output)
                QApplication.processEvents() 

        def readError():
            error = str(process.readAllStandardError(), 'utf-8').strip()  
            self.outputArea.append(error)

        process.readyReadStandardOutput.connect(readOutput)
        process.readyReadStandardError.connect(readError)


    def calculateRates(self):
        try:
            d = 0.106
            n = 30
            m = 10
            dy_in_0 = 0.00142
            dy_wall_0 = 0.008

            results = calculate_increase_rate(d, n, m, dy_in_0, dy_wall_0)

            self.outputArea.append("Resultados do cálculo de Δy")
            for key, value in results.items():
                self.outputArea.append(f"{key}: {value:.5f}" if isinstance(value, float) else f"{key}: {value}")
        except Exception as e:
            self.outputArea.append(f"Erro ao calcular taxas: {str(e)}")

    def openRateCalculationDialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Calcular Δy")
        dialog.setModal(True)
        dialog.resize(350, 250)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #2c3e50;
                border: 2px solid #3498db;
                border-radius: 2px;
            }
        """)

        layout = QVBoxLayout(dialog)

        # Styling for labels in dialog
        label_style = """
            QLabel {
                color: #ecf0f1;
                font-weight: bold;
                font-size: 12px;
                padding: 5px;
            }
        """
        
        # Styling for input fields in dialog
        input_style = """
            QLineEdit {
                background-color: #34495e;
                color: white;
                border: 1px solid #3498db;
                border-radius: 2px;
                padding: 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #2ecc71;
                background-color: #3c4f66;
            }
        """

        dLabel = QLabel("d (diâmetro):", dialog)
        dLabel.setStyleSheet(label_style)
        dInput = QLineEdit(dialog)
        dInput.setStyleSheet(input_style)
        dInput.setPlaceholderText("Exemplo: 0.106")

        nLabel = QLabel("n (distância do bocal):", dialog)
        nLabel.setStyleSheet(label_style)
        nInput = QLineEdit(dialog)
        nInput.setStyleSheet(input_style)
        nInput.setPlaceholderText("Exemplo: 30")

        mLabel = QLabel("m (distância de transição):", dialog)
        mLabel.setStyleSheet(label_style)
        mInput = QLineEdit(dialog)
        mInput.setStyleSheet(input_style)
        mInput.setPlaceholderText("Exemplo: 10")

        dyIn0Label = QLabel("dy_in_0 (altura inicial):", dialog)
        dyIn0Label.setStyleSheet(label_style)
        dyIn0Input = QLineEdit(dialog)
        dyIn0Input.setStyleSheet(input_style)
        dyIn0Input.setPlaceholderText("Exemplo: 0.00142")

        dyWall0Label = QLabel("dy_wall_0 (altura na parede):", dialog)
        dyWall0Label.setStyleSheet(label_style)
        dyWall0Input = QLineEdit(dialog)
        dyWall0Input.setStyleSheet(input_style)
        dyWall0Input.setPlaceholderText("Exemplo: 0.008")

        calculateButton = QPushButton("Calcular", dialog)
        calculateButton.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 2px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #229954;
            }
        """)
        calculateButton.clicked.connect(lambda: self.calculateRatesFromDialog(
            dialog, dInput.text(), nInput.text(), mInput.text(), dyIn0Input.text(), dyWall0Input.text()
        ))

        layout.addWidget(dLabel)
        layout.addWidget(dInput)
        layout.addWidget(nLabel)
        layout.addWidget(nInput)
        layout.addWidget(mLabel)
        layout.addWidget(mInput)
        layout.addWidget(dyIn0Label)
        layout.addWidget(dyIn0Input)
        layout.addWidget(dyWall0Label)
        layout.addWidget(dyWall0Input)
        layout.addWidget(calculateButton)

        dialog.exec_()

    def calculateRatesFromDialog(self, dialog, d, n, m, dy_in_0, dy_wall_0):
        try:
            
            d = float(d)
            n = float(n)
            m = float(m)
            dy_in_0 = float(dy_in_0)
            dy_wall_0 = float(dy_wall_0)

            results = calculate_increase_rate(d, n, m, dy_in_0, dy_wall_0)

            self.outputArea.append("Resultados do cálculo de Δy")
            for key, value in results.items():
                self.outputArea.append(f"{key}: {value:.5f}" if isinstance(value, float) else f"{key}: {value}")

            dialog.accept()
        except ValueError:
            self.outputArea.append("Erro: Certifique-se de que todos os valores são números válidos.")
        except Exception as e:
            self.outputArea.append(f"Erro ao calcular taxas: {str(e)}")

    def openFluidPropertiesDialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Calcular Propriedades do Fluido")
        dialog.setModal(True)
        dialog.resize(300, 300)

        layout = QVBoxLayout(dialog)

        tempLabel = QLabel("Temperatura (°C):", dialog)
        tempInput = QLineEdit(dialog)
        tempInput.setPlaceholderText("Exemplo: 46.6")

        pressureLabel = QLabel("Pressão (MPa):", dialog)
        pressureInput = QLineEdit(dialog)
        pressureInput.setPlaceholderText("Exemplo: 9.64")

        salinityLabel = QLabel("Salinidade (mg/L):", dialog)
        salinityInput = QLineEdit(dialog)
        salinityInput.setPlaceholderText("Exemplo: 323000")

        calculateButton = QPushButton("Calcular", dialog)
        calculateButton.clicked.connect(lambda: self.calculateFluidProperties(
            dialog, tempInput.text(), pressureInput.text(), salinityInput.text()
        ))

        layout.addWidget(tempLabel)
        layout.addWidget(tempInput)
        layout.addWidget(pressureLabel)
        layout.addWidget(pressureInput)
        layout.addWidget(salinityLabel)
        layout.addWidget(salinityInput)
        layout.addWidget(calculateButton)

        dialog.exec_()

    def calculateFluidProperties(self, dialog, temp, pressure, salinity):
        try:
            temp = float(temp)
            pressure = float(pressure) * 10  # Converte MPa para bar
            salinity = float(salinity) / 1e6  # Converte mg/L para fração mássica

            fluid = FluidProperties()

            density = fluid.brine_density(temp, pressure, salinity)
            viscosity = fluid.brine_viscosity(temp, pressure, salinity) * 1000  # Converte Pa.s para mPa.s

            self.outputArea.append("Resultados das Propriedades do Fluido:")
            self.outputArea.append(f"Temperatura: {temp} °C")
            self.outputArea.append(f"Pressão: {pressure} bar")
            self.outputArea.append(f"Salinidade: {salinity:.6f} (fração mássica)")
            self.outputArea.append(f"Densidade: {density:.2f} kg/m³")
            self.outputArea.append(f"Viscosidade: {viscosity:.6f} mPa·s")

            dialog.accept()
        except ValueError:
            self.outputArea.append("Erro: Certifique-se de que todos os valores são números válidos.")
        except Exception as e:
            self.outputArea.append(f"Erro ao calcular propriedades: {str(e)}")

    def openSimulationHistory(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Histórico de Simulações")
        dialog.resize(800, 400)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #2c3e50;
                border: 2px solid #3498db;
                border-radius: 2px;
            }
        """)

        layout = QVBoxLayout(dialog)

        self.historyTable = QTableWidget(dialog)
        self.historyTable.setStyleSheet("""
            QTableWidget {
                background-color: #34495e;
                color: white;
                border: 1px solid #3498db;
                border-radius: 2px;
                gridline-color: #3498db;
                selection-background-color: #3498db;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3498db;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: white;
                padding: 10px;
                border: 1px solid #3498db;
                font-weight: bold;
            }
        """)
        self.historyTable.setColumnCount(5)
        self.historyTable.setHorizontalHeaderLabels(["Solver", "Malha", "Início", "Fim", "Status"])
        self.loadHistoryIntoTable()
        layout.addWidget(self.historyTable)

        buttonLayout = QHBoxLayout()
        # Styled buttons for dialog
        button_style = """
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 2px;
                font-weight: bold;
                font-size: 12px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
        """
        clearAllButton = QPushButton("Limpar Tudo", dialog)
        clearAllButton.setStyleSheet(button_style)
        clearAllButton.clicked.connect(self.clearAllSimulations)
        buttonLayout.addWidget(clearAllButton)

        deleteSelectedButton = QPushButton("Excluir Selecionado", dialog)
        deleteSelectedButton.setStyleSheet(button_style.replace("#e74c3c", "#f39c12").replace("#c0392b", "#e67e22").replace("#a93226", "#d35400"))
        deleteSelectedButton.clicked.connect(self.deleteSelectedSimulation)
        buttonLayout.addWidget(deleteSelectedButton)

        # Botão para ver os últimos logs
        viewLogsButton = QPushButton("Ver Últimos Logs", dialog)
        viewLogsButton.setStyleSheet(button_style.replace("#e74c3c", "#2980b9").replace("#c0392b", "#3498db").replace("#a93226", "#2471a3"))
        viewLogsButton.clicked.connect(self.showSelectedSimulationLogs)
        buttonLayout.addWidget(viewLogsButton)

        layout.addLayout(buttonLayout)
        dialog.setLayout(layout)
        dialog.exec_()

    def showSelectedSimulationLogs(self):
        selectedRow = self.historyTable.currentRow()
        if selectedRow == -1:
            QMessageBox.warning(self, "Nenhuma Seleção", "Por favor, selecione uma simulação para ver os logs.")
            return
        history = self.simulationHistory.get_history()
        if selectedRow >= len(history):
            QMessageBox.warning(self, "Erro", "Índice de simulação inválido.")
            return
        entry = history[selectedRow]
        log_data = entry.get("log_data", [])
        log_text = "\n".join(log_data) if log_data else "Nenhum log relevante encontrado."
        logDialog = QDialog(self)
        logDialog.setWindowTitle("Últimos Logs da Simulação")
        logDialog.resize(700, 400)
        vbox = QVBoxLayout(logDialog)
        logEdit = QTextEdit(logDialog)
        logEdit.setReadOnly(True)
        logEdit.setPlainText(log_text)
        vbox.addWidget(logEdit)
        closeBtn = QPushButton("Fechar", logDialog)
        closeBtn.clicked.connect(logDialog.accept)
        vbox.addWidget(closeBtn)
        logDialog.setLayout(vbox)
        logDialog.exec_()

    def loadHistoryIntoTable(self):
        """Carrega o histórico na tabela."""
        history = self.simulationHistory.get_history()
        self.historyTable.setRowCount(len(history))
        for row, entry in enumerate(history):
            self.historyTable.setItem(row, 0, QTableWidgetItem(entry["solver"]))
            self.historyTable.setItem(row, 1, QTableWidgetItem(entry["case_path"]))
            self.historyTable.setItem(row, 2, QTableWidgetItem(entry["start_time"]))
            self.historyTable.setItem(row, 3, QTableWidgetItem(entry["end_time"]))
            self.historyTable.setItem(row, 4, QTableWidgetItem(entry["status"]))

    def clearAllSimulations(self):
        """Limpa todo o histórico de simulações."""
        reply = QMessageBox.question(
            self, "Confirmação", "Tem certeza de que deseja limpar todo o histórico?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.simulationHistory.history = []
            self.simulationHistory.save_history()
            self.loadHistoryIntoTable()  
            QMessageBox.information(self, "Histórico Limpo", "Todo o histórico foi limpo com sucesso.")

    def deleteSelectedSimulation(self):
        """Exclui a simulação selecionada na tabela."""
        selectedRow = self.historyTable.currentRow()
        if selectedRow == -1:
            QMessageBox.warning(self, "Nenhuma Seleção", "Por favor, selecione uma simulação para excluir.")
            return

        reply = QMessageBox.question(
            self, "Confirmação", "Tem certeza de que deseja excluir a simulação selecionada?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            del self.simulationHistory.history[selectedRow]
            self.simulationHistory.save_history()
            self.loadHistoryIntoTable()
            QMessageBox.information(self, "Simulação Excluída", "A simulação selecionada foi excluída com sucesso.")

    def filterTreeView(self, text):
        """Filtra os itens da árvore de diretórios com base no texto inserido."""
        def filterItems(item, text):
            match = text.lower() in item.text().lower()
            for row in range(item.rowCount()):
                child = item.child(row)
                match = filterItems(child, text) or match
            item.setHidden(match)
            return match

        for row in range(self.treeModel.rowCount()):
            rootItem = self.treeModel.item(row)
            filterItems(rootItem, text)

    def configureDecomposeParCores(self):
        """Abre um diálogo para configurar o número de núcleos e atualiza o decomposeParDict."""
        num_cores, ok = QInputDialog.getInt(
            self,
            "Configurar Núcleos",
            "Digite o número de núcleos para decomposePar:",
            min=1,
            max=128,  
            value=2 
        )
        if ok:
            self.num_cores = num_cores  
            decompose_par_dict_path = os.path.join(self.baseDir, "system", "decomposeParDict")
            try:
                with open(decompose_par_dict_path, "r") as file:
                    lines = file.readlines()

                with open(decompose_par_dict_path, "w") as file:
                    for line in lines:
                        if "numberOfSubdomains" in line:
                            file.write(f"numberOfSubdomains {num_cores};\n")
                        else:
                            file.write(line)

                self.outputArea.append(f"Arquivo decomposeParDict atualizado com {num_cores} núcleos.")

            except FileNotFoundError:
                self.outputArea.append("Erro: Arquivo decomposeParDict não encontrado.")
            except Exception as e:
                self.outputArea.append(f"Erro ao atualizar decomposeParDict: {str(e)}")

    def load_config(self):
        """Carrega as configurações do arquivo config.json."""
        if os.path.exists(self.config_file):
            with open(self.config_file, "r") as file:
                return json.load(file)
        else:
            return {}

    def save_config(self):
        """Salva as configurações no arquivo config.json."""
        with open(self.config_file, "w") as file:
            json.dump(self.config, file, indent=4)

    def set_base_dir(self):
        """Permite ao usuário definir o diretório base."""
        new_base_dir = QFileDialog.getExistingDirectory(
            self, "Escolher Diretório Base", 
            self.baseDir, 
            QFileDialog.ShowDirsOnly
        )
        if new_base_dir: 
            self.baseDir = new_base_dir
            self.systemDir = os.path.join(self.baseDir, "system")
            self.config["baseDir"] = self.baseDir
            self.save_config()
            self.outputArea.append(f"Diretório base configurado para: {self.baseDir}")
            
            # self.populateTreeView(self.baseDir)
        else:
            self.outputArea.append("Nenhum diretório base selecionado.")

    def showSimulationLogs(self):
        """Exibe os logs da simulação em tempo real."""
        if not self.baseDir or not os.path.exists(self.baseDir):
            self.outputArea.append("Erro: Nenhum caso selecionado ou diretório base inválido.")
            return

        logFilePath = os.path.join(self.baseDir, "log.foamRun")
        if not os.path.exists(logFilePath):
            self.outputArea.append(f"Erro: Arquivo de log não encontrado em {logFilePath}.")
            return

        self.outputArea.append("Exibindo logs em tempo real...")
        command = f"tail -f {logFilePath}"

        self.logProcess = QProcess(self)
        self.logProcess.setProcessChannelMode(QProcess.MergedChannels)
        self.logProcess.readyReadStandardOutput.connect(self.readLogOutput)
        self.logProcess.finished.connect(self.logProcessFinished)

        self.logProcess.start("bash", ["-c", command])

    def readLogOutput(self):
        """Lê a saída do processo de logs e exibe na área de saída."""
        if self.logProcess:
            output = str(self.logProcess.readAllStandardOutput(), 'utf-8').strip()
            lines = output.split("\n") 
            for line in lines:
                self.outputArea.append(line) 
                self.parseResiduals(line)  

    def logProcessFinished(self):
        """Notifica quando o processo de logs é finalizado."""
        self.outputArea.append("Exibição de logs finalizada.")
        self.logProcess = None

    def closeEvent(self, event):
        """Intercepta o evento de fechamento da janela para encerrar processos em execução."""
        if self.currentProcess and self.currentProcess.state() == QProcess.Running:
            self.currentProcess.terminate()
            if not self.currentProcess.waitForFinished(3000):  
                self.currentProcess.kill() 
            self.outputArea.append("Simulação interrompida ao fechar o programa.")
        
        if self.logProcess and self.logProcess.state() == QProcess.Running:
            self.logProcess.terminate()
            if not self.logProcess.waitForFinished(3000):
                self.logProcess.kill()
            self.outputArea.append("Processo de logs interrompido ao fechar o programa.")
        
        event.accept()  
        
class FluidProperties:
    def __init__(self):
        self.c0, self.c1, self.c2, self.c3 = (999.842594, 0.06793952, -0.00909529, 0.0001001685) # Example values
        self.A, self.B = (0.0004831439, 0.000001617e-05) # Example values
        self.mu_c_800 = 2.0  
        self.mu_w_base = 0.00089  

    def water_density(self, T, P):
        """Calcula a densidade da água pura (rho_w) em função da temperatura (T) e pressão (P)."""
        rho_0 = self.c0 + self.c1 * T + self.c2 * T**2 + self.c3 * T**3
        rho_w = rho_0 + self.A * P + self.B * P**2
        return rho_w

    def brine_density(self, T, P, X):
        """Calcula a densidade da salmoura (rho_b) em função de T, P e salinidade (X)."""
        rho_w_TP = self.water_density(T, P)
        rho_b = rho_w_TP + X * (1695 - rho_w_TP)
        return rho_b

    def brine_viscosity(self, T, P, X):
        """Calcula a viscosidade da salmoura (mu_b) em função de T, P e salinidade (X)."""
        if T < 800:
            term1 = self.mu_w_base * (1 + 3 * X) * ((800 - T) / 800) ** 9
            term2 = ((T / 800) ** 9) * (self.mu_w_base * (1 - X) + X * self.mu_c_800)
            mu_b = (term1 + term2) / (((800 - T) / 800) ** 9 + (T / 800) ** 9)
        else:
            mu_b = self.mu_w_base * (1 - X) + self.mu_c_800 * X
        return mu_b

class FileEditorWindow(QDialog):
    def __init__(self, baseDir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("File Editor")
        self.resize(800, 600)
        self.setModal(True)  

        self.baseDir = baseDir
        self.currentFilePath = ""

        layout = QVBoxLayout(self)

        self.fileEditor = QTextEdit(self)
        layout.addWidget(self.fileEditor)

        buttonLayout = QHBoxLayout()
        self.saveButton = QPushButton("Save File", self)
        self.saveButton.clicked.connect(self.saveFile)
        buttonLayout.addWidget(self.saveButton)

        self.closeButton = QPushButton("Close", self)
        self.closeButton.clicked.connect(self.close)
        buttonLayout.addWidget(self.closeButton)

        layout.addLayout(buttonLayout)

    def saveFile(self):
        if not self.currentFilePath:
            QMessageBox.warning(self, "Error", "No file loaded to save.")
            return

        file = QtCore.QFile(self.currentFilePath)
        if file.open(QtCore.QIODevice.WriteOnly | QtCore.QIODevice.Text):
            file.write(self.fileEditor.toPlainText().encode('utf-8'))
            file.close()
            QMessageBox.information(self, "Success", f"File saved: {self.currentFilePath}")
        else:
            QMessageBox.warning(self, "Error", "Failed to save the file.")

def openFileEditor(self):
    """Abre a janela separada para o editor de arquivos."""
    self.fileEditorWindow = FileEditorWindow(self.baseDir, self)
    self.fileEditorWindow.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Inicializa a interface
    interface = OpenFOAMInterface()
    interface.show()
    
    sys.exit(app.exec_())
