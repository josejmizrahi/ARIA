"""
Agente de Recursos Humanos - Gestión de Personal.

Responsabilidades:
- Monitorear asistencia y puntualidad
- Controlar vacaciones y ausencias
- Alertar sobre vencimiento de contratos
- Gestionar evaluaciones de desempeño
- Preparar información de nómina
- Monitorear cumplimiento de capacitación
"""

from datetime import datetime, timedelta
from typing import Any
from calendar import monthrange

from aria.agents.base import BaseAgent
from aria.config import settings
from aria.models.proposal import Priority
from aria.models.task import TaskDefinition, TaskResult


class HRAgent(BaseAgent):
    """
    Agente autónomo para gestión de recursos humanos.
    
    Monitorea personal, asistencia y cumplimiento laboral.
    """
    
    def __init__(self) -> None:
        super().__init__(
            name="rrhh",
            description="Gestión de recursos humanos"
        )
        
        # Configuración desde settings
        self.company_id = settings.odoo.company_id
        
        # Parámetros de análisis
        self.contract_warning_days = 30  # Días antes de vencimiento para alertar
        self.vacation_warning_days = 60  # Días de vacaciones pendientes para alertar
        self.late_tolerance_minutes = 10  # Minutos de tolerancia para retardo
        self.absence_alert_threshold = 3  # Faltas en el mes para alertar
    
    def _register_tasks(self) -> None:
        """Registra tareas del agente de RRHH."""
        
        # Asistencia diaria
        self.register_task(TaskDefinition(
            name="daily_attendance",
            method="check_daily_attendance",
            schedule="0 10 * * 1-5",  # 10:00 AM L-V
            description="Revisa asistencia del día"
        ))
        
        # Contratos por vencer
        self.register_task(TaskDefinition(
            name="expiring_contracts",
            method="check_expiring_contracts",
            schedule="0 8 * * 1",  # Lunes 8:00 AM
            description="Contratos próximos a vencer"
        ))
        
        # Vacaciones pendientes
        self.register_task(TaskDefinition(
            name="pending_vacations",
            method="check_pending_vacations",
            schedule="0 9 1 * *",  # Día 1 del mes
            description="Empleados con vacaciones pendientes"
        ))
        
        # Cumpleaños del mes
        self.register_task(TaskDefinition(
            name="monthly_birthdays",
            method="check_birthdays",
            schedule="0 8 1 * *",  # Día 1 del mes
            description="Cumpleaños del mes"
        ))
        
        # Preparación de nómina
        self.register_task(TaskDefinition(
            name="payroll_preparation",
            method="prepare_payroll_data",
            schedule="0 8 25 * *",  # Día 25 del mes
            description="Prepara información para nómina"
        ))
        
        # Antigüedad laboral
        self.register_task(TaskDefinition(
            name="work_anniversaries",
            method="check_anniversaries",
            schedule="0 8 1 * *",  # Día 1 del mes
            description="Aniversarios laborales del mes"
        ))
        
        # Resumen semanal de RRHH
        self.register_task(TaskDefinition(
            name="weekly_hr_summary",
            method="weekly_summary",
            schedule="0 17 * * 5",  # Viernes 5:00 PM
            description="Resumen semanal de recursos humanos"
        ))
        
        # Análisis de horas extra
        self.register_task(TaskDefinition(
            name="overtime_analysis",
            method="analyze_overtime",
            schedule="0 9 * * 1",  # Lunes 9:00 AM
            description="Analiza horas extra de la semana"
        ))
    
    async def get_status_summary(self) -> dict[str, Any]:
        """Retorna resumen del estado de RRHH."""
        
        # Total empleados activos
        active_employees = self._count_active_employees()
        
        # Contratos por vencer (30 días)
        expiring_contracts = self._count_expiring_contracts()
        
        # Ausencias hoy
        absences_today = self._count_absences_today()
        
        # Determinar estado
        if expiring_contracts > 5:
            status = "warning"
        else:
            status = "ok"
        
        return {
            "status": status,
            "company_id": self.company_id,
            "active_employees": active_employees,
            "expiring_contracts": expiring_contracts,
            "absences_today": absences_today,
            "last_updated": datetime.now().isoformat(),
        }
    
    # ==================== Tareas ====================
    
    async def check_daily_attendance(self) -> TaskResult:
        """Revisa asistencia del día."""
        started_at = datetime.now()
        
        self.logger.info("Revisando asistencia del día...")
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Verificar si el modelo hr.attendance existe
        if not self._model_exists("hr.attendance"):
            self.logger.info("Módulo de asistencia no instalado")
            return TaskResult(
                task_name="daily_attendance",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"message": "Módulo de asistencia no instalado"}
            )
        
        # Empleados activos
        employees = self.search_read(
            "hr.employee",
            [
                ("active", "=", True),
                ("company_id", "=", self.company_id),
            ],
            ["id", "name", "department_id"],
            limit=500
        )
        
        # Asistencias de hoy
        attendances = self.search_read(
            "hr.attendance",
            [
                ("check_in", ">=", f"{today} 00:00:00"),
                ("check_in", "<=", f"{today} 23:59:59"),
            ],
            ["employee_id", "check_in", "check_out"],
            limit=1000
        )
        
        # Ausencias aprobadas
        leaves = self.search_read(
            "hr.leave",
            [
                ("state", "=", "validate"),
                ("date_from", "<=", today),
                ("date_to", ">=", today),
            ],
            ["employee_id"],
            limit=500
        ) if self._model_exists("hr.leave") else []
        
        employees_with_attendance = {a["employee_id"][0] for a in attendances if a.get("employee_id")}
        employees_on_leave = {l["employee_id"][0] for l in leaves if l.get("employee_id")}
        
        # Empleados sin registro (ni asistencia ni ausencia)
        missing = []
        for emp in employees:
            if emp["id"] not in employees_with_attendance and emp["id"] not in employees_on_leave:
                missing.append(emp)
        
        # Retardos (entrada después de las 9:10 AM por ejemplo)
        late_threshold = f"{today} 09:{self.late_tolerance_minutes:02d}:00"
        late_employees = [
            a for a in attendances
            if a.get("check_in", "") > late_threshold
        ]
        
        if missing or late_employees:
            message = ""
            
            if missing:
                message += f"*Sin registro ({len(missing)}):*\n"
                for emp in missing[:10]:
                    dept = emp["department_id"][1] if emp.get("department_id") else "N/A"
                    message += f"• {emp['name']} ({dept})\n"
                if len(missing) > 10:
                    message += f"... y {len(missing) - 10} más\n"
            
            if late_employees:
                message += f"\n*Retardos ({len(late_employees)}):*\n"
                for att in late_employees[:10]:
                    name = att["employee_id"][1] if att.get("employee_id") else "N/A"
                    time = att["check_in"][11:16] if att.get("check_in") else "N/A"
                    message += f"• {name}: {time}\n"
            
            priority = Priority.HIGH if len(missing) > 5 else Priority.MEDIUM
            
            await self.notify(
                title=f"👥 Asistencia: {len(missing)} sin registro, {len(late_employees)} retardos",
                message=message,
                priority=priority,
            )
        else:
            await self.notify(
                title="✅ Asistencia completa",
                message=f"Todos los {len(employees)} empleados registraron asistencia",
                priority=Priority.LOW,
            )
        
        return TaskResult(
            task_name="daily_attendance",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"missing": len(missing), "late": len(late_employees)}
        )
    
    async def check_expiring_contracts(self) -> TaskResult:
        """Revisa contratos próximos a vencer."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Revisando contratos por vencer...")
        
        # Verificar si el modelo hr.contract existe
        if not self._model_exists("hr.contract"):
            self.logger.info("Módulo de contratos no instalado")
            return TaskResult(
                task_name="expiring_contracts",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"message": "Módulo de contratos no instalado"}
            )
        
        today = datetime.now().strftime("%Y-%m-%d")
        expiry_limit = (datetime.now() + timedelta(days=self.contract_warning_days)).strftime("%Y-%m-%d")
        
        expiring = self.search_read(
            "hr.contract",
            [
                ("state", "=", "open"),
                ("date_end", "<=", expiry_limit),
                ("date_end", ">=", today),
                ("company_id", "=", self.company_id),
            ],
            ["employee_id", "date_end", "wage", "name"],
            limit=50,
            order="date_end asc"
        )
        
        if expiring:
            # Agrupar por urgencia
            urgent = []  # < 7 días
            soon = []    # 7-30 días
            
            for contract in expiring:
                end_date = contract.get("date_end", "")
                if end_date:
                    days_left = (datetime.strptime(end_date, "%Y-%m-%d") - datetime.now()).days
                    contract["days_left"] = days_left
                    
                    if days_left <= 7:
                        urgent.append(contract)
                    else:
                        soon.append(contract)
            
            # Propuestas para urgentes
            for contract in urgent:
                employee_name = contract["employee_id"][1] if contract.get("employee_id") else "N/A"
                
                await self.propose(
                    title=f"⚠️ Contrato por vencer: {employee_name}",
                    description=f"Vence en {contract['days_left']} días",
                    priority=Priority.HIGH,
                    situation_summary=f"""
