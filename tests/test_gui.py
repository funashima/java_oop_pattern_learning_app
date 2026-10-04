"""Offscreen GUI integration checks; skipped when PyQt6 is unavailable."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
try:
    from PyQt6.QtWidgets import QApplication
    from pattern_lab.gui import Window
    AVAILABLE=True
except ImportError:
    AVAILABLE=False

@unittest.skipUnless(AVAILABLE,'PyQt6 is not installed')
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):self.win=Window()
    def tearDown(self):self.win.close()
    def test_all_lessons_variants_steps_and_evidence(self):
        for index in range(4):
            self.win.lesson.setCurrentIndex(index)
            for variant in range(2):
                self.win.variant.setCurrentIndex(variant)
                for step in range(len(self.win.events)+1):
                    self.win.slider.setValue(step);self.app.processEvents()
                self.assertTrue(self.win.source_matches)
                self.assertEqual(self.win.timeline.rowCount(),len(self.win.events))
                self.assertEqual(self.win.checks.rowCount(),len(self.win.findings))
                self.win.goto_finding(0,0)
                self.assertEqual(self.win.slider.value(),self.win.findings[0].evidence[-1])
    def test_backward_navigation_and_play(self):
        self.win.slider.setValue(len(self.win.events));self.win.toggle_play()
        self.assertTrue(self.win.timer.isActive());self.assertEqual(self.win.slider.value(),0)
        self.win.toggle_play();self.assertFalse(self.win.timer.isActive())
        self.win.slider.setValue(7);self.win.move(-1);self.assertEqual(self.win.slider.value(),6)
    def test_source_hash_mismatch_disables_highlight(self):
        import copy
        ev=copy.deepcopy(self.win.events);ev[0]['source_sha256']='wrong'
        self.win.activate(ev);self.win.slider.setValue(5)
        self.assertFalse(self.win.source_matches);self.assertEqual(len(self.win.source.extraSelections()),0)
    def test_state_input_disabled(self):
        self.win.lesson.setCurrentIndex(2);self.assertFalse(self.win.value.isEnabled())
        self.win.lesson.setCurrentIndex(1);self.assertTrue(self.win.value.isEnabled())

if __name__=='__main__':unittest.main()
