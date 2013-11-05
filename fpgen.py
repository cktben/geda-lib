#!/usr/bin/python
# -*- coding: utf-8 -*-

# Always use conventional right-handed coordinates: +X, +Y is upper right.
# All coordinates are in mm.

import sys

# 25.4 mm/inch
def mm_to_mil(mm):
    return mm * 1000.0 / 25.4

def mil_to_mm(mil):
    return mil * 25.4 / 1000.0

def sgn(x):
    if x < 0:
        return -1
    elif x == 0:
        return 0
    else:
        return 1

def arg_string(seq):
    first = True
    s = ''
    for item in seq:
        if not first:
            s += ' '
        else:
            first = False
        
        if type(item) == type(''):
            s += '"' + item + '"'
        else:
            s += str(item)
    
    return s

class Footprint:
    def __init__(self):
        self.file = sys.stdout
        
        # Distance between edge of pin/pad and any adjacent copper
        self.clearance = mil_to_mm(15)
        
        # Distance between edge of pin/pad and soldermask
        self.mask = mil_to_mm(3)
        
        # Size of SMD pads
        self.pad_width = 1
        self.pad_height = 1
        
        # Width of silkscreen lines
        self.silk_width = mil_to_mm(10)
        
        # True to emit through-hole pins, False for SMD pins (pads)
        self.through_hole = False
        
        # Through-hole pin parameters
        #
        # Hole diameter
        self.pin_drill_dia = 0
        # Copper annulus diameter
        self.pin_copper_dia = 0
        # Distance between copper pad and adjacent elements
        self.pin_clearance = mil_to_mm(15)
        # Distance between copper pad and edge of soldermask hole
        self.pin_mask = self.mask
        # If True, square pads are produced around pins/pads.
        # If False, round pads are produced around pins/pads.
        self.square = True
    
    def header(self):
        print 'header'
    
    def trailer(self):
        print 'trailer'
    
    # Emits one pin.
    # (x, y) is the center.
    def pin(self, n, x, y):
        print 'pin', n, 'at', x, ',', y
    
    # Emits pins (first_pin, last_pin).
    def pin_row(self, first_pin, last_pin, x1, y1, dx, dy, dpin = 1):
        for pin in range(first_pin, last_pin + 1, dpin):
            x = x1 + (pin - first_pin) / dpin * dx
            y = y1 + (pin - first_pin) / dpin * dy
            self.pin(pin, x, y)
    
    def silk_line(self, x1, y1, x2, y2):
        print 'silk line', x1, ',', y1, ' to', x2, ',', y2
    
    def silk_poly(self, points):
        last_point = None
        for pt in points:
            if last_point != None:
                self.silk_line(last_point[0], last_point[1], pt[0], pt[1])
            last_point = pt
        self.silk_line(last_point[0], last_point[1], points[0][0], points[0][1])
    
    def silk_rect(self, x1, y1, x2, y2):
        self.silk_poly([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])

# Converts mils to PCB internal units (centimils)
def mm_to_pcb(mil):
    return int(round(mil * 100000.0 / 25.4))

class PCB_Footprint(Footprint):
    # NOTE: PCB uses CRT coordinates (upper left is -X, -Y).
    #       Negate Y when writing.
    
    def header(self):
        args = ['', '', '', '', 0, 0, 0, 0, 0, 100, '']
        self.file.write('Element [' + arg_string(args) + ']\n(\n')
    
    def trailer(self):
        self.file.write(')\n')
    
    def pin(self, n, x, y):
        flags = []
        if self.square:
            flags.append('square')
        
        if self.through_hole:
            # Through-hole
            thickness = mm_to_pcb(self.pin_copper_dia)
            clearance = mm_to_pcb(self.pin_clearance * 2)
            mask = mm_to_pcb(self.pin_copper_dia + self.pin_mask * 2)
            drill = mm_to_pcb(self.pin_drill_dia)
            
            if self.pin_copper_dia <= self.pin_drill_dia:
                flags.append('hole')
            
            args = [mm_to_pcb(x), mm_to_pcb(-y), thickness, clearance, mask, drill,
                    str(n), str(n), ','.join(flags)]
            
            self.file.write('    Pin [' + arg_string(args) + ']\n')
        else:
            # SMT
            thickness = min(self.pad_width, self.pad_height)
            if self.pad_width > self.pad_height:
                dx = self.pad_width - thickness
                dy = 0
            else:
                dx = 0
                dy = self.pad_height - thickness
            
            x1 = mm_to_pcb(x - dx / 2)
            y1 = mm_to_pcb(y - dy / 2)
            x2 = mm_to_pcb(x + dx / 2)
            y2 = mm_to_pcb(y + dy / 2)
            
            args = [x1, -y1, x2, -y2, mm_to_pcb(thickness), mm_to_pcb(self.clearance * 2),
                    mm_to_pcb(thickness + self.mask * 2), str(n), str(n), ','.join(flags)]
            
            self.file.write('    Pad [' + arg_string(args) + ']\n')
    
    def silk_line(self, x1, y1, x2, y2):
        args = [mm_to_pcb(x1), mm_to_pcb(-y1), mm_to_pcb(x2), mm_to_pcb(-y2), mm_to_pcb(self.silk_width)]
        self.file.write('    ElementLine [' + arg_string(args) + ']\n')

    def silk_circle(self, x, y, r):
        pcb_r = mm_to_pcb(r)
        args = [mm_to_pcb(x), mm_to_pcb(-y), pcb_r, pcb_r, 0, 360, mm_to_pcb(self.silk_width)]
        self.file.write('    ElementArc [' + arg_string(args) + ']\n')