Empleado: {employee_name}
Contrato: {contract.get('name', 'N/A')}
Vence: {self.format_date(contract['date_end'])} ({contract['days_left']} días)
Salario: {self.format_currency(contract.get('wage', 0))}

Requiere decisión sobre renovación o terminación.
                    """.strip(),
                    proposed_action_detail="Renovar contrato o iniciar proceso de terminación",
                    supporting_data={"contract": contract},
                )
                proposals_created += 1
            
            # Notificación consolidada para próximos
            if soon:
                message = f"*{len(soon)} contratos vencen en los próximos 30 días:*\n\n"
                for c in soon[:10]:
                    emp = c["employee_id"][1] if c.get("employee_id") else "N/A"
                    message += f"• {emp}: {self.format_date(c['date_end'])} ({c['days_left']} días)\n"
                
                await self.notify(
                    title=f"📋 {len(soon)} contratos por vencer",
                    message=message,
                    priority=Priority.MEDIUM,
                )
        
        return TaskResult(
            task_name="expiring_contracts",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            data={"expiring": len(expiring) if expiring else 0}
        )
    
    async def check_pending_vacations(self) -> TaskResult:
        """Revisa empleados con vacaciones pendientes."""
        started_at = datetime.now()
        
        self.logger.info("Revisando vacaciones pendientes...")
        
        # Verificar si el módulo de vacaciones está instalado
        if not self._model_exists("hr.leave.allocation"):
            return TaskResult(
                task_name="pending_vacations",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"message": "Módulo de vacaciones no instalado"}
            )
        
        # Obtener todas las asignaciones de vacaciones en UNA sola consulta
        allocations = self.search_read(
            "hr.leave.allocation",
            [
                ("state", "=", "validate"),
                ("holiday_status_id.active", "=", True),
            ],
            ["employee_id", "number_of_days"],
            limit=5000
        )
        
        # Agrupar días por empleado
        vacation_by_employee: dict[int, float] = {}
        for alloc in allocations:
            if alloc.get("employee_id"):
                emp_id = alloc["employee_id"][0]
                vacation_by_employee[emp_id] = vacation_by_employee.get(emp_id, 0) + alloc.get("number_of_days", 0)
        
        # Filtrar empleados con muchos días
        high_pending_ids = [
            emp_id for emp_id, days in vacation_by_employee.items()
            if days >= self.vacation_warning_days
        ]
        
        high_pending = []
        if high_pending_ids:
            # Obtener info de empleados con vacaciones altas
            employees = self.search_read(
                "hr.employee",
                [
                    ("id", "in", high_pending_ids),
                    ("active", "=", True),
                    ("company_id", "=", self.company_id),
                ],
                ["id", "name", "department_id"],
                limit=500
            )
            
            for emp in employees:
                emp["remaining_leaves"] = vacation_by_employee.get(emp["id"], 0)
                high_pending.append(emp)
        
        if high_pending:
            high_pending.sort(key=lambda x: x.get("remaining_leaves", 0), reverse=True)
            
            message = f"*Empleados con más de {self.vacation_warning_days} días pendientes:*\n\n"
            for emp in high_pending[:15]:
                dept = emp["department_id"][1] if emp.get("department_id") else "N/A"
                message += f"• {emp['name']} ({dept}): {emp.get('remaining_leaves', 0):.0f} días\n"
            
            await self.notify(
                title=f"🏖️ {len(high_pending)} empleados con vacaciones pendientes",
                message=message,
                priority=Priority.MEDIUM,
            )
        
        return TaskResult(
            task_name="pending_vacations",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"high_pending": len(high_pending) if high_pending else 0}
        )
    
    async def check_birthdays(self) -> TaskResult:
        """Lista cumpleaños del mes."""
        started_at = datetime.now()
        
        self.logger.info("Buscando cumpleaños del mes...")
        
        current_month = datetime.now().month
        
        employees = self.search_read(
            "hr.employee",
            [
                ("active", "=", True),
                ("birthday", "!=", False),
                ("company_id", "=", self.company_id),
            ],
            ["name", "birthday", "department_id"],
            limit=500
        )
        
        birthdays_this_month = []
        
        for emp in employees:
            birthday = emp.get("birthday", "")
            if birthday:
                try:
                    birth_month = int(birthday[5:7])
                    if birth_month == current_month:
                        emp["birth_day"] = int(birthday[8:10])
                        birthdays_this_month.append(emp)
                except (ValueError, IndexError):
                    continue
        
        if birthdays_this_month:
            birthdays_this_month.sort(key=lambda x: x["birth_day"])
            
            month_name = datetime.now().strftime("%B")
            message = f"*🎂 Cumpleaños de {month_name}:*\n\n"
            for emp in birthdays_this_month:
                dept = emp["department_id"][1] if emp.get("department_id") else ""
                message += f"• {emp['birth_day']:02d} - {emp['name']}"
                if dept:
                    message += f" ({dept})"
                message += "\n"
            
            await self.notify(
                title=f"🎂 {len(birthdays_this_month)} cumpleaños este mes",
                message=message,
                priority=Priority.LOW,
            )
        
        return TaskResult(
            task_name="monthly_birthdays",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"birthdays": len(birthdays_this_month) if birthdays_this_month else 0}
        )
    
    async def prepare_payroll_data(self) -> TaskResult:
        """Prepara información para nómina."""
        started_at = datetime.now()
        
        self.logger.info("Preparando datos de nómina...")
        
        # Obtener mes actual
        today = datetime.now()
        month_start = today.replace(day=1).strftime("%Y-%m-%d")
        month_end = today.replace(day=monthrange(today.year, today.month)[1]).strftime("%Y-%m-%d")
        
        # Contar empleados activos
        active_employees = self._count_active_employees()
        
        # Nuevos ingresos del mes
        new_employees = 0
        terminated = 0
        
        if self._model_exists("hr.contract"):
            new_employees = len(self.search_read(
                "hr.contract",
                [
                    ("state", "=", "open"),
                    ("date_start", ">=", month_start),
                    ("date_start", "<=", month_end),
                    ("company_id", "=", self.company_id),
                ],
                ["id"],
                limit=100
            ))
            
            # Bajas del mes
            terminated = len(self.search_read(
                "hr.contract",
                [
                    ("state", "=", "close"),
                    ("date_end", ">=", month_start),
                    ("date_end", "<=", month_end),
                    ("company_id", "=", self.company_id),
                ],
                ["id"],
                limit=100
            ))
        
        # Faltas (si hay módulo de ausencias)
        absences = 0
        if self._model_exists("hr.leave"):
            absences = len(self.search_read(
                "hr.leave",
                [
                    ("state", "=", "validate"),
                    ("date_from", ">=", month_start),
                    ("date_from", "<=", month_end),
                ],
                ["id"],
                limit=500
            ))
        
        message = f"""
