"""PySide6 desktop control panel."""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kb_app.core.config_merge import KB_HOOK_MARKER
from kb_app.core.mcp_setup import (
    find_claude_code_config,
    find_claude_config,
    find_codex_config,
    mcp_is_configured,
    mcp_is_configured_claude_code,
    mcp_is_configured_codex,
)
from kb_app.core.paths import (
    default_kb_root,
    ensure_kb_layout,
    is_same_path,
    resolve_app_paths,
    resolve_kb_paths,
)
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


def normalize_startup_kb_root(
    *,
    requested_root: Path,
    profile_store: ProfileStore,
    app_paths=None,
    platform: str | None = None,
    env: dict[str, str] | None = None,
) -> Path:
    """Choose a safe KB root for UI startup and repair install-dir profiles."""
    resolved_app_paths = app_paths or resolve_app_paths(platform=platform, env=env)
    fallback_root = default_kb_root(platform=platform, env=env)
    active = profile_store.get_active_profile()

    if active is not None:
        active_root = Path(active.root_path)
        if is_same_path(active_root, resolved_app_paths.install_dir):
            ensured = ensure_kb_layout(fallback_root)
            profile_store.update_profile_root(active.id, ensured.root)
            return ensured.root
        return ensure_kb_layout(active_root).root

    if not is_same_path(requested_root, resolved_app_paths.install_dir):
        return ensure_kb_layout(requested_root).root
    return ensure_kb_layout(fallback_root).root


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

        tray = TrayController(app, window)
        tray.install()

    return int(app.exec())


