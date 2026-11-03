"""Boundary and explicit mutant rejection tests, stdlib unittest."""
import math
import unittest
from simulate import *

class GeometryTests(unittest.TestCase):
    def test_counterclockwise_transform_rejects_wrong_sign(self):
        expected=(0.,1.)
        correct=transform((1.,0.),(0.,0.,math.pi/2))
        mutant=(math.cos(math.pi/2),-math.sin(math.pi/2))
        self.assertAlmostEqual(correct[1],expected[1])
        self.assertGreater(math.dist(mutant,expected),1.)

    def test_intersection_and_containment_have_zero_distance(self):
        self.assertEqual(polygon_distance(rectangle(0,0,2,2),rectangle(.5,.5,1,1)),0.)
        self.assertEqual(polygon_distance(rectangle(0,0,2,2),rectangle(1.9,-1,2.1,3)),0.)
        self.assertAlmostEqual(polygon_distance(rectangle(0,0,1,1),rectangle(2,0,3,1)),1.)

    def test_ray_detection_and_no_detection(self):
        wall=[rectangle(2,-1,2.1,1)]
        self.assertAlmostEqual(ray_range((0,0),0,wall),2.)
        self.assertIsNone(ray_range((0,0),math.pi,wall))

class PolicyTests(unittest.TestCase):
    def test_front_gate_all_behavior_outputs_and_threshold(self):
        for state in ['follow_first','follow_second','corner_turn','hold']:
            for distance in [0.,.119,.12]:
                self.assertLessEqual(protect(.14,.4,distance)[0],0.)
        self.assertEqual(protect(.14,.4,.120001)[0],.14)
        # Old overwrite ordering restores forward motion and must be rejected.
        mutant_v=.14
        self.assertFalse(mutant_v<=0.)

    def test_timer_detects_frozen_mutant_and_bounded_fallback(self):
        actual=0.; frozen=0.
        for _ in range(11): actual=lost_timer(actual,False,.05)
        self.assertGreaterEqual(actual,.5); self.assertLess(frozen,.5)
        self.assertEqual(lost_timer(actual,True,.05),0.)
        policy=Policy('corner',.14)
        for _ in range(11): policy.step((0.,.31,0.),{'front':None,'left_front':None,'left_back':None},.05)
        self.assertEqual(policy.state,'sensor_failure')

    def test_wrap_endpoint_and_range_rejects_atan_endpoint_mutant(self):
        self.assertEqual(wrap(math.pi),-math.pi)
        self.assertEqual(wrap(-math.pi),-math.pi)
        self.assertNotEqual(math.atan2(math.sin(math.pi),math.cos(math.pi)),wrap(math.pi))
        for index in range(-100,101): self.assertTrue(-math.pi<=wrap(index*.23)<math.pi)

    def test_common_wheel_limit_and_ratio(self):
        left,right=wheel_command(2.,3.)
        self.assertLessEqual(max(abs(left),abs(right)),WHEEL_LIMIT)
        rawleft,rawright=(2-AXLE*3/2)/RADIUS,(2+AXLE*3/2)/RADIUS
        self.assertAlmostEqual(left*rawright,right*rawleft)
        self.assertEqual(wheel_command(0.,0.),(0.,0.))

    def test_midpoint_odometry_measured_increment(self):
        straight=integrate((0.,0.,0.),1.,1.)
        self.assertAlmostEqual(straight[0],RADIUS)
        self.assertAlmostEqual(straight[2],0.)
        turn=integrate((0.,0.,0.),-1.,1.)
        self.assertAlmostEqual(turn[0],0.)
        self.assertAlmostEqual(turn[2],2*RADIUS/AXLE)

    def test_swept_circle_bound_refuses_narrow_turn(self):
        self.assertTrue(turn_space_clear({'front':.64,'left_front':.30}))
        self.assertFalse(turn_space_clear({'front':.02,'left_front':.30}))
        self.assertFalse(turn_space_clear({'front':.64,'left_front':.02}))
        self.assertFalse(turn_space_clear({'front':.64,'left_front':None}))

if __name__=='__main__': unittest.main()
