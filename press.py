#! /usr/bin/env python3
# use this to get live editing:
# echo press.py |entr ./press.py

import solid as s
import solid.objects as so
import os
import solid.utils as su
from math import pi, sqrt, atan2, asin, tan, cos

screw_clearance = {
        'm4': 4.5,
        'm3': 3.4,
}
screw_head_sink = {
        'm4': {'h': 4, 'diameter': 7.3},
        'm3': {'h': 2.5, 'diameter': 6.2}
}
screw_nut = {
        'm4': {'width': 7.0, 'depth': 3.6},
        'm3': {'width': 5.85, 'depth': 2.9}
}

def hex(width, h, fillet_radius = 0.1):
    """
    width is the distance between opposing flat sides
    """
    r = width/2.0/cos(pi/6.0) # magic so that we have the width b/w flat faces instead of corners
    pole = so.translate((r - fillet_radius, 0, 0))(so.cylinder(r=fillet_radius, h=h))
    body = pole
    for i in range(1,6):
        body += so.rotate((0,0,60 * i))(pole)
    return so.hull()(body)

def rail_section(h):
    rail =  so.scale((25.4,25.4,1))(so.dxf_linear_extrude(file='SINGLE_RAIL_XSECTION.dxf', height=h))
    return so.translate((25.4, 23.8, 0))(rail)


def double_side_rail(h, bottom_thickness=10, holes=None):
    stack = rail_section(h) + so.rotate((0,0,180))(rail_section(h))
    if holes is not None:
        bolt_hole = so.rotate((0,90,0))(so.translate((0,0,-40))(so.cylinder(r=screw_clearance[holes]/2.0, h=80)))
        def mkhole(offset):
            nonlocal stack
            stack -= so.translate((0,0,offset))(bolt_hole)
        mkhole(20-bottom_thickness)
        mkhole(40-bottom_thickness)
        mkhole(h-10)
    return stack


# TODO printlist
# 1x double side rail
# 4x bearing cover
# 2x bearing carraige
# 1x bottom bracket
# 1x left pulley bracket
# 1x right pulley bracket
# 1x bearing cage
# 1x grooved wheel
# 1x iron arm TBD
# 1x presser arm TBD

scad = double_side_rail(180) # 18cm

def chamfer_hull(x=False, y=False, z=False, chamfer=1):
    ps = {}
    if x:
        ps[0] = x if isinstance(x, list) else [1,-1]
    if y:
        ps[1] = y if isinstance(y, list) else [1,-1]
    if z:
        ps[2] = z if isinstance(z, list) else [1,-1]
    def impl(scad):
        body = None
        for p in ps:
            for o in ps[p]:
                a = so.translate(([0]*p + [o * chamfer] + [0]*2)[:3])(scad)
                if body is None:
                    body = a
                else:
                    body += a
        return so.hull()(body)
    return impl

def bracket(bottom_thickness, chamfer, height, clearance, through_offsets, through_screw='m4'):
    body_orig = so.translate((-15,-20,0))(so.cube((30,40,height)))
    body = chamfer_hull(x=True,y=True,z=[1], chamfer=chamfer)(body_orig)
    rail_hole = so.minkowski()(so.translate((0,0,bottom_thickness))(double_side_rail(height)), so.cube([clearance]*3))
    body -= so.hole()(rail_hole)

    # add mount holes
    bolt_hole = so.rotate((0,90,0))(so.translate((0,0,-50))(so.cylinder(r=screw_clearance[through_screw]/2.0, h=200)))
    nut_recess = so.translate((-15.5-chamfer-100,0,0))(so.rotate((0,90,0))(hex(screw_nut[through_screw]['width'], 100+screw_nut[through_screw]['depth'])))
    bolt_hole += nut_recess
    head_recess = so.translate((15.5+chamfer,0,0))(so.rotate((0,-90,0))(so.translate((0,0,-100))(so.cylinder(r=screw_head_sink[through_screw]['diameter']/2.0, h=100+screw_head_sink[through_screw]['h']))))
    bolt_hole += head_recess
    for off in through_offsets:
        body -= so.hole()(so.translate((0,0,off))(bolt_hole))

    return body