*📋 Resumen para Nómina - {today.strftime('%B %Y')}*

👥 *Plantilla:*
- Empleados activos: {active_employees}
- Nuevos ingresos: {new_employees}
- Bajas: {terminated}

📊 *Incidencias:*
- Ausencias registradas: {absences}

⏰ Fecha límite de nómina: {month_end}
        """.strip()
        
        await self.notify(
            title=f"📋 Preparación de nómina - {today.strftime('%B')}",
            message=message,
            priority=Priority.MEDIUM,
        )
        
        return TaskResult(
            task_name="payroll_preparation",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "active_employees": active_employees,
                "new_employees": new_employees,
                "terminated": terminated,
                "absences": absences,
            }
        )
    
    async def check_anniversaries(self) -> TaskResult:
        """Lista aniversarios laborales del mes."""
        started_at = datetime.now()
        
        self.logger.info("Buscando aniversarios laborales...")
        
        if not self._model_exists("hr.contract"):
            return TaskResult(
                task_name="work_anniversaries",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"message": "Módulo de contratos no instalado"}
            )
        
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        # Buscar contratos activos
        contracts = self.search_read(
            "hr.contract",
            [
                ("state", "=", "open"),
                ("company_id", "=", self.company_id),
            ],
            ["employee_id", "date_start"],
            limit=500
        )
        
        anniversaries = []
        
        for contract in contracts:
            start_date = contract.get("date_start", "")
            if start_date:
                try:
                    start_month = int(start_date[5:7])
                    start_year = int(start_date[:4])
                    
                    if start_month == current_month and start_year < current_year:
                        years = current_year - start_year
                        emp_name = contract["employee_id"][1] if contract.get("employee_id") else "N/A"
                        anniversaries.append({
                            "name": emp_name,
                            "years": years,
                            "day": int(start_date[8:10]),
                        })
                except (ValueError, IndexError):
                    continue
        
        if anniversaries:
            anniversaries.sort(key=lambda x: x["day"])
            
            # Destacar aniversarios importantes (5, 10, 15, 20 años)
            milestone = [a for a in anniversaries if a["years"] in [5, 10, 15, 20, 25, 30]]
            
            month_name = datetime.now().strftime("%B")
            message = f"*🎉 Aniversarios laborales de {month_name}:*\n\n"
            
            for a in anniversaries:
                emoji = "🏆" if a["years"] in [5, 10, 15, 20, 25, 30] else "🎉"
                message += f"{emoji} {a['day']:02d} - {a['name']}: {a['years']} años\n"
            
            priority = Priority.MEDIUM if milestone else Priority.LOW
            
            await self.notify(
                title=f"🎉 {len(anniversaries)} aniversarios laborales",
                message=message,
                priority=priority,
            )
        
        return TaskResult(
            task_name="work_anniversaries",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"anniversaries": len(anniversaries) if anniversaries else 0}
        )
    
    async def weekly_summary(self) -> TaskResult:
        """Genera resumen semanal de RRHH."""
        started_at = datetime.now()
        
        self.logger.info("Generando resumen semanal de RRHH...")
        
        active_employees = self._count_active_employees()
        expiring_contracts = self._count_expiring_contracts()
        
        # Resumen de la semana
        week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        message = f"""