class ControlPanelWindow:
    """Small operational control panel built with Qt widgets."""

    def __init__(self, kb_root: Path, app_db: Path) -> None:
        QtCore, QtWidgets = require_pyside6()
        self.QtCore = QtCore
        self.QtWidgets = QtWidgets
        self.app_paths = resolve_app_paths()
        self.profile_store = ProfileStore(Path(app_db))
        self.job_store = JobStore(Path(app_db))
        self.kb_root = normalize_startup_kb_root(
            requested_root=Path(kb_root),
            profile_store=self.profile_store,
            app_paths=self.app_paths,
        )
        self.kb_paths = resolve_kb_paths(self.kb_root)
        self.runner = JobRunner(self.job_store, profile_store=self.profile_store)

        self.window = QtWidgets.QMainWindow()
        self.window.setWindowTitle("LLM Knowledge Base")
        self.window.resize(1100, 720)
        try:
            from kb_app.ui.resources.qicon import app_icon
            icon = app_icon()
            if icon:
                self.window.setWindowIcon(icon)
        except Exception:
            pass
        self._build()

        self._job_running = False
        self._pending_job_result = None

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
        Qt = self.QtCore.Qt

        # Wrap everything in a scroll area so it never clips
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        container = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(container)
        vbox.setSpacing(12)
        vbox.setContentsMargins(4, 4, 4, 4)

        # ── Status card ──────────────────────────────────────────────
        status_card = QtWidgets.QFrame()
        status_card.setStyleSheet(
            "QFrame { border: 1px solid #444; border-radius: 8px;"
            " background: #1e2a1e; padding: 4px; }"
        )
        sc_layout = QtWidgets.QVBoxLayout(status_card)
        sc_layout.setSpacing(6)

        status_title = QtWidgets.QLabel("📊  Status Atual")
        status_title.setStyleSheet("font-size: 13px; font-weight: bold; border: none;")
        sc_layout.addWidget(status_title)

        self._tut_profile_lbl      = self._status_label(QtWidgets)
        self._tut_claude_hooks_lbl = self._status_label(QtWidgets)
        self._tut_codex_hooks_lbl  = self._status_label(QtWidgets)
        self._tut_claude_mcp_lbl   = self._status_label(QtWidgets)
        self._tut_codex_mcp_lbl    = self._status_label(QtWidgets)
        for lbl in (
            self._tut_profile_lbl,
            self._tut_claude_hooks_lbl,
            self._tut_codex_hooks_lbl,
            self._tut_claude_mcp_lbl,
            self._tut_codex_mcp_lbl,
        ):
            sc_layout.addWidget(lbl)

        refresh_btn = QtWidgets.QPushButton("🔄  Atualizar Status")
        refresh_btn.setFixedHeight(30)
        refresh_btn.clicked.connect(self.refresh_tutorial)
        sc_layout.addWidget(refresh_btn)
        vbox.addWidget(status_card)

        # ── Step helper ──────────────────────────────────────────────
        def make_step(num: int, icon: str, title: str, body_html: str,
                      btn_label: str | None = None, btn_slot=None):
            card = QtWidgets.QFrame()
            card.setStyleSheet(
                "QFrame { border: 1px solid #3a3a4a; border-radius: 8px;"
                " background: #1e1e2e; padding: 4px; }"
            )
            cl = QtWidgets.QVBoxLayout(card)
            cl.setSpacing(6)

            # Header row
            hrow = QtWidgets.QHBoxLayout()
            badge = QtWidgets.QLabel(str(num))
            badge.setFixedSize(30, 30)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(
                "background: #4a6fa5; color: white; border-radius: 15px;"
                " font-weight: bold; font-size: 13px; border: none;"
            )
            title_lbl = QtWidgets.QLabel(f"{icon}  <b>{title}</b>")
            title_lbl.setStyleSheet("font-size: 13px; border: none;")
            title_lbl.setTextFormat(Qt.RichText)
            hrow.addWidget(badge)
            hrow.addSpacing(8)
            hrow.addWidget(title_lbl)
            hrow.addStretch(1)
            cl.addLayout(hrow)

            # Body
            desc = QtWidgets.QLabel(f"<p style='margin:0; line-height:160%'>{body_html}</p>")
            desc.setWordWrap(True)
            desc.setTextFormat(Qt.RichText)
            desc.setStyleSheet("color: #aaa; border: none; padding-left: 38px;")
            cl.addWidget(desc)

            if btn_label and btn_slot:
                btn = QtWidgets.QPushButton(f"  {btn_label}  →")
                btn.setFixedHeight(30)
                btn.setStyleSheet(
                    "QPushButton { background: #2d4a7a; color: white; border-radius: 5px;"
                    " font-weight: bold; }"
                    " QPushButton:hover { background: #3a5f9f; }"
                )
                btn.clicked.connect(btn_slot)
                brow = QtWidgets.QHBoxLayout()
                brow.addStretch(1)
                brow.addWidget(btn)
                cl.addLayout(brow)

            return card

        # Step 1
        vbox.addWidget(make_step(1, "👤", "Criar Perfil",
            "Um perfil diz ao app <b>onde salvar</b> sua base de conhecimento.<br>"
            "Se ainda não tem um: vá em <b>Profiles</b>, escreva um nome, escolha "
            "a pasta e clique em <b>Create</b> → <b>Activate Selected</b>.",
            "Ir para Profiles", lambda: self.sidebar.setCurrentRow(3)))

        # Step 2
        vbox.addWidget(make_step(2, "🔗", "Instalar Hooks",
            "Hooks são scripts que o <b>Claude Code / Codex</b> chama "
            "automaticamente ao iniciar e encerrar cada sessão.<br>"
            "Sem eles o app não captura nada.<br><br>"
            "① Clique em <b>Ir para Hooks</b><br>"
            "② Escolha o cliente: <b>Claude Code</b> ou <b>Codex</b><br>"
            "③ Clique em <b>Install Hooks</b> e aguarde ✅",
            "Ir para Hooks", lambda: self.sidebar.setCurrentRow(_PAGE_HOOKS)))

        # Step 3
        vbox.addWidget(make_step(3, "🔄", "Reiniciar o Claude Code / Codex",
            "Depois de instalar os hooks, <b>feche completamente</b> o Claude Code "
            "ou Codex e abra novamente.<br>"
            "Isso faz os hooks e o MCP entrarem em vigor."))

        # Step 4
        vbox.addWidget(make_step(4, "💻", "Trabalhar Normalmente",
            "A partir de agora, toda sessão com o Claude Code é "
            "<b>capturada automaticamente</b> em segundo plano.<br>"
            "Você não precisa fazer nada — só trabalhar como sempre."))

        # Step 5
        vbox.addWidget(make_step(5, "⚙️", "Compilar os Logs",
            "Após suas primeiras sessões, compile os logs para gerar "
            "<b>artigos de wiki</b> organizados.<br>"
            "Você pode fazer isso quando quiser, ou ativar a compilação "
            "automática diária em <b>Settings</b>.<br><br>"
            "① Clique em <b>Ir para Operations</b><br>"
            "② Clique em <b>Compile Changed</b>",
            "Ir para Operations", lambda: self.sidebar.setCurrentRow(_PAGE_OPERATIONS)))

        # Step 6
        vbox.addWidget(make_step(6, "🔍", "Consultar sua Base de Conhecimento",
            "Pergunte em linguagem natural sobre o que você já aprendeu:<br>"
            "<i>\"Como eu fiz X?\", \"Qual biblioteca eu uso para Y?\"</i><br><br>"
            "① Clique em <b>Ir para Knowledge</b><br>"
            "② Digite sua pergunta<br>"
            "③ Clique em <b>Query</b>",
            "Ir para Knowledge", lambda: self.sidebar.setCurrentRow(_PAGE_KNOWLEDGE)))

        # MCP info card
        mcp_card = QtWidgets.QFrame()
        mcp_card.setStyleSheet(
            "QFrame { border: 1px solid #4a3a1a; border-radius: 8px;"
            " background: #2a1e0a; padding: 4px; }"
        )
        mc_layout = QtWidgets.QVBoxLayout(mcp_card)
        mcp_title = QtWidgets.QLabel("🤖  Sobre o MCP — Integração automática com a IA")
        mcp_title.setStyleSheet("font-size: 13px; font-weight: bold; border: none;")
        mcp_desc = QtWidgets.QLabel(
            "<p style='margin:0; line-height:160%; color:#aaa'>"
            "O MCP permite que o Claude Code / Codex consulte sua KB "
            "<b>automaticamente durante a conversa</b>, sem você precisar pedir.<br>"
            "Foi configurado durante a instalação. Para verificar ou reconfigurar:<br>"
            "• Windows: <code>LLMKnowledgeBase.exe setup-mcp --status</code><br>"
            "• Linux:&nbsp;&nbsp; <code>llm-knowledge-base setup-mcp --status</code>"
            "</p>"
        )
        mcp_desc.setWordWrap(True)
        mcp_desc.setTextFormat(Qt.RichText)
        mcp_desc.setStyleSheet("border: none;")
        mc_layout.addWidget(mcp_title)
        mc_layout.addWidget(mcp_desc)
        vbox.addWidget(mcp_card)

        vbox.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _status_label(self, QtWidgets) -> object:
        lbl = QtWidgets.QLabel()
        lbl.setWordWrap(True)
        lbl.setTextFormat(self.QtCore.Qt.RichText)
        lbl.setStyleSheet("border: none; padding: 1px 0;")
        return lbl

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

        # MCP is considered configured if either Claude Desktop or Claude Code CLI has it
        claude_mcp = mcp_is_configured() or mcp_is_configured_claude_code()
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
            paths = ensure_kb_layout(root)
            profile_id = self.profile_store.create_profile(name, str(paths.root))
            self.profile_store.set_active_profile(profile_id)
            # Update kb_root so the window reflects the new profile
            self.kb_root = paths.root
            self.kb_paths = paths
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
        return default_kb_root()

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
        # Check if a background worker finished and deliver the result on the main thread
        pending = self._pending_job_result
        if pending is not None:
            self._pending_job_result = None
            self._on_job_done(*pending)

        if self._job_running:
            return
        # Peek at queue to show meaningful status without blocking
        try:
            with self.job_store._connection() as conn:
                row = conn.execute(
                    "SELECT job_type FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1"
                ).fetchone()
        except Exception:
            row = None

        if row is None:
            return  # nothing pending, skip thread allocation

        status_msg = {
            "compile_changed": "⏳  Compilando logs alterados...",
            "compile_all":     "⏳  Compilando todos os logs...",
            "compile_file":    "⏳  Compilando arquivo...",
            "query":           "⏳  Consultando base de conhecimento...",
            "query_file_back": "⏳  Consultando e salvando resposta...",
            "install_hooks":   "⏳  Instalando hooks...",
            "remove_hooks":    "⏳  Removendo hooks...",
            "lint_structural": "⏳  Verificando estrutura...",
            "lint_full":       "⏳  Verificando KB completo...",
        }.get(row["job_type"] if row else "", "⏳  Processando job...")
        self.bottom_bar.setText(status_msg)

        self._job_running = True

        def worker():
            result = None
            error = None
            try:
                result = self.runner.run_next()
            except Exception as exc:
                error = exc
            finally:
                self._job_running = False
                self._pending_job_result = (result, error)

        threading.Thread(target=worker, daemon=True).start()

    def _on_job_done(self, result, error) -> None:
        """Called on the main Qt thread when a background job completes."""
        if error is not None:
            self.bottom_bar.setText(f"❌  Erro no runner: {error}")
            self.refresh_jobs()
            return
        if result.status == "succeeded":
            self.bottom_bar.setText("✅  Job concluído com sucesso.")
            self.refresh_jobs()
            self.refresh_tutorial()
            self.refresh_dashboard()
        elif result.status == "failed":
            try:
                job = self.job_store.get_job(result.job_id)
                err = job.error_message or "erro desconhecido"
            except Exception:
                err = "erro desconhecido"
            self.bottom_bar.setText(f"❌  Job falhou: {err}")
            self.refresh_jobs()
            self.refresh_tutorial()
        elif result.status == "cancelled":
            self.bottom_bar.setText("⚠️  Job cancelado.")
            self.refresh_jobs()
        # idle: leave status bar unchanged

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

        compile_group = QtWidgets.QGroupBox("Compilação automática")
        cg_layout = QtWidgets.QVBoxLayout(compile_group)

        daily_row = QtWidgets.QHBoxLayout()
        self.daily_compile_checkbox = QtWidgets.QCheckBox("Compilar diariamente")
        self.daily_compile_time = QtWidgets.QLineEdit(
            self.profile_store.get_setting("daily_compile_time", "17:00")
        )
        self.daily_compile_time.setFixedWidth(70)
        self.daily_compile_checkbox.setChecked(
            bool(self.profile_store.get_setting("daily_compile_enabled", False))
        )
        daily_row.addWidget(self.daily_compile_checkbox)
        daily_row.addWidget(QtWidgets.QLabel("às"))
        daily_row.addWidget(self.daily_compile_time)
        daily_row.addStretch(1)
        cg_layout.addLayout(daily_row)

        self.compile_on_compact_checkbox = QtWidgets.QCheckBox(
            "Compilar após compactação de contexto (PostCompact — Claude Code)"
        )
        self.compile_on_compact_checkbox.setChecked(
            bool(self.profile_store.get_setting("compile_on_compact", False))
        )
        cg_layout.addWidget(self.compile_on_compact_checkbox)

        layout.addWidget(compile_group)

        btn_row = QtWidgets.QHBoxLayout()
        layout.addLayout(btn_row)
        self._button(btn_row, "Salvar Configurações", self.save_scheduler_settings)
        self._button(btn_row, "Install Autostart", lambda: self.enqueue_action("install_autostart"))
        self._button(btn_row, "Remove Autostart", lambda: self.enqueue_action("remove_autostart"))

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
        paths = ensure_kb_layout(root)
        profile_id = self.profile_store.create_profile(name, paths.root)
        if self.profile_store.get_active_profile() is None:
            self.profile_store.set_active_profile(profile_id)
            self.kb_root = paths.root
            self.kb_paths = paths
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
        self.profile_store.set_setting(
            "compile_on_compact",
            self.compile_on_compact_checkbox.isChecked(),
        )
        self.enqueue_action(
            "configure_daily_schedule",
            {
                "enabled": self.daily_compile_checkbox.isChecked(),
                "time": self.daily_compile_time.text().strip() or "17:00",
            },
        )

    def export_diagnostics_now(self) -> None:
        self.enqueue_action("diagnostics_export", {})

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