def base_bracket(mount_screw_hole, through_screw='m4', chamfer=1, clearance=0.25, base_flange_width = 20, base_flange_thickness=25, bottom_thickness=10, height=50, holes_offset=10):
    # bolt holes at 20-bottom_thickness and 40-bottom_thickness offsets for rail
    body = bracket(bottom_thickness=bottom_thickness, chamfer=chamfer, height=height, clearance=clearance, through_offsets=[20,40])

    bracket_bottom = so.translate((-15-base_flange_width,-20-base_flange_width,0))(so.cube((30+base_flange_width*2,40+base_flange_width*2,base_flange_thickness)))
    bracket_chamfer = so.translate((-15-chamfer,-20-chamfer,-chamfer))(so.cube((30+2*chamfer,40+2*chamfer,chamfer)))

    body += chamfer_hull(x=True, y=True, z=[1])(bracket_bottom)
    for x in [1,-1]:
        for y in [1,-1]:
            body -= so.translate((x*(15+base_flange_width - holes_offset),y*(20+base_flange_width - holes_offset),base_flange_thickness+chamfer+0.001))(mount_screw_hole)

    return body

def countersunk_screw(diameter, depth, widest):
    body = so.cylinder(r=diameter/2.0, h=100)
    head = so.cylinder(r1=diameter/2.0, r2=widest/2.0, h=depth)
    return so.translate((0,0,-100))(body) + so.translate((0,0,-depth))(head)

def top_bracket(through_screw='m4', chamfer=1, clearance=0.25, bottom_thickness=12, height=30):
    body = bracket(bottom_thickness=bottom_thickness, chamfer=chamfer, height=height, clearance=clearance, through_offsets=[20])
    d = screw_nut[through_screw]['depth'] + 2
    nut_recess = so.translate((0,0,bottom_thickness-d))(hex(screw_nut[through_screw]['width'], d))

    bolt_hole = so.cylinder(r=screw_clearance[through_screw]/2.0, h=bottom_thickness)
    return body - nut_recess - bolt_hole

def pulley_arms(height=40, through_screw='m4', arm_width=15, arm_thickness=7.5, pully_width=10, base_width=30, base_thickness=10):
    arm_base = so.translate((0,-arm_width/2.0,0))(so.cube((arm_thickness, arm_width, 1)))
    arm = so.hull()(so.translate((0,0,height-arm_width/2.0))(so.rotate((0,90,0))(so.cylinder(r=arm_width/2.0, h=arm_thickness))) + arm_base)
    def arms_xf_left(obj):
        return so.translate((pully_width/2.0,0,0))(obj)
    def arms_xf_right(obj):
        return so.translate((-pully_width/2.0,0,0))(so.rotate((0,0,180))(obj))
    arms = arms_xf_left(arm) + arms_xf_right(arm)
    plate_orig = so.translate((-base_width/2.0,-base_width/2.0,-base_thickness))(so.cube((base_width, base_width, base_thickness)))
    plate = so.hull()(plate_orig, so.translate((0,0,base_thickness/2.0))(arms_xf_left(arm_base)))
    plate += so.hull()(plate_orig, so.translate((0,0,base_thickness/2.0))(arms_xf_right(arm_base)))

    # add mount holes
    spacing = arm_thickness*2.0+pully_width
    bolt_hole = so.rotate((0,90,0))(so.translate((0,0,-spacing))(so.cylinder(r=screw_clearance[through_screw]/2.0, h=spacing*2.0)))
    nut_recess = so.translate((-spacing/2.0,0,0))(so.rotate((0,90,0))(hex(screw_nut[through_screw]['width'], screw_nut[through_screw]['depth'])))
    bolt_hole += nut_recess
    head_recess = so.translate((spacing/2.0,0,0))(so.rotate((0,-90,0))(so.cylinder(r=screw_head_sink[through_screw]['diameter']/2.0, h=screw_head_sink[through_screw]['h'])))
    bolt_hole += head_recess

    arms -= so.translate((0,0,height-arm_width/2.0))(bolt_hole)

    # add base mount hole
    head_recess = so.translate((0,0,0))(so.cylinder(r=screw_head_sink[through_screw]['diameter']/2.0, h=screw_head_sink[through_screw]['h']*base_thickness))
    bolt_hole = so.translate((0,0,-base_thickness))(so.cylinder(r=screw_clearance[through_screw]/2.0, h=base_thickness*2.0))
    bolt_hole += head_recess

    return arms + plate - bolt_hole

