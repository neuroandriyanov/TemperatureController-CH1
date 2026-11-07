"""Bounded temperature history with explicit gaps for stale/invalid samples."""
from collections import deque
from datetime import datetime
import math
from PySide6.QtCore import Qt,QPointF,QRectF
from PySide6.QtGui import QColor,QPainter,QPainterPath,QPen,QFont
from PySide6.QtWidgets import QWidget,QToolTip

class TemperatureChart(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.points=deque(maxlen=43200);self.window_seconds=600
        self.follow=True;self.end_time=None;self.hover=None;self.tolerance=(0,0)
        self.setMinimumHeight(270);self.setMouseTracking(True)
        self.setAccessibleName('График температуры и уставки')
    def add(self,t,low,high):
        self.points.append((t['received'],t['temperature'],t['setpoint'],t['working_setpoint'] if t['mode']==1 else None))
        self.tolerance=(low,high)
        if self.follow: self.end_time=t['received']
        self.update()
    def break_line(self,stamp,setpoint):
        if self.points and self.points[-1][1] is not None:
            self.points.append((stamp,None,setpoint,None));self.update()
    def set_window(self,seconds): self.window_seconds=seconds;self.update()
    def set_follow(self,on):
        self.follow=on
        if on and self.points: self.end_time=self.points[-1][0]
        self.update()
    def bounds(self):
        right=self.end_time or (self.points[-1][0] if self.points else 1)
        left=right-self.window_seconds
        shown=[p for p in self.points if left<=p[0]<=right]
        values=[v for p in shown for v in p[1:3] if v is not None and math.isfinite(v)]
        if values:
            low=min(values)-max(2,self.tolerance[0]);high=max(values)+max(2,self.tolerance[1])
            span=max(10,high-low);middle=(high+low)/2;low=middle-span*0.6;high=middle+span*0.6
        else: low,high=0,100
        return left,right,low,high,shown
    def plot_rect(self): return QRectF(61,30,max(10,self.width()-82),max(10,self.height()-73))
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor('#101a27'))
        rect=self.plot_rect();left,right,low,high,shown=self.bounds()
        xy=lambda x,y:QPointF(rect.left()+(x-left)/(right-left)*rect.width(),rect.bottom()-(y-low)/(high-low)*rect.height())
        p.setFont(QFont('Segoe UI',9))
        for i in range(6):
            y=low+(high-low)*i/5;pixel=xy(left,y).y()
            p.setPen(QPen(QColor('#253449'),1));p.drawLine(QPointF(rect.left(),pixel),QPointF(rect.right(),pixel))
            p.setPen(QColor('#98acc5'));p.drawText(QRectF(0,pixel-10,52,20),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,f'{y:.1f}')
        for i in range(6):
            x=left+(right-left)*i/5;pixel=xy(x,low).x()
            p.setPen(QPen(QColor('#1d2b3d'),1));p.drawLine(QPointF(pixel,rect.top()),QPointF(pixel,rect.bottom()))
            p.setPen(QColor('#98acc5'))
            text=datetime.fromtimestamp(x).strftime('%H:%M:%S') if self.points else '—'
            p.drawText(QRectF(pixel-32,rect.bottom()+8,64,20),Qt.AlignmentFlag.AlignCenter,text)
        p.setPen(QColor('#98acc5'));p.drawText(QPointF(12,18),'°C')
        if not shown:
            p.setPen(QColor('#8196b0'));p.drawText(rect,Qt.AlignmentFlag.AlignCenter,'График появится после подключения к прибору')
            return
        p.save();p.setClipRect(rect)
        # Decimate to screen resolution while keeping extrema and gaps per bucket.
        step=max(1,len(shown)//max(1,int(rect.width())))
        for index,color,width,dashed in [(2,'#e9b567',1.8,True),(3,'#9d9ae5',1.3,True),(1,'#4ad3c0',2.4,False)]:
            path=QPainterPath();started=False
            for i in range(0,len(shown),step):
                bucket=shown[i:i+step]
                if index==1 and any(q[index] is None for q in bucket): started=False;continue
                valid=[q for q in bucket if q[index] is not None]
                if not valid: started=False;continue
                selected=sorted({q[0]:q for q in [valid[0],min(valid,key=lambda q:q[index]),max(valid,key=lambda q:q[index]),valid[-1]]}.values())
                for q in selected:
                    point=xy(q[0],q[index])
                    if started:path.lineTo(point)
                    else:path.moveTo(point);started=True
            pen=QPen(QColor(color),width)
            if dashed:pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen);p.drawPath(path)
        if self.hover is not None and rect.contains(self.hover):
            p.setPen(QPen(QColor('#647992'),1,Qt.PenStyle.DotLine))
            p.drawLine(QPointF(self.hover.x(),rect.top()),QPointF(self.hover.x(),rect.bottom()))
        p.restore()
        if all(q[1] is None for q in shown):
            p.setPen(QColor('#b5c3d5'));p.drawText(rect.adjusted(0,12,0,-rect.height()+38),Qt.AlignmentFlag.AlignCenter,'Нет достоверной температуры — проверьте диагностику')
    def mouseMoveEvent(self,event):
        self.hover=event.position();rect=self.plot_rect()
        left,right,_,_,shown=self.bounds()
        if shown and rect.contains(self.hover):
            timestamp=left+(self.hover.x()-rect.left())/rect.width()*(right-left)
            point=min(shown,key=lambda p:abs(p[0]-timestamp))
            actual='нет данных' if point[1] is None else f'{point[1]:.1f} °C'
            QToolTip.showText(event.globalPosition().toPoint(),f"{datetime.fromtimestamp(point[0]):%H:%M:%S}\nТемпература: {actual}\nУставка: {point[2]:.1f} °C",self)
        self.update()
    def leaveEvent(self,event): self.hover=None;QToolTip.hideText();self.update()
    def wheelEvent(self,event):
        self.window_seconds=max(30,min(21600,self.window_seconds*(0.8 if event.angleDelta().y()>0 else 1.25)));self.update();event.accept()