*📊 Resumen Semanal de RRHH*
_{self.format_date(week_start)} - {datetime.now().strftime('%d/%m/%Y')}_

👥 *Plantilla actual:* {active_employees} empleados

📋 *Pendientes:*
• Contratos por vencer (30 días): {expiring_contracts}

_¡Buen fin de semana!_
        """.strip()
        
        await self.notify(
            title="📊 Resumen Semanal RRHH",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="weekly_hr_summary",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"active_employees": active_employees}
        )
    
    async def analyze_overtime(self) -> TaskResult:
        """Analiza horas extra de la semana."""
        started_at = datetime.now()
        
        self.logger.info("Analizando horas extra...")
        
        # Asistencias de la última semana
        week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        attendances = self.search_read(
            "hr.attendance",
            [
                ("check_in", ">=", f"{week_start} 00:00:00"),
                ("overtime_hours", ">", 0),  # Solo con horas extra
            ],
            [
                "employee_id", "check_in", "check_out", 
                "worked_hours", "overtime_hours", "validated_overtime_hours",
                "overtime_status", "in_mode", "out_mode"
            ],
            limit=1000,
            order="overtime_hours desc"
        )
        
        if not attendances:
            await self.notify(
                title="⏰ Sin horas extra esta semana",
                message="No se registraron horas extra en los últimos 7 días.",
                priority=Priority.LOW,
            )
            return TaskResult(
                task_name="overtime_analysis",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Agrupar por empleado
        by_employee = {}
        total_overtime = 0
        total_validated = 0
        
        for att in attendances:
            employee = att.get("employee_id")
            emp_name = employee[1] if employee else "Desconocido"
            
            if emp_name not in by_employee:
                by_employee[emp_name] = {
                    "overtime": 0,
                    "validated": 0,
                    "days": 0,
                    "modes": set(),
                }
            
            overtime = att.get("overtime_hours", 0)
            validated = att.get("validated_overtime_hours", 0)
            
            by_employee[emp_name]["overtime"] += overtime
            by_employee[emp_name]["validated"] += validated
            by_employee[emp_name]["days"] += 1
            
            # Registrar modos de entrada/salida
            if att.get("in_mode"):
                by_employee[emp_name]["modes"].add(att["in_mode"])
            
            total_overtime += overtime
            total_validated += validated
        
        # Ordenar por horas extra
        sorted_employees = sorted(
            by_employee.items(),
            key=lambda x: x[1]["overtime"],
            reverse=True
        )
        
        message = f"""
