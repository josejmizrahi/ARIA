"""
Inspector Contextual de Recursos Humanos.

Analiza RRHH en 4 niveles:
1. Vista general: Empleados, contratos por vencer, ausentismo
2. Por categorías: Por departamento, tipo de contrato
3. Detalles: Sin contrato, período prueba, ausencias
4. Anomalías: Sin departamento, datos incompletos
"""

from datetime import datetime, timedelta

from .context_inspector import BaseContextInspector
from .models import (
    AgentDependency,
    AreaContext,
    ImpactLevel,
    ImpactType,
)


class HRInspector(BaseContextInspector):
    """Inspector contextual para Recursos Humanos."""
    
    AGENT_NAME = "rrhh"
    AREA_NAME = "Recursos Humanos"
    
    UPSTREAM_DEPENDENCIES = []  # RRHH no tiene dependencias upstream
    
    DOWNSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="finanzas",
            dependency_type="downstream",
            data_flow="Costo de nómina",
            criticality=ImpactLevel.HIGH,
            description="Datos de empleados para cálculo de nómina"
        ),
        AgentDependency(
            agent_name="produccion",
            dependency_type="downstream",
            data_flow="Personal disponible",
            criticality=ImpactLevel.MEDIUM,
            description="Disponibilidad de personal operativo"
        ),
        AgentDependency(
            agent_name="ceo",
            dependency_type="downstream",
            data_flow="Headcount y rotación",
            criticality=ImpactLevel.MEDIUM,
            description="Indicadores de personal para reportes"
        ),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.contract_warning_days = 30
        self.high_vacation_days = 20
    
    def _get_area_context(self) -> AreaContext:
        """Obtiene contexto general de RRHH."""
        
        # Empleados activos
        employees = self._search_count(
            "hr.employee",
            [("active", "=", True)]
        )
        
        # Contratos por vencer
        expiry_date = (datetime.now() + timedelta(days=self.contract_warning_days)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        
        expiring = 0
        if self._model_exists("hr.contract"):
            expiring = self._search_count(
                "hr.contract",
                [
                    ("state", "=", "open"),
                    ("date_end", "<=", expiry_date),
                    ("date_end", ">=", today),
                ]
            )
        
        health = 100 - (expiring * 5)
        
        return AreaContext(
            area_name=self.AREA_NAME,
            total_records=employees,
            total_value=0,
            health_score=max(0, min(100, health)),
            status=self._get_status_from_health(max(0, min(100, health))),
            summary={
                "active_employees": employees,
                "expiring_contracts": expiring,
            }
        )
    
    def _inspect_level_1_overview(self) -> None:
        """Nivel 1: KPIs generales de RRHH."""
        
        summary = self._context.summary if self._context else {}
        employees = summary.get("active_employees", 0)
        expiring = summary.get("expiring_contracts", 0)
        
        # Headcount
        self._add_finding(
            level=1,
            category="Headcount",
            title=f"Empleados activos: {employees}",
            description="Total de empleados en nómina",
            severity=ImpactLevel.INFO,
            affected_records=employees,
        )
        
        # Contratos por vencer
        if expiring > 0:
            self._add_finding(
                level=1,
                category="Contratos",
                title=f"⚠️ {expiring} contratos por vencer en {self.contract_warning_days} días",
                description="Contratos que requieren renovación o decisión",
                severity=ImpactLevel.HIGH if expiring > 5 else ImpactLevel.MEDIUM,
                affected_records=expiring,
                impacts=[
                    self._increases_risk_for(
                        "produccion",
                        "Personal en riesgo",
                        f"{expiring} empleados pueden salir",
                        "Renovar o planificar reemplazo"
                    )
                ],
                solution="Revisar y tomar decisiones de renovación"
            )
    
    def _inspect_level_2_categories(self) -> None:
        """Nivel 2: Por departamento."""
        
        employees = self._search_read(
            "hr.employee",
            [("active", "=", True)],
            ["department_id"],
            limit=1000
        )
        
        by_dept: dict[str, int] = {}
        no_dept = 0
        
        for emp in employees:
            dept = self._safe_get_name(emp, "department_id")
            if dept:
                by_dept[dept] = by_dept.get(dept, 0) + 1
            else:
                no_dept += 1
        
        if by_dept:
            sorted_depts = sorted(by_dept.items(), key=lambda x: x[1], reverse=True)
            
            self._add_finding(
                level=2,
                category="Distribución",
                title="Empleados por departamento",
                description="Distribución de headcount",
                severity=ImpactLevel.INFO,
                sample_data=[{"dept": d, "count": c} for d, c in sorted_depts[:10]],
            )
        
        if no_dept > 0:
            self._add_finding(
                level=2,
                category="Sin Departamento",
                title=f"{no_dept} empleados sin departamento asignado",
                description="Empleados que no tienen departamento",
                severity=ImpactLevel.MEDIUM,
                affected_records=no_dept,
                solution="Asignar departamento a empleados"
            )
    
    def _inspect_level_3_details(self) -> None:
        """Nivel 3: Empleados específicos."""
        
        if self._model_exists("hr.contract"):
            # Contratos por vencer (detalle)
            expiry_date = (datetime.now() + timedelta(days=self.contract_warning_days)).strftime("%Y-%m-%d")
            today = datetime.now().strftime("%Y-%m-%d")
            
            expiring = self._search_read(
                "hr.contract",
                [
                    ("state", "=", "open"),
                    ("date_end", "<=", expiry_date),
                    ("date_end", ">=", today),
                ],
                ["employee_id", "date_end", "wage", "name"],
                limit=50,
                order="date_end asc"
            )
            
            if expiring:
                urgent = [c for c in expiring if self._days_between(c.get("date_end")) >= -7]
                
                if urgent:
                    self._add_finding(
                        level=3,
                        category="Contratos Urgentes",
                        title=f"{len(urgent)} contratos vencen en 7 días o menos",
                        description="Requieren decisión inmediata",
                        severity=ImpactLevel.CRITICAL,
                        affected_records=len(urgent),
                        sample_data=[
                            {
                                "employee": self._safe_get_name(c, "employee_id"),
                                "contract": c.get("name"),
                                "ends": c.get("date_end"),
                                "days": abs(self._days_between(c.get("date_end"))),
                            }
                            for c in urgent[:10]
                        ],
                        solution="Tomar decisión de renovación o terminación"
                    )
        
        # Ausencias hoy
        if self._model_exists("hr.leave"):
            today = datetime.now().strftime("%Y-%m-%d")
            
            absences = self._search_read(
                "hr.leave",
                [
                    ("state", "=", "validate"),
                    ("date_from", "<=", today),
                    ("date_to", ">=", today),
                ],
                ["employee_id", "holiday_status_id", "number_of_days"],
                limit=100
            )
            
            if absences:
                self._add_finding(
                    level=3,
                    category="Ausencias",
                    title=f"{len(absences)} empleados ausentes hoy",
                    description="Personal con ausencia aprobada",
                    severity=ImpactLevel.INFO,
                    affected_records=len(absences),
                    sample_data=[
                        {
                            "employee": self._safe_get_name(a, "employee_id"),
                            "type": self._safe_get_name(a, "holiday_status_id"),
                            "days": a.get("number_of_days"),
                        }
                        for a in absences[:10]
                    ],
                )
    
    def _inspect_level_4_anomalies(self) -> None:
        """Nivel 4: Errores e inconsistencias."""
        
        # Empleados sin datos críticos
        incomplete = self._search_read(
            "hr.employee",
            [
                ("active", "=", True),
                "|", "|",
                ("job_id", "=", False),
                ("work_email", "=", False),
                ("department_id", "=", False),
            ],
            ["name", "job_id", "work_email", "department_id"],
            limit=100
        )
        
        if incomplete:
            self._add_finding(
                level=4,
                category="Datos Incompletos",
                title=f"{len(incomplete)} empleados con datos faltantes",
                description="Empleados sin puesto, email o departamento",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(incomplete),
                sample_data=[
                    {
                        "employee": e.get("name"),
                        "has_job": bool(e.get("job_id")),
                        "has_email": bool(e.get("work_email")),
                        "has_dept": bool(e.get("department_id")),
                    }
                    for e in incomplete[:10]
                ],
                solution="Completar datos de empleados"
            )
        
        if self._model_exists("hr.contract"):
            # Contratos con salario 0
            zero_wage = self._search_read(
                "hr.contract",
                [
                    ("state", "=", "open"),
                    ("wage", "<=", 0),
                ],
                ["employee_id", "name"],
                limit=50
            )
            
            if zero_wage:
                self._add_finding(
                    level=4,
                    category="Error de Datos",
                    title=f"🔴 {len(zero_wage)} contratos con salario = 0",
                    description="Contratos activos sin salario configurado",
                    severity=ImpactLevel.CRITICAL,
                    affected_records=len(zero_wage),
                    sample_data=[
                        {
                            "employee": self._safe_get_name(c, "employee_id"),
                            "contract": c.get("name"),
                        }
                        for c in zero_wage[:10]
                    ],
                    impacts=[
                        self._create_impact(
                            "finanzas",
                            ImpactType.REDUCES_QUALITY,
                            "Nómina incorrecta",
                            "Empleados no recibirán pago correcto",
                            "Corregir salarios"
                        )
                    ],
                    solution="Corregir salarios en contratos"
                )
