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
import pyavtools.filters as filters
import instruments.ai.VirtualVfr as VirtualVfr

class AirBall(QGraphicsView):
    max_color_danger_level = 8.0
    max_danger_level = 10.0

    def __init__(self, parent=None, filter_depth=0):
        super(AirBall, self).__init__(parent)
        self.myparent = parent
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0%); border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        if filter_depth:
            self.filter = filters.AvgFilter(filter_depth)
        else:
            self.filter = None
        self.agl_item = fix.db.get_item("AGL")
        self.alat_item = fix.db.get_item("ALAT")
        self.aoa_item = fix.db.get_item("AOA")
        self.ias_item = fix.db.get_item("IAS")
        self.roll_item = fix.db.get_item("ROLL")
        self.vs_item = fix.db.get_item("VS")
        self._ias = self.ias_item.value
        self._aoa = self.aoa_item.value
        self._alat = self.alat_item.value
        self.alat_multiplier = 1.0 / (0.217)
        self.max_tc_displacement = 1.0 / self.alat_multiplier

    def y_pos(self, alpha):
        ret = (alpha - self.alpha_min) * self.height() / self.alpha_range
        return ret

    def resizeEvent(self, event):
        # Get configuration
        self.line_color = self.myparent.get_config_item('line_color')
        if self.line_color is None:
            self.line_color = Qt.yellow
        self.stall_color = self.myparent.get_config_item('stall_color')
        if self.stall_color is None:
            self.stall_color = Qt.red
        self.ball_color_safe = self.myparent.get_config_item('ball_color_safe')
        if self.ball_color_safe is None:
            self.ball_color_safe = Qt.green
        self.ball_color_danger = self.myparent.get_config_item('ball_color_danger')
        if self.ball_color_danger is None:
            self.ball_color_danger = Qt.red
        self.ball_color_border = self.myparent.get_config_item('ball_color_border')
        if self.ball_color_border is None:
            self.ball_color_border = Qt.black
        self.alpha_x = self.myparent.get_config_item('alpha_x')
        self.alpha_y = self.myparent.get_config_item('alpha_y')
        self.alpha_approach = self.myparent.get_config_item('alpha_approach')
        self.alpha_stall = self.myparent.get_config_item('alpha_stall')
        if self.alpha_stall is None:
            self.alpha_stall = 10
        self.alpha_max = self.myparent.get_config_item('alpha_max')
        if self.alpha_max is None:
            self.alpha_max = self.alpha_stall * 1.3
        self.alpha_min = self.myparent.get_config_item('alpha_min')
        if self.alpha_min is None:
            self.alpha_min = -self.alpha_max
        self.alpha_range = self.alpha_max - self.alpha_min

        filter_depth = self.myparent.get_config_item('alat_filter_depth')
        if filter_depth is not None and filter_depth > 0:
            self.filter = filters.AvgFilter(filter_depth)
        alat_multiplier = self.myparent.get_config_item('alat_multiplier')
        if alat_multiplier is not None and alat_multiplier > 0:
            self.alat_multiplier = alat_multiplier
            self.max_tc_displacement = 1.0 / self.alat_multiplier

        sceneHeight = self.height()
        sceneWidth = self.width()
        w_2 = sceneWidth/2
        self.scene = QGraphicsScene(0, 0, sceneWidth, sceneHeight)

        # Get a failure scene ready in case it's needed
        self.fail_scene = QGraphicsScene(0, 0, sceneWidth, sceneHeight)
        self.fail_scene.addRect(0,0, sceneWidth, sceneHeight, QPen(QColor(Qt.white)), QBrush(QColor(50,50,50)))
        font = QFont("FixedSys", 80, QFont.Bold)
        t = self.fail_scene.addSimpleText("XXX", font)
        t.setPen (QPen(QColor(Qt.red)))
        t.setBrush (QBrush(QColor(Qt.red)))
        r = t.boundingRect()
        t.setPos ((sceneWidth-r.width())/2, (sceneHeight-r.height())/2)

        # Construct main scene, starting from the back
        ball_radius = sceneWidth/5
        self.ball = self.scene.addEllipse(-ball_radius,-ball_radius,
                                          ball_radius*2, ball_radius*2,
                                          QPen(QColor(self.ball_color_border)),
                                          QBrush(QColor(self.ball_color_safe)))

        # Cow catcher
        cow_top = self.y_pos(self.alpha_stall)
        cow_bottom = sceneHeight-1
        cow_width_2 = sceneWidth * 7 / (10*2)
        cow_top_x = w_2 - cow_width_2
        cow_pen = QPen(QColor(self.stall_color))
        self.scene.addLine (0, cow_bottom, sceneWidth, cow_bottom, cow_pen)
        self.scene.addLine (cow_top_x, cow_top,
                            sceneWidth - cow_top_x, cow_top, cow_pen)
        half_cross = (w_2 + cow_top_x) / 2
        self.scene.addLine (cow_top_x, cow_top, half_cross, cow_bottom, cow_pen)
        self.scene.addLine (half_cross, cow_bottom, w_2, cow_top, cow_pen)
        self.scene.addLine (sceneWidth - cow_top_x, cow_top,
                            sceneWidth - half_cross, cow_bottom, cow_pen)
        self.scene.addLine (sceneWidth - half_cross, cow_bottom,
                            w_2, cow_top, cow_pen)
        self.scene.addLine (cow_top_x, cow_top,
                            0, cow_bottom, cow_pen)
        self.scene.addLine (sceneWidth - cow_top_x, cow_top,
                            sceneWidth, cow_bottom, cow_pen)
        # Alpha x
        line_pen = QPen(QColor(self.line_color))
        if self.alpha_x is not None:
            ax_offset = sceneWidth / 20
            ax_width = sceneWidth / 20
            ax_y = self.y_pos(self.alpha_x)
            self.scene.addLine (w_2 - ax_offset, ax_y,
                                w_2 - ax_offset - ax_width, ax_y, line_pen)
            self.scene.addLine (w_2 + ax_offset, ax_y,
                                w_2 + ax_offset + ax_width, ax_y, line_pen)
        # Alpha y
        if self.alpha_y is not None:
            ay_offset = sceneWidth / 20
            ay_width = sceneWidth / 15
            ay_offset_height = sceneWidth / 30
            ay_width_2 = sceneWidth / 20
            ay_y = self.y_pos(self.alpha_y)
            self.scene.addLine (w_2 - ay_offset, ay_y,
                                w_2 - ay_offset - ay_width, ay_y, line_pen)
            self.scene.addLine (w_2 + ay_offset, ay_y,
                                w_2 + ay_offset + ay_width, ay_y, line_pen)
            self.scene.addLine (w_2 - ay_offset - ay_width, ay_y,
                                w_2 - ay_offset - ay_width - ay_width_2,
                                ay_y-ay_offset_height,
                                line_pen)
            self.scene.addLine (w_2 + ay_offset + ay_width, ay_y,
                                w_2 + ay_offset + ay_width + ay_width_2,
                                ay_y-ay_offset_height,
                                line_pen)
        # Center line
        line_pen.setWidth(2)
        self.scene.addLine (w_2, 0, w_2, sceneHeight, line_pen)

        # Center cross on ball
        cross_radius = ball_radius / 2
        cross_pen = QPen(QColor(Qt.white))
        cross_pen.setWidth(2)
        self.ball_cross_h = self.scene.addLine (-cross_radius, 0,
                                                cross_radius, 0, cross_pen)
        self.ball_cross_v = self.scene.addLine (0, -cross_radius,
                                                0,  cross_radius, cross_pen)

        self.setScene(self.scene)
        self.alat_item.valueChanged[float].connect(self.setLatAcc)
        self.alat_item.badChanged.connect(self.quality_change)
        self.alat_item.oldChanged.connect(self.quality_change)
        self.alat_item.failChanged.connect(self.quality_change)
        self.ias_item.valueChanged[float].connect(self.setIAS)
        self.ias_item.badChanged.connect(self.quality_change)
        self.ias_item.oldChanged.connect(self.quality_change)
        self.ias_item.failChanged.connect(self.quality_change)
        self.aoa_item.valueChanged[float].connect(self.setAOA)
        self.aoa_item.badChanged.connect(self.quality_change)
        self.aoa_item.oldChanged.connect(self.quality_change)
        self.aoa_item.failChanged.connect(self.quality_change)

        self.update()

    def update(self):
        acc_displacement = self._alat
        if acc_displacement > self.max_tc_displacement:
            acc_displacement = self.max_tc_displacement
        if acc_displacement < -self.max_tc_displacement:
            acc_displacement = -self.max_tc_displacement
        centerball_x = (self.width()/2) * (1.0-(
                     acc_displacement * self.alat_multiplier))
        centerball_y = self.y_pos (self._aoa)
        ball_color,flash = self.get_ball_color()
        if self.aoa_item.bad or self.ias_item.bad or self.alat_item.bad or \
           self.aoa_item.old or self.ias_item.old or self.alat_item.old:
            ball_color = QColor(Qt.gray)
            flash = False
        ball_brush = QBrush(ball_color)
        self.ball.setBrush (ball_brush)
        self.ball.setX(centerball_x)
        self.ball.setY(centerball_y)
        self.ball_cross_h.setX(centerball_x)
        self.ball_cross_h.setY(centerball_y)
        self.ball_cross_v.setX(centerball_x)
        self.ball_cross_v.setY(centerball_y)

    def get_ball_color(self):
        danger_level = self.get_danger_level()
        color_ratio = danger_level / self.max_color_danger_level
        flash = False
        if color_ratio > 1:
            flash = True
            color_ratio = 1.0
        safe_color = QColor(self.ball_color_safe)
        red_safe = safe_color.red()
        green_safe = safe_color.green()
        blue_safe = safe_color.blue()
        dang_color = QColor(self.ball_color_danger)
        red_dang = dang_color.red()
        green_dang = dang_color.green()
        blue_dang = dang_color.blue()
        r = int(round(interpolate (color_ratio, red_safe, red_dang)))
        g = int(round(interpolate (color_ratio, green_safe, green_dang)))
        b = int(round(interpolate (color_ratio, blue_safe, blue_dang)))
        #print ("danger %.2g, rgb=%02x%02x%02x"%(danger_level, r,g,b))
        return QColor(r,g,b),flash

    def get_danger_level(self):
        Vs = self.ias_item.get_aux_value('Vs')
        Vs0 = self.ias_item.get_aux_value('Vs0')
        Vx = self.ias_item.get_aux_value('Vx')
        if Vx is None:
            Vx = Vs * 1.2
        ret = 0
        agl = self.agl_item.value
        if self.agl_item.old or self.agl_item.bad or self.agl_item.fail:
            agl = 10000
        # First eliminate some standard flight states as 0 danger
        if self.alpha_x is None:
            alpha_x = self.alpha_stall * 3 / 4
        else:
            alpha_x = self.alpha_x
        if self._ias >= Vx and self._aoa < alpha_x:
            return 0
        if abs(self.vs_item.value) < 20 and \
                VirtualVfr.in_airport_vicinity():
            # Landed or taxi'ing. Either way, no need to sound the alarm here
            return 0
        if self._alat < .05 and \
                abs(self.roll_item.value) < 5 and VirtualVfr.is_over_runway():
            # Normal takeoff and landing
            return 0
        # Things are not quite normal here. Evaluate danger.
        # Assume imminent death, and downgrade alarm according to
        # input data
        ret = 10.0
        ias_margin = (self._ias - Vs) / Vs
        ret -= ias_margin * 10  # 10% speed margin sheds 1 point of danger
        aoa_margin = (self.alpha_stall - abs(self._aoa)) / self.alpha_stall
        ret -= aoa_margin * 10  # 10% AOA margin sheds 1 point of danger
        roll_safety = (5 - abs(self.roll_item.value)) / 4
        roll_safety = min(1,roll_safety)
        ret -= roll_safety
        altitude_safety = agl / 10000
        if altitude_safety > 1:
            altitude_safety = 1
        ret -= altitude_safety
        if ret < 0:
            ret = 0
        if ret > 10:
            ret = 10
        return ret


    def getIAS(self):
        return self._ias

    def setIAS(self, ias):
        if ias != self._ias:
            self._ias = ias
            self.update()

    ias = property(getIAS, setIAS)

    def getAOA(self):
        return self._aoa

    def setAOA(self, aoa):
        if aoa != self._aoa:
            self._aoa = aoa
            self.update()

    aoa = property(getAOA, setAOA)

    def getLatAcc(self):
        return self._alat

    def setLatAcc(self, acc):
        last_acc = self._alat
        if self.filter is not None:
            self._alat = self.filter.setValue(acc)
        else:
            self._alat = acc
        if last_acc != self._alat:
            self.update()

    latAcc = property(getLatAcc, setLatAcc)

    def quality_change(self, x):
        if self.aoa_item.fail or self.ias_item.fail or self.alat_item.fail:
            self.setScene(self.fail_scene)
        else:
            self.setScene(self.scene)
            self.update()

def interpolate (ratio, bottom, top):
    rng = top - bottom
    return bottom + ratio*rng
