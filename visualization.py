import sys
import os
import numpy as np
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, 
    QPushButton, QLabel, QSplitter, QTreeWidget, QTreeWidgetItem, 
    QColorDialog, QSlider, QGroupBox, QCheckBox, QToolBar, QAction,
    QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QSize, QTimer
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
    """Janela para visualização de casos OpenFOAM similar ao ParaView."""
    
    def __init__(self, case_path, parent=None):
        super().__init__(parent)
        self.case_path = case_path
        self.foam_file = None
        
        # Verificar se o VTK está disponível
        if vtk is None:
            QMessageBox.critical(self, "VTK não disponível", 
                                "A biblioteca VTK não está instalada. Instale com: pip install vtk")
            self.close()
            return
        
        print(f"Inicializando VisualizationWindow com caso em: {case_path}")
        
        # Encontrar o arquivo .foam
        for file in os.listdir(case_path):
            if file.endswith('.foam'):
                self.foam_file = os.path.join(case_path, file)
                print(f"Arquivo .foam encontrado: {self.foam_file}")
                break
        
        if not self.foam_file:
            # Criar arquivo .foam se não existir
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
        
        # Timer para animação
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.advance_time_step)
        self.animation_timer.setInterval(200)  # Intervalo em ms (5 fps)
        
        self.setup_ui()
        self.setup_vtk()
        self.load_foam_case()
        
        # Configurar estado inicial dos botões
        self.pause_button.setEnabled(False)

    def setup_ui(self):
        self.setWindowTitle(f"GAFoam Visualization - {os.path.basename(self.case_path)}")
        self.resize(1200, 800)
        
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        
        # Painel lateral esquerdo
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(250)
        left_panel.setMaximumWidth(300)
        
        # Grupo para controles de tempo
        time_group = QGroupBox("Controle de Tempo")
        time_layout = QVBoxLayout(time_group)
        
        # Slider e label para tempo
        self.time_label = QLabel("Tempo: 0.0s")
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(0)
        self.time_slider.setSingleStep(1)
        self.time_slider.setPageStep(1)
        self.time_slider.setTracking(True)  # Atualize conforme o slider é movido
        self.time_slider.valueChanged.connect(self.on_time_slider_changed)
        time_layout.addWidget(self.time_label)
        time_layout.addWidget(self.time_slider)
        
        # Botões de animação
        animation_layout = QHBoxLayout()
        
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play_animation)
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause_animation)
        self.pause_button.setEnabled(False)
        
        # Slider para controle de velocidade da animação
        self.speed_label = QLabel("Velocidade:")
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(1)  # 1 = muito lento
        self.speed_slider.setMaximum(100)  # 100 = muito rápido
        self.speed_slider.setValue(60)  # Padrão: 60fps
        self.speed_slider.valueChanged.connect(self.update_animation_speed)
        
        # Botão de ajuda para o controle de velocidade
        self.speed_help_button = QPushButton("?")
        self.speed_help_button.setMaximumWidth(30)
        self.speed_help_button.clicked.connect(self.show_speed_help)
        animation_layout.addWidget(self.speed_help_button)
        
        # Status da velocidade
        self.speed_status = QLabel("60 fps")
        animation_layout.addWidget(self.speed_status)
        
        animation_layout.addWidget(self.play_button)
        animation_layout.addWidget(self.pause_button)
        animation_layout.addWidget(self.speed_label)
        animation_layout.addWidget(self.speed_slider)
        time_layout.addLayout(animation_layout)
        
        # Controles para escolher o campo
        field_group = QGroupBox("Campos")
        field_layout = QVBoxLayout(field_group)
        
        field_label = QLabel("Campo:")
        self.field_combo = QComboBox()
        self.field_combo.currentIndexChanged.connect(self.on_field_changed)
        
        # Opções de visualização
        self.colorbar_checkbox = QCheckBox("Mostrar barra de cores")
        self.colorbar_checkbox.setChecked(True)
        self.colorbar_checkbox.stateChanged.connect(self.update_visualization)
        
        self.outline_checkbox = QCheckBox("Mostrar contorno")
        self.outline_checkbox.setChecked(True)
        self.outline_checkbox.stateChanged.connect(self.toggle_outline)
        
        self.color_button = QPushButton("Alterar escala de cores")
        self.color_button.clicked.connect(self.change_color_map)
        
        field_layout.addWidget(field_label)
        field_layout.addWidget(self.field_combo)
        field_layout.addWidget(self.colorbar_checkbox)
        field_layout.addWidget(self.outline_checkbox)
        field_layout.addWidget(self.color_button)
        
        # Botões de visualização
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
        
        # Adicionar grupos ao layout esquerdo
        left_layout.addWidget(time_group)
        left_layout.addWidget(field_group)
        left_layout.addWidget(view_group)
        left_layout.addStretch()
        
        # Configuração do visualizador VTK
        self.vtk_widget = QVTKRenderWindowInteractor()
        
        # Organizar layout principal
        main_layout.addWidget(left_panel)
        main_layout.addWidget(self.vtk_widget, 1)
        
        self.setCentralWidget(central_widget)
        
        # Criar barra de ferramentas
        toolbar = QToolBar("Ferramentas de Visualização")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # Adicionar ações à barra de ferramentas
        save_action = QAction("Salvar Visualização", self)
        save_action.triggered.connect(self.save_visualization)
        toolbar.addAction(save_action)
        
        export_action = QAction("Exportar para VTK", self)
        export_action.triggered.connect(self.export_to_vtk)
        toolbar.addAction(export_action)

    def setup_vtk(self):
        # Inicializar o renderizador VTK
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.2, 0.2, 0.3)  # Fundo azul escuro
        
        self.render_window = self.vtk_widget.GetRenderWindow()
        self.render_window.AddRenderer(self.renderer)
        
        self.interactor = self.render_window.GetInteractor()
        
        # Configurar estilo de interação
        style = vtkInteractorStyleTrackballCamera()
        self.interactor.SetInteractorStyle(style)
        
        # Configurar barra de cores
        self.scalar_bar = vtk.vtkScalarBarActor()
        self.scalar_bar.SetTitle("Valor")
        self.scalar_bar.SetNumberOfLabels(5)
        self.scalar_bar.SetLabelFormat("%.2e")
        self.scalar_bar.SetPosition(0.85, 0.15)
        self.scalar_bar.SetWidth(0.12)
        self.scalar_bar.SetHeight(0.8)
        self.renderer.AddActor2D(self.scalar_bar)
        
        # Iniciar interação
        self.interactor.Initialize()

    def is_decomposed_case(self):
        """Verifica se o caso está decomposto checando a existência de 'processor0'."""
        return os.path.isdir(os.path.join(self.case_path, 'processor0'))

    def load_foam_case(self):
        try:
            # Criar o leitor OpenFOAM
            self.reader = vtkPOpenFOAMReader()
            self.reader.SetFileName(self.foam_file)
            
            # Configurações importantes para carregar corretamente os diretórios de tempo
            # Usando try/except para lidar com diferenças na API do VTK
            try:
                # API antiga
                if hasattr(self.reader, 'SetParseRegions'):
                    self.reader.SetParseRegions(True)   # Parse todas as regiões
                
                if hasattr(self.reader, 'CacheMetaDataOff'):
                    self.reader.CacheMetaDataOff()      # Não usar cache (forçar leitura)
                
                if hasattr(self.reader, 'SetCreateCellToPoint'):
                    self.reader.SetCreateCellToPoint(True)  # Converter dados de célula para ponto se necessário
                
                # Desativar arrays existentes
                if hasattr(self.reader, 'DisableAllPointArrays'):
                    self.reader.DisableAllPointArrays()  # Limpar para reconfigurar
                
                if hasattr(self.reader, 'DisableAllCellArrays'):
                    self.reader.DisableAllCellArrays()   # Limpar para reconfigurar
                
                if hasattr(self.reader, 'DisableAllLagrangianArrays'):
                    self.reader.DisableAllLagrangianArrays()  # Limpar para reconfigurar
                
                if hasattr(self.reader, 'DisableAllPatchArrays'):
                    self.reader.DisableAllPatchArrays()  # Limpar para reconfigurar
                
                print("Configurações do leitor OpenFOAM aplicadas.")
            except Exception as api_error:
                print(f"Aviso ao configurar o leitor OpenFOAM: {str(api_error)}")
            
            self.reader.UpdateInformation()
            
            print(f"Carregando caso: {self.foam_file}")
            
            if self.is_decomposed_case():
                if hasattr(self.reader, 'SetCaseType'):
                    self.reader.SetCaseType(0)  # Decomposed case
                print("Caso está decomposto.")
            else:
                if hasattr(self.reader, 'SetCaseType'):
                    self.reader.SetCaseType(1)  # Reconstructed case
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
                
                # Configurar lookup table para cores
                lut = vtk.vtkLookupTable()
                lut.SetHueRange(0.667, 0.0)  # Azul para vermelho
                lut.SetNumberOfColors(256)
                lut.Build()
                
                self.mapper.SetLookupTable(lut)
                if hasattr(self.mapper, 'SetUseLookupTableScalarRange'):
                    self.mapper.SetUseLookupTableScalarRange(True)
                
                # Criar ator
                self.actor = vtk.vtkActor()
                self.actor.SetMapper(self.mapper)
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
                
                # Iniciar o timer com base no slider de velocidade
                speed_value = self.speed_slider.value()
                
                # Calcular o intervalo com base no valor do slider
                min_interval = 5    # 5ms = 200fps (muito rápido)
                max_interval = 1000 # 1000ms = 1fps (muito lento)
                
                # Cálculo logarítmico para dar mais controle
                normalized_value = speed_value / 100.0  # 0.01 a 1.0
                interval = max_interval * (1 - normalized_value) + min_interval * normalized_value
                
                self.animation_timer.setInterval(int(interval))
                self.animation_timer.start()
                
                fps = 1000 / int(interval)
                print(f"Animação iniciada a {fps:.1f} fps (intervalo: {int(interval)}ms)")
                
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

    def save_visualization(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Estado da Visualização", "", "Arquivos VTK (*.vtk)"
        )
        
        if file_path:
            # Implementar salvamento do estado atual da visualização
            QMessageBox.information(self, "Salvar Visualização", "Funcionalidade a ser implementada")

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

    def update_animation_speed(self, value):
        """Atualiza a velocidade da animação com base no valor do slider."""
        # Valores menores = intervalo maior = mais lento
        # Valores maiores = intervalo menor = mais rápido
        if value <= 0:
            value = 1  # Evitar divisão por zero
            
        # Mapear o valor do slider para um intervalo de tempo inverso
        # 1-100 → 1000ms-5ms (1fps a 200fps)
        min_interval = 5    # 5ms = 200fps (muito rápido)
        max_interval = 1000 # 1000ms = 1fps (muito lento)
        
        # Cálculo logarítmico para dar mais controle nas velocidades mais baixas
        # e menos sensibilidade nas velocidades mais altas
        normalized_value = value / 100.0  # 0.01 a 1.0
        interval = max_interval * (1 - normalized_value) + min_interval * normalized_value
        
        # Se a animação estiver ativa, atualizar o intervalo
        if self.animation_timer.isActive():
            self.animation_timer.setInterval(int(interval))
            
        # Calcular FPS aproximado
        fps = 1000 / int(interval)
        
        # Atualizar o status da velocidade
        self.speed_status.setText(f"{fps:.1f} fps")
            
        print(f"Velocidade de animação ajustada: {value}/100 → {int(interval)}ms ({fps:.1f}fps)")

    def show_speed_help(self):
        """Exibe uma mensagem de ajuda sobre o controle de velocidade."""
        QMessageBox.information(
            self,
            "Ajuda - Controle de Velocidade",
            "Use o controle deslizante para ajustar a velocidade da animação:\n\n"
            "- Esquerda: mais lento (1 fps)\n"
            "- Direita: mais rápido (até 200 fps)\n\n"
            "Para obter os melhores resultados, ajuste conforme o desempenho do seu computador.\n"
            "Em máquinas mais lentas, utilize uma velocidade menor para evitar lentidão na interface."
        )
