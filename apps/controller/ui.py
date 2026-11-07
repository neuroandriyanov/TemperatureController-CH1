"""Russian bench UI: live readings, device-owned configuration and calibration."""
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import time
from PySide6.QtCore import Qt,QTimer,QUrl,QLocale
from PySide6.QtGui import QDesktopServices,QKeySequence,QShortcut
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QPushButton,QComboBox,
    QSpinBox,QDoubleSpinBox,QVBoxLayout,QHBoxLayout,QGridLayout,QFormLayout,QScrollArea,QTabWidget,
    QCheckBox,QPlainTextEdit,QFileDialog,QMessageBox,QProgressBar)
from model import (HERE,REGISTERS,MODE_NAMES,engineering,wire_value,validate_config,set_draft,
    current_noise,current_gain,loop_point,burst_period_ms,set_burst_period)
from protocol import ports
from worker import Worker
from chart import TemperatureChart

STYLE='''
QMainWindow,QDialog { background:#0c121b; color:#e5edf7; }
QWidget { color:#dce5f1; font-family:"Segoe UI"; font-size:13px; }
QFrame#card { background:#141e2b; border:1px solid #263448; border-radius:12px; }
QLabel#title { font-size:25px; font-weight:650; color:#f4f8ff; }
QLabel#section { font-size:15px; font-weight:650; color:#eef5ff; }
QLabel#muted { color:#94a8c1; }
QLabel#metric { font-size:33px; font-weight:600; color:#55d9c6; }
QLabel#badge { color:#64e4d8; background:#17383d; border-radius:7px; padding:8px 14px; }
QLabel#notice { color:#efbc79; background:#302c26; border:1px solid #65533b; border-radius:7px; padding:9px; }
QPushButton { background:#223147; border:1px solid #344862; padding:8px 13px; border-radius:7px; }
QPushButton:hover { background:#2d425e; border-color:#5d7698; }
QPushButton:pressed { background:#172638; }
QPushButton:disabled { color:#63758b; background:#17202d; border-color:#223044; }
QPushButton#primary { background:#29b8a8; color:#071e24; font-weight:700; border:none; padding:11px; }
QPushButton#primary:hover { background:#54d3c1; }
QPushButton#primary:disabled { background:#284a50; color:#779b9d; }
QPushButton#stop { background:#482d34; color:#ffb6ad; border:1px solid #9a5c5e; font-weight:700; padding:11px; }
QPushButton#stop:hover { background:#673943; }
QComboBox,QSpinBox,QDoubleSpinBox { background:#0e1723; border:1px solid #34455e; border-radius:6px; padding:6px 8px; min-height:21px; }
QComboBox:disabled,QSpinBox:disabled,QDoubleSpinBox:disabled { color:#677990; background:#111b28; }
QComboBox QAbstractItemView { background:#172538; color:#e5edf7; selection-background-color:#2b5665; }
QTabWidget::pane { border:none; }
QTabBar::tab { background:#111c2a; color:#99aec8; padding:11px 20px; border-bottom:2px solid #263448; margin-right:4px; }
QTabBar::tab:selected { background:#1a2b3d; color:#63dfce; border-bottom:2px solid #42c7b5; }
QScrollArea { border:none; background:transparent; }
QWidget#monitorPage { background:#0c121b; }
QScrollBar:vertical { background:#142032; width:10px; }
QScrollBar::handle:vertical { background:#3d526e; min-height:20px; border-radius:5px; }
QPlainTextEdit { background:#0b1420; border:1px solid #263448; border-radius:7px; padding:8px; }
QCheckBox { spacing:8px; }
QCheckBox::indicator { width:16px; height:16px; border:1px solid #4d647f; background:#101b29; border-radius:3px; }
QCheckBox::indicator:checked { background:#30bca9; border-color:#6edbcc; }
QProgressBar { background:#0e1723; border:1px solid #2b4057; border-radius:5px; text-align:center; min-height:19px; }
QProgressBar::chunk { background:#289d91; border-radius:4px; }
QStatusBar { background:#101b29; color:#a6b9ce; }
QToolTip { background:#24384c; color:#edf4fc; border:1px solid #52718b; padding:6px; }
'''

def label(text,kind=None,wrap=False):
    w=QLabel(text)
    if kind:w.setObjectName(kind)
    w.setWordWrap(wrap)
    return w

def card(title=None):
    frame=QFrame();frame.setObjectName('card');layout=QVBoxLayout(frame)
    layout.setContentsMargins(16,14,16,14);layout.setSpacing(10)
    if title:layout.addWidget(label(title,'section'))
    return frame,layout

def scroll(content):
    area=QScrollArea();area.setWidgetResizable(True);area.setWidget(content);return area

class Field(QDoubleSpinBox):
    def wheelEvent(self,event):
        if self.hasFocus():super().wheelEvent(event)
        else:event.ignore()

