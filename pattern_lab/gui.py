"""PyQt6 desktop interface. The model and contracts do not depend on Qt."""
from __future__ import annotations
import html
import json
import math
import sys
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPointF
from PyQt6.QtGui import QColor, QFont, QPen, QBrush, QPolygonF, QTextCursor, QTextCharFormat
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QSpinBox, QSplitter, QTabWidget, QTextBrowser,
    QPlainTextEdit, QTextEdit, QGraphicsView, QGraphicsScene, QSlider, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox)
from .core import ROOT, LESSONS, load_trace, save_trace, assess, overall, replay
from .runner import run_java, source_hash, SOURCE

COLORS = {"PASS": "#087e68", "FAIL": "#bb3434", "UNKNOWN": "#88600b"}

class RunWorker(QThread):
    done = pyqtSignal(object)
    failed = pyqtSignal(str)
    def __init__(self, lesson, value, parent=None):
        super().__init__(parent); self.lesson, self.value = lesson, value
    def run(self):
        try: self.done.emit({v: run_java(self.lesson, v, self.value) for v in ("normal", "broken")})
        except Exception as ex: self.failed.emit(str(ex))

class ObjectView(QGraphicsView):
    def __init__(self):
        super().__init__(); self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor('#f4f7fa'))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        from PyQt6.QtGui import QPainter
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.scale(1.12 if event.angleDelta().y()>0 else 1/1.12, 1.12 if event.angleDelta().y()>0 else 1/1.12)
        else: super().wheelEvent(event)
    def draw_state(self, state, spec, all_ids):
        s = self.scene(); s.clear()
        pos = {oid: (35+(i%2)*345, 40+(i//2)*235) for i,oid in enumerate(all_ids)}
        width, height = 268, 166
        def label(text, x, y, size=10, color='#17344a', max_width=None):
            item=s.addText(text, QFont('sans-serif',size)); item.setDefaultTextColor(QColor(color)); item.setPos(x,y)
            if max_width: item.setTextWidth(max_width)
            return item
        def edge(src,dst,text,dashed=False):
            if src not in state.objects or dst not in state.objects: return
            x,y=pos[src]; xx,yy=pos[dst]
            if x==xx: a=QPointF(x+width/2,y+height); b=QPointF(xx+width/2,yy)
            else:
                a=QPointF(x+(width if xx>x else 0),y+height/2)
                b=QPointF(xx+(0 if xx>x else width),yy+height/2)
            pen=QPen(QColor('#d66b25' if dashed else '#7c94a8'),3 if dashed else 1.6)
            if dashed: pen.setStyle(Qt.PenStyle.DashLine)
            s.addLine(a.x(),a.y(),b.x(),b.y(),pen)
            angle=math.atan2(b.y()-a.y(),b.x()-a.x())
            tri=QPolygonF([b,QPointF(b.x()-10*math.cos(angle-.45),b.y()-10*math.sin(angle-.45)),QPointF(b.x()-10*math.cos(angle+.45),b.y()-10*math.sin(angle+.45))])
            s.addPolygon(tri,pen,QBrush(pen.color()))
            item=label(text,(a.x()+b.x())/2-35,(a.y()+b.y())/2-26,9,'#a44d17' if dashed else '#446277',100)
            item.setZValue(2)
        for oid,obj in state.objects.items():
            for field,val in obj['fields'].items():
                entries=val if isinstance(val,list) else [val]
                for j,v in enumerate(entries):
                    if isinstance(v,dict) and 'ref' in v: edge(oid,v['ref'],field+(f'[{j}]' if isinstance(val,list) else ''))
        if state.last_call: edge(state.last_call['from'],state.last_call['to'],state.last_call['method']+'()',True)
        for oid,obj in state.objects.items():
            x,y=pos[oid]
            active=state.event and oid in (state.event.get('id'), state.event.get('to'))
            s.addRect(x,y,width,height,QPen(QColor('#247a95' if active else '#cedae3'),2),QBrush(QColor('#eaf6fa' if active else '#ffffff')))
            label(f"{oid} : {obj['type']}",x+9,y+7,11,'#103751')
            label(spec.get('roles',{}).get(oid,'教材オブジェクト'),x+9,y+34,9,'#537786')
            lines=[]
            for f,v in obj['fields'].items():
                typ=spec.get('declared',{}).get(oid+'.'+f,'')
                def valstr(v):
                    if isinstance(v,dict): return '→ '+v['ref']
                    if isinstance(v,list): return '['+', '.join(valstr(x) for x in v)+']'
                    return 'null' if v is None else str(v)
                lines.append(f"{f}{': '+typ if typ else ''} = {valstr(v)}")
            label('\n'.join(lines) or '（観測するフィールドなし）',x+9,y+63,9,'#274455',width-18)
        if not state.objects: label('「次へ」でJava実行の記録を進めます。',35,45,12)
        s.setSceneRect(0,0,690,max(290,((len(all_ids)+1)//2)*235+35))

class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Java OOP Pattern Lab — KOSEN pilot 0.1')
        self.resize(1440,960); self.events=[]; self.worker=None; self.pairs={}
        central=QWidget(); self.setCentralWidget(central); layout=QVBoxLayout(central)
        self.heading=QLabel('Java OOP Pattern Lab'); self.heading.setStyleSheet('font-size:24px;font-weight:600;color:#143b52;padding:5px;')
        layout.addWidget(self.heading)
        bar=QHBoxLayout(); layout.addLayout(bar)
        self.lesson=QComboBox(); self.specs={k:json.loads((ROOT/'lessons'/f'{k}.json').read_text()) for k in LESSONS}
        for k in LESSONS: self.lesson.addItem(self.specs[k]['title'],k)
        self.variant=QComboBox(); self.variant.addItem('正常例','normal'); self.variant.addItem('比較例（課題の条件に違反）','broken')
        self.value=QSpinBox(); self.value.setRange(0,10000); self.value.setValue(100)
        self.run=QPushButton('Javaで再実行'); self.run.clicked.connect(self.run_live)
        self.load=QPushButton('記録を開く'); self.load.clicked.connect(self.open_trace)
        self.save=QPushButton('記録を保存'); self.save.clicked.connect(self.export)
        for w in (self.lesson,self.variant,QLabel('入力'),self.value,self.run,self.load,self.save):bar.addWidget(w)
        bar.addStretch()
        self.subtitle=QLabel(); self.subtitle.setWordWrap(True); layout.addWidget(self.subtitle)
        split=QSplitter(); layout.addWidget(split,1)
        left=QWidget(); lv=QVBoxLayout(left); lv.setContentsMargins(0,0,0,0)
        self.view=ObjectView(); lv.addWidget(self.view,1)
        self.event_label=QLabel(); self.event_label.setWordWrap(True); lv.addWidget(self.event_label)
        lv.addWidget(QLabel('実線: 保持する参照　　橙の破線: 現在の呼び出し　　Ctrl＋ホイール: 拡大縮小'))
        split.addWidget(left)
        self.tabs=QTabWidget(); split.addWidget(self.tabs); split.setSizes([770,620])
        self.lesson_text=QTextBrowser(); self.tabs.addTab(self.lesson_text,'教材と問い')
        self.source=QPlainTextEdit(); self.source.setReadOnly(True); self.source.setFont(QFont('monospace',10))
        self.tabs.addTab(self.source,'Javaソース')
        self.checks=QTableWidget(0,3); self.checks.setHorizontalHeaderLabels(['判定','項目','根拠・説明'])
        self.checks.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self.checks.setColumnWidth(0,65); self.checks.setColumnWidth(1,150)
        self.checks.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.checks.cellClicked.connect(self.goto_finding); self.tabs.addTab(self.checks,'全記録の検証')
        self.comparison=QTextBrowser(); self.tabs.addTab(self.comparison,'正常例との比較')
        controls=QHBoxLayout(); layout.addLayout(controls)
        for text,fn in [('最初',lambda:self.slider.setValue(0)),('戻る',lambda:self.move(-1)),('次へ',lambda:self.move(1)),('最後',lambda:self.slider.setValue(len(self.events)))]:
            b=QPushButton(text); b.clicked.connect(fn); controls.addWidget(b)
        self.play=QPushButton('自動再生'); self.play.clicked.connect(self.toggle_play); controls.addWidget(self.play)
        self.slider=QSlider(Qt.Orientation.Horizontal); self.slider.valueChanged.connect(self.show_step); controls.addWidget(self.slider,1)
        self.counter=QLabel(); controls.addWidget(self.counter)
        self.timeline=QTableWidget(0,4); self.timeline.setHorizontalHeaderLabels(['連番','種別','行','観測されたイベント'])
        self.timeline.setMaximumHeight(190); self.timeline.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch)
        self.timeline.setColumnWidth(0,65);self.timeline.setColumnWidth(1,110);self.timeline.setColumnWidth(2,55)
        self.timeline.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.timeline.cellClicked.connect(lambda row,col:self.slider.setValue(row+1));layout.addWidget(self.timeline)
        self.status=QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.timer=QTimer(self); self.timer.setInterval(650); self.timer.timeout.connect(lambda:self.move(1))
        self.lesson.currentIndexChanged.connect(self.load_lesson); self.variant.currentIndexChanged.connect(self.change_variant)
        self.load_lesson()
    def load_lesson(self):
        self.timer.stop(); self.play.setText('自動再生'); self.value.setValue(100)
        key=self.lesson.currentData()
        self.pairs={v:load_trace(ROOT/'traces'/f'{key}_{v}.jsonl') for v in ('normal','broken')}
        self.change_variant()
    def change_variant(self):
        variant=self.variant.currentData()
        if variant not in self.pairs:
            QMessageBox.information(self,'比較記録なし','このvariantの記録がありません。教材を選び直すか、Javaで再実行してください。')
            self.variant.blockSignals(True)
            self.variant.setCurrentIndex(0 if self.events[0]['variant']=='normal' else 1)
            self.variant.blockSignals(False)
            return
        self.activate(self.pairs[variant])
    def activate(self,events):
        self.timer.stop(); self.play.setText('自動再生'); self.events=events
        self.spec=self.specs[events[0]['lesson']];self.value.setValue(events[0]['input'])
        self.value.setEnabled(events[0]['lesson'] != 'state')
        self.value.setToolTip('State教材では入力値を使いません。' if events[0]['lesson']=='state' else '0〜10000。変更後はJavaで再実行してください。')
        self.subtitle.setText(self.spec['subtitle']+'　｜ '+('正常例' if events[0]['variant']=='normal' else self.spec['broken']))
        self.lesson_text.setHtml('<h2>'+html.escape(self.spec['title'])+'</h2><p>'+html.escape(self.spec['intro'])+'</p><h3>考えてみる</h3><p>'+html.escape(self.spec['question'])+'</p><h3>構造（教材作者の注釈）</h3><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in self.spec['structure'])+'</ul><h3>変更と比較</h3><p>'+html.escape(self.spec['change'])+'</p><p>対象は同梱教材の明示的な観測点です。任意のJavaプログラムを解析するデバッガではありません。</p>')
        self.source_matches=events[0].get('source_sha256')==source_hash()
        self.source.setPlainText(SOURCE.read_text(encoding='utf-8') if self.source_matches else 'ソースのハッシュが一致しません。行の強調表示は無効です。')
        self.findings=assess(events);self.checks.setRowCount(len(self.findings))
        for row,f in enumerate(self.findings):
            for col,text in enumerate([f.status,f.title,('観測整合性: ' if f.category=='integrity' else '教材契約: ')+f.detail+' / events '+str(f.evidence)]):
                item=QTableWidgetItem(text);item.setToolTip(text);self.checks.setItem(row,col,item)
            self.checks.item(row,0).setForeground(QColor(COLORS[f.status]))
        self.status.setText(f"全記録の結果: 観測整合性 {overall(self.findings,'integrity')} ／ 教材契約 {overall(self.findings)}　｜ Java {events[0].get('java','不明')}　｜ 入力 {events[0]['input']}　｜ ソース一致 {self.source_matches}")
        self.timeline.setRowCount(len(events))
        for row,e in enumerate(events):
            brief={k:v for k,v in e.items() if k not in ('seq','kind','line','observed')}
            for col,text in enumerate([str(e['seq']),e['kind'],str(e['line']),json.dumps(brief,ensure_ascii=False)]):
                item=QTableWidgetItem(text);item.setToolTip(text);self.timeline.setItem(row,col,item)
        self.all_ids=[e['id'] for e in events if e['kind']=='new']
        self.slider.setRange(0,len(events));self.slider.setValue(0);self.show_step(0);self.compare()
    def compare(self):
        if not all(v in self.pairs for v in ('normal','broken')):
            self.comparison.setPlainText('読み込んだ記録に対応する比較記録がありません。教材を選び直すかJavaで再実行してください。');return
        pieces=['<h2>同じ入力の正常例と比較例</h2><p>操作名を基準に比較します。イベント番号は両者で異なります。</p>']
        a,b=self.pairs['normal'],self.pairs['broken']
        if a[0]['input']!=b[0]['input']:
            self.comparison.setPlainText('入力が異なるため比較しません。');return
        for name in ['normal','broken']:
            ev=self.pairs[name]; f=assess(ev)
            pieces.append('<p><b>'+('正常例' if name=='normal' else '比較例')+'</b>: 契約 '+overall(f)+' / 整合性 '+overall(f,'integrity')+'</p>')
        ac={e['name']:e for e in a if e['kind']=='checkpoint'};bc={e['name']:e for e in b if e['kind']=='checkpoint'}
        for name in ac:
            if name not in bc:continue
            av=replay(a,ac[name]['seq']).objects;bv=replay(b,bc[name]['seq']).objects
            diffs=[oid for oid in sorted(set(av)|set(bv)) if av.get(oid)!=bv.get(oid)]
            pieces.append('<h3>'+html.escape(name)+'</h3><p>'+('差のあるオブジェクト: '+html.escape(', '.join(diffs)) if diffs else '観測されたオブジェクト状態は同じ。呼び出し先や契約も確認する。')+'</p>')
        self.comparison.setHtml(''.join(pieces))
    def show_step(self,n):
        state=replay(self.events,n);self.view.draw_state(state,self.spec,self.all_ids);self.counter.setText(f'{n} / {len(self.events)}')
        e=state.event
        self.event_label.setText('開始前' if not e else f"#{e['seq']}  {e['kind']}  ｜ Javaの観測点: {e['line']}行  ｜ "+self.explain(e))
        if n: self.timeline.selectRow(n-1)
        if self.source_matches and e and e['line']>0:
            block=self.source.document().findBlockByLineNumber(e['line']-1)
            if block.isValid():
                cursor=QTextCursor(block);self.source.setTextCursor(cursor);self.source.centerCursor()
                selection=QTextEdit.ExtraSelection();selection.cursor=cursor;selection.format.setBackground(QColor('#fff0b5'))
                selection.format.setProperty(QTextCharFormat.Property.FullWidthSelection,True);self.source.setExtraSelections([selection])
        else: self.source.setExtraSelections([])
        if n>=len(self.events): self.timer.stop();self.play.setText('自動再生')
    def explain(self,e):
        k=e['kind']
        if k=='new': return f"{e['id']} は {e['type']} のインスタンス。"
        if k=='set': return f"{e['id']}.{e['field']} の観測値が {e['value']} になりました。"
        if k=='call': return f"{e['from']} から {e['to']} の {e['method']} を呼び出します。"
        if k=='checkpoint':return 'Javaオブジェクトを直接読み取り、記録からの再構成と照合する地点です。'
        if k=='return':return f"{e['from']} から {e['value']} を返しました。"
        if k=='cycle_begin':return '現在の登録先を基準に、通知サイクルを開始します。'
        if k=='result':return str(e['value'])
        return '実行記録の境界イベントです。'
    def move(self,delta): self.slider.setValue(self.slider.value()+delta)
    def toggle_play(self):
        if self.timer.isActive():self.timer.stop();self.play.setText('自動再生')
        else:
            if self.slider.value()==len(self.events):self.slider.setValue(0)
            self.timer.start();self.play.setText('停止')
    def goto_finding(self,row,col):
        ids=self.findings[row].evidence
        if ids:self.slider.setValue(ids[-1])
    def run_live(self):
        if self.worker and self.worker.isRunning():return
        self.run.setEnabled(False);self.lesson.setEnabled(False);self.load.setEnabled(False)
        self.worker=RunWorker(self.lesson.currentData(),self.value.value(),self)
        self.worker.done.connect(self.live_done);self.worker.failed.connect(lambda msg:QMessageBox.warning(self,'Java実行',msg))
        self.worker.finished.connect(self.live_finished);self.worker.start()
    def live_done(self,pairs): self.pairs=pairs;self.change_variant()
    def live_finished(self):self.run.setEnabled(True);self.lesson.setEnabled(True);self.load.setEnabled(True)
    def open_trace(self):
        path,_=QFileDialog.getOpenFileName(self,'JSON Lines記録を開く','','Trace (*.jsonl)')
        if not path:return
        try:
            ev=load_trace(path);assess(ev)
            self.lesson.blockSignals(True);self.lesson.setCurrentIndex(LESSONS.index(ev[0]['lesson']));self.lesson.blockSignals(False)
            self.variant.blockSignals(True);self.variant.setCurrentIndex(0 if ev[0]['variant']=='normal' else 1);self.variant.blockSignals(False)
            self.pairs={ev[0]['variant']:ev};self.activate(ev)
        except Exception as ex:QMessageBox.warning(self,'記録を読み込めません',str(ex))
    def export(self):
        path,_=QFileDialog.getSaveFileName(self,'記録の保存',f"{self.events[0]['lesson']}.jsonl",'Trace (*.jsonl)')
        if path:
            try:save_trace(self.events,Path(path))
            except OSError as ex:QMessageBox.warning(self,'保存に失敗',str(ex))
    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self,'Java実行中','実行が終わってから閉じてください（最大約50秒）。');event.ignore()
        else:event.accept()

def launch(screenshot=None):
    app=QApplication(sys.argv[:1]);app.setStyle('Fusion')
    app.setFont(QFont('sans-serif',10))
    win=Window();win.show()
    if screenshot:
        def capture():
            win.lesson.setCurrentIndex(3);win.variant.setCurrentIndex(1);win.slider.setValue(len(win.events));win.tabs.setCurrentIndex(2)
            app.processEvents();win.grab().save(str(screenshot));app.quit()
        QTimer.singleShot(500,capture)
    sys.exit(app.exec())
