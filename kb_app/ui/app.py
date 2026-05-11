"""PySide6 desktop control panel."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kb_app.core.config_merge import KB_HOOK_MARKER
from kb_app.core.mcp_setup import find_claude_config, find_codex_config, mcp_is_configured, mcp_is_configured_codex
from kb_app.core.paths import resolve_app_paths, resolve_kb_paths
from kb_app.diagnostics.export import export_diagnostics
from kb_app.jobs.queue import JobStore
from kb_app.jobs.runner import JobRunner, default_hook_config_path
from kb_app.profiles.store import ProfileStore

PYSIDE_PACKAGE_NAME = "PySide6"


@dataclass(frozen=True)
class PageDefinition:
    page_id: str
    title: str


PAGE_REGISTRY = [
    PageDefinition("tutorial",   "Tutorial"),       # 0
    PageDefinition("dashboard",  "Dashboard"),      # 1
    PageDefinition("setup",      "Setup"),          # 2
    PageDefinition("profiles",   "Profiles"),       # 3
    PageDefinition("hooks",      "Hooks"),          # 4
    PageDefinition("daily_logs", "Daily Logs"),     # 5
    PageDefinition("knowledge",  "Knowledge"),      # 6
    PageDefinition("operations", "Operations"),     # 7
    PageDefinition("jobs",       "Jobs"),           # 8
    PageDefinition("settings",   "Settings"),       # 9
    PageDefinition("diagnostics","Diagnostics"),    # 10
]

# Sidebar indices — keep in sync with PAGE_REGISTRY above
_PAGE_TUTORIAL    = 0
_PAGE_HOOKS       = 4
_PAGE_OPERATIONS  = 7
_PAGE_KNOWLEDGE   = 6

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
        QtCore, QtWidgets = require_pyside6()
        self.QtWidgets = QtWidgets
        self.kb_root = Path(kb_root)
        self.kb_paths = resolve_kb_paths(self.kb_root)
        self.app_paths = resolve_app_paths()
        self.profile_store = ProfileStore(Path(app_db))
        self.job_store = JobStore(Path(app_db))
        self.runner = JobRunner(self.job_store, profile_store=self.profile_store)

        self.window = QtWidgets.QMainWindow()
        self.window.setWindowTitle("LLM Knowledge Base")
        self.window.resize(1100, 720)
        self._build()

        # Process one queued job every 2 seconds
        self._job_timer = QtCore.QTimer()
        self._job_timer.setInterval(2000)
        self._job_timer.timeout.connect(self._tick)
        self._job_timer.start()

    def show(self) -> None:
        self.window.show()
        self._show_first_run_dialog()
        self.refresh_all()
        self.sidebar.setCurrentRow(_PAGE_TUTORIAL)

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
        self._add_page("Tutorial",   self._tutorial_controls)
        self.dashboard_label = self._add_page("Dashboard", self._dashboard_controls)
        self._add_page("Setup",      self._setup_controls)
        self.profiles_list = self._add_page("Profiles", self._profiles_controls)
        self._add_page("Hooks",      self._hooks_controls)
        self.daily_list = self._add_page("Daily Logs", self._daily_controls)
        self.knowledge_list = self._add_page("Knowledge", self._knowledge_controls)
        self._add_page("Operations", self._operations_controls)
        self.jobs_list = self._add_page("Jobs", self._jobs_controls)
        self._add_page("Settings",   self._settings_controls)
        self._add_page("Diagnostics",self._diagnostics_controls)

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

    # ------------------------------------------------------------------
    # Tutorial page
    # ------------------------------------------------------------------

    def _tutorial_controls(self, layout):
        QtWidgets = self.QtWidgets

        # ── Status box ──────────────────────────────────────────────
        status_box = QtWidgets.QGroupBox("Status Atual")
        status_layout = QtWidgets.QVBoxLayout(status_box)

        self._tut_profile_lbl      = QtWidgets.QLabel()
        self._tut_claude_hooks_lbl = QtWidgets.QLabel()
        self._tut_codex_hooks_lbl  = QtWidgets.QLabel()
        self._tut_claude_mcp_lbl   = QtWidgets.QLabel()
        self._tut_codex_mcp_lbl    = QtWidgets.QLabel()

        for lbl in (
            self._tut_profile_lbl,
            self._tut_claude_hooks_lbl,
            self._tut_codex_hooks_lbl,
            self._tut_claude_mcp_lbl,
            self._tut_codex_mcp_lbl,
        ):
            lbl.setWordWrap(True)
            status_layout.addWidget(lbl)

        refresh_status_btn = QtWidgets.QPushButton("Atualizar Status")
        refresh_status_btn.clicked.connect(self.refresh_tutorial)
        status_layout.addWidget(refresh_status_btn)
        layout.addWidget(status_box)

        # ── Steps ────────────────────────────────────────────────────
        def step(number: str, title: str, body: str) -> QtWidgets.QWidget:
            frame = QtWidgets.QFrame()
            frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
            vbox = QtWidgets.QVBoxLayout(frame)
            header = QtWidgets.QLabel(f"<b>Passo {number} — {title}</b>")
            header.setStyleSheet("font-size: 13px;")
            desc = QtWidgets.QLabel(body)
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #444;")
            vbox.addWidget(header)
            vbox.addWidget(desc)
            return frame, vbox

        # Step 1 — Perfil
        f1, v1 = step("1", "Criar Perfil  ✅",
            "Um perfil diz ao app onde salvar sua base de conhecimento. "
            "Se você ainda não tem um, vá em <b>Profiles</b>, preencha o nome "
            "e a pasta, e clique em <b>Create</b> e depois <b>Activate Selected</b>.")
        btn_profiles = QtWidgets.QPushButton("Ir para Profiles →")
        btn_profiles.clicked.connect(lambda: self.sidebar.setCurrentRow(3))
        v1.addWidget(btn_profiles)
        layout.addWidget(f1)

        # Step 2 — Hooks
        f2, v2 = step("2", "Instalar Hooks",
            "Hooks são pequenos scripts que o Claude Code / Codex chama "
            "automaticamente ao início e fim de cada sessão. "
            "Sem eles o app não captura nada.\n\n"
            "→ Clique em <b>Ir para Hooks</b>\n"
            "→ Escolha o cliente (Claude Code ou Codex)\n"
            "→ Clique em <b>Install Hooks</b>")
        btn_hooks = QtWidgets.QPushButton("Ir para Hooks →")
        btn_hooks.clicked.connect(lambda: self.sidebar.setCurrentRow(_PAGE_HOOKS))
        v2.addWidget(btn_hooks)
        layout.addWidget(f2)

        # Step 3 — Restart
        f3, _ = step("3", "Reiniciar o Claude Code / Codex",
            "Depois de instalar os hooks, feche completamente o Claude Code "
            "(ou Codex) e abra de novo. Isso faz os hooks entrarem em vigor.")
        layout.addWidget(f3)

        # Step 4 — Work normally
        f4, _ = step("4", "Trabalhar Normalmente",
            "A partir de agora, toda sessão com o Claude Code é capturada "
            "automaticamente em segundo plano. Você não precisa fazer nada — "
            "basta trabalhar como sempre.")
        layout.addWidget(f4)

        # Step 5 — Compile
        f5, v5 = step("5", "Compilar os Logs (após as primeiras sessões)",
            "Depois de alguns dias de trabalho, compile os logs para gerar "
            "artigos de wiki organizados. Você pode fazer isso quando quiser, "
            "ou ativar a compilação automática diária em <b>Settings</b>.\n\n"
            "→ Clique em <b>Ir para Operations</b>\n"
            "→ Clique em <b>Compile Changed</b>")
        btn_ops = QtWidgets.QPushButton("Ir para Operations →")
        btn_ops.clicked.connect(lambda: self.sidebar.setCurrentRow(_PAGE_OPERATIONS))
        v5.addWidget(btn_ops)
        layout.addWidget(f5)

        # Step 6 — Query
        f6, v6 = step("6", "Consultar sua Base de Conhecimento",
            "Pergunte em linguagem natural sobre o que você já aprendeu:\n"
            "\"Como eu fiz X?\", \"Qual biblioteca eu uso para Y?\"\n\n"
            "→ Clique em <b>Ir para Knowledge</b>\n"
            "→ Digite sua pergunta\n"
            "→ Clique em <b>Query</b>")
        btn_know = QtWidgets.QPushButton("Ir para Knowledge →")
        btn_know.clicked.connect(lambda: self.sidebar.setCurrentRow(_PAGE_KNOWLEDGE))
        v6.addWidget(btn_know)
        layout.addWidget(f6)

        # MCP info box
        mcp_box = QtWidgets.QGroupBox("Sobre o MCP (integração automática com a IA)")
        mcp_vbox = QtWidgets.QVBoxLayout(mcp_box)
        mcp_desc = QtWidgets.QLabel(
            "O MCP permite que o Claude Code / Codex consulte sua KB "
            "<b>automaticamente durante a conversa</b>, sem você precisar pedir.\n\n"
            "Foi configurado durante a instalação. Se precisar reconfigurar:\n"
            "  • Windows: abra o terminal e execute  "
            "<code>LLMKnowledgeBase.exe setup-mcp --status</code>\n"
            "  • Linux: <code>llm-knowledge-base setup-mcp --status</code>"
        )
        mcp_desc.setWordWrap(True)
        mcp_vbox.addWidget(mcp_desc)
        layout.addWidget(mcp_box)

    def refresh_tutorial(self) -> None:
        """Update live status labels on the Tutorial page."""
        ok  = "✅"
        err = "❌"
        na  = "—"

        profile = self.active_profile()
        if profile:
            self._tut_profile_lbl.setText(f"{ok}  Perfil ativo: <b>{profile.name}</b>  ({profile.root_path})")
        else:
            self._tut_profile_lbl.setText(f"{err}  Nenhum perfil configurado — vá em <b>Profiles</b>")

        for client, lbl in (("claude", self._tut_claude_hooks_lbl), ("codex", self._tut_codex_hooks_lbl)):
            icon = ok if self._hooks_installed(client) else err
            label = "Claude Code" if client == "claude" else "Codex"
            lbl.setText(f"{icon}  Hooks {label}: {'instalados' if icon == ok else 'não instalados'}")

        claude_mcp = mcp_is_configured()
        codex_mcp  = mcp_is_configured_codex()
        self._tut_claude_mcp_lbl.setText(
            f"{ok if claude_mcp else err}  MCP Claude Code: {'configurado' if claude_mcp else 'não configurado'}"
        )
        self._tut_codex_mcp_lbl.setText(
            f"{ok if codex_mcp else err}  MCP Codex: {'configurado' if codex_mcp else 'não configurado'}"
        )

    def _hooks_installed(self, client: str) -> bool:
        """Return True if our hook marker exists in the client's config file."""
        try:
            config = default_hook_config_path(client)
            if not config.exists():
                return False
            return KB_HOOK_MARKER in config.read_text(encoding="utf-8")
        except OSError:
            return False

    # ------------------------------------------------------------------
    # First-run dialog
    # ------------------------------------------------------------------

    def _show_first_run_dialog(self) -> None:
        """If no profiles exist, show a dialog to create the first one."""
        if self.profile_store.list_profiles():
            return  # Already set up

        QtWidgets = self.QtWidgets
        dialog = QtWidgets.QDialog(self.window)
        dialog.setWindowTitle("Bem-vindo ao LLM Knowledge Base!")
        dialog.setMinimumWidth(520)
        dialog.setModal(True)

        layout = QtWidgets.QVBoxLayout(dialog)

        welcome = QtWidgets.QLabel(
            "<h2>👋 Bem-vindo!</h2>"
            "<p>Antes de começar, precisamos criar seu primeiro <b>perfil</b>.<br>"
            "Um perfil define o nome e onde sua base de conhecimento fica salva.</p>"
        )
        welcome.setWordWrap(True)
        layout.addWidget(welcome)

        form = QtWidgets.QFormLayout()

        name_input = QtWidgets.QLineEdit("Meu KB")
        form.addRow("Nome do perfil:", name_input)

        root_row = QtWidgets.QHBoxLayout()
        default_root = str(self._detect_default_kb_root())
        root_input = QtWidgets.QLineEdit(default_root)
        browse_btn = QtWidgets.QPushButton("Procurar…")
        root_row.addWidget(root_input)
        root_row.addWidget(browse_btn)
        root_container = QtWidgets.QWidget()
        root_container.setLayout(root_row)
        form.addRow("Pasta da base de conhecimento:", root_container)

        layout.addLayout(form)

        def browse() -> None:
            folder = QtWidgets.QFileDialog.getExistingDirectory(
                dialog, "Escolha a pasta da sua KB", root_input.text()
            )
            if folder:
                root_input.setText(folder)

        browse_btn.clicked.connect(browse)

        error_lbl = QtWidgets.QLabel("")
        error_lbl.setStyleSheet("color: red;")
        layout.addWidget(error_lbl)

        btn_row = QtWidgets.QHBoxLayout()
        create_btn = QtWidgets.QPushButton("Criar Perfil e Continuar →")
        create_btn.setDefault(True)
        btn_row.addStretch(1)
        btn_row.addWidget(create_btn)
        layout.addLayout(btn_row)

        def create() -> None:
            name = name_input.text().strip() or "Meu KB"
            root = Path(root_input.text().strip())
            if not root_input.text().strip():
                error_lbl.setText("Escolha uma pasta para a base de conhecimento.")
                return
            # Create directory structure
            for sub in [
                "kb/daily",
                "kb/knowledge/concepts",
                "kb/knowledge/connections",
                "kb/knowledge/qa",
            ]:
                (root / sub).mkdir(parents=True, exist_ok=True)
            profile_id = self.profile_store.create_profile(name, str(root))
            self.profile_store.set_active_profile(profile_id)
            # Update kb_root so the window reflects the new profile
            self.kb_root = root
            self.kb_paths = resolve_kb_paths(root)
            dialog.accept()

        create_btn.clicked.connect(create)

        # Prevent closing without creating a profile
        dialog.setWindowFlag(0x00040000, False)  # Qt.WindowCloseButtonHint
        dialog.exec()

    def _detect_default_kb_root(self) -> Path:
        """Read KB_ROOT from .install-config (installer) or fall back to OS default."""
        exe_dir = Path(sys.executable).parent
        config_file = exe_dir / ".install-config"
        if config_file.exists():
            try:
                for line in config_file.read_text(encoding="utf-8").splitlines():
                    if line.startswith("KB_ROOT="):
                        val = line.split("=", 1)[1].strip()
                        if val:
                            return Path(val)
            except OSError:
                pass
        return Path.home() / "Documents" / "LLM Knowledge Base"

    # ------------------------------------------------------------------
    # Hooks page
    # ------------------------------------------------------------------

    def _hooks_controls(self, layout):
        QtWidgets = self.QtWidgets

        client_row = QtWidgets.QHBoxLayout()
        layout.addLayout(client_row)
        client_row.addWidget(QtWidgets.QLabel("AI Client:"))
        self.hooks_client_combo = QtWidgets.QComboBox()
        self.hooks_client_combo.addItem("Claude Code", "claude")
        self.hooks_client_combo.addItem("Codex", "codex")
        client_row.addWidget(self.hooks_client_combo)
        client_row.addStretch(1)

        desc = QtWidgets.QLabel(
            "Claude Code — hooks em ~/.claude/settings.json (SessionStart, SessionEnd, PreCompact)\n"
            "Codex — hooks em ~/.codex/hooks.json (SessionStart, Stop)"
        )
        desc.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(desc)

        row = QtWidgets.QHBoxLayout()
        layout.addLayout(row)
        self._button(row, "Install Hooks", lambda: self._hooks_action("install_hooks"))
        self._button(row, "Repair Hooks",  lambda: self._hooks_action("repair_hooks"))
        self._button(row, "Remove Hooks",  lambda: self._hooks_action("remove_hooks"))

    def _hooks_action(self, action: str) -> None:
        client = self.hooks_client_combo.currentData()
        self.enqueue_action(action, {"client": client})

    def _tick(self) -> None:
        """Called every 2 s by QTimer — runs one pending job and refreshes UI."""
        result = self.runner.run_next()
        if result.status != "idle":
            self.refresh_jobs()
            self.refresh_dashboard()

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
        self.refresh_tutorial()
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