def pulley(width=10, diameter=30, screw='m4', clearance=0.3, flat=1):
    groove_depth = width/2.0 - flat
    r = diameter/2.0
    bolt_hole = so.translate((0,0,-width))(so.cylinder(r=screw_clearance[screw]/2.0+clearance, h=width*2.0))
    return so.cylinder(r=r, h=flat) + so.translate((0,0,flat))(so.cylinder(r1=r, r2=r-groove_depth, h=width/2.0-flat)) + so.translate((0,0,groove_depth+flat))(so.cylinder(r2=r, r1=r-groove_depth, h=width/2.0-flat)) + so.translate((0,0,2*groove_depth+flat))(so.cylinder(r=r, h=flat)) - bolt_hole


def carriage_plate(dims=(49, 42, 10), chamfer=1, screw_thickness=8, arm_screw='m4', arm_mount_dist=20):
    (x,y,z) = dims
    plate = so.translate((0,0,z/2.0))(chamfer_hull(x=True,y=True,z=[1])(so.cube(dims, center=True)))
    head_recess = so.translate((0,0,8))(so.cylinder(r=screw_head_sink['m3']['diameter']/2.0, h=screw_head_sink['m3']['h']*z))
    bolt_hole = so.translate((0,0,-z))(so.cylinder(r=screw_clearance['m3']/2.0, h=z*2.0))
    for x in [1,-1]:
        for y in [1,-1]:
            plate -= so.translate((y*41.4/2,x*34.8/2,0))(bolt_hole + head_recess)

    head_recess = so.cylinder(r=screw_head_sink[arm_screw]['diameter']/2.0, h=screw_head_sink[arm_screw]['h']+1)
    bolt_hole = so.cylinder(r=screw_clearance[arm_screw]/2.0, h=z+chamfer)
    mount_hole = head_recess + bolt_hole

    return plate - so.translate((arm_mount_dist/2.0,0,0))(mount_hole) - so.translate((-arm_mount_dist/2.0,0,0))(mount_hole)

def iron_holder(thickness=30, depth=40, length=75, iron_diameter=20, chamfer=1, iron_holder_thickness=5,arm_screw='m4', arm_mount_dist=20, gap=0.75, split_screw='m3'):
    arm = chamfer_hull(x=True,y=True,z=[1])(so.translate((-thickness/2.0, -depth/2.0, 0))(so.cube((thickness,depth,length))))
    
    holder = so.translate((0,0,length+iron_diameter/2.0-iron_holder_thickness/2.0))(so.rotate((0,-90,0))(split_lock(iron_diameter, thickness=iron_holder_thickness, depth=depth, lip=10, chamfer=chamfer, gap=gap, screw=split_screw)))

    rope_tie = so.translate((0,depth/2.0,length-iron_diameter/2.0-iron_holder_thickness*2.0))(so.rotate((-90,90,0))(arch()))

    nut_recess = hex(screw_nut[arm_screw]['width'], screw_nut[arm_screw]['depth'])
    bolt_hole = so.cylinder(r=screw_clearance[arm_screw]/2.0, h=10)
    nut_slide = so.translate((0,-screw_nut[arm_screw]['width']/2.0))(so.cube((thickness, screw_nut[arm_screw]['width'], screw_nut[arm_screw]['depth'])))
    nut_attachment = so.translate((0,0,10))(nut_slide + nut_recess) + bolt_hole
    return arm + holder - so.translate((0,arm_mount_dist/2.0,0))(nut_attachment) - so.translate((0,-arm_mount_dist/2.0,0))(nut_attachment) + rope_tie

