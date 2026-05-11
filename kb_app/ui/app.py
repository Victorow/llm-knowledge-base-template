"""PySide6 desktop control panel."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kb_app.core.paths import resolve_app_paths, resolve_kb_paths
from kb_app.diagnostics.export import export_diagnostics
from kb_app.jobs.queue import JobStore
from kb_app.profiles.store import ProfileStore

PYSIDE_PACKAGE_NAME = "PySide6"


@dataclass(frozen=True)
class PageDefinition:
    page_id: str
    title: str


PAGE_REGISTRY = [
    PageDefinition("dashboard", "Dashboard"),
    PageDefinition("setup", "Setup"),
    PageDefinition("profiles", "Profiles"),
    PageDefinition("hooks", "Hooks"),
    PageDefinition("daily_logs", "Daily Logs"),
    PageDefinition("knowledge", "Knowledge"),
    PageDefinition("operations", "Operations"),
    PageDefinition("jobs", "Jobs"),
    PageDefinition("settings", "Settings"),
    PageDefinition("diagnostics", "Diagnostics"),
]

ACTION_TO_JOB_TYPE = {
    "compile_changed": "compile_changed",
    "compile_all": "compile_all",
    "compile_file": "compile_file",
    "query": "query",
    "query_file_back": "query_file_back",
    "lint_structural": "lint_structural",
    "lint_full": "lint_full",
    "install_hooks": "install_hooks",
    "repair_hooks": "repair_hooks",
    "remove_hooks": "remove_hooks",
    "manual_memory": "manual_memory",
    "diagnostics_export": "diagnostics_export",
    "backend_smoke_test": "backend_smoke_test",
    "flush_test": "flush_test",
    "install_autostart": "install_autostart",
    "remove_autostart": "remove_autostart",
    "configure_daily_schedule": "configure_daily_schedule",
}


def build_quick_action_job(
    action: str,
    *,
    profile_id: int,
    payload: dict[str, Any] | None = None,
    priority: int = 100,
) -> dict[str, Any]:
    """Convert a UI action into a durable job payload."""
    if action not in ACTION_TO_JOB_TYPE:
        raise ValueError(f"Unsupported UI action: {action}")
    return {
        "profile_id": profile_id,
        "job_type": ACTION_TO_JOB_TYPE[action],
        "payload": payload or {},
        "priority": priority,
    }


def format_dashboard_summary(
    *,
    profile_name: str | None,
    backend: str | None,
    agent_status: str,
    last_job_status: str | None,
) -> str:
    profile_text = profile_name or "No active profile"
    backend_text = backend or "no backend"
    last_job_text = last_job_status or "no jobs yet"
    return f"{profile_text} | backend: {backend_text} | agent: {agent_status} | last job: {last_job_text}"


def require_pyside6():
    """Import PySide6 lazily so tests and CLI help do not start Qt."""
    try:
        from PySide6 import QtCore, QtWidgets
    except ImportError as e:
        raise RuntimeError(
            "PySide6 is required for the desktop UI. Install project dependencies with `uv sync`."
        ) from e
    return QtCore, QtWidgets


def launch_ui(
    *,
    kb_root: Path | None = None,
    app_db: Path | None = None,
    no_tray: bool = False,
) -> int:
    """Launch the desktop control panel."""
    _qtcore, QtWidgets = require_pyside6()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app_paths = resolve_app_paths()
    resolved_kb_root = kb_root or Path.cwd()
    db_path = app_db or app_paths.db_path
    window = ControlPanelWindow(resolved_kb_root, db_path)
    window.show()

    if not no_tray:
        from kb_app.ui.tray import TrayController

        TrayController(app, window).install()

    return int(app.exec())


class ControlPanelWindow:
    """Small operational control panel built with Qt widgets."""

    def __init__(self, kb_root: Path, app_db: Path) -> None:
        _qtcore, QtWidgets = require_pyside6()
        self.QtWidgets = QtWidgets
        self.kb_root = Path(kb_root)
        self.kb_paths = resolve_kb_paths(self.kb_root)
        self.app_paths = resolve_app_paths()
        self.profile_store = ProfileStore(Path(app_db))
        self.job_store = JobStore(Path(app_db))

        self.window = QtWidgets.QMainWindow()
        self.window.setWindowTitle("LLM Knowledge Base")
        self.window.resize(1100, 720)
        self._build()

    def show(self) -> None:
        self.refresh_all()
        self.window.show()

    def _build(self) -> None:
        QtWidgets = self.QtWidgets
        root = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(root)

        self.top_bar = QtWidgets.QLabel()
        self.top_bar.setObjectName("topBar")
        outer.addWidget(self.top_bar)

        body = QtWidgets.QHBoxLayout()
        outer.addLayout(body, 1)

        self.sidebar = QtWidgets.QListWidget()
        self.sidebar.setFixedWidth(180)
        for page in PAGE_REGISTRY:
            self.sidebar.addItem(page.title)
        body.addWidget(self.sidebar)

        self.stack = QtWidgets.QStackedWidget()
        body.addWidget(self.stack, 1)
        self._create_pages()

        self.bottom_bar = QtWidgets.QLabel("Ready")
        outer.addWidget(self.bottom_bar)

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)
        self.window.setCentralWidget(root)

    def _create_pages(self) -> None:
        self.dashboard_label = self._add_page("Dashboard", self._dashboard_controls)
        self._add_page("Setup", self._setup_controls)
        self.profiles_list = self._add_page("Profiles", self._profiles_controls)
        self._add_page("Hooks", self._hooks_controls)
        self.daily_list = self._add_page("Daily Logs", self._daily_controls)
        self.knowledge_list = self._add_page("Knowledge", self._knowledge_controls)
        self._add_page("Operations", self._operations_controls)
        self.jobs_list = self._add_page("Jobs", self._jobs_controls)
        self._add_page("Settings", self._settings_controls)
        self._add_page("Diagnostics", self._diagnostics_controls)

    def _add_page(self, title: str, builder):
        QtWidgets = self.QtWidgets
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        heading = QtWidgets.QLabel(title)
        heading.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(heading)
        result = builder(layout)
        layout.addStretch(1)
        self.stack.addWidget(page)
        return result

    def _dashboard_controls(self, layout):
        QtWidgets = self.QtWidgets
        label = QtWidgets.QLabel()
        layout.addWidget(label)
        row = QtWidgets.QHBoxLayout()
        layout.addLayout(row)
        self._button(row, "Compile Changed", lambda: self.enqueue_action("compile_changed"))
        self._button(row, "Structural Lint", lambda: self.enqueue_action("lint_structural"))
        self._button(row, "Diagnostics Export", self.export_diagnostics_now)
        return label

    def _setup_controls(self, layout):
        row = self.QtWidgets.QHBoxLayout()
        layout.addLayout(row)
        self._button(row, "Backend Smoke Test", lambda: self.enqueue_action("backend_smoke_test"))
        self._button(row, "Flush Test", lambda: self.enqueue_action("flush_test"))
        self._button(row, "Enable Daily Compile", self.enable_daily_compile)

    def _profiles_controls(self, layout):
        QtWidgets = self.QtWidgets
        profile_list = QtWidgets.QListWidget()
        layout.addWidget(profile_list)
        form = QtWidgets.QHBoxLayout()
        layout.addLayout(form)
        self.profile_name_input = QtWidgets.QLineEdit()
        self.profile_name_input.setPlaceholderText("Profile name")
        self.profile_root_input = QtWidgets.QLineEdit(str(self.kb_root))
        form.addWidget(self.profile_name_input)
        form.addWidget(self.profile_root_input)
        self._button(form, "Create", self.create_profile)
        self._button(form, "Activate Selected", self.activate_selected_profile)
        return profile_list

    def _hooks_controls(self, layout):
        row = self.QtWidgets.QHBoxLayout()
        layout.addLayout(row)
        self._button(row, "Install Hooks", lambda: self.enqueue_action("install_hooks"))
        self._button(row, "Repair Hooks", lambda: self.enqueue_action("repair_hooks"))
        self._button(row, "Remove Hooks", lambda: self.enqueue_action("remove_hooks"))

    def _daily_controls(self, layout):
        QtWidgets = self.QtWidgets
        daily_list = QtWidgets.QListWidget()
        layout.addWidget(daily_list)
        self.manual_memory_input = QtWidgets.QTextEdit()
        self.manual_memory_input.setPlaceholderText("Manual memory")
        layout.addWidget(self.manual_memory_input)
        row = QtWidgets.QHBoxLayout()
        layout.addLayout(row)
        self._button(row, "Add Memory", self.add_manual_memory)
        self._button(row, "Compile Selected", self.compile_selected_daily)
        return daily_list

    def _knowledge_controls(self, layout):
        QtWidgets = self.QtWidgets
        self.query_input = QtWidgets.QLineEdit()
        self.query_input.setPlaceholderText("Ask the knowledge base")
        layout.addWidget(self.query_input)
        row = QtWidgets.QHBoxLayout()
        layout.addLayout(row)
        self._button(row, "Query", lambda: self.enqueue_query(file_back=False))
        self._button(row, "File Back", lambda: self.enqueue_query(file_back=True))
        knowledge_list = QtWidgets.QListWidget()
        layout.addWidget(knowledge_list)
        return knowledge_list

    def _operations_controls(self, layout):
        row = self.QtWidgets.QHBoxLayout()
        layout.addLayout(row)
        self._button(row, "Compile Changed", lambda: self.enqueue_action("compile_changed"))
        self._button(row, "Compile All", lambda: self.enqueue_action("compile_all"))
        self._button(row, "Structural Lint", lambda: self.enqueue_action("lint_structural"))
        self._button(row, "Full Lint", lambda: self.enqueue_action("lint_full"))

    def _jobs_controls(self, layout):
        QtWidgets = self.QtWidgets
        jobs_list = QtWidgets.QListWidget()
        layout.addWidget(jobs_list)
        row = QtWidgets.QHBoxLayout()
        layout.addLayout(row)
        self._button(row, "Refresh", self.refresh_jobs)
        self._button(row, "Cancel Selected", self.cancel_selected_job)
        return jobs_list

    def _settings_controls(self, layout):
        QtWidgets = self.QtWidgets
        self.daily_compile_checkbox = QtWidgets.QCheckBox("Daily compile")
        self.daily_compile_time = QtWidgets.QLineEdit("17:00")
        layout.addWidget(self.daily_compile_checkbox)
        layout.addWidget(self.daily_compile_time)
        row = QtWidgets.QHBoxLayout()
        layout.addLayout(row)
        self._button(row, "Save Scheduler", self.save_scheduler_settings)
        self._button(row, "Install Autostart", lambda: self.enqueue_action("install_autostart"))
        self._button(row, "Remove Autostart", lambda: self.enqueue_action("remove_autostart"))

    def _diagnostics_controls(self, layout):
        row = self.QtWidgets.QHBoxLayout()
        layout.addLayout(row)
        self._button(row, "Export Support Bundle", self.export_diagnostics_now)

    def _button(self, layout, text: str, callback):
        button = self.QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def active_profile(self):
        return self.profile_store.get_active_profile()

    def require_active_profile_id(self) -> int | None:
        profile = self.active_profile()
        if profile is None:
            self.bottom_bar.setText("No active profile configured")
            return None
        return profile.id

    def enqueue_action(self, action: str, payload: dict[str, Any] | None = None) -> None:
        profile_id = self.require_active_profile_id()
        if profile_id is None:
            return
        job = build_quick_action_job(action, profile_id=profile_id, payload=payload)
        job_id = self.job_store.enqueue(**job)
        self.bottom_bar.setText(f"Queued job {job_id}")
        self.refresh_jobs()

    def enqueue_query(self, *, file_back: bool) -> None:
        question = self.query_input.text().strip()
        if not question:
            self.bottom_bar.setText("Query is empty")
            return
        self.enqueue_action("query_file_back" if file_back else "query", {"question": question})

    def add_manual_memory(self) -> None:
        content = self.manual_memory_input.toPlainText().strip()
        if not content:
            self.bottom_bar.setText("Manual memory is empty")
            return
        self.enqueue_action("manual_memory", {"content": content})
        self.manual_memory_input.clear()

    def compile_selected_daily(self) -> None:
        selected = self.daily_list.currentItem()
        if selected is None:
            self.bottom_bar.setText("No daily log selected")
            return
        self.enqueue_action("compile_file", {"file": selected.text()})

    def create_profile(self) -> None:
        name = self.profile_name_input.text().strip() or "Personal"
        root = self.profile_root_input.text().strip() or str(self.kb_root)
        profile_id = self.profile_store.create_profile(name, root)
        if self.profile_store.get_active_profile() is None:
            self.profile_store.set_active_profile(profile_id)
        self.refresh_profiles()

    def activate_selected_profile(self) -> None:
        item = self.profiles_list.currentItem()
        if item is None:
            self.bottom_bar.setText("No profile selected")
            return
        profile_id = int(item.data(1))
        self.profile_store.set_active_profile(profile_id)
        self.refresh_all()

    def enable_daily_compile(self) -> None:
        self.profile_store.set_setting("daily_compile_enabled", True)
        self.profile_store.set_setting("daily_compile_time", "17:00")
        self.bottom_bar.setText("Daily compile enabled")

    def save_scheduler_settings(self) -> None:
        self.enqueue_action(
            "configure_daily_schedule",
            {
                "enabled": self.daily_compile_checkbox.isChecked(),
                "time": self.daily_compile_time.text().strip() or "17:00",
            },
        )

    def export_diagnostics_now(self) -> None:
        bundle = export_diagnostics(self.app_paths, self.kb_paths)
        self.bottom_bar.setText(f"Diagnostics exported: {bundle}")

    def cancel_selected_job(self) -> None:
        item = self.jobs_list.currentItem()
        if item is None:
            self.bottom_bar.setText("No job selected")
            return
        self.job_store.request_cancel(item.data(1))
        self.refresh_jobs()

    def refresh_all(self) -> None:
        self.refresh_dashboard()
        self.refresh_profiles()
        self.refresh_daily_logs()
        self.refresh_knowledge()
        self.refresh_jobs()

    def refresh_dashboard(self) -> None:
        profile = self.active_profile()
        self.dashboard_label.setText(
            format_dashboard_summary(
                profile_name=profile.name if profile else None,
                backend=profile.backend if profile else None,
                agent_status="ready",
                last_job_status=None,
            )
        )
        self.top_bar.setText(self.dashboard_label.text())

    def refresh_profiles(self) -> None:
        self.profiles_list.clear()
        for profile in self.profile_store.list_profiles():
            marker = "*" if profile.active else " "
            item = self.QtWidgets.QListWidgetItem(
                f"{marker} {profile.name} [{profile.backend}] {profile.root_path}"
            )
            item.setData(1, profile.id)
            self.profiles_list.addItem(item)

    def refresh_daily_logs(self) -> None:
        self.daily_list.clear()
        if self.kb_paths.daily_dir.exists():
            for path in sorted(self.kb_paths.daily_dir.glob("*.md"), reverse=True):
                self.daily_list.addItem(path.name)

    def refresh_knowledge(self) -> None:
        self.knowledge_list.clear()
        if self.kb_paths.index_file.exists():
            for line in self.kb_paths.index_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("| [["):
                    self.knowledge_list.addItem(line)

    def refresh_jobs(self) -> None:
        self.jobs_list.clear()
        conn = self.job_store._connection()
        with conn as db:
            rows = db.execute(
                "SELECT id, job_type, status, created_at FROM jobs ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
        for row in rows:
            item = self.QtWidgets.QListWidgetItem(
                f"{row['status']} | {row['job_type']} | {row['created_at']}"
            )
            item.setData(1, row["id"])
            self.jobs_list.addItem(item)
