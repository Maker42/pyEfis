#  Copyright (c) 2019 Garrett Herschleb
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import pyavtools.fix as fix

class Message(QGraphicsView):
    def __init__(self, anchor_x, anchor_y,
                    parent=None, align=Qt.AlignRight, sz=30):
        super(Message, self).__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0%); border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self.message_item = fix.db.get_item("SYSMSG", create=True, wait=False)
        self.message_item.dtype = 'str'
        self.message_item.value = ''
        self.message_item.valueChanged[str].connect(self.update_message)
        self.fontSize = sz
        self.align = align
        self.font = QFont("FixedSys", 10, QFont.Bold)
        self.gtext_item = None
        self.scene = None
        self.anchor_x = anchor_x
        self.anchor_y = anchor_y
        if self.align != Qt.AlignRight:
            self.move (self.anchor_x, self.anchor_y)
        self.update_message(self.message_item.value)

    def update_message(self, msg):
        if len(msg) == 0:
            self.hide()
            return
        t = QGraphicsSimpleTextItem (msg)
        t.setFont (self.font)
        self.w = t.boundingRect().width()
        self.h = t.boundingRect().height()
        self.resize(self.w, self.h)
        if self.scene is None:
            self.scene = QGraphicsScene(0, 0, self.w, self.h)
            self.setScene(self.scene)
        else:
            self.scene.setSceneRect(0,0, self.w, self.h)
        if self.align == Qt.AlignRight:
            self.move (self.anchor_x - self.w, self.anchor_y)
        if self.gtext_item is None:
            self.gtext_item = self.scene.addSimpleText (msg, self.font)
            self.gtext_item.setPen(QPen(QColor(Qt.red)))
            self.gtext_item.setBrush(QBrush(QColor(Qt.red)))
        else:
            self.gtext_item.setText(msg)
        self.show()