def split_lock(diameter, thickness=3, depth=40, lip=10, chamfer=1, gap=2, screw='m3', shape='circle'):
    lip_part = so.translate((diameter/2.0,-thickness/2.0,0))(so.cube((lip,thickness,depth)))
    if shape == 'circle':
        hole = so.cylinder(r=diameter/2.0, h=depth*2)
        brace = so.cylinder(r=diameter/2.0+thickness, h=depth)
    elif shape == 'square':
        hole = so.rotate((0,0,45))(so.translate((-diameter/2.0,-diameter/2.0,0))(so.cube((diameter,diameter,depth*2))))
        brace = so.rotate((0,0,45))(so.translate((-diameter/2.0-thickness,-diameter/2.0-thickness,0))(so.cube((2*thickness+diameter,2*thickness+diameter,depth))))
    holder = so.translate((0,depth/2.0,0))(chamfer_hull(x=True,y=True)(so.rotate((90,0,0))(brace + lip_part)) - so.hole()(so.translate((0,depth/2.0,0))(so.rotate((90,0,0))(hole))))

    split = so.translate((0, -depth/2.0-chamfer, -gap/2.0))(so.cube((thickness + diameter + lip,depth+chamfer*2,gap)))
    split_nut_recess = hex(screw_nut[screw]['width'], screw_nut[screw]['depth'])
    split_nut_slide = so.translate((0,-screw_nut[screw]['width']/2))(so.cube((thickness + diameter, screw_nut[screw]['width'], screw_nut[screw]['depth'])))
    split_bolt_hole = so.translate((0,0,-thickness*2-chamfer))(so.cylinder(r=screw_clearance[screw]/2.0, h=100))
    split_head_recess = so.translate((0,0,-diameter-thickness*2.0))(so.cylinder(r=screw_head_sink[screw]['diameter']/2.0, h=diameter+thickness))
    split_tensioner = so.translate(((diameter+lip)/2.0,0,thickness/2.0+chamfer))(split_nut_recess + split_bolt_hole + split_nut_slide + split_head_recess)
    return holder - split - split_tensioner

def counterweight(thickness=30, depth=50, length=55, cup_diameter=30, chamfer=1, cup_thickness=5,arm_screw='m4', arm_mount_dist=20, press_rod_diameter=12.66, gap=0.75):
    arm = chamfer_hull(x=True,y=True,z=[1])(so.translate((-thickness/2.0, -depth/2.0, 0))(so.cube((thickness,depth,length))))
    holder = so.translate((0,depth/2.0,length-cup_thickness))(chamfer_hull(x=True,y=True)(so.rotate((90,0,0))(so.cylinder(r=cup_diameter/2.0+cup_thickness, h=depth))) - so.hole()(so.translate((0,depth/2.0-cup_thickness,0))(so.rotate((90,0,0))(so.cylinder(r=cup_diameter/2.0, h=depth)))))

    nut_recess = hex(screw_nut[arm_screw]['width'], screw_nut[arm_screw]['depth'])
    bolt_hole = so.cylinder(r=screw_clearance[arm_screw]/2.0, h=10)
    nut_slide = so.translate((0,-screw_nut[arm_screw]['width']/2.0))(so.cube((thickness, screw_nut[arm_screw]['width'], screw_nut[arm_screw]['depth'])))
    nut_attachment = so.translate((0,0,10))(nut_slide + nut_recess) + bolt_hole

    shaft_holder = split_lock(diameter=press_rod_diameter, depth=depth, shape='square', gap=gap)
    rope_tie = so.translate((0,depth/2.0,length-cup_diameter/2.0-cup_thickness*2))(so.rotate((-90,90,0))(arch()))
    return arm + holder - so.translate((0,arm_mount_dist/2.0,0))(nut_attachment) - so.translate((0,-arm_mount_dist/2.0,0))(nut_attachment) + so.translate((0,0,length+cup_diameter/2.0+cup_thickness))(so.rotate((0,-90,0))(shaft_holder)) + rope_tie