*⏰ Análisis de Horas Extra (última semana)*

*Totales:*
• Horas extra registradas: {total_overtime:.1f} hrs
• Horas extra validadas: {total_validated:.1f} hrs
• Empleados con HE: {len(by_employee)}

*Top 10 por horas extra:*
"""
        
        for emp_name, data in sorted_employees[:10]:
            status = "✅" if data["validated"] >= data["overtime"] * 0.9 else "⏳"
            message += f"• {emp_name[:25]}: {data['overtime']:.1f} hrs ({data['days']} días) {status}\n"
        
        # Alertar si hay muchas horas extra sin validar
        pending_validation = total_overtime - total_validated
        
        if pending_validation > total_overtime * 0.3:
            message += f"\n⚠️ *{pending_validation:.1f} hrs pendientes de validar*"
        
        await self.notify(
            title=f"⏰ {total_overtime:.1f} horas extra registradas",
            message=message,
            priority=Priority.MEDIUM if pending_validation > 20 else Priority.LOW,
        )
        
        return TaskResult(
            task_name="overtime_analysis",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "total_overtime": total_overtime,
                "total_validated": total_validated,
                "employees_count": len(by_employee),
            }
        )
    
    # ==================== Helpers ====================
    
    def _count_active_employees(self) -> int:
        """Cuenta empleados activos."""
        return len(self.search_read(
            "hr.employee",
            [
                ("active", "=", True),
                ("company_id", "=", self.company_id),
            ],
            ["id"],
            limit=1000
        ))
    
    def _count_expiring_contracts(self) -> int:
        """Cuenta contratos por vencer."""
        if not self._model_exists("hr.contract"):
            return 0
        
        today = datetime.now().strftime("%Y-%m-%d")
        expiry_date = (datetime.now() + timedelta(days=self.contract_warning_days)).strftime("%Y-%m-%d")
        
        return len(self.search_read(
            "hr.contract",
            [
                ("state", "=", "open"),
                ("date_end", "<=", expiry_date),
                ("date_end", ">=", today),
                ("company_id", "=", self.company_id),
            ],
            ["id"],
            limit=100
        ))
    
    def _count_absences_today(self) -> int:
        """Cuenta ausencias de hoy."""
        if not self._model_exists("hr.leave"):
            return 0
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        return len(self.search_read(
            "hr.leave",
            [
                ("state", "=", "validate"),
                ("date_from", "<=", today),
                ("date_to", ">=", today),
            ],
            ["id"],
            limit=500
        ))
    
    def _get_vacation_balance(self, employee_id: int) -> float:
        """Obtiene balance de vacaciones de un empleado."""
        # Simplificado - depende de la configuración de Odoo
        try:
            if self._model_exists("hr.leave.allocation"):
                allocations = self.search_read(
                    "hr.leave.allocation",
                    [
                        ("employee_id", "=", employee_id),
                        ("state", "=", "validate"),
                        ("holiday_status_id.active", "=", True),
                    ],
                    ["number_of_days"],
                    limit=10
                )
                return sum(a.get("number_of_days", 0) for a in allocations)
        except Exception:
            pass
        return 0
    
    def _model_exists(self, model_name: str) -> bool:
        """Verifica si un modelo existe en Odoo."""
        try:
            self.search_read(model_name, [("id", ">", 0)], ["id"], limit=1)
            return True
        except Exception:
            return False


def create_hr_agent() -> HRAgent:
    """Crea y retorna el agente de RRHH."""
    return HRAgent()