class MainWindow(QMainWindow):
    def __init__(self,args):
        super().__init__();self.args=args;self.worker=Worker();self.worker.event.connect(self.on_event)
        self.worker.finished.connect(self.worker_finished)
        self.online=False;self.busy=False;self.loading=False;self.closing=False;self.can_close=False
        self.baseline=[];self.draft=[];self.telemetry=None;self.fields={};self.cal_checks={}
        self.editors=[];self.device_buttons=[];self.last_alarm=None;self.last_received=0;self.session_log=None
        self.setWindowTitle('Стенд · Терморегулятор CH1');self.setStyleSheet(STYLE)
        screen=QApplication.primaryScreen().availableGeometry()
        self.resize(min(1440,screen.width()-40),min(960,screen.height()-60));self.setMinimumSize(1100,740)
        body=QWidget();self.setCentralWidget(body);layout=QVBoxLayout(body)
        layout.setContentsMargins(20,16,20,10);layout.setSpacing(10)
        row=QHBoxLayout();titles=QVBoxLayout();titles.setSpacing(3)
        titles.addWidget(label('Терморегулятор CH1','title'))
        titles.addWidget(label('Стенд управления  /  температура · мощность · калибровка','muted'))
        row.addLayout(titles);row.addStretch();self.badge=label('НЕТ ПОДКЛЮЧЕНИЯ','badge');row.addWidget(self.badge)
        layout.addLayout(row)
        panel,col=card();row=QHBoxLayout();row.addWidget(label('СВЯЗЬ','section'))
        self.port=QComboBox();self.port.setMinimumWidth(260);self.port.setAccessibleName('Порт RS-485');row.addWidget(self.port,1)
        self.refresh_button=QPushButton('Обновить');self.refresh_button.clicked.connect(self.refresh_ports);row.addWidget(self.refresh_button)
        row.addWidget(label('Адрес','muted'));self.address=QSpinBox();self.address.setRange(1,247);self.address.setValue(args.address)
        self.address.setAccessibleName('Адрес прибора');row.addWidget(self.address)
        self.scan_button=QPushButton('Найти адрес');self.scan_button.clicked.connect(self.scan_address);row.addWidget(self.scan_button)
        self.connect_button=QPushButton('Подключить');self.connect_button.setObjectName('primary');self.connect_button.clicked.connect(self.connect_clicked);row.addWidget(self.connect_button)
        col.addLayout(row);self.connection_note=label('38400 · 8E1  |  RS-485 — управление  ·  UART — прошивка  |  адрес задаётся переключателями на приборе','muted')
        col.addWidget(self.connection_note);layout.addWidget(panel)
        metrics=QHBoxLayout();self.metric_values={}
        for key,title,unit in [('temperature','ТЕМПЕРАТУРА','°C'),('setpoint','УСТАВКА','°C'),('output','МОЩНОСТЬ','%'),('current','ТОК НАГРЕВАТЕЛЯ','А')]:
            box,vl=card();vl.setSpacing(4);vl.addWidget(label(title,'muted'))
            value=label('—','metric');vl.addWidget(value);hint=label(unit,'muted');vl.addWidget(hint)
            self.metric_values[key]=(value,hint);metrics.addWidget(box,1)
        layout.addLayout(metrics)
        self.notice=label('Подключитесь к прибору — программа считает его настройки.','notice',True);layout.addWidget(self.notice)
        self.tabs=QTabWidget();self.tabs.addTab(self.monitor_page(),'Наблюдение');self.tabs.addTab(self.sensors_page(),'Датчики и калибровка')
        self.tabs.addTab(self.control_page(),'PID и защиты');self.tabs.addTab(self.relay_page(),'Реле и прогрев');self.tabs.addTab(self.diagnostics_page(),'Диагностика')
        layout.addWidget(self.tabs,1)
        footer=QHBoxLayout();self.config_status=label('Настройки ещё не считаны','muted');footer.addWidget(self.config_status,1)
        self.read_button=self.button('Считать из прибора',lambda:self.submit('read'))
        self.save_button=self.button('Сохранить в прибор',self.save_clicked,'primary')
        footer.addWidget(self.read_button);footer.addWidget(self.save_button)
        self.global_stop=self.button('STOP · F8',lambda:self.submit('stop'),'stop');footer.addWidget(self.global_stop)
        help_button=QPushButton('Инструкция');help_button.clicked.connect(lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(HERE/'ИНСТРУКЦИЯ.txt'))));footer.addWidget(help_button)
        layout.addLayout(footer)
        self.statusBar().showMessage('Готово к подключению')
        self.refresh_ports();self.worker.start();self.update_enabled()
        self.timer=QTimer(self);self.timer.timeout.connect(self.check_freshness);self.timer.start(250)
        QShortcut(QKeySequence('F8'),self,activated=lambda:self.submit('stop') if self.online else None)
        if args.connect:QTimer.singleShot(250,self.connect_clicked)

    def button(self,text,callback,kind=None):
        b=QPushButton(text);b.clicked.connect(callback)
        if kind:b.setObjectName(kind)
        self.device_buttons.append(b);return b

    def editor(self,address,options=None):
        meta=REGISTERS[address]
        if options:
            widget=QComboBox()
            for text,value in options:widget.addItem(text,value)
            widget.currentIndexChanged.connect(lambda _,a=address,w=widget:self.field_changed(a,w.currentData()))
        else:
            widget=Field();widget.setLocale(QLocale('ru_RU'));widget.setKeyboardTracking(False)
            divisor=meta['divisor'];widget.setDecimals(round(math.log10(divisor)) if divisor>1 else 0)
            widget.setRange(meta['minimum']/divisor,meta['maximum']/divisor)
            widget.setSingleStep(1/divisor if divisor<=10 else (0.1 if divisor>=100 else 1))
            suffix={'ms':' мс','°C':' °C','%':' %','mA':' мА','µA':' мкА','mV':' мВ','°C/min':' °C/мин',
                'µA/count':' мкА/count','ADC count':' count','s':' с'}.get(meta['unit'],'')
            if address==13:
                widget.setRange(2,300);widget.setDecimals(3);widget.setSingleStep(1);widget.setSuffix(' с')
                widget.valueChanged.connect(self.period_changed)
            else:
                widget.setSuffix(suffix);widget.valueChanged.connect(lambda v,a=address:self.field_changed(a,wire_value(a,v)))
        widget.setMinimumWidth(150);widget.setAccessibleName(meta['description'])
        widget.setToolTip(meta['description']);widget.setObjectName('field_'+meta['name'])
        if address==13:
            widget.setAccessibleName('Период ШИМ в секундах')
            widget.setToolTip('2–300 секунд в прошивке 2.5; прежние версии — 0,2–10 секунд')
        self.fields.setdefault(address,[]).append(widget);self.editors.append(widget);return widget

    def form_card(self,title,rows):
        frame,layout=card(title);form=QFormLayout();form.setSpacing(9)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        for text,address,options in rows:
            name=label(text,wrap=True);name.setMinimumWidth(140);form.addRow(name,self.editor(address,options))
        layout.addLayout(form);return frame,layout

    def monitor_page(self):
        page=QWidget();row=QHBoxLayout(page);row.setContentsMargins(0,10,0,0);row.setSpacing(12)
        page.setObjectName('monitorPage')
        frame,col=card();toolbar=QHBoxLayout();toolbar.addWidget(label('Температура во времени','section'));toolbar.addStretch()
        self.window_combo=QComboBox()
        for text,seconds in [('2 мин',120),('10 мин',600),('30 мин',1800),('1 час',3600),('6 часов',21600)]:self.window_combo.addItem(text,seconds)
        self.window_combo.setCurrentIndex(1);toolbar.addWidget(self.window_combo)
        self.pause=QPushButton('Пауза графика');self.pause.setCheckable(True);toolbar.addWidget(self.pause);col.addLayout(toolbar)
        legends=QHBoxLayout()
        for text,color in [('━ Температура','#4ad3c0'),('┄ Уставка','#e9b567'),('┄ Рабочая уставка','#9d9ae5')]:
            x=label(text);x.setStyleSheet(f'color:{color}');legends.addWidget(x)
        legends.addStretch();col.addLayout(legends)
        self.chart=TemperatureChart();col.addWidget(self.chart,1)
        self.window_combo.currentIndexChanged.connect(lambda _:self.chart.set_window(self.window_combo.currentData()))
        self.pause.toggled.connect(lambda value:self.chart.set_follow(not value))
        chart_footer=QHBoxLayout();chart_footer.addWidget(label('Колесо — масштаб · курсор — значения · разрывы означают отсутствие данных','muted',True),1)
        export=QPushButton('Экспорт CSV');export.clicked.connect(self.export_chart);chart_footer.addWidget(export)
        shot=QPushButton('Снимок');shot.clicked.connect(self.screenshot);chart_footer.addWidget(shot);col.addLayout(chart_footer)
        row.addWidget(frame,1)
        right,vl=self.form_card('Управление',[
            ('Уставка',0,None),('Допуск ниже уставки',18,None),('Допуск выше уставки',19,None),
            ('Выбор режима',41,[('STOP · выключено',0),('AUTO · PID',1),('MANUAL · мощность',2)]),('Ручная мощность',42,None)])
        right.setMinimumWidth(360);right.setMaximumWidth(385)
        self.power_bar=QProgressBar();self.power_bar.setRange(0,10000);self.power_bar.setValue(0);self.power_bar.setFormat('Выход выключен');vl.addWidget(self.power_bar)
        self.mode_text=label('Состояние прибора: —','muted',True);vl.addWidget(self.mode_text)
        self.resume_text=label('После питания: —','muted',True);vl.addWidget(self.resume_text)
        controls=QHBoxLayout();self.start_button=self.button('ВКЛЮЧИТЬ',self.start_clicked,'primary')
        self.stop_button=self.button('STOP · F8',lambda:self.submit('stop'),'stop');controls.addWidget(self.start_button);controls.addWidget(self.stop_button);vl.addLayout(controls)
        self.apply_button=self.button('Применить и запомнить',self.apply_clicked);vl.addWidget(self.apply_button)
        vl.addWidget(label('Уставка и допуски сохраняются в приборе (v2.5+). При записи — короткая пауза выхода.','muted',True))
        self.relay_text=label('Реле K1: —','muted',True);vl.addWidget(self.relay_text);vl.addStretch()
        row.addWidget(scroll(right));row.setStretch(1,0)
        row.itemAt(1).widget().setMinimumWidth(380);row.itemAt(1).widget().setMaximumWidth(405)
        return scroll(page)

    def calibration_check(self,bit,text):
        cb=QCheckBox(text);cb.setToolTip('Подтверждайте после проверки по эталону. Это разрешает использование канала для управления.')
        cb.toggled.connect(lambda checked,b=bit:self.calibration_changed(b,checked))
        self.cal_checks[bit]=cb;self.editors.append(cb);return cb

    def sensors_page(self):
        content=QWidget();grid=QGridLayout(content);grid.setContentsMargins(0,10,0,0);grid.setSpacing(12)
        tc,vl=self.form_card('Термопара и холодный спай',[
            ('Тип термопары',1,[(name,i) for i,name in enumerate(['B','E','J','K','N','R','S','T'])]),
            ('Компенсация',2,[('Внутренняя MAX31856',0),('Внешняя PT100 · 4–20 мА',1)]),
            ('Сетевой фильтр',3,[('50 Гц',0),('60 Гц',1)]),
            ('Усреднение',4,[(str(1<<i)+' измерений',i) for i in range(5)]),
            ('Тайм-аут термопары',5,None),('Поправка внутреннего CJ',6,None),('Поправка термопары',7,None)])
        self.tc_live=label('Холодный спай: —','muted',True);vl.addWidget(self.tc_live);vl.addStretch();grid.addWidget(tc,0,0)
        current,vl=self.form_card('Ток · ACS712 30 А',[
            ('Коэффициент тока',20,None),('Поправка тока',21,None),('RMS шума при нулевом токе',22,None)])
        self.current_live=label('ADC: —','muted',True);vl.addWidget(self.current_live)
        vl.addWidget(self.button('Взять нулевой шум · ток должен быть 0',lambda:self.calibrate('noise')))
        refs=QHBoxLayout();refs.addWidget(label('Эталонный ток'));self.reference_current=Field();self.reference_current.setRange(0.001,30);self.reference_current.setDecimals(3);self.reference_current.setValue(1);self.reference_current.setSuffix(' A');refs.addWidget(self.reference_current);vl.addLayout(refs)
        vl.addWidget(self.button('Рассчитать коэффициент по эталону',lambda:self.calibrate('gain')))
        vl.addWidget(self.calibration_check(0,'Канал тока проверен по эталону'))
        vl.addWidget(label('Кнопки меняют поля. После проверки сохраните параметры в прибор. Автоматического включения нагрузки нет.','muted',True));vl.addStretch();grid.addWidget(current,0,1)
        ext,vl=self.form_card('PT100 · диапазон и поправки',[
            ('Температура при 4 мА',31,None),('Температура при 20 мА',32,None),
            ('Поправка тока петли',35,None),('Поправка температуры PT100',36,None),
            ('Тайм-аут внешнего датчика',37,None),('Минимальный ток петли',38,None),('Максимальный ток петли',39,None)])
        vl.addWidget(label('Введите диапазон, настроенный в преобразователе PT100. Для внешней компенсации датчик должен измерять температуру холодного спая.','muted',True));grid.addWidget(ext,1,0)
        points,vl=self.form_card('Калибровка входа 4–20 мА',[
            ('Напряжение при эталонных 4 мА',33,None),('Напряжение при эталонных 20 мА',34,None)])
        self.ext_live=label('Ток петли: — · напряжение: —','muted',True);vl.addWidget(self.ext_live)
        vl.addWidget(self.button('Запомнить точку 4 мА',lambda:self.calibrate('4ma')))
        vl.addWidget(self.button('Запомнить точку 20 мА',lambda:self.calibrate('20ma')))
        vl.addWidget(self.calibration_check(1,'PT100 / вход 4–20 мА проверен по эталону'))
        vl.addWidget(label('Перед каждой точкой подайте соответствующий эталонный ток. Проверьте промежуточные точки. Температура CJ выше 125 °C не допускается MAX31856.','muted',True));vl.addStretch();grid.addWidget(points,1,1)
        grid.setColumnStretch(0,1);grid.setColumnStretch(1,1);return scroll(content)

    def control_page(self):
        content=QWidget();grid=QGridLayout(content);grid.setContentsMargins(0,10,0,0);grid.setSpacing(12)
        pid,vl=self.form_card('PID и динамика',[
            ('Kp · % / °C',8,None),('Ki · % / (°C·с)',9,None),('Kd · %·с / °C',10,None),
            ('Фильтр производной',11,None),('Период расчёта PID',12,None),('Период ШИМ · 2–300 с',13,None),
            ('Ограничение мощности',14,None),('Скорость уставки · 0 = без ограничения',15,None)])
        vl.addWidget(label('Пакетное управление симистором: PID задаёт долю включённого времени в каждом периоде. Выберите коэффициенты и период под инерцию вашей нагрузки.','muted',True));vl.addStretch();grid.addWidget(pid,0,0,2,1)
        temp,vl=self.form_card('Температура и связь',[
            ('Нижний технологический предел',16,None),('Верхний технологический предел',17,None),
            ('Тайм-аут связи · 0 = отключён',29,None),('Тайм-аут измерения тока',30,None)])
        self.autonomous=QCheckBox('Автономно · работать без программы ПК')
        self.autonomous.toggled.connect(lambda checked:self.field_changed(29,0 if checked else 5000))
        self.editors.append(self.autonomous);vl.addWidget(self.autonomous)
        vl.addWidget(label('Сохраните выбор в прибор. Автономно: тайм-аут связи 0, закрытие программы оставляет регулятор в работе. При включённом контроле связи программа отправляет STOP при закрытии. После питания восстанавливается последний режим.','muted',True));grid.addWidget(temp,0,1)
        protection,vl=self.form_card('Контроль тока',[
            ('Порог перегрузки',23,None),('Задержка перегрузки',24,None),('Допустимый ток при OFF',25,None),
            ('Задержка ошибки при OFF',26,None),('Минимальный ток при ON · 0 = отключён',27,None),('Время ON без достаточного тока',28,None)])
        vl.addWidget(label('Время накапливается по достоверным ON-окнам разных пакетов; OFF не учитывается. Нормальный ON-ток сбрасывает счётчик. Очень короткие импульсы без полного окна RMS не диагностируются. Порог 0 отключает проверку.','muted',True));grid.addWidget(protection,1,1)
        grid.setColumnStretch(0,1);grid.setColumnStretch(1,1);return scroll(content)

    def relay_page(self):
        content=QWidget();grid=QVBoxLayout(content);grid.setContentsMargins(0,10,0,0)
        relay,vl=self.form_card('Реле K1 · назначение и прогрев',[
            ('Функция реле',43,[('Выключено',0),('Температура в допуске',1),('В допуске после прогрева',2),
                ('Любая ошибка',3),('Превышение тока',4),('Неисправность нагревателя · малый ток',5),('Ошибка прибора / датчиков',6)]),
            ('Время прогрева',44,None)])
        self.soak_text=label('Прогрев: —','muted',True);vl.addWidget(self.soak_text)
        vl.addWidget(label('Отсчёт с первого попадания в допуск. Краткий выход из допуска не сбрасывает время, но реле отключается. STOP, авария или изменение уставки сбрасывают прогрев. После питания выдержка начинается заново.','muted',True))
        vl.addWidget(label('Релейные аварии учитывают текущие и зафиксированные ошибки и работают в STOP. Назначение реле и время сохраняются кнопкой «Сохранить в прибор».','muted',True))
        grid.addWidget(relay);grid.addStretch();return scroll(content)

    def diagnostics_page(self):
        content=QWidget();grid=QGridLayout(content);grid.setContentsMargins(0,10,0,0);grid.setSpacing(12)
        faults,vl=card('Ошибки и условия запуска');self.fault_text=QPlainTextEdit();self.fault_text.setReadOnly(True);self.fault_text.setMinimumHeight(150);vl.addWidget(self.fault_text)
        self.clear_button=self.button('Сбросить зафиксированные ошибки',lambda:self.submit('clear'));vl.addWidget(self.clear_button);grid.addWidget(faults,0,0)
        raw,vl=card('Измерения и состояние прибора');self.raw_text=QPlainTextEdit();self.raw_text.setReadOnly(True);self.raw_text.setMinimumHeight(150);vl.addWidget(self.raw_text);grid.addWidget(raw,0,1)
        log,vl=card('Журнал');self.log_text=QPlainTextEdit();self.log_text.setReadOnly(True);self.log_text.setMaximumBlockCount(1000);vl.addWidget(self.log_text)
        self.log_path=label('Журнал измерений создаётся при подключении','muted',True);vl.addWidget(self.log_path);grid.addWidget(log,1,0,1,2)
        grid.setRowStretch(1,1);grid.setColumnStretch(0,1);grid.setColumnStretch(1,1);return content

    def refresh_ports(self):
        selected=self.port.currentData() or self.args.port;self.port.clear()
        for item in sorted(ports(),key=lambda x:x['port']):
            self.port.addItem(f"{item['port']}  ·  {item['description']}",item['port'])
        index=self.port.findData(selected)
        if index>=0:self.port.setCurrentIndex(index)

    def connect_clicked(self):
        if self.online:self.submit('disconnect');return
        if not self.port.currentData():self.show_error('Выберите доступный COM-порт');return
        self.submit('connect',port=self.port.currentData(),address=self.address.value())

    def scan_address(self):
        if self.busy=='scan':self.worker.submit('cancel_scan');return
        if self.port.currentData():self.submit('scan',port=self.port.currentData())

    def field_changed(self,address,raw):
        if self.loading or address>=len(self.draft) or raw is None:return
        self.draft=set_draft(self.draft,address,int(raw));self.sync_fields();self.update_enabled()

    def period_changed(self,seconds):
        if self.loading or not self.draft:return
        self.draft=set_burst_period(self.draft,seconds);self.sync_fields();self.update_enabled()

    def calibration_changed(self,bit,checked):
        if self.loading or not self.draft:return
        self.draft[40]=(self.draft[40]|(1<<bit)) if checked else (self.draft[40]&~(1<<bit))
        self.update_enabled()

    def sync_fields(self):
        self.loading=True
        try:
            for address,widgets in self.fields.items():
                raw=self.draft[address] if address<len(self.draft) else REGISTERS[address]['default']&65535
                for widget in widgets:
                    widget.blockSignals(True)
                    if isinstance(widget,QComboBox):widget.setCurrentIndex(widget.findData(raw))
                    elif address==13:
                        widget.setRange(2 if len(self.draft)>=47 else .2,300 if len(self.draft)>=47 else 10)
                        widget.setValue(burst_period_ms(self.draft)/1000 if self.draft else 2)
                    else:
                        if address in (18,19):widget.setMaximum(1800 if len(self.draft)>=47 else 500)
                        widget.setValue(engineering(address,raw))
                    widget.blockSignals(False)
            self.autonomous.blockSignals(True);self.autonomous.setChecked(bool(self.draft and self.draft[29]==0));self.autonomous.blockSignals(False)
            for bit,check in self.cal_checks.items():
                check.blockSignals(True);check.setChecked(bool(self.draft and self.draft[40]&(1<<bit)));check.blockSignals(False)
        finally:self.loading=False

    def submit(self,action,**kwargs):
        if self.closing and action!='shutdown':return
        self.busy=action;self.update_enabled();self.worker.submit(action,**kwargs)
        names={'connect':'Подключение и чтение настроек…','read':'Чтение из прибора…','save':'STOP → запись → сохранение EEPROM…',
               'start':'Проверка настроек и запуск…','stop':'Отправка STOP…','clear':'Сброс ошибок…','scan':'Поиск адресов…','disconnect':'STOP и отключение…','apply':'Применение рабочих значений…'}
        self.statusBar().showMessage(names.get(action,action))

    def values(self):validate_config(self.draft);return self.draft.copy()

    def save_clicked(self):
        try:self.submit('save',values=self.values(),baseline=self.baseline.copy())
        except Exception as e:self.show_error(str(e))

    def apply_clicked(self):
        try:self.submit('apply',values=self.values())
        except Exception as e:self.show_error(str(e))

    def start_clicked(self):
        try:
            values=self.values();mode=values[41] if len(values)>41 else 1;manual=values[42] if len(values)>42 else 0
            self.submit('start',values=values,baseline=self.baseline.copy(),mode=mode,manual=manual)
        except Exception as e:self.show_error(str(e))

    def calibrate(self,kind):
        try:
            if not self.telemetry or time.time()-self.last_received>1.5:raise ValueError('Нужны свежие показания прибора')
            if self.telemetry['mode']!=0:raise ValueError('Калибровка выполняется в STOP')
            if kind=='noise':address,raw=22,current_noise(self.telemetry)
            elif kind=='gain':address,raw=20,current_gain(self.telemetry,self.draft,self.reference_current.value())
            else:address,raw=(33 if kind=='4ma' else 34),wire_value(33 if kind=='4ma' else 34,loop_point(self.telemetry))
            self.field_changed(address,raw);self.log('Калибровочное значение рассчитано; проверьте его и сохраните в прибор.')
        except Exception as e:self.show_error(str(e))

    def on_event(self,event,data):
        if event=='busy':self.busy=data
        elif event=='connected':
            self.online=True;self.telemetry=None;self.last_alarm=None;self.last_received=0
            self.badge.setText(f"{data['port']}  ·  АДРЕС {data['address']}  ·  v{data['firmware']>>8}.{data['firmware']&255}")
            self.session_log=data['log'];self.log_path.setText('CSV: '+data['log']);self.log('Связь установлена. Настройки считаны из терморегулятора.')
        elif event=='disconnected':
            if self.telemetry:self.chart.break_line(time.time(),self.telemetry['setpoint'])
            self.online=False;self.badge.setText('НЕТ ПОДКЛЮЧЕНИЯ');self.notice.setText('Связь отключена. Показания недоступны; перед запуском подключитесь заново.')
            self.clear_metrics();self.log('Связь отключена'+(': STOP не подтверждён' if data else ''))
        elif event=='config':
            reason=data['reason'];values=data['values']
            if len(values)>45 and self.baseline and values[:45]+values[46:]==self.baseline[:45]+self.baseline[46:]:
                self.baseline[45]=values[45];self.draft[45]=values[45]
            if reason in ('connect','read','save','start') or not self.draft:
                self.baseline=values.copy();self.draft=values.copy()
            elif reason=='apply':
                self.baseline=values.copy()
            elif self.draft==self.baseline:
                self.baseline=values.copy();self.draft=values.copy()
            else:
                self.log('Настройки в приборе изменились; локальные правки сохранены. Перед записью перечитайте прибор.')
            self.sync_fields()
            if reason=='save':self.log('EEPROM: сохранение подтверждено прибором и повторным чтением.')
        elif event=='telemetry':
            self.telemetry=data;self.last_received=data['received'];self.display_telemetry(data)
        elif event=='warning':self.log(data);self.statusBar().showMessage(data)
        elif event=='recovered':self.log('Связь восстановлена');self.statusBar().showMessage('Связь восстановлена',5000)
        elif event=='error':
            self.busy=False;self.show_error(data['text'])
        elif event=='done':
            self.busy=False;self.statusBar().showMessage({'save':'Параметры сохранены в EEPROM','stop':'STOP подтверждён','read':'Настройки считаны из прибора','start':'Запуск подтверждён','apply':('Уставка и допуски сохранены в приборе' if len(self.baseline)>=47 else 'Рабочие значения применены; EEPROM сохраняется отдельной кнопкой')}.get(data,'Готово'))
        elif event=='scan_progress':self.statusBar().showMessage(f"Поиск: {data['address']}/247 · найдено: {', '.join(map(str,data['found'])) or '—'}")
        elif event=='scan_result':
            if data:self.address.setValue(data[0]);self.log('Найдены адреса: '+', '.join(map(str,data)))
            else:self.log('Прибор не найден. Проверьте A/B, BOOT0=0 и hex-переключатели (не 00 и не F8…FF).')
        self.update_enabled()

    def display_telemetry(self,t):
        for key,(value,hint) in self.metric_values.items():
            raw=t[key];value.setText('—' if raw is None else (f'{raw:.3f}' if key=='current' else f'{raw:.1f}'))
        self.metric_values['temperature'][1].setText('°C · достоверное измерение' if t['tc_valid'] else '°C · нет достоверного измерения')
        self.metric_values['current'][1].setText('A · AC RMS, 200 мс'+(' · нужна калибровка' if not t['calibration']&1 else ''))
        self.metric_values['output'][1].setText('% · '+MODE_NAMES.get(t['mode'],'?'))
        self.metric_values['setpoint'][1].setText('°C · значение в приборе')
        self.mode_text.setText('Состояние прибора: '+MODE_NAMES.get(t['mode'],'?'))
        self.power_bar.setValue(round(t['output']*100));self.power_bar.setFormat(f"{t['output']:.1f} % · выход {'ON' if t['gate'] else 'OFF'}")
        self.relay_text.setText('Реле K1: '+('включено' if t['relay'] else 'выключено'))
        self.resume_text.setText('После питания: '+(MODE_NAMES.get(t['powerup_mode'],'—') if t['powerup_mode'] is not None else 'STOP · прошивка до 2.2'))
        self.soak_text.setText('Прогрев: '+({0:'остановлен',1:'ожидание первого попадания в допуск',2:f"осталось {t['soak_remaining']} с",3:'завершён'}.get(t['soak_state'],'требуется прошивка 2.2')))
        summary=list(dict.fromkeys(t['max_errors']+t['errors']+t['latched_errors']))
        self.notice.setText(' · '.join(summary[:3]) if summary else 'Измерения достоверны. '+('Нагрев остановлен.' if not t['mode'] else 'Регулирование работает.'))
        alarm=(t['active'],t['latched'],t['max_status'])
        if alarm!=self.last_alarm:
            self.log('Диагностика: '+('; '.join(summary) if summary else 'ошибок нет'));self.last_alarm=alarm
        cj='—' if t['cold_junction'] is None else f"{t['cold_junction']:.2f} °C"
        self.tc_live.setText(f"Компенсация CJ: {cj}\nMAX31856: "+('; '.join(t['max_errors']) or 'готов'))
        self.current_live.setText(f"RMS до калибровки: {t['adc_rms']:.1f} count\nСреднее ADC: {t['adc_mean']} · min/max: {t['adc_min']}/{t['adc_max']}")
        self.ext_live.setText(f"Петля: {t['loop_ma']:.3f} мА · напряжение: {t['external_mv']} мВ\nЧастота: {t['external_hz']} Гц · PT100: "+('—' if t['external_temperature'] is None else f"{t['external_temperature']:.1f} °C"))
        self.fault_text.setPlainText('ТЕКУЩИЕ\n'+('\n'.join(t['errors']) or 'Нет')+'\n\nMAX31856\n'+('\n'.join(t['max_errors']) or 'Нет')+'\n\nЗАФИКСИРОВАННЫЕ\n'+('\n'.join(t['latched_errors']) or 'Нет'))
        storage={0:'загружено из EEPROM',1:'сохранение…',2:'сохранено',3:'начальные значения',4:'ошибка EEPROM'}.get(t['storage_status'],'?')
        self.raw_text.setPlainText(f"Адрес: {t['address']} · Sa2={t['rotary']>>4:X}, Sa3={t['rotary']&15:X}\nРабота: {t['uptime']} с · TC sample: {t['sample']}\nВозраст TC / тока / PT100: {t['tc_age']} / {t['current_age']} / {t['external_age']} мс\nMAX SR: 0x{t['max_status']:04X}\nEEPROM: {storage} · запись №{t['saved_sequence']}\nИзменения RAM: {'есть' if t['dirty'] else 'нет'} · ревизия {t['revision']}\nПропуски ADC: {t['adc_overruns']}\nModbus: OK {t['valid_frames']} · CRC {t['crc_errors']}\nКадры {t['malformed']} · UART {t['framing_errors']} · exceptions {t['exceptions']}\nPID I: {t['integral']:.2f} % · dPV: {t['derivative']:.2f} °C/с")
        low=engineering(18,self.baseline[18]) if self.baseline else 0;high=engineering(19,self.baseline[19]) if self.baseline else 0
        self.chart.add(t,low,high)

    def clear_metrics(self):
        for value,hint in self.metric_values.values():value.setText('—')
        self.power_bar.setFormat('Нет свежих данных');self.mode_text.setText('Состояние прибора: неизвестно')
        self.relay_text.setText('Реле K1: неизвестно');self.resume_text.setText('После питания: нет свежих данных');self.soak_text.setText('Прогрев: нет свежих данных')

    def check_freshness(self):
        if self.online and self.last_received and time.time()-self.last_received>1.5:
            self.clear_metrics();self.notice.setText('Нет свежего ответа. Состояние выхода неизвестно; действует тайм-аут связи прибора.')
            self.chart.break_line(time.time(),self.telemetry['setpoint']);self.update_enabled()

    def update_enabled(self):
        ready=self.online and bool(self.draft) and not self.busy and not self.closing
        fresh=bool(self.last_received and time.time()-self.last_received<=1.5)
        for editor in self.editors:editor.setEnabled(ready)
        for address,widgets in self.fields.items():
            for w in widgets:w.setEnabled(ready and address<len(self.draft))
        for button in self.device_buttons:button.setEnabled(ready)
        if hasattr(self,'stop_button'):self.stop_button.setEnabled(self.online and not self.closing)
        if hasattr(self,'global_stop'):self.global_stop.setEnabled(self.online and not self.closing)
        if hasattr(self,'start_button'):
            t=self.telemetry;self.start_button.setEnabled(ready and fresh and bool(t) and not t['mode'] and not (t['active']|t['latched']) and (len(self.draft)<=41 or self.draft[41]!=0))
        self.port.setEnabled(not self.online and not self.busy);self.address.setEnabled(not self.online and not self.busy)
        self.refresh_button.setEnabled(not self.online and not self.busy)
        self.scan_button.setEnabled(not self.online and (not self.busy or self.busy=='scan'));self.scan_button.setText('Остановить поиск' if self.busy=='scan' else 'Найти адрес')
        self.connect_button.setText('Отключить' if self.online else 'Подключить');self.connect_button.setEnabled(not self.busy and not self.closing)
        if hasattr(self,'save_button'):
            running=self.telemetry and self.telemetry['mode']!=0
            self.save_button.setText('STOP → сохранить в прибор' if running else 'Сохранить в прибор')
            local_dirty=self.draft!=self.baseline
            self.config_status.setText('Есть правки в окне' if local_dirty else ('Параметры в RAM прибора не сохранены в EEPROM' if self.telemetry and self.telemetry['dirty'] else ('Настройки считаны из прибора' if self.online else 'Нет подключения')))
            self.read_button.setText('Считать · заменить правки' if local_dirty else 'Считать из прибора')

    def log(self,text):
        line=f'{datetime.now():%H:%M:%S}  {text}'
        if hasattr(self,'log_text'):self.log_text.appendPlainText(line)
        with (HERE/'.runtime/events.log').open('a',encoding='utf-8') as f:f.write(line+'\n')

    def show_error(self,text):
        self.notice.setText(text);self.log(text);self.statusBar().showMessage(text,15000)

    def export_chart(self):
        path,_=QFileDialog.getSaveFileName(self,'Сохранить график CSV',str(HERE/'captures'/f'chart_{datetime.now():%Y%m%d_%H%M%S}.csv'),'CSV (*.csv)')
        if not path:return
        with open(path,'w',encoding='utf-8-sig',newline='') as f:
            writer=csv.writer(f,delimiter=';');writer.writerow(['timestamp','temperature_C','setpoint_C','working_setpoint_C'])
            for point in self.chart.points:writer.writerow([datetime.fromtimestamp(point[0]).astimezone().isoformat(),*point[1:]])
        self.log('График сохранён: '+path)

    def screenshot(self):
        path=HERE/'captures'/f'window_{datetime.now():%Y%m%d_%H%M%S}.png'
        if not self.grab().save(str(path)):self.show_error('Не удалось сохранить снимок');return
        self.log('Снимок сохранён: '+str(path))

    def closeEvent(self,event):
        if self.can_close:event.accept();return
        event.ignore()
        if not self.closing:
            self.closing=True;self.statusBar().showMessage('Освобождение COM-порта; автономный режим прибора сохраняется…' if self.baseline and self.baseline[29]==0 else 'Отправка STOP и освобождение COM-порта…')
            self.worker.submit('shutdown');self.update_enabled()

    def worker_finished(self):self.can_close=True;self.close()
