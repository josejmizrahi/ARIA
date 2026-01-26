"""
Generador de reportes PDF usando WeasyPrint.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from aria.config import settings
from aria.utils.logger import get_logger

logger = get_logger("reports")

# Importar WeasyPrint solo si está disponible
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logger.warning("WeasyPrint no instalado. Generación de PDF deshabilitada.")


class ReportGenerator:
    """
    Generador de reportes PDF.
    
    Usa Jinja2 para templates HTML y WeasyPrint para convertir a PDF.
    """
    
    def __init__(self, templates_dir: str | Path | None = None):
        """
        Inicializa el generador.
        
        Args:
            templates_dir: Directorio de templates (default: aria/reports/templates)
        """
        self.templates_dir = Path(templates_dir) if templates_dir else Path(__file__).parent / "templates"
        
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        
        # Registrar filtros personalizados
        self.env.filters["currency"] = self._format_currency
        self.env.filters["date"] = self._format_date
        self.env.filters["datetime"] = self._format_datetime
        self.env.filters["number"] = self._format_number
        self.env.filters["percentage"] = self._format_percentage
        
        # Configuración de empresa
        self.company_name = getattr(settings, "company_name", "ARIA")
        self.default_currency = settings.odoo.default_currency
    
    def generate(
        self,
        template_name: str,
        data: dict[str, Any],
        output_path: str | None = None,
        css_files: list[str] | None = None,
    ) -> str:
        """
        Genera un reporte PDF.
        
        Args:
            template_name: Nombre del template (ej: "aging_report.html")
            data: Datos para el reporte
            output_path: Ruta de salida (default: temporal)
            css_files: Archivos CSS adicionales
            
        Returns:
            Ruta del archivo PDF generado
        """
        if not WEASYPRINT_AVAILABLE:
            raise RuntimeError("WeasyPrint no está instalado. Ejecute: pip install weasyprint")
        
        logger.info(f"Generando reporte: {template_name}")
        
        # Cargar template
        template = self.env.get_template(template_name)
        
        # Agregar datos comunes
        data["generated_at"] = datetime.now()
        data["company_name"] = self.company_name
        data["default_currency"] = self.default_currency
        
        # Renderizar HTML
        html_content = template.render(**data)
        
        # Preparar CSS
        stylesheets = [CSS(string=self._get_base_css())]
        
        if css_files:
            for css_file in css_files:
                css_path = self.templates_dir / css_file
                if css_path.exists():
                    stylesheets.append(CSS(filename=str(css_path)))
        
        # Generar PDF
        if not output_path:
            output_path = tempfile.mktemp(suffix=".pdf")
        
        HTML(string=html_content).write_pdf(output_path, stylesheets=stylesheets)
        
        logger.info(f"Reporte generado: {output_path}")
        return output_path
    
    def generate_from_string(
        self,
        html_content: str,
        output_path: str | None = None,
    ) -> str:
        """
        Genera PDF desde HTML string.
        
        Args:
            html_content: Contenido HTML
            output_path: Ruta de salida
            
        Returns:
            Ruta del PDF
        """
        if not WEASYPRINT_AVAILABLE:
            raise RuntimeError("WeasyPrint no está instalado")
        
        if not output_path:
            output_path = tempfile.mktemp(suffix=".pdf")
        
        stylesheets = [CSS(string=self._get_base_css())]
        HTML(string=html_content).write_pdf(output_path, stylesheets=stylesheets)
        
        return output_path
    
    def render_html(
        self,
        template_name: str,
        data: dict[str, Any],
    ) -> str:
        """
        Renderiza template a HTML (sin convertir a PDF).
        
        Útil para previsualización o envío por email.
        """
        template = self.env.get_template(template_name)
        
        data["generated_at"] = datetime.now()
        data["company_name"] = self.company_name
        data["default_currency"] = self.default_currency
        
        return template.render(**data)
    
    def _get_base_css(self) -> str:
        """CSS base para todos los reportes."""
        return """
            @page {
                size: letter;
                margin: 1.5cm;
                @top-right {
                    content: "Página " counter(page) " de " counter(pages);
                    font-size: 9pt;
                    color: #666;
                }
                @bottom-center {
                    content: "Generado por ARIA";
                    font-size: 8pt;
                    color: #999;
                }
            }
            
            body {
                font-family: 'Helvetica Neue', Arial, sans-serif;
                font-size: 10pt;
                line-height: 1.4;
                color: #333;
            }
            
            h1 {
                font-size: 18pt;
                color: #2c3e50;
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
                margin-bottom: 20px;
            }
            
            h2 {
                font-size: 14pt;
                color: #34495e;
                margin-top: 20px;
                margin-bottom: 10px;
            }
            
            h3 {
                font-size: 12pt;
                color: #7f8c8d;
            }
            
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
            }
            
            th {
                background-color: #3498db;
                color: white;
                padding: 8px 10px;
                text-align: left;
                font-weight: 600;
            }
            
            td {
                padding: 6px 10px;
                border-bottom: 1px solid #ecf0f1;
            }
            
            tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            
            .text-right { text-align: right; }
            .text-center { text-align: center; }
            .text-success { color: #27ae60; }
            .text-danger { color: #e74c3c; }
            .text-warning { color: #f39c12; }
            .text-muted { color: #95a5a6; }
            
            .amount { 
                text-align: right; 
                font-family: 'Courier New', monospace;
            }
            
            .total-row {
                font-weight: bold;
                background-color: #ecf0f1 !important;
            }
            
            .header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 30px;
            }
            
            .logo {
                max-height: 60px;
            }
            
            .report-info {
                text-align: right;
                font-size: 9pt;
                color: #7f8c8d;
            }
            
            .summary-box {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                padding: 15px;
                margin: 15px 0;
            }
            
            .kpi {
                display: inline-block;
                text-align: center;
                padding: 10px 20px;
                margin: 5px;
                background-color: #fff;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            
            .kpi-value {
                font-size: 24pt;
                font-weight: bold;
                color: #2c3e50;
            }
            
            .kpi-label {
                font-size: 9pt;
                color: #7f8c8d;
            }
            
            .chart-placeholder {
                background-color: #ecf0f1;
                height: 200px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #95a5a6;
                border-radius: 5px;
            }
            
            .page-break {
                page-break-after: always;
            }
            
            .no-break {
                page-break-inside: avoid;
            }
            
            .alert {
                padding: 10px 15px;
                border-radius: 5px;
                margin: 10px 0;
            }
            
            .alert-danger {
                background-color: #f8d7da;
                border: 1px solid #f5c6cb;
                color: #721c24;
            }
            
            .alert-warning {
                background-color: #fff3cd;
                border: 1px solid #ffeeba;
                color: #856404;
            }
            
            .alert-success {
                background-color: #d4edda;
                border: 1px solid #c3e6cb;
                color: #155724;
            }
        """
    
    # Filtros de formato
    @staticmethod
    def _format_currency(value: float | None, symbol: str = "$") -> str:
        if value is None:
            return "-"
        return f"{symbol}{value:,.2f}"
    
    @staticmethod
    def _format_date(value) -> str:
        if not value:
            return "-"
        if isinstance(value, str):
            try:
                value = datetime.strptime(value[:10], "%Y-%m-%d")
            except ValueError:
                return value
        return value.strftime("%d/%m/%Y")
    
    @staticmethod
    def _format_datetime(value) -> str:
        if not value:
            return "-"
        if isinstance(value, str):
            try:
                value = datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return value
        return value.strftime("%d/%m/%Y %H:%M")
    
    @staticmethod
    def _format_number(value: float | None, decimals: int = 0) -> str:
        if value is None:
            return "-"
        return f"{value:,.{decimals}f}"
    
    @staticmethod
    def _format_percentage(value: float | None) -> str:
        if value is None:
            return "-"
        return f"{value:.1f}%"


# Instancia global
report_generator = ReportGenerator()