def arch(thickness=5, hole_width=5, hole_height=5,chamfer=1):
    pillar = chamfer_hull(x=True,y=True,chamfer=chamfer)(so.translate((-thickness/2.0,hole_width/2.0+chamfer,0))(so.cube((5,5, hole_height+thickness))))
    cross = chamfer_hull(x=True,y=True,z=True, chamfer=chamfer)(so.translate((-thickness/2.0,-hole_width/2.0-thickness-chamfer,hole_height+chamfer))(so.cube((thickness, hole_width+2*(thickness+chamfer), thickness))))
    out = pillar + so.rotate((0,0,180))(pillar) + cross
    return out

def stopper(screw='m4'):
    body = so.cube((40,20,10), center=True)
    nut_recess = hex(screw_nut[screw]['width'], screw_nut[screw]['depth'])
    bolt_hole = so.translate((0,0,-10))(so.cylinder(r=screw_clearance[screw]/2.0, h=20))
    nut_slide = so.translate((0,-screw_nut[screw]['width']/2.0))(so.cube((20, screw_nut[screw]['width'], screw_nut[screw]['depth'])))
    nut_attachment = so.rotate((0,-90,-90))(so.translate((0,0,-screw_nut[screw]['depth']/2.0))(nut_slide + nut_recess) + bolt_hole)
    return body - so.rotate((0,0,180))(so.translate((0,-13,-10))(rail_section(20))) - so.translate((0,-5,0))(nut_attachment)


wood_screw = countersunk_screw(5.9, 4.5, 10.8)
scad = so.rotate((90,0,0))(double_side_rail(180, holes='m4')) # orient for printing
scad = pulley()

# NOTE the carriage has 4x m3 mounting holes with captive nuts centered on the edges of a rectangle approx. 34.8mm x 41.4mm
scad = so.scale((25.4,25.4,25.4))(so.import_('LB-V1-CARRIAGE.stl'))
scad = stopper()
scad = so.rotate((90,0,0))(counterweight())
scad = so.rotate((90,0,0))(iron_holder())
scad = base_bracket(mount_screw_hole=wood_screw)
scad = pulley_arms()
scad = top_bracket()
scad = carriage_plate()

#scad = arch()
#scad=split_lock(diameter=8)
#scad = hex(20, 5)
# TODO make a set-screw lock for the soldering iron
# TODO add tie points for rope

SEGMENTS = 48
s.scad_render_to_file(scad, 'parts.scad', file_header=f'$fn = {SEGMENTS};')

def render_stl(scad, stl):
    s.scad_render_to_file(scad, 'tmp.scad', file_header=f'$fn = {SEGMENTS};')
    print(f'rendering {stl}...', end='', flush=True)
    os.system(f'openscad -q -o {stl} tmp.scad')
    print(f'complete!')


if False:
    render_stl(base_bracket(mount_screw_hole=wood_screw), 'base_bracket.stl')
    render_stl(so.rotate((90,0,0))(double_side_rail(180, holes='m4')), 'rail.stl')
    render_stl(top_bracket(), 'top_bracket.stl')
    render_stl(pulley_arms(), 'pulley_arms.stl')
    render_stl(pulley(), 'pulley.stl')
    render_stl(so.scale((25.4,25.4,25.4))(so.import_('LB-V1-CARRIAGE.stl')), '2x_carriage.stl')
    render_stl(so.scale((25.4,25.4,25.4))(so.import_('LB-V1-BEARING_COVER.stl')), '4x_carriage_bearing_cover.stl')
    render_stl(carriage_plate(), '2x_carriage_plate.stl')
    render_stl(iron_holder(), 'iron_holder.stl')
    render_stl(counterweight(), 'counterweight.stl')
    render_stl(stopper(), '2x_stopper.stl')
print('done')
