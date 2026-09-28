import tempfile,unittest
from pathlib import Path
from test_desktop import APP
from PySide6.QtCore import Qt,QPropertyAnimation,QCoreApplication,QEvent
from PySide6.QtTest import QTest,QSignalSpy
from PySide6.QtWidgets import QPushButton
from desktop.window import Window
from desktop.storage import Store
from desktop.hud import clock
from desktop.icons import icon

class VisualMotionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name))
        self.window=Window(self.store);self.window.show();QTest.qWait(230)
    def tearDown(self):
        self.window.close();self.window.deleteLater();APP.processEvents();self.temp.cleanup()
    def test_hidden_panels_stop_and_static_mode_persists(self):
        self.window.navigate(3);QTest.qWait(230);phase=self.window.hero.phase
        QTest.qWait(100);self.assertEqual(self.window.hero.phase,phase)
        self.window.motion_toggle.setChecked(False);APP.processEvents()
        self.assertFalse(clock().timer.isActive());self.assertFalse(Store(self.store.root).settings['animations'])
        self.window.navigate(0);phase=self.window.hero.phase;QTest.qWait(100)
        self.assertEqual(self.window.hero.phase,phase)
    def test_rate_persists_and_reactor_freezes_when_hidden(self):
        self.window.motion_rate.setCurrentIndex(1)
        self.assertEqual(clock().timer.interval(),33)
        self.assertEqual(Store(self.store.root).settings['animation_fps'],30)
        reactor=self.window.hero.reactor
        self.window.navigate(2);QTest.qWait(250);phase=reactor.phase
        QTest.qWait(100);self.assertEqual(reactor.phase,phase)
        self.window.showMinimized();QTest.qWait(100)
        self.assertFalse(clock().timer.isActive())
    def test_reactor_moves_and_static_frame_is_stable(self):
        reactor=self.window.hero.reactor
        self.window.resize(1440,920);QTest.qWait(250)
        before=reactor.grab().toImage();QTest.qWait(180)
        self.assertNotEqual(before,reactor.grab().toImage())
        self.window.motion_toggle.setChecked(False);QTest.qWait(250)
        frozen=reactor.grab().toImage();QTest.qWait(100)
        self.assertEqual(frozen,reactor.grab().toImage())
    def test_finished_transitions_are_released(self):
        page=self.window.stack.widget(0)
        for _ in range(8):
            self.window.navigate(0)
            # Wait for the actual end signal under loaded CI runners, then
            # process Qt's deferred deletion before checking object ownership.
            animation=page._fade_anim
            self.assertIsNotNone(animation)
            self.assertTrue(QSignalSpy(animation.finished).wait(2000))
            self.assertIsNone(page._fade_anim)
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.assertEqual(len(page.findChildren(QPropertyAnimation)),0)
    def test_overview_icon_keeps_all_four_quadrants(self):
        image=icon('overview').pixmap(32,32).toImage()
        for left,top in [(0,0),(16,0),(0,16),(16,16)]:
            count=sum(image.pixelColor(x,y).alpha()>0 for x in range(left,left+16) for y in range(top,top+16))
            self.assertGreater(count,10)
    def test_hero_actions_and_search_shortcut(self):
        buttons=self.window.hero.findChildren(QPushButton)
        QTest.mouseClick(buttons[0],Qt.MouseButton.LeftButton);self.assertEqual(self.window.stack.currentIndex(),2)
        self.window.navigate(0);QTest.qWait(200)
        QTest.mouseClick(buttons[1],Qt.MouseButton.LeftButton);self.assertEqual(self.window.stack.currentIndex(),6)
        self.window.focus_search();self.assertTrue(self.window.search.hasFocus())
    def test_execution_effect_follows_actual_activity(self):
        self.window.navigate(3);self.assertFalse(self.window.scan.motion_active)
        self.window.active_changed(True);self.assertTrue(self.window.scan.motion_active)
        self.window.active_changed(False);self.assertFalse(self.window.scan.motion_active)
