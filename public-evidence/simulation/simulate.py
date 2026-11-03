"""Deterministic free 2-D kinematic surrogate; NOT a CoppeliaSim/MATLAB run."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path

RADIUS, AXLE, HALF_LENGTH, HALF_WIDTH = .0975, .381, .23, .19
DT, WHEEL_LIMIT = .05, 6.

def wrap(theta):
    return (theta + math.pi) % (2 * math.pi) - math.pi

def transform(point, pose):
    x,y=point; px,py,theta=pose; c,s=math.cos(theta),math.sin(theta)
    return px+c*x-s*y, py+s*x+c*y

def footprint(pose):
    return [transform(p,pose) for p in [(-HALF_LENGTH,-HALF_WIDTH),(HALF_LENGTH,-HALF_WIDTH),(HALF_LENGTH,HALF_WIDTH),(-HALF_LENGTH,HALF_WIDTH)]]

def cross(a,b):
    return a[0]*b[1]-a[1]*b[0]

def sub(a,b):
    return a[0]-b[0],a[1]-b[1]

def point_segment(p,a,b):
    d=sub(b,a); length=d[0]**2+d[1]**2
    t=max(0.,min(1.,sum(x*y for x,y in zip(sub(p,a),d))/length)) if length else 0.
    return math.hypot(p[0]-a[0]-t*d[0],p[1]-a[1]-t*d[1])

def intersects(a,b,c,d):
    ab,cd=sub(b,a),sub(d,c)
    values=[cross(ab,sub(c,a)),cross(ab,sub(d,a)),cross(cd,sub(a,c)),cross(cd,sub(b,c))]
    if values[0]*values[1]<0 and values[2]*values[3]<0:
        return True
    return any(abs(v)<1e-12 and point_segment(p,u,w)<1e-12 for v,p,u,w in
               [(values[0],c,a,b),(values[1],d,a,b),(values[2],a,c,d),(values[3],b,c,d)])

def contains(point,polygon):
    signs=[cross(sub(b,a),sub(point,a)) for a,b in zip(polygon,polygon[1:]+polygon[:1])]
    return all(v>=-1e-12 for v in signs) or all(v<=1e-12 for v in signs)

def polygon_distance(left,right):
    edges=lambda p:list(zip(p,p[1:]+p[:1]))
    if contains(left[0],right) or contains(right[0],left):
        return 0.
    minimum=math.inf
    for a,b in edges(left):
        for c,d in edges(right):
            if intersects(a,b,c,d):
                return 0.
            minimum=min(minimum,point_segment(a,c,d),point_segment(b,c,d),point_segment(c,a,b),point_segment(d,a,b))
    return minimum

def rectangle(x0,y0,x1,y1):
    return [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]

def ray_range(origin,angle,walls,maximum=3.):
    ray=(math.cos(angle),math.sin(angle)); best=maximum; detected=False
    for wall in walls:
        for a,b in zip(wall,wall[1:]+wall[:1]):
            edge=sub(b,a); denominator=cross(ray,edge)
            if abs(denominator)<1e-12:
                continue
            delta=sub(a,origin); distance=cross(delta,edge)/denominator; t=cross(delta,ray)/denominator
            if 0<=distance<=best and 0<=t<=1:
                best,detected=distance,True
    return best if detected else None

def sensors(pose,walls):
    return {
        'front':ray_range(transform((HALF_LENGTH,0),pose),pose[2],walls),
        'left_front':ray_range(transform((.16,HALF_WIDTH),pose),pose[2]+math.pi/2,walls),
        'left_back':ray_range(transform((-.16,HALF_WIDTH),pose),pose[2]+math.pi/2,walls),
    }

def wheel_command(v,omega):
    left,right=(v-AXLE*omega/2)/RADIUS,(v+AXLE*omega/2)/RADIUS
    scale=max(1.,abs(left)/WHEEL_LIMIT,abs(right)/WHEEL_LIMIT)
    return left/scale,right/scale

def protect(v,omega,front,threshold=.12):
    return (0. if front is not None and front<=threshold else v),omega

def lost_timer(previous,detected,dt):
    return 0. if detected else previous+dt

def turn_space_clear(readings,margin=.02):
    """Conservative stationary full-circle bound for these axis-aligned walls.

    Valid only when both observed walls are perpendicular to current sensor rays.
    A full swept-disc calculation from actual polygons is logged independently.
    """
    radius=math.hypot(HALF_LENGTH,HALF_WIDTH)
    front=readings['front']; side=readings['left_front']
    return (front is not None and side is not None and
            front+HALF_LENGTH>=radius+margin and side+HALF_WIDTH>=radius+margin)

def integrate(pose,left_delta,right_delta):
    ds=RADIUS*(left_delta+right_delta)/2
    dtheta=RADIUS*(right_delta-left_delta)/AXLE
    middle=pose[2]+dtheta/2
    return pose[0]+ds*math.cos(middle),pose[1]+ds*math.sin(middle),wrap(pose[2]+dtheta)

class Policy:
    """Pure feedback input: odometry, proximity, elapsed time. No truth pose."""
    def __init__(self,test,speed):
        self.test,self.speed=test,speed
        self.state='rotate_to_goal' if test=='goal' else 'approach' if test=='approach' else 'follow_first'
        self.hold=0.; self.lost=0.; self.turn_origin=None; self.second_origin=None
        self.finished=False

    def step(self,odom,readings,dt):
        x,y,theta=odom; front=readings['front']; left=readings['left_front']; back=readings['left_back']
        v=omega=0.
        if self.test=='goal':
            distance=math.hypot(.8-x,.5-y); target=math.atan2(.5-y,.8-x)
            if self.state=='rotate_to_goal':
                error=wrap(target-theta); omega=max(-.8,min(.8,2.4*error))
                if abs(error)<.04: self.state='translate'
            elif self.state=='translate':
                error=wrap(target-theta); v=min(self.speed,.8*distance); omega=max(-.8,min(.8,2.*error))
                if distance<=.04: self.state='final_heading'; v=0.
            elif self.state=='final_heading':
                omega=max(-.8,min(.8,-2.4*theta))
                if abs(theta)<=math.radians(3): self.state='hold'; omega=0.
            elif self.state=='hold':
                if distance>.05 or abs(theta)>math.radians(5):
                    self.state='rotate_to_goal'; self.hold=0.
                else:
                    self.hold+=dt; self.finished=self.hold>=1.
        elif self.test=='approach':
            if self.state=='approach':
                self.lost=lost_timer(self.lost,front is not None,dt)
                if front is None:
                    v=0.
                    if self.lost>=.5: self.state='sensor_failure'
                elif front<=.202:
                    self.state='hold'
                else:
                    v=min(self.speed,max(.005,.7*(front-.20)))
            elif self.state=='hold':
                self.hold+=dt; self.finished=self.hold>=1.
        else:
            if self.state=='corner_turn':
                error=wrap(self.turn_origin-math.pi/2-theta)
                omega=max(-.65,min(.65,2.2*error))
                if abs(error)<.025:
                    self.state='follow_second'; self.second_origin=odom[:2]; omega=0.
            elif self.state in ['follow_first','follow_second']:
                self.lost=lost_timer(self.lost,left is not None and back is not None,dt)
                if self.state=='follow_first' and front is not None and front<.65:
                    if turn_space_clear(readings):
                        self.state='corner_turn'; self.turn_origin=theta
                    else:
                        self.state='unsafe_turn_stop'
                elif self.lost>=.5:
                    self.state='sensor_failure'
                else:
                    v=self.speed if self.lost==0 else .03
                    if left is not None and back is not None:
                        heading=math.atan2(back-left,.32)
                        omega=max(-.6,min(.6,1.8*((left+back)/2-.30)-2.5*heading))
                    if self.state=='follow_second' and math.hypot(x-self.second_origin[0],y-self.second_origin[1])>=1.2:
                        self.state='hold'; v=omega=0.
            elif self.state=='hold':
                self.hold+=dt; self.finished=self.hold>=1.
        # Final protection applies AFTER every behavior, never before overwrite.
        return protect(v,omega,front)

def run_case(name,test,speed,destination,slip=0.):
    walls=[] if test=='goal' else [rectangle(1.73,-2,1.83,2)] if test=='approach' else [rectangle(-2,.8,3.1,.9),rectangle(3,-4,3.1,.9)]
    pose=(0.,0.,0.) if test!='corner' else (0.,.31,0.)
    odom=pose; policy=Policy(test,speed); rows=[]; left_angle=right_angle=0.
    collision=False; min_clearance=math.inf; stop_time=None; second_start=None; first_progress=0.
    for step in range(int(180/DT)+1):
        t=step*DT; readings=sensors(pose,walls)
        v,omega=policy.step(odom,readings,DT); wl,wr=wheel_command(v,omega)
        clearance=min((polygon_distance(footprint(pose),wall) for wall in walls),default=math.inf)
        collision=collision or clearance<=1e-10; min_clearance=min(min_clearance,clearance)
        if policy.state=='corner_turn' and not first_progress: first_progress=odom[0]
        if policy.state=='follow_second' and second_start is None: second_start=odom[:2]
        if policy.state=='hold' and stop_time is None: stop_time=t
        rows.append({'time_s':t,'x_gt_m':pose[0],'y_gt_m':pose[1],'theta_gt_rad':pose[2],
                     'x_odom_m':odom[0],'y_odom_m':odom[1],'theta_odom_rad':odom[2],
                     'wheel_left_angle_rad':left_angle,'wheel_right_angle_rad':right_angle,
                     'wheel_left_measured_rad_s':wl,'wheel_right_measured_rad_s':wr,
                     'wheel_left_command_rad_s':wl,'wheel_right_command_rad_s':wr,
                     'front_range_m':readings['front'],'left_front_range_m':readings['left_front'],
                     'left_back_range_m':readings['left_back'],'state':policy.state,
                     'footprint_clearance_m':None if math.isinf(clearance) else clearance,'collision':int(collision)})
        if policy.finished or collision or policy.state in ['sensor_failure','unsafe_turn_stop']: break
        # Ideal wheel-rate actuator. Ground-truth translation can optionally have
        # a slip factor; encoder odometry continues to use measured wheel rotation.
        increments=(wl*DT,wr*DT); left_angle+=increments[0]; right_angle+=increments[1]
        odom=integrate(odom,*increments)
        true_next=integrate(pose,*increments)
        pose=(pose[0]+(true_next[0]-pose[0])*(1-slip),pose[1]+(true_next[1]-pose[1])*(1-slip),true_next[2])
    destination.mkdir(parents=True,exist_ok=True)
    with (destination/(name+'.csv')).open('w',newline='',encoding='utf-8') as file:
        writer=csv.DictWriter(file,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    write_trajectory_svg(destination/(name+'.svg'),name,rows,walls)
    result={'case':name,'evidence_type':'ideal_2d_kinematic_surrogate','completed':policy.finished,
            'final_state':policy.state,'duration_s':rows[-1]['time_s'],'stop_time_s':stop_time,
            'collision':collision,'minimum_clearance_m':None if math.isinf(min_clearance) else min_clearance,
            'final_clearance_m':rows[-1]['footprint_clearance_m'],'final_estimated_pose':odom,'final_actual_pose':pose,
            'odometry_error':[odom[0]-pose[0],odom[1]-pose[1],wrap(odom[2]-pose[2])],
            'speed_m_s':speed,'sample_s':DT,'slip_fraction':slip,'hold_s':policy.hold}
    if test=='goal':
        result.update(estimated_goal_position_error_m=math.hypot(odom[0]-.8,odom[1]-.5),estimated_goal_heading_error_deg=math.degrees(abs(wrap(odom[2]))))
    elif test=='corner':
        second_progress=math.hypot(odom[0]-second_start[0],odom[1]-second_start[1]) if second_start else 0.
        # Shortest footprint distance to the relevant wall, evaluated only from GT.
        errors=[abs(polygon_distance(footprint((r['x_gt_m'],r['y_gt_m'],r['theta_gt_rad'])), walls[0 if r['state']=='follow_first' else 1])-.30)
                for r in rows if r['state'] in ['follow_first','follow_second']]
        result.update(first_straight_progress_m=first_progress,second_section_displacement_m=second_progress,
                      second_wall_parallel_progress_m=second_start[1]-odom[1] if second_start else 0.,
                      mean_abs_straight_clearance_error_m=sum(errors)/len(errors) if errors else None,
                      max_abs_straight_clearance_error_m=max(errors) if errors else None)
    return result

def write_trajectory_svg(path,name,rows,walls):
    """Dependency-free equal-scale trajectory plot. GT evaluation only."""
    points=[(r['x_gt_m'],r['y_gt_m']) for r in rows]+[p for wall in walls for p in wall]
    lo_x=min(p[0] for p in points)-.2; hi_x=max(p[0] for p in points)+.2
    lo_y=min(p[1] for p in points)-.2; hi_y=max(p[1] for p in points)+.2
    scale=min(660/max(hi_x-lo_x,.1),420/max(hi_y-lo_y,.1))
    xy=lambda p:f'{60+(p[0]-lo_x)*scale:.2f},{485-(p[1]-lo_y)*scale:.2f}'
    chunks=['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="560" viewBox="0 0 800 560">',
            '<rect width="800" height="560" fill="white"/>',
            f'<text x="35" y="28" font-family="sans-serif" font-size="18">{name}: ideal 2D surrogate, equal x/y scale</text>',
            '<text x="35" y="52" font-family="sans-serif" font-size="13">Blue: truth. Red dashed: encoder odometry. Wall polygons: grey.</text>']
    for wall in walls: chunks.append('<polygon points="'+' '.join(xy(p) for p in wall)+'" fill="#aaa" stroke="#333"/>')
    for xkey,ykey,color,dash in [('x_gt_m','y_gt_m','#2563eb',''),('x_odom_m','y_odom_m','#dc2626',' stroke-dasharray="4 3"')]:
        chunks.append('<polyline points="'+' '.join(xy((r[xkey],r[ykey])) for r in rows)+f'" fill="none" stroke="{color}" stroke-width="2"{dash}/>')
    chunks.extend([f'<text x="60" y="520" font-family="sans-serif" font-size="13">x [m]: {lo_x:.2f} to {hi_x:.2f}; y [m]: {lo_y:.2f} to {hi_y:.2f}; scale {scale:.1f} px/m</text>',
                   '<text x="60" y="543" font-family="sans-serif" font-size="12">Not MATLAB/CoppeliaSim evidence. No contact dynamics or calibrated Pioneer model.</text>','</svg>'])
    path.write_text('\n'.join(chunks),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,default=Path(__file__).parent/'results'); parser.add_argument('--slip',type=float,default=0.)
    args=parser.parse_args()
    results=[run_case(name,test,speed,args.output,args.slip) for name,test,speed in [('goal','goal',.14),('approach','approach',.14),('corner_slow','corner',.08),('corner_fast','corner',.14)]]
    report={'scope':'Supplementary surrogate only. Assignment explicitly requires MATLAB and CoppeliaSim.','assumptions':['Ideal instantaneous wheel-rate actuator','2D rectangular footprint and axis-aligned solid wall polygons','Ideal ray proximity sensors, no beam volume/noise','No rigid-body contact dynamics; stop at first geometric contact','Fixed declared geometry; not independently calibrated Pioneer dimensions'], 'cases':results}
    (args.output/'metrics.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
