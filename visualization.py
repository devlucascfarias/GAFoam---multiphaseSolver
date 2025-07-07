import sys
import os
import numpy as np
import traceback
import tempfile
import subprocess
import shutil
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, 
    QPushButton, QLabel, QSplitter, QTreeWidget, QTreeWidgetItem, 
    QColorDialog, QSlider, QGroupBox, QCheckBox, QToolBar, QAction,
    QFileDialog, QMessageBox, QProgressDialog, QInputDialog
)
from PyQt5.QtCore import Qt, QSize, QTimer, QDir
from PyQt5.QtGui import QIcon, QColor

try:
    import vtk
    from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
    from vtkmodules.vtkCommonDataModel import vtkDataSet
    from vtkmodules.vtkIOParallel import vtkPOpenFOAMReader
    from vtkmodules.vtkIOXML import vtkXMLMultiBlockDataWriter
    from vtkmodules.vtkCommonExecutionModel import vtkAlgorithmOutput
    from vtkmodules.vtkFiltersExtraction import vtkExtractBlock
except ImportError:
    print("VTK não está instalado. Instale com: pip install vtk")
    vtk = None

class VisualizationWindow(QMainWindow):
    
    def __init__(self, case_path, parent=None):
        super().__init__(parent)
        self.case_path = case_path
        self.foam_file = None
        
        if vtk is None:
            QMessageBox.critical(self, "VTK não disponível", 
                                "A biblioteca VTK não está instalada. Instale com: pip install vtk")
            self.close()
            return
        
        print(f"Inicializando VisualizationWindow com caso em: {case_path}")
        
        for file in os.listdir(case_path):
            if file.endswith('.foam'):
                self.foam_file = os.path.join(case_path, file)
                print(f"Arquivo .foam encontrado: {self.foam_file}")
                break
        
        if not self.foam_file:
            self.foam_file = os.path.join(case_path, 'foam.foam')
            with open(self.foam_file, 'w') as f:
                f.write('')
        
        self.reader = None
        self.mapper = None
        self.actor = None
        self.available_fields = []
        self.available_times = []
        self.current_field = None
        self.current_time_index = 0
        self.outline_actor = None
        
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.advance_time_step)
        self.animation_timer.setInterval(33)
        
        self.setup_ui()
        self.setup_vtk()
        self.load_foam_case()
        
        self.pause_button.setEnabled(False)

    def setup_ui(self):
        self.setWindowTitle(f"GAFoam Visualization - {os.path.basename(self.case_path)}")
        self.resize(1200, 800)
        
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(250)
        left_panel.setMaximumWidth(300)
        
        time_group = QGroupBox("Controle de Tempo")
        time_layout = QVBoxLayout(time_group)
        
        self.time_label = QLabel("Tempo: 0.0s")
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(0)
        self.time_slider.setSingleStep(1)
        self.time_slider.setPageStep(1)
        self.time_slider.setTracking(True)
        self.time_slider.valueChanged.connect(self.on_time_slider_changed)
        time_layout.addWidget(self.time_label)
        time_layout.addWidget(self.time_slider)
        
        animation_layout = QHBoxLayout()
        
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play_animation)
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause_animation)
        self.pause_button.setEnabled(False)
        
        animation_layout.addWidget(self.play_button)
        animation_layout.addWidget(self.pause_button)
        time_layout.addLayout(animation_layout)
        
        field_group = QGroupBox("Campos")
        field_layout = QVBoxLayout(field_group)
        
        field_label = QLabel("Campo:")
        self.field_combo = QComboBox()
        self.field_combo.currentIndexChanged.connect(self.on_field_changed)
        
        self.colorbar_checkbox = QCheckBox("Mostrar barra de cores")
        self.colorbar_checkbox.setChecked(True)
        self.colorbar_checkbox.stateChanged.connect(self.update_visualization)
        
        self.outline_checkbox = QCheckBox("Mostrar contorno")
        self.outline_checkbox.setChecked(True)
        self.outline_checkbox.stateChanged.connect(self.toggle_outline)
        
        self.auto_scale_checkbox = QCheckBox("Escala automática")
        self.auto_scale_checkbox.setChecked(False)
        self.auto_scale_checkbox.setToolTip("Usar escala automática baseada nos valores mínimos e máximos do campo")
        self.auto_scale_checkbox.stateChanged.connect(self.update_visualization)
        
        self.shading_checkbox = QCheckBox("Sombreamento suave")
        self.shading_checkbox.setChecked(True)
        self.shading_checkbox.setToolTip("Ativar sombreamento suave para melhor visualização")
        self.shading_checkbox.stateChanged.connect(self.toggle_shading)
        
        self.color_button = QPushButton("Alterar escala de cores")
        self.color_button.clicked.connect(self.change_color_map)
        
        field_layout.addWidget(field_label)
        field_layout.addWidget(self.field_combo)
        field_layout.addWidget(self.colorbar_checkbox)
        field_layout.addWidget(self.outline_checkbox)
        field_layout.addWidget(self.auto_scale_checkbox)
        field_layout.addWidget(self.shading_checkbox)
        field_layout.addWidget(self.color_button)
        
        view_group = QGroupBox("Visualização")
        view_layout = QVBoxLayout(view_group)
        
        self.reset_view_button = QPushButton("Resetar Visualização")
        self.reset_view_button.clicked.connect(self.reset_camera)
        
        self.wireframe_button = QPushButton("Modo Wireframe")
        self.wireframe_button.setCheckable(True)
        self.wireframe_button.clicked.connect(self.toggle_wireframe)
        
        self.screenshot_button = QPushButton("Capturar Tela")
        self.screenshot_button.clicked.connect(self.take_screenshot)
        
        view_layout.addWidget(self.reset_view_button)
        view_layout.addWidget(self.wireframe_button)
        view_layout.addWidget(self.screenshot_button)
        
        left_layout.addWidget(time_group)
        left_layout.addWidget(field_group)
        left_layout.addWidget(view_group)
        left_layout.addStretch()
        
        self.vtk_widget = QVTKRenderWindowInteractor()
        
        main_layout.addWidget(left_panel)
        main_layout.addWidget(self.vtk_widget, 1)
        
        self.setCentralWidget(central_widget)
        
        toolbar = QToolBar("Ferramentas de Visualização")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        export_mp4_action = QAction("Exportar para MP4", self)
        export_mp4_action.triggered.connect(self.export_to_mp4)
        toolbar.addAction(export_mp4_action)
        
        export_action = QAction("Exportar para VTK", self)
        export_action.triggered.connect(self.export_to_vtk)
        toolbar.addAction(export_action)

    def setup_vtk(self):
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.15, 0.15, 0.2)
        
        light1 = vtk.vtkLight()
        light1.SetPosition(1, 1, 1)
        light1.SetIntensity(0.8)
        light1.SetLightTypeToHeadlight()
        self.renderer.AddLight(light1)
        
        light2 = vtk.vtkLight()
        light2.SetPosition(-1, -1, 1)
        light2.SetIntensity(0.3)
        light2.SetLightTypeToHeadlight()
        self.renderer.AddLight(light2)
        
        self.renderer.SetTwoSidedLighting(True)
        
        self.render_window = self.vtk_widget.GetRenderWindow()
        self.render_window.AddRenderer(self.renderer)
        
        self.interactor = self.render_window.GetInteractor()
        
        style = vtkInteractorStyleTrackballCamera()
        self.interactor.SetInteractorStyle(style)
        
        self.scalar_bar = vtk.vtkScalarBarActor()
        self.scalar_bar.SetTitle("Valor")
        self.scalar_bar.SetNumberOfLabels(6)
        self.scalar_bar.SetLabelFormat("%.3g")
        self.scalar_bar.SetPosition(0.88, 0.15)
        self.scalar_bar.SetWidth(0.12)
        self.scalar_bar.SetHeight(0.7)
        
        self.scalar_bar.GetLabelTextProperty().SetFontFamilyToArial()
        self.scalar_bar.GetLabelTextProperty().SetFontSize(11)
        self.scalar_bar.GetLabelTextProperty().SetBold(True)
        self.scalar_bar.GetLabelTextProperty().SetItalic(False)
        self.scalar_bar.GetLabelTextProperty().SetShadow(False)
        self.scalar_bar.GetLabelTextProperty().SetColor(1, 1, 1)
        
        self.scalar_bar.GetTitleTextProperty().SetFontFamilyToArial()
        self.scalar_bar.GetTitleTextProperty().SetFontSize(13)
        self.scalar_bar.GetTitleTextProperty().SetBold(True)
        self.scalar_bar.GetTitleTextProperty().SetItalic(False)
        self.scalar_bar.GetTitleTextProperty().SetShadow(False)
        self.scalar_bar.GetTitleTextProperty().SetColor(1, 1, 1)
        
        if hasattr(self.scalar_bar, 'SetTextPositionToPrecedeScalarBar'):
            self.scalar_bar.SetTextPositionToPrecedeScalarBar()
        
        self.scalar_bar.SetDrawFrame(True)
        
        self.renderer.AddActor2D(self.scalar_bar)
        
        self.interactor.Initialize()

    def is_decomposed_case(self):
        return os.path.isdir(os.path.join(self.case_path, 'processor0'))

    def load_foam_case(self):
        try:
            self.reader = vtkPOpenFOAMReader()
            self.reader.SetFileName(self.foam_file)
            
            try:
                if hasattr(self.reader, 'SetParseRegions'):
                    self.reader.SetParseRegions(True)
                
                if hasattr(self.reader, 'CacheMetaDataOff'):
                    self.reader.CacheMetaDataOff()
                
                if hasattr(self.reader, 'SetCreateCellToPoint'):
                    self.reader.SetCreateCellToPoint(True)
                
                if hasattr(self.reader, 'DisableAllPointArrays'):
                    self.reader.DisableAllPointArrays()
                
                if hasattr(self.reader, 'DisableAllCellArrays'):
                    self.reader.DisableAllCellArrays()
                
                if hasattr(self.reader, 'DisableAllLagrangianArrays'):
                    self.reader.DisableAllLagrangianArrays()
                
                if hasattr(self.reader, 'DisableAllPatchArrays'):
                    self.reader.DisableAllPatchArrays()
                
                print("Configurações do leitor OpenFOAM aplicadas.")
            except Exception as api_error:
                print(f"Aviso ao configurar o leitor OpenFOAM: {str(api_error)}")
            
            self.reader.UpdateInformation()
            
            print(f"Carregando caso: {self.foam_file}")
            
            if self.is_decomposed_case():
                if hasattr(self.reader, 'SetCaseType'):
                    self.reader.SetCaseType(0)
                print("Caso está decomposto.")
            else:
                if hasattr(self.reader, 'SetCaseType'):
                    self.reader.SetCaseType(1)
                print("Caso está reconstruído.")
            
            # Ativar todos os campos
            try:
                # Arrays de pontos (Point Arrays)
                if hasattr(self.reader, 'GetNumberOfPointArrays'):
                    for i in range(self.reader.GetNumberOfPointArrays()):
                        try:
                            array_name = self.reader.GetPointArrayName(i)
                            self.reader.SetPointArrayStatus(array_name, 1)
                            self.available_fields.append(array_name)
                            print(f"Campo de pontos ativado: {array_name}")
                        except Exception as e:
                            print(f"Erro ao ativar campo de pontos {i}: {e}")
                
                # Arrays de células (Cell Arrays)
                if hasattr(self.reader, 'GetNumberOfCellArrays'):
                    for i in range(self.reader.GetNumberOfCellArrays()):
                        try:
                            array_name = self.reader.GetCellArrayName(i)
                            self.reader.SetCellArrayStatus(array_name, 1)
                            if array_name not in self.available_fields:
                                self.available_fields.append(array_name)
                            print(f"Campo de células ativado: {array_name}")
                        except Exception as e:
                            print(f"Erro ao ativar campo de células {i}: {e}")
                
                # Patches
                if hasattr(self.reader, 'GetNumberOfPatchArrays'):
                    for i in range(self.reader.GetNumberOfPatchArrays()):
                        try:
                            patch_name = self.reader.GetPatchArrayName(i)
                            self.reader.SetPatchArrayStatus(patch_name, 1)
                            print(f"Patch ativado: {patch_name}")
                        except Exception as e:
                            print(f"Erro ao ativar patch {i}: {e}")
                            
            except Exception as e:
                print(f"Erro ao ativar campos: {e}")
            
            # Atualizar o leitor
            self.reader.Update()
            print("Leitor atualizado.")
            
            # Carregar tempos disponíveis
            try:
                times_found = False
                
                if hasattr(self.reader, 'GetTimeValues'):
                    print("Tentando obter tempos via GetTimeValues()")
                    self.reader.Update()  # Forçar atualização antes de tentar obter tempos
                    time_values = self.reader.GetTimeValues()
                    
                    if time_values:
                        # Verificar se é um objeto VTK
                        if hasattr(time_values, 'GetNumberOfValues') and time_values.GetNumberOfValues() > 0:
                            self.available_times = [time_values.GetValue(i) for i in range(time_values.GetNumberOfValues())]
                            print(f"Obtidos {len(self.available_times)} tempos via GetTimeValues() (objeto VTK)")
                        else:
                            # É uma tupla, lista ou outro tipo
                            if time_values and len(time_values) > 0:
                                self.available_times = list(time_values)
                                print(f"Obtidos {len(self.available_times)} tempos via GetTimeValues() (lista)")
                            else:
                                print("AVISO: GetTimeValues() retornou uma lista vazia.")
                        
                        # Ordenar os tempos para garantir que a animação seja correta
                        if self.available_times:
                            self.available_times.sort()
                            times_found = True
                            self.update_time_slider()
                    else:
                        print("AVISO: GetTimeValues() retornou None ou vazio.")
                else:
                    print("AVISO: O leitor não possui o método GetTimeValues()")
                
                if not times_found:
                    print("AVISO: Não foi possível obter tempos via API do VTK. Tentando detectar manualmente.")
                    # Tentar detectar tempos manualmente
                    time_dirs = self._find_time_directories()
                    if time_dirs and len(time_dirs) > 0:
                        print(f"Diretórios de tempo encontrados manualmente: {len(time_dirs)} tempos")
                        self.available_times = time_dirs
                        times_found = True
                        self.update_time_slider()
                
                if not times_found or len(self.available_times) == 0:
                    print("AVISO: Nenhum tempo disponível foi encontrado!")
                
                print(f"Total de tempos disponíveis: {len(self.available_times) if self.available_times else 0}")
                if self.available_times:
                    print(f"Primeiro tempo: {self.available_times[0]:.3f}s, Último tempo: {self.available_times[-1]:.3f}s")
                
            except Exception as e:
                print(f"Erro ao carregar tempos disponíveis: {e}")
                # Tentar detectar tempos manualmente como último recurso
                try:
                    time_dirs = self._find_time_directories()
                    if time_dirs and len(time_dirs) > 0:
                        print(f"Tempos encontrados como último recurso: {len(time_dirs)} tempos")
                        self.available_times = time_dirs
                        self.update_time_slider()
                except Exception as inner_e:
                    print(f"Erro ao tentar encontrar tempos manualmente: {inner_e}")
                    import traceback
                    traceback.print_exc()
                    if time_dirs:
                        print(f"Encontrados diretórios de tempo manualmente: {time_dirs}")
                        self.available_times = time_dirs
                        self.time_slider.setMaximum(len(self.available_times) - 1)
                        self.time_label.setText(f"Tempo: {self.available_times[0]:.3f}s")
            else:
                print("AVISO: GetTimeValues() não retornou valores.")
            
            field_names = ["alpha.particles", "alpha.water", "p", "p_rgh", "U.particles", "U.water"]
            for field in field_names:
                if field in self.available_fields:
                    self.field_combo.addItem(field)
            
            for field in self.available_fields:
                if field not in field_names:
                    self.field_combo.addItem(field)
            
            if self.field_combo.count() > 0:
                default_index = self.field_combo.findText("alpha.particles")
                if default_index == -1:
                    default_index = 0
                self.field_combo.setCurrentIndex(default_index)
                self.current_field = self.field_combo.currentText()
            
            try:
                # Criar contorno da malha
                outline = vtk.vtkOutlineFilter()
                outline.SetInputConnection(self.reader.GetOutputPort())
                outline_mapper = vtk.vtkPolyDataMapper()
                outline_mapper.SetInputConnection(outline.GetOutputPort())
                self.outline_actor = vtk.vtkActor()
                self.outline_actor.SetMapper(outline_mapper)
                self.outline_actor.GetProperty().SetColor(1, 1, 1)  # Branco
                self.renderer.AddActor(self.outline_actor)
                print("Contorno da malha criado com sucesso.")
            except Exception as outline_error:
                print(f"Erro ao criar contorno da malha: {outline_error}")
                self.outline_actor = None
            
            # Criar visualização inicial
            # Verificar uma última vez se temos tempos disponíveis
            if not self.available_times or len(self.available_times) == 0:
                print("Tentando encontrar tempos como último recurso...")
                time_dirs = self._find_time_directories()
                if time_dirs:
                    self.available_times = time_dirs
                    # Atualizar o slider
                    self.update_time_slider()
                    
            # Forçar atualização do slider novamente para garantir
            if self.available_times:
                self.update_time_slider()
                print(f"Estado final do slider: valor={self.time_slider.value()}, máximo={self.time_slider.maximum()}")
                print(f"Tempos disponíveis para animação: {len(self.available_times)}")
                
            self.update_visualization()
            print("Visualização inicializada com sucesso.")
            
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "Erro ao Carregar Caso", f"Ocorreu um erro ao carregar o caso: {str(e)}")
            print(f"Erro ao carregar caso OpenFOAM: {e}")
            traceback.print_exc()
            self.close()

    def _find_time_directories(self):
        """Encontra manualmente os diretórios de tempo no caso."""
        time_dirs = []
        
        print(f"Procurando diretórios de tempo em: {self.case_path}")
        
        # Verificar se o caso está decomposto
        processor_dir = os.path.join(self.case_path, 'processor0')
        if os.path.isdir(processor_dir):
            # Se estiver decomposto, buscar tempos no processor0
            print("Caso decomposto, buscando tempos em processor0")
            found_times = []
            for item in os.listdir(processor_dir):
                try:
                    # Tenta converter para float para ver se é um diretório de tempo
                    time_value = float(item)
                    found_times.append(time_value)
                except ValueError:
                    # Não é um diretório de tempo
                    pass
            
            # Se encontrou tempos, usa eles
            if found_times:
                time_dirs = found_times
                print(f"Encontrados {len(found_times)} tempos em processor0")
        
        # Se não encontrou tempos em processor0 ou não é um caso decomposto
        if not time_dirs:
            # Buscar tempos no diretório principal
            print("Buscando tempos no diretório principal")
            for item in os.listdir(self.case_path):
                item_path = os.path.join(self.case_path, item)
                
                # Verificar se é um diretório e se o nome pode ser convertido para float
                if os.path.isdir(item_path):
                    try:
                        time_value = float(item)
                        # Adicionamos sem verificar conteúdo para maximizar a chance de encontrar tempos
                        time_dirs.append(time_value)
                        print(f"Tempo encontrado: {time_value}")
                    except ValueError:
                        # Não é um diretório de tempo
                        pass
        
        # Ordenar os tempos
        time_dirs.sort()
        print(f"Total de diretórios de tempo encontrados: {len(time_dirs)}")
        
        # Atualizar o slider diretamente aqui se encontrarmos tempos
        if time_dirs:
            self.available_times = time_dirs
            self.time_slider.setMaximum(len(time_dirs) - 1)
            print(f"Slider atualizado diretamente para máximo: {len(time_dirs) - 1}")
            
        return time_dirs

    def update_visualization(self):
        if not self.reader or not self.current_field:
            print("Não é possível atualizar a visualização: leitor ou campo não definidos")
            return
        
        try:
            # Remover visualizações anteriores
            if self.actor:
                self.renderer.RemoveActor(self.actor)
            
            # Atualizar para o tempo selecionado
            if self.available_times and len(self.available_times) > self.current_time_index:
                try:
                    time_step = self.available_times[self.current_time_index]
                    print(f"Definindo tempo para: {time_step:.3f}s (índice {self.current_time_index})")
                    
                    # Definir o passo de tempo para o leitor
                    exec_info = self.reader.GetExecutive().GetOutputInformation(0)
                    exec_info.Set(vtk.vtkStreamingDemandDrivenPipeline.UPDATE_TIME_STEP(), time_step)
                    
                    # Forçar uma atualização do leitor com o novo tempo
                    self.reader.Modified()
                    self.reader.Update()
                except Exception as time_error:
                    print(f"Erro ao definir o tempo: {time_error}")
            
            # Extrair os dados do campo selecionado
            try:
                self.reader.Update()
                output = self.reader.GetOutput()
                
                # Verificar se temos um bloco válido
                if not output or not output.GetNumberOfBlocks():
                    print("Aviso: O leitor não retornou blocos de dados válidos.")
                    return
                
                # Criar geometria para visualização
                geometry = vtk.vtkGeometryFilter()
                try:
                    # Tentar obter o primeiro bloco (pode variar dependendo da versão do VTK)
                    geometry.SetInputData(output.GetBlock(0))
                except Exception as block_error:
                    print(f"Erro ao acessar bloco 0: {block_error}")
                    try:
                        # Tentar outro método
                        geometry.SetInputConnection(self.reader.GetOutputPort())
                    except Exception as alt_error:
                        print(f"Erro ao usar porta de saída direta: {alt_error}")
                        return
                        
                geometry.Update()
                
                # Criar mapper e ator
                self.mapper = vtk.vtkPolyDataMapper()
                self.mapper.SetInputConnection(geometry.GetOutputPort())
                
                # Configurar o mapper para usar o campo selecionado
                try:
                    if "." in self.current_field:
                        # Campos vetoriais ou com nomes compostos
                        self.mapper.SelectColorArray(self.current_field)
                        self.mapper.SetScalarModeToUsePointFieldData()
                    else:
                        # Campos escalares
                        self.mapper.SetScalarModeToUsePointData()
                        self.mapper.SelectColorArray(self.current_field)
                except Exception as array_error:
                    print(f"Erro ao selecionar array para colorir: {array_error}")
                
                # Configurar lookup table para cores - melhor visualização como o ParaView
                lut = vtk.vtkLookupTable()
                
                # Verificar se é alpha.particles para usar paleta específica similar ao ParaView
                # Configurar paleta de cores para os diferentes campos
                if "alpha" in self.current_field:
                    # Cores similares às do ParaView para alpha fields (azul-branco-vermelho)
                    lut.SetNumberOfTableValues(256)
                    
                    # Definir gradiente azul -> branco -> vermelho com foco nos valores para alpha
                    # Com maior saturação e contraste para melhor visualização
                    for i in range(256):
                        if i < 128:  # Primeira metade (azul intenso -> branco)
                            t = i / 127.0
                            # Aumentar o contraste com curva mais acentuada para valores baixos
                            t_enhanced = pow(t, 0.6)  # Exponente menor para destacar valores baixos
                            r = t_enhanced
                            g = t_enhanced
                            b = 1.0
                        else:  # Segunda metade (branco -> vermelho intenso)
                            t = (i - 128) / 127.0
                            # Aumentar o contraste com curva mais acentuada
                            t_enhanced = pow(t, 1.4)  # Exponente maior para aumentar contraste
                            r = 1.0
                            g = 1.0 - t_enhanced  # Redução total do verde para vermelho mais vibrante
                            b = 1.0 - t_enhanced  # Redução total do azul
                        # Usar opacidade total para melhor visualização
                        lut.SetTableValue(i, r, g, b, 1.0)
                    
                    # Verificar se deve usar escala automática
                    if not self.auto_scale_checkbox.isChecked():
                        # Ajustar o range para melhor visualização de alpha (geralmente 0-1)
                        self.mapper.SetScalarRange(0.0, 1.0)
                    else:
                        # Usar a escala automática baseada nos dados (como ParaView)
                        dataRange = geometry.GetOutput().GetScalarRange()
                        self.mapper.SetScalarRange(dataRange[0], dataRange[1])
                        print(f"Range automático: {dataRange[0]} - {dataRange[1]}")
                    
                    # Atualizar o título da barra de cores com o range
                    scalarRange = self.mapper.GetScalarRange()
                    self.scalar_bar.SetTitle(f"{self.current_field}\n[{scalarRange[0]:.3f} - {scalarRange[1]:.3f}]")
                else:
                    # Para outros campos, escolher coloração baseada no tipo de campo
                    if "p" in self.current_field or "pressure" in self.current_field.lower():
                        # Escala de cores melhorada para pressão - verde intenso-amarelo-vermelho intenso
                        lut.SetNumberOfTableValues(256)
                        for i in range(256):
                            if i < 128:
                                t = i / 127.0
                                # Intensificar cores para melhor visualização
                                t_enhanced = pow(t, 0.8)  # Aumentar contraste
                                r = t_enhanced * 0.5  # Reduzir componente vermelho
                                g = 1.0  # Verde intenso
                                b = t_enhanced * 0.5  # Reduzir componente azul
                            else:
                                t = (i - 128) / 127.0
                                t_enhanced = pow(t, 1.2)  # Aumentar contraste
                                r = 1.0  # Vermelho intenso
                                g = 1.0 - t_enhanced  # Redução total do verde
                                b = 0.0  # Sem azul para vermelho mais vibrante
                            lut.SetTableValue(i, r, g, b, 1.0)  # Sem transparência
                    elif "U" in self.current_field or "velocity" in self.current_field.lower():
                        # Escala de cores melhorada para velocidade - azul-ciano-verde-amarelo-vermelho
                        # Com maior saturação e sem transparência
                        lut.SetNumberOfTableValues(256)
                        for i in range(256):
                            pos = i / 255.0
                            if pos < 0.25:
                                # Azul intenso para ciano
                                t = pos * 4
                                t_enhanced = pow(t, 0.8)  # Aumentar contraste
                                r = 0.0
                                g = t_enhanced
                                b = 1.0
                            elif pos < 0.5:
                                # Ciano para verde intenso
                                t = (pos - 0.25) * 4
                                t_enhanced = pow(t, 1.0)  # Linear
                                r = 0.0
                                g = 1.0
                                b = 1.0 - t_enhanced
                            elif pos < 0.75:
                                # Verde intenso para amarelo
                                t = (pos - 0.5) * 4
                                t_enhanced = pow(t, 1.0)  # Linear
                                r = t_enhanced
                                g = 1.0
                                b = 0.0
                            else:
                                # Amarelo para vermelho intenso
                                t = (pos - 0.75) * 4
                                t_enhanced = pow(t, 1.0)  # Linear
                                r = 1.0
                                g = 1.0 - t_enhanced
                                b = 0.0
                            lut.SetTableValue(i, r, g, b, 1.0)  # Sem transparência
                    else:
                        # Coloração padrão aprimorada para outros campos
                        # Usando mapa de cores personalizado para melhor visualização
                        lut.SetNumberOfTableValues(256)
                        
                        # Definir gradiente personalizado com cores mais intensas
                        for i in range(256):
                            # Mapeamento HSV melhorado (Matiz, Saturação, Valor)
                            # Matiz vai de azul (240°) a vermelho (0°)
                            hue = 0.667 - (i / 255.0) * 0.667  # De 0.667 (azul) a 0 (vermelho)
                            sat = 0.9  # Alta saturação para cores mais vibrantes
                            val = 0.95  # Alto brilho para melhor visualização
                            
                            # Converter HSV para RGB
                            import colorsys
                            r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
                            lut.SetTableValue(i, r, g, b, 1.0)  # Sem transparência
                    
                    # Verificar se deve usar escala automática
                    if self.auto_scale_checkbox.isChecked():
                        # Usar a escala automática baseada nos dados (como ParaView)
                        try:
                            dataRange = geometry.GetOutput().GetScalarRange()
                            if dataRange[0] != dataRange[1]:  # Evitar range zerado
                                self.mapper.SetScalarRange(dataRange[0], dataRange[1])
                                print(f"Range automático: {dataRange[0]} - {dataRange[1]}")
                        except Exception as range_error:
                            print(f"Erro ao obter range automático: {range_error}")
                    
                    # Atualizar o título da barra de cores com o range
                    try:
                        scalarRange = self.mapper.GetScalarRange()
                        self.scalar_bar.SetTitle(f"{self.current_field}\n[{scalarRange[0]:.3g} - {scalarRange[1]:.3g}]")
                    except Exception as title_error:
                        print(f"Erro ao atualizar título da barra: {title_error}")
                
                self.mapper.SetLookupTable(lut)
                if hasattr(self.mapper, 'SetUseLookupTableScalarRange'):
                    self.mapper.SetUseLookupTableScalarRange(True)
                
                # Criar ator
                self.actor = vtk.vtkActor()
                self.actor.SetMapper(self.mapper)
                
                # Aplicar sombreamento suave se estiver marcado
                if self.shading_checkbox.isChecked():
                    self.actor.GetProperty().SetInterpolationToPhong()
                else:
                    self.actor.GetProperty().SetInterpolationToFlat()
                
                # Melhorar a aparência visual
                self.actor.GetProperty().SetAmbient(0.1)
                self.actor.GetProperty().SetDiffuse(0.7)
                self.actor.GetProperty().SetSpecular(0.5)
                self.actor.GetProperty().SetSpecularPower(20)
                
                self.renderer.AddActor(self.actor)
                
                # Configurar a barra de cores
                self.scalar_bar.SetLookupTable(self.mapper.GetLookupTable())
                self.scalar_bar.SetTitle(self.current_field)
                self.scalar_bar.SetVisibility(self.colorbar_checkbox.isChecked())
                
                # Resetar a câmera para enquadrar a visualização
                self.renderer.ResetCamera()
                
                # Atualizar a visualização
                self.render_window.Render()
                print("Visualização atualizada com sucesso.")
                
            except Exception as output_error:
                print(f"Erro ao processar saída do leitor: {output_error}")
                import traceback
                traceback.print_exc()
                
        except Exception as viz_error:
            print(f"Erro ao atualizar visualização: {viz_error}")
            import traceback
            traceback.print_exc()
        
        # Atualizar a visualização
        self.render_window.Render()

    def play_animation(self):
        """Inicia a animação dos passos de tempo."""
        # Verificar novamente se temos tempos disponíveis
        if not self.available_times or len(self.available_times) <= 1:
            print("Tempos insuficientes para animação, tentando detectar novamente...")
            # Se ainda não temos tempos, tentar detê-los manualmente
            time_dirs = self._find_time_directories()
            if time_dirs and len(time_dirs) > 1:
                print(f"Detectados {len(time_dirs)} tempos para animação")
                self.available_times = time_dirs
                self.update_time_slider()
            
            # Verificar novamente após a tentativa de detecção
            if not self.available_times or len(self.available_times) <= 1:
                QMessageBox.warning(self, "Aviso", "Não há passos de tempo suficientes para animar.")
                return
        
        # Garantir que o slider esteja atualizado
        self.update_time_slider()
        
        # Mostrar informações de depuração
        print(f"Iniciando animação com {len(self.available_times)} tempos disponíveis")
        print(f"Configuração do slider: valor atual={self.time_slider.value()}, máximo={self.time_slider.maximum()}")
        
        if not self.animation_timer.isActive():
            # Reinicia se estiver no final
                if self.time_slider.value() >= self.time_slider.maximum():
                    print("Reiniciando animação do início")
                    self.time_slider.setValue(0)
                    self.current_time_index = 0
                    self.update_visualization()
                
                # Iniciar o timer com intervalo fixo (33ms = aprox. 30fps)
                self.animation_timer.setInterval(33)
                self.animation_timer.start()
                
                print("Animação iniciada com 30 FPS")
                
                self.play_button.setEnabled(False)
                self.pause_button.setEnabled(True)

    def pause_animation(self):
        """Pausa a animação."""
        if self.animation_timer.isActive():
            self.animation_timer.stop()
            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(False)

    def advance_time_step(self):
        """Avança um passo de tempo na animação."""
        if not self.available_times or len(self.available_times) <= 1:
            print("Não há tempos suficientes para animar")
            self.animation_timer.stop()
            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            return
            
        current_index = self.time_slider.value()
        max_index = self.time_slider.maximum()
        
        print(f"Animação: índice atual={current_index}, máximo={max_index}")
        
        if current_index < max_index:
            next_index = current_index + 1
            try:
                # Verificar se o índice está dentro dos limites
                if next_index < len(self.available_times):
                    print(f"Avançando para o tempo {next_index}/{max_index}: {self.available_times[next_index]:.3f}s")
                    self.current_time_index = next_index
                    self.time_slider.setValue(next_index)
                    self.time_label.setText(f"Tempo: {self.available_times[next_index]:.3f}s")
                    self.update_visualization()
                else:
                    print(f"Índice fora dos limites: {next_index}, max disponível: {len(self.available_times)-1}")
                    self.animation_timer.stop()
                    self.play_button.setEnabled(True)
                    self.pause_button.setEnabled(False)
            except Exception as e:
                print(f"Erro ao avançar para tempo {next_index}: {e}")
                import traceback
                traceback.print_exc()
                self.animation_timer.stop()
                self.play_button.setEnabled(True)
                self.pause_button.setEnabled(False)
        else:
            print("Animação concluída")
            self.animation_timer.stop() # Para a animação no final
            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(False)

    def on_time_slider_changed(self, value):
        if not self.available_times:
            print("Aviso: Não há tempos disponíveis.")
            return
            
        if 0 <= value < len(self.available_times):
            print(f"Slider alterado para valor {value}, tempo: {self.available_times[value]:.3f}s")
            self.current_time_index = value
            self.time_label.setText(f"Tempo: {self.available_times[value]:.3f}s")
            self.update_visualization()
        else:
            print(f"Valor do slider fora dos limites: {value}, max: {len(self.available_times)-1}")
            # Corrigir o valor do slider
            if value >= len(self.available_times):
                self.time_slider.setValue(len(self.available_times) - 1)
            elif value < 0:
                self.time_slider.setValue(0)

    def on_field_changed(self, index):
        if index >= 0:
            self.current_field = self.field_combo.currentText()
            self.update_visualization()

    def toggle_outline(self, state):
        if self.outline_actor:
            self.outline_actor.SetVisibility(state == Qt.Checked)
            self.render_window.Render()

    def toggle_wireframe(self, checked):
        if self.actor:
            if checked:
                self.actor.GetProperty().SetRepresentationToWireframe()
            else:
                self.actor.GetProperty().SetRepresentationToSurface()
            self.render_window.Render()

    def reset_camera(self):
        self.renderer.ResetCamera()
        self.render_window.Render()

    def change_color_map(self):
        if not self.mapper:
            return
        
        color_dialog = QColorDialog(self)
        color_dialog.setWindowTitle("Selecionar Cor Inicial")
        if color_dialog.exec_():
            start_color = color_dialog.currentColor()
            
            color_dialog.setWindowTitle("Selecionar Cor Final")
            if color_dialog.exec_():
                end_color = color_dialog.currentColor()
                
                # Criar novo lookup table
                lut = vtk.vtkLookupTable()
                lut.SetNumberOfColors(256)
                
                # Configurar as cores iniciais e finais
                lut.SetRampToLinear()
                start_rgb = [start_color.redF(), start_color.greenF(), start_color.blueF()]
                end_rgb = [end_color.redF(), end_color.greenF(), end_color.blueF()]
                
                # Configurar mapa de cores
                for i in range(256):
                    t = i / 255.0
                    r = start_rgb[0] + t * (end_rgb[0] - start_rgb[0])
                    g = start_rgb[1] + t * (end_rgb[1] - start_rgb[1])
                    b = start_rgb[2] + t * (end_rgb[2] - start_rgb[2])
                    lut.SetTableValue(i, r, g, b, 1.0)
                
                lut.Build()
                self.mapper.SetLookupTable(lut)
                self.scalar_bar.SetLookupTable(lut)
                self.render_window.Render()

    def take_screenshot(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Captura de Tela", "", "Imagens PNG (*.png);;Imagens JPEG (*.jpg *.jpeg)"
        )
        
        if file_path:
            # Capturar a janela de renderização
            window_to_image = vtk.vtkWindowToImageFilter()
            window_to_image.SetInput(self.render_window)
            window_to_image.SetInputBufferTypeToRGBA()
            window_to_image.ReadFrontBufferOff()
            window_to_image.Update()
            
            # Salvar a imagem
            writer = None
            if file_path.lower().endswith('.png'):
                writer = vtk.vtkPNGWriter()
            else:
                writer = vtk.vtkJPEGWriter()
            
            writer.SetFileName(file_path)
            writer.SetInputConnection(window_to_image.GetOutputPort())
            writer.Write()
            
            QMessageBox.information(self, "Captura de Tela", f"Imagem salva em:\n{file_path}")

    def export_to_mp4(self):
        """Exporta a simulação para um vídeo MP4 com FPS configurável."""
        if not self.available_times or len(self.available_times) <= 1:
            QMessageBox.warning(self, "Aviso", "Não há passos de tempo suficientes para criar um vídeo.")
            return
        
        # Mostrar a quantidade total de frames e perguntar sobre o FPS
        total_frames = len(self.available_times)
        fps_options = ["15", "24", "30", "60"]
        fps, ok = QInputDialog.getItem(
            self, 
            f"Configuração de Exportação - {total_frames} Frames",
            f"Total de frames a serem exportados: {total_frames}\nSelecione os quadros por segundo (FPS):",
            fps_options, 
            2,  # Default: 30 FPS (índice 2 na lista)
            False
        )
        
        if not ok:
            return
            
        fps = int(fps)
        
        # Perguntar ao usuário o tamanho desejado dos frames
        size_options = ["1920x1080", "1280x720", "1024x768", "800x600", "640x480"]
        size_str, ok = QInputDialog.getItem(
            self,
            "Tamanho dos Frames do Vídeo",
            "Escolha a resolução dos frames (Largura x Altura):",
            size_options,
            1,  # Padrão: 1280x720
            False
        )
        if not ok:
            return
        width, height = map(int, size_str.split("x"))
        
        # Explicitamente adicionar o filtro *.mp4 para forçar a extensão correta
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exportar Animação para MP4", "", "Arquivos de Vídeo (*.mp4)"
        )
        
        if not file_path:
            return
            
        # Garantir que o arquivo tenha a extensão .mp4
        if not file_path.lower().endswith('.mp4'):
            original_path = file_path
            file_path = file_path + '.mp4'
            print(f"Adicionando extensão .mp4 ao arquivo: {original_path} -> {file_path}")
            # Informar ao usuário que a extensão foi adicionada
            QMessageBox.information(
                self, 
                "Extensão Adicionada", 
                f"Foi adicionada a extensão .mp4 ao arquivo:\n{file_path}"
            )
            
        # Verificar se o nome do arquivo contém caracteres problemáticos para o ffmpeg
        import re
        if re.search(r'[^\w\-\./\\]', file_path):
            response = QMessageBox.warning(
                self,
                "Nome de Arquivo Inválido",
                "O nome de arquivo contém caracteres especiais que podem causar problemas com o ffmpeg.\n"
                "Recomendamos usar apenas letras, números, hifens e underscores.\n\n"
                "Deseja continuar mesmo assim?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if response == QMessageBox.No:
                return
            
        # Verificar se o ffmpeg está instalado
        try:
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            QMessageBox.critical(
                self, 
                "Erro", 
                "ffmpeg não encontrado. Por favor, instale o ffmpeg para poder exportar vídeos.\n\n"
                "Você pode instalar ffmpeg com o comando:\n"
                "sudo apt-get install ffmpeg"
            )
            return
            
        # Criar diretório temporário para os frames
        temp_dir = tempfile.mkdtemp(prefix="gafoam_video_")
        print(f"Criado diretório temporário para frames: {temp_dir}")
        
        try:
            # Configurar a barra de progresso
            total_frames = len(self.available_times)
            progress = QProgressDialog(f"Gerando frames para o vídeo ({total_frames} quadros a {fps} FPS)...", 
                                      "Cancelar", 0, total_frames, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            progress.setWindowTitle(f"Exportando para MP4 - {fps} FPS")
            
            # Salvar o estado atual para restaurar depois
            current_time_index = self.current_time_index
            
            # Gerar frames para cada passo de tempo
            for i, time_value in enumerate(self.available_times):
                if progress.wasCanceled():
                    break
                # Atualizar visualização para o tempo atual
                self.current_time_index = i
                self.time_slider.setValue(i)
                self.update_visualization()
                # Redimensionar a janela de renderização para o tamanho escolhido
                self.render_window.SetSize(width, height)

                # Capturar o frame
                window_to_image = vtk.vtkWindowToImageFilter()
                window_to_image.SetInput(self.render_window)
                window_to_image.SetInputBufferTypeToRGBA()
                window_to_image.ReadFrontBufferOff()
                window_to_image.Update()

                # Salvar o frame como PNG
                frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                writer = vtk.vtkPNGWriter()
                writer.SetFileName(frame_path)
                writer.SetInputConnection(window_to_image.GetOutputPort())
                writer.Write()

                # --- NOVO: Escrever o tempo no frame usando PIL ---
                try:
                    from PIL import Image, ImageDraw, ImageFont
                    img = Image.open(frame_path)
                    draw = ImageDraw.Draw(img, 'RGBA')
                    try:
                        font = ImageFont.truetype("DejaVuSansMono.ttf", 36)
                    except Exception:
                        font = ImageFont.load_default()
                    text = f"Tempo: {time_value:.3f} s"
                    # Compatibilidade: usar textbbox se disponível, senão fallback para getsize
                    if hasattr(draw, 'textbbox'):
                        bbox = draw.textbbox((0,0), text, font=font)
                        text_w = bbox[2] - bbox[0]
                        text_h = bbox[3] - bbox[1]
                    else:
                        text_w, text_h = font.getsize(text)
                    x = img.width - text_w - 30
                    y = img.height - text_h - 30
                    draw.rectangle([(x-10, y-5), (x+text_w+10, y+text_h+5)], fill=(0,0,0,180))
                    draw.text((x, y), text, font=font, fill=(255,255,255,255))
                    img.save(frame_path)
                except Exception as e:
                    print(f"Não foi possível inserir texto no frame {i}: {e}")
                
                # Atualizar a barra de progresso
                progress.setValue(i + 1)
            
            # Verificar se a operação foi cancelada
            if progress.wasCanceled():
                QMessageBox.information(self, "Exportação Cancelada", "A exportação do vídeo foi cancelada.")
                return
                
            # Fechar a barra de progresso
            progress.close()
            
            # Mostrar progresso para a codificação do vídeo
            encoding_progress = QProgressDialog(f"Codificando vídeo com ffmpeg a {fps} FPS...", "Cancelar", 0, 100, self)
            encoding_progress.setWindowModality(Qt.WindowModal)
            encoding_progress.setMinimumDuration(0)
            encoding_progress.setValue(10)
            encoding_progress.setWindowTitle(f"Criando Arquivo MP4 ({total_frames} frames, {fps} FPS)")
            
            # Construir o comando ffmpeg para criar o vídeo
            # Usamos o FPS selecionado pelo usuário e garantimos que as dimensões são pares
            # para compatibilidade com o codec h264 (que requer dimensões pares)
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-framerate', str(fps),
                '-i', os.path.join(temp_dir, 'frame_%04d.png'),
                '-c:v', 'libx264',
                '-vf', 'pad=width=ceil(iw/2)*2:height=ceil(ih/2)*2:color=black', # Garantir dimensões pares
                '-pix_fmt', 'yuv420p',
                '-crf', '23',  # Qualidade (0-51, menor é melhor)
                file_path
            ]
            
            encoding_progress.setValue(30)
            
            # Executar o comando ffmpeg
            try:
                print(f"Executando comando ffmpeg: {' '.join(ffmpeg_cmd)}")
                process = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                encoding_progress.setValue(100)
                encoding_progress.close()
                QMessageBox.information(self, "Exportação Concluída", 
                                    f"Vídeo exportado com sucesso para:\n{file_path}\n\n"
                                    f"Detalhes:\n"
                                    f"- {total_frames} frames\n"
                                    f"- {fps} FPS\n"
                                    f"- Duração: {total_frames/fps:.1f} segundos")
            except subprocess.CalledProcessError as e:
                encoding_progress.close()
                error_msg = e.stderr.decode('utf-8') if e.stderr else "Erro desconhecido"
                print(f"Erro ao executar ffmpeg: {error_msg}")
                
                # Fornecer mensagem de erro mais informativa
                detailed_error = f"Falha ao codificar o vídeo:\n\n{error_msg}\n\n"
                
                # Verificar problemas comuns
                if "Permission denied" in error_msg:
                    detailed_error += "ERRO DE PERMISSÃO: Você não tem permissão para escrever no diretório selecionado.\n" \
                                      "Tente salvar em um local onde você tenha permissões de escrita, como sua pasta de Documentos."
                elif "No such file or directory" in error_msg:
                    detailed_error += "ERRO DE CAMINHO: O diretório selecionado não existe.\n" \
                                      "Verifique se o caminho onde você está tentando salvar existe."
                elif "Invalid argument" in error_msg:
                    detailed_error += "ERRO DE ARGUMENTO: O nome do arquivo pode conter caracteres inválidos.\n" \
                                      "Tente um nome de arquivo mais simples, sem caracteres especiais."
                elif "divisible by 2" in error_msg or "not divisible by 2" in error_msg:
                    detailed_error += "ERRO DE DIMENSÕES: A altura ou largura da imagem não é divisível por 2.\n" \
                                      "Este erro deveria ter sido corrigido automaticamente pelo programa.\n" \
                                      "Por favor, reporte este erro aos desenvolvedores."
                else:
                    detailed_error += f"Verifique se o caminho '{file_path}' é válido e se você tem permissão para escrever nessa pasta."
                
                QMessageBox.critical(self, "Erro na Exportação", detailed_error)
            
            # Restaurar o estado original
            self.current_time_index = current_time_index
            self.time_slider.setValue(current_time_index)
            self.update_visualization()
            
        finally:
            # Limpar arquivos temporários
            try:
                print(f"Removendo diretório temporário: {temp_dir}")
                shutil.rmtree(temp_dir)
                print("Diretório temporário removido com sucesso")
            except Exception as e:
                print(f"Erro ao remover diretório temporário: {e}")
                # Não exibir erro para o usuário, apenas registrar no console

    def export_to_vtk(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exportar para VTK", "", "Arquivos VTK (*.vtk)"
        )
        
        if file_path:
            try:
                # Converter a visualização atual para VTK
                geometry = vtk.vtkGeometryFilter()
                geometry.SetInputData(self.reader.GetOutput().GetBlock(0))
                geometry.Update()
                
                writer = vtk.vtkPolyDataWriter()
                writer.SetFileName(file_path)
                writer.SetInputConnection(geometry.GetOutputPort())
                writer.Write()
                
                QMessageBox.information(self, "Exportar para VTK", f"Dados exportados com sucesso para:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Erro na Exportação", f"Ocorreu um erro ao exportar: {str(e)}")

    def closeEvent(self, event):
        # Limpar recursos VTK ao fechar
        if hasattr(self, 'interactor') and self.interactor:
            self.interactor.TerminateApp()
        
        super().closeEvent(event)

    def update_time_slider(self):
        """Atualiza o slider de tempo com base nos tempos disponíveis."""
        if not self.available_times:
            print("Nenhum tempo disponível para atualizar o slider")
            return False
            
        # Definir o valor máximo do slider
        max_index = len(self.available_times) - 1
        if max_index >= 0:
            print(f"Atualizando slider com {len(self.available_times)} tempos, máximo: {max_index}")
            self.time_slider.setMaximum(max_index)
            
            # Verificar se o índice atual está dentro dos limites
            if self.current_time_index > max_index:
                self.current_time_index = 0
            
            # Defina o valor do slider para o índice atual
            self.time_slider.setValue(self.current_time_index)
                
            # Atualizar o label
            self.time_label.setText(f"Tempo: {self.available_times[self.current_time_index]:.3f}s")
            
            print(f"Slider atualizado: valor={self.time_slider.value()}, máximo={self.time_slider.maximum()}")
            return True
        
        print("Erro: lista de tempos vazia após processamento")
        return False

    def toggle_shading(self, state):
        """Ativa ou desativa o sombreamento suave para melhor visualização."""
        if self.actor:
            if state == Qt.Checked:
                self.actor.GetProperty().SetInterpolationToPhong()  # Sombreamento suave
            else:
                self.actor.GetProperty().SetInterpolationToFlat()  # Sombreamento plano
            self.render_window.Render()