# Generates a two-row SMD IC footprint.
# Pin 1 is in the lower left corner.
class Generate_SMD_Two_Rows:
    def __init__(self):
        # Number of pins.  Must be divisable by 2.
        self.num_pins = 0
        
        # Distance between centers of adjacent pins.
        self.pin_pitch = 0
        
        # Distance between centers of pins on opposite rows.
        self.row_pitch = 0
        
        # Distance between elements and center of silk outline
        self.silk_spacing = mil_to_mm(10)
        
        # Size of the component body.
        # This can be used to increase the size of the silk outline.
        self.body_width = 0
        self.body_height = 0
        
        # Size of die attach pad, drawn in the center.
        # If either is <= 0, the DAP is not drawn.
        self.dap_width = 0
        self.dap_height = 0
        
        # Name of the die attach pad
        self.dap_name = None
        
        # Outline style
        # 'outside', 'outside-notched', 'inside', 'inside-line'
        self.outline = 'outside'
        
        self.notch_depth = mil_to_mm(30)
        self.bevel = mil_to_mm(30)
        
        self.add_trailer = True
    
    # Outline with a notch on the -X side
    def notched_outline(self, fp, x1, y1, x2, y2):
        if abs(y2 - y1) < (self.notch_depth * 2):
            # No room for a notch
            fp.silk_rect(x1, y1, x2, y2)
        else:
            my = (y1 + y2) / 2.0
            sx = sgn(x2 - x1)
            sy = sgn(y2 - y1)
            nx = x1 + self.notch_depth * sx
            ny1 = my - self.notch_depth * sy
            ny2 = my + self.notch_depth * sy
            
            fp.silk_poly([(x1, y1), (x2, y1), (x2, y2), (x1, y2),
                          (x1, ny2), (nx, my), (x1, ny1), (x1, y1)])
    
    # Outline with a bevel on the +Y side
    #
    # CONSTRAINTS: x1 < x2, y1 < y2
    def bevel_outline(self, fp, x1, y1, x2, y2):
        if abs(y2 - y1) < self.bevel:
            # Too small
            fp.silk_rect(x1, y1, x2, y2)
        else:
            fp.silk_poly([(x1, y1), (x2, y1), (x2, y2 - self.bevel),
                          (x2 - self.bevel, y2), (x1 + self.bevel, y2),
                          (x1, y2 - self.bevel)])
    
    def run(self, fp):
        fp.header()

        # Pins
        row_pins = self.num_pins / 2
        x1 = (row_pins - 1) / 2.0 * self.pin_pitch
        y1 = self.row_pitch / 2.0
        fp.pin_row(1, row_pins, -x1, -y1, self.pin_pitch, 0)
        fp.pin_row(row_pins + 1, self.num_pins, x1, y1, -self.pin_pitch, 0)

        # DAP
        if self.dap_width > 0 and self.dap_height > 0:
            old_width = fp.pad_width
            old_height = fp.pad_height

            fp.pad_width = self.dap_width
            fp.pad_height = self.dap_height
            dap_name = self.dap_name
            if not dap_name:
                dap_name = self.num_pins + 1
            fp.pin(dap_name, 0, 0)

            fp.pad_width = old_width
            fp.pad_height = old_height

        self.make_outline(fp)

        if self.add_trailer:
			fp.trailer()

    def make_outline(self, fp):
        row_pins = self.num_pins / 2
        if self.outline.startswith('outside'):
            # Outside
            outline_width = self.pin_pitch * (row_pins - 1) + fp.pad_width + self.silk_spacing * 2
            outline_height = self.row_pitch + fp.pad_height + self.silk_spacing * 2
            h = max(outline_height, self.body_height)
        else:
            # Inside
            outline_width = self.pin_pitch * (row_pins - 1)
            outline_height = self.row_pitch - fp.pad_height - self.silk_spacing * 2
            h = outline_height
            
        w = max(outline_width, self.body_width)
        x1 = -w / 2.0
        y1 = -h / 2.0
        x2 = w / 2.0
        y2 = h / 2.0
        
        if 'notched' in self.outline:
            self.notched_outline(fp, x1, y1, x2, y2)
        elif 'bevel' in self.outline:
            self.bevel_outline(fp, x1, y1, x2, y2)
        else:
            fp.silk_rect(x1, y1, x2, y2)
        
        if 'line' in self.outline:
            y = y1 + self.silk_spacing + fp.silk_width
            fp.silk_line(x1, y, x2, y)

