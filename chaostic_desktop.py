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

    app = QApplication(sys.argv)
    app.setApplicationName("ChaosticTool Desktop")
    app.setOrganizationName("ChaosticTool")
    root = data_root()
    root.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(root / "desktop.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, "ChaosticTool Desktop", "L’application est déjà ouverte pour cet espace de travail.")
        return 0
    apply_theme(app)
    store = Store(root)
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
        QMessageBox.warning(window, "Erreur", f"{value}\n\nLes détails sont conservés dans desktop-errors.log.")
    sys.excepthook = exception_handler
    window.show()
    if sys.platform=='win32' and '--smoke-test' not in sys.argv:
        import json
        try:
            pending=json.loads((root/'wsl-setup.json').read_text(encoding='utf-8')).get('stage')!='ready'
        except (OSError,ValueError): pending=False
        if '--setup-wsl' in sys.argv or pending:
            QTimer.singleShot(400,window.setup_wsl)
    # Deterministic smoke test for the packaged application, with isolated data.
    if "--smoke-test" in sys.argv:
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
