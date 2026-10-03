"""Graphical entry point; does not import the Linux CLI modules."""
import sys


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--linux-bridge':
        from desktop.linux_bridge import main as bridge_main
        return bridge_main()
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        from desktop.workers import main as worker_main
        return worker_main(sys.argv[2:])

    from PySide6.QtCore import QLockFile, QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    from desktop.storage import Store, data_root
    from desktop.theme import apply_theme
    from desktop.window import Window
    from desktop.i18n import T, set_language

    app = QApplication(sys.argv)
    from PySide6.QtGui import QIcon
    from pathlib import Path
    app.setWindowIcon(QIcon(str(Path(__file__).parent/"desktop/assets/icon.png")))
    app.setApplicationName("ChaosticTool Desktop")
    app.setOrganizationName("ChaosticTool")
    root = data_root()
    root.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(root / "desktop.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, "ChaosticTool Desktop", T("L’application est déjà ouverte pour cet espace de travail."))
        return 0
    apply_theme(app)
    store = Store(root)
    set_language(store.settings.get("language", "en"))
    if '--smoke-test' in sys.argv:
        from desktop.storage import write_json
        from desktop.backends import get_config
        write_json(root/'smoke-initial-state.json',{
            'history':len(store.history()),'targets':len(store.targets),
            'configured_linux':bool(get_config(root))})
    window = Window(store)

    def exception_handler(kind, value, traceback):
        import traceback as tb
        with (root / "desktop-errors.log").open("a", encoding="utf-8") as stream:
            tb.print_exception(kind, value, traceback, file=stream)
        QMessageBox.warning(window, T("Erreur"), T("{error}\n\nLes détails sont conservés dans desktop-errors.log.").format(error=value))
    sys.excepthook = exception_handler
    window.show()
    if sys.platform=='win32' and '--smoke-test' not in sys.argv:
        import json
        try:
            pending=json.loads((root/'wsl-setup.json').read_text(encoding='utf-8')).get('stage')!='ready'
        except (OSError,ValueError): pending=False
        if '--setup-wsl' in sys.argv or pending:
            QTimer.singleShot(400,window.setup_wsl)
    if sys.platform.startswith('linux') and '--smoke-test' not in sys.argv:
        from desktop.backends import get_config
        if get_config(root).get('backend','local')=='local':
            QTimer.singleShot(400,window.check_backend)
    # Deterministic smoke test for the packaged application, with isolated data.
    if "--smoke-test" in sys.argv:
        import py7zr
        assert callable(py7zr.SevenZipFile), 'Packaged 7z support is missing'
        assert not window.hero.art.isNull(), "Packaged README artwork is missing"
        assert not window.brand_panel.art.isNull(), "Packaged brand artwork is missing"
        assert window.windowIcon().pixmap(256,256).save(str(root/"smoke-icon.png")), "Window icon is missing"
        result_file = root / "smoke-result.json"
        def done(result):
            from desktop.storage import write_json
            write_json(result_file, result)
            QTimer.singleShot(100, app.quit)
        window.runner.completed.connect(done)
        QTimer.singleShot(100, lambda: window.launch("desktop-diagnostic", show_dialog=False))
        QTimer.singleShot(20000, app.quit)
    code = app.exec()
    window.runner.shutdown()
    lock.unlock()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