# SMD diode, drawn horizontally.
# Diode symbol in the center.
# Pins labelled A and K.
class Generate_SMD_Diode:
    def __init__(self):
        # Distance between inside edges of pads
        self.inside_distance = 0
        
        # Size of the diode's body (not including leads)
        self.body_width = 0
        self.body_height = 0
    
    # Set the pad size in the footprint before calling run()
    def run(self, fp):
        fp.header()
        
        # Distance between pad centers
        pitch = self.inside_distance + fp.pad_width / 2
        
        # Pads
        fp.pin('K', -pitch, 0)
        fp.pin('A', pitch, 0)
        
        # Upper left corner of diode symbol
        sx = -self.inside_distance / 2.0 - fp.silk_width * 2
        sy = self.body_height / 2.0 - fp.silk_width * 2
        
        # Diode symbol
        fp.silk_line(sx, sy, sx, -sy)
        fp.silk_line(sx, 0, -sx, -sy)
        fp.silk_line(sx, 0, -sx, sy)
        fp.silk_line(-sx, -sy, -sx, sy)
        
        # Body sides
        w = self.body_width / 2.0
        h = self.body_height / 2.0
        fp.silk_line(-w, -h, w, -h)
        fp.silk_line(-w, h, w, h)
        
        fp.trailer()

class Generate_QFN:
    def __init__(self):
        self.num_pins = 0
        self.inside = 0
        self.pin_pitch = 0
        self.dap_width = 0
        self.dap_height = 0
        self.dap_name = None

    def run(self, fp):
        fp.header()
        
        row_pins = self.num_pins / 4
        
        # Center X of leftmost pad for top/bottom
        x_left = (row_pins - 1) * self.pin_pitch / 2.0
        
        # Center Y of top/bottom pads
        # self.inside is the distance between the inside edges of pads
        y_top = (self.inside + fp.pad_height) / 2.0
        
        # Top
        fp.pin_row(row_pins * 3 + 1, row_pins * 4, x_left, y_top, -self.pin_pitch, 0)
        
        # Bottom
        fp.pin_row(row_pins + 1, row_pins * 2, -x_left, -y_top, self.pin_pitch, 0)
        
        # Swap pad width/height
        old_width = fp.pad_width
        old_height = fp.pad_height
        
        t = fp.pad_height
        fp.pad_height = fp.pad_width
        fp.pad_width = t
        
        # Left
        fp.pin_row(1, row_pins, -y_top, x_left, 0, -self.pin_pitch)
        
        # Right
        fp.pin_row(row_pins * 2 + 1, row_pins * 3, y_top, -x_left, 0, self.pin_pitch)
        
        # DAP
        if self.dap_width > 0:
            fp.pad_width = self.dap_width
            fp.pad_height = self.dap_height
            dap_name = self.dap_name
            if not dap_name:
                dap_name = self.num_pins + 1
            fp.pin(dap_name, 0, 0)
        
        fp.pad_width = old_width
        fp.pad_height = old_height
        
        # Outline
        s = y_top + fp.pad_height / 2 + fp.silk_width
        fp.silk_line(-s, -s, s, -s)
        fp.silk_line(-s, s, s, s)
        fp.silk_line(-s, -s, -s, s)
        fp.silk_line(s, -s, s, s)
        fp.silk_line(-s, s, -s - 0.381, s + 0.381)
        
        fp.trailer()
