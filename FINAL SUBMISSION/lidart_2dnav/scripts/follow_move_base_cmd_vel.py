#!/usr/bin/env python
import rospy
import math
from tf.transformations import euler_from_quaternion
from tf.transformations import quaternion_from_euler
from race.msg import drive_param
from geometry_msgs.msg import Twist

pub = rospy.Publisher('drive_parameters', drive_param, queue_size=1)
WHEELBASE_LENGTH = 0.325
vel = 0
ang = 0

def callback(data):
    global vel
    global ang
    vx = data.linear.x
    vy = data.linear.y
    theta_dot = data.angular.z
    velocity = math.sqrt(vx**2 + vy**2)
    angle = math.atan2(WHEELBASE_LENGTH * theta_dot, velocity)
    msg = drive_param()



    msg.velocity = velocity
    msg.angle = angle

    ## FOR TEB
    msg.velocity = data.linear.x
    if data.linear.x == 0 or data.angular.z == 0:
        msg.angle = 0
    else:
        msg.angle = math.atan2(WHEELBASE_LENGTH, data.linear.x/data.angular.z)
    msg.angle = data.angular.z

    # pub.publish(msg)

    ## THIS PREVENTS THE LOCAL PLANNER FROM SENDING 0's
    if msg.velocity != 0:
        vel = msg.velocity
    if msg.angle !=0:
        ang = msg.angle


if __name__ == '__main__':
    rospy.init_node('follow_move_base_cmd_vel')
    r = rospy.Rate(40)
    rospy.Subscriber('/cmd_vel', Twist, callback, queue_size=1)
    msg = drive_param()

    while not rospy.is_shutdown():
        msg.angle = ang
        msg.velocity = vel
        pub.publish(msg)
        r.sleep()
