import matplotlib.pyplot as plt
import matplotlib.animation as animation
import re
import os
import sys
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class MatplotlibResidualPlotter(QWidget):
    def __init__(self, parent=None, log_path=None, base_dir=None):
        super().__init__(parent)
        self.base_dir = base_dir if base_dir else ""
        self.log_path = log_path if log_path else os.path.join(self.base_dir, "log.foamRun")
        
        self.fields = [
            "p_rgh", "p", "alpha.particles", "alpha.water", "epsilon.water", "k.water",
            "nut.water", "nut.particles", "T.particles", "T.water", "Theta.particles"
        ]

        self.regex_patterns = {
            # "p_rgh": r"Solving for p_rgh, Initial residual = ([\d\.eE\-\+]+)",
            "p": r"Solving for p, Initial residual = ([\d\.eE\-\+]+)",
            "alpha.particles": r"Solving for alpha.particles, Initial residual = ([\d\.eE\-\+]+)",
            "alpha.water": r"Solving for alpha.water, Initial residual = ([\d\.eE\-\+]+)",
            "epsilon.water": r"Solving for epsilon.water, Initial residual = ([\d\.eE\-\+]+)",
            "k.water": r"Solving for k.water, Initial residual = ([\d\.eE\-\+]+)",
            "nut.water": r"Solving for nut.water, Initial residual = ([\d\.eE\-\+]+)",
            "nut.particles": r"Solving for nut.particles, Initial residual = ([\d\.eE\-\+]+)",
            "T.particles": r"Solving for T.particles, Initial residual = ([\d\.eE\-\+]+)",
            "T.water": r"Solving for T.water, Initial residual = ([\d\.eE\-\+]+)",
            "Theta.particles": r"Solving for Theta.particles, Initial residual = ([\d\.eE\-\+]+)",
        }

        self.residuals = {field: [] for field in self.fields}
        self.visibility = {field: True for field in self.fields}
        self.plot_lines = {}
        self.ani = None
        self.is_plotting = False
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.fig = Figure(figsize=(12, 7))  
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        
        layout.addWidget(self.canvas)
        self.setLayout(layout)
        
        self.ax.set_yscale("log")
        self.ax.set_xlabel("Iterações")
        self.ax.set_ylabel("Resíduo (log)")
        self.ax.grid(True)
        
        self.fig.subplots_adjust(left=0.1, right=0.95, top=0.9, bottom=0.1)
        
        self.fig.canvas.mpl_connect("pick_event", self.on_pick)
        
        self.canvas.draw()
    
    def read_log(self):
        if not os.path.exists(self.log_path):
            return

        try:
            with open(self.log_path, "r") as f:
                lines = f.readlines()

            for field in self.residuals:
                self.residuals[field].clear()

            for line in lines:
                for field, pattern in self.regex_patterns.items():
                    match = re.search(pattern, line)
                    if match:
                        self.residuals[field].append(float(match.group(1)))
        except Exception as e:
            print(f"Error reading log file: {e}")
    
    def update_plot(self, frame):
        self.read_log()
        self.ax.clear()

        self.ax.set_yscale("log")
        self.ax.set_xlabel("Iterações")
        self.ax.set_ylabel("Resíduo (log)")
        self.ax.grid(True)

        self.plot_lines.clear()
        colors = plt.cm.tab10.colors
        has_data = False

        for idx, field in enumerate(self.fields):
            if len(self.residuals[field]) > 0 and self.visibility[field]:
                line, = self.ax.plot(
                    self.residuals[field],
                    label=field,
                    color=colors[idx % len(colors)],
                    linewidth=1
                )
                self.plot_lines[field] = line
                has_data = True

        # Só cria a legenda se houver pelo menos uma linha plotada
        if has_data:
            legend = self.ax.legend(fontsize="small", loc="upper right")
            if legend:
                for legline, field in zip(legend.get_lines(), self.fields):
                    if field in self.residuals and len(self.residuals[field]) > 0:
                        legline.set_picker(True)
                        legline.set_pickradius(5)
                        legline.set_alpha(1.0 if self.visibility[field] else 0.2)

        self.canvas.draw()
    
    def on_pick(self, event):
        legend_line = event.artist
        legend = self.ax.get_legend()
        if legend and hasattr(legend, 'get_lines'):
            lines = legend.get_lines()
            if legend_line in lines:
                field_idx = lines.index(legend_line)
                if field_idx < len(self.fields):
                    field = self.fields[field_idx]
                    self.visibility[field] = not self.visibility[field]
                    self.update_plot(None)
    
    def clear_plot(self):
        # Para a animação se estiver rodando
        if self.is_plotting and self.ani is not None:
            self.stop_plotting()
            
        # Limpa os dados
        for field in self.residuals:
            self.residuals[field].clear()
            
        # Limpa o plot
        self.ax.clear()
        self.ax.set_yscale("log")
        self.ax.set_title("Resíduos da Simulação OpenFOAM")
        self.ax.set_xlabel("Iterações")
        self.ax.set_ylabel("Resíduo (log)")
        self.ax.grid(True)
        
        # Atualiza o canvas
        self.canvas.draw()
        
        # Limpa as referências às linhas plotadas
        self.plot_lines.clear()
    
    def set_log_path(self, path):
        self.log_path = path
        self.clear_plot()
    
    def export_data(self, file_path):
        try:
            with open(file_path, 'w') as f:
                # Write header
                fields_with_data = [field for field in self.fields if self.residuals[field]]
                header = "Iteration," + ",".join(fields_with_data)
                f.write(header + "\n")
                
                # Write data
                max_length = max([len(self.residuals[field]) for field in fields_with_data], default=0)
                for i in range(max_length):
                    line = f"{i+1}"
                    for field in fields_with_data:
                        if i < len(self.residuals[field]):
                            line += f",{self.residuals[field][i]}"
                        else:
                            line += ","
                    f.write(line + "\n")
            return True
        except Exception as e:
            print(f"Error exporting data: {e}")
            return False
    
    def start_plotting(self):
        """Inicia a animação do gráfico"""
        if not self.is_plotting:
            self.is_plotting = True
            # Mantém a referência global para a animação
            global _anim_reference_list
            if not hasattr(sys.modules[__name__], '_anim_reference_list'):
                _anim_reference_list = []
                
            # Cria nova animação
            self.ani = animation.FuncAnimation(
                self.fig, 
                self.update_plot, 
                interval=1000, 
                cache_frame_data=False,  # Evita cache ilimitado
                save_count=100  # Limita o número de frames salvos
            )
            
            # Adiciona à lista global para evitar que seja coletada pelo garbage collector
            _anim_reference_list.append(self.ani)
            
            return True
        return False
    
    def stop_plotting(self):
        """Para a animação do gráfico"""
        if self.is_plotting and self.ani is not None:
            # Armazena a animação em uma variável local para evitar garbage collection
            _temp_anim = self.ani
            
            # Para o evento de atualização
            if hasattr(self.ani, 'event_source') and self.ani.event_source is not None:
                self.ani.event_source.stop()
                
            # Limpa a referência à animação
            self.ani = None
            self.is_plotting = False
            return True
        return False
