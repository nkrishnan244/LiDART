#!/usr/bin/env python

import rospy
import math
import numpy as np
import genpy
import yaml
import sys
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
import pdb
from geometry_msgs.msg import Point
import matplotlib.pyplot as plt
import time
from copy import deepcopy

pub = rospy.Publisher('scan_match_location', Point, queue_size=10)
pub_odom = rospy.Publisher('scan_match_corr_odom_pos', Point, queue_size=10)

# macros
N = 0

# Get the real time estimated location, based on the most recent pair of odom_pos and scan
is_first_time = True
prev_scan = np.array(N)
curr_scan = np.array(N)
curr_x = 0
curr_y = 0
prev_x = 0
prev_y = 0
curr_direction =  0 # initialized to be 0 (pointing in +x) degrees. positive is counter-clockwise
curr_pos = np.array([0,0,0])

# Mean Squared Error variables
mse_location = 0
max_error_location = sys.float_info.min
tot_error_rot = 0
avg_error_rot = 0
tot_error_translation = 0
avg_error_translation = 0

def real_time_estimated_location():
	global is_first_time
	global prev_scan
	global curr_scan
	global curr_direction
	global curr_x
	global curr_y
	global prev_x
	global prev_y
	global prev_
	global error_list
	global error_2_list
	global curr_pos

	global mse_location
	global max_error_location
	global tot_error_rot
	global avg_error_rot
	global tot_error_translation
	global avg_error_translation

	estimated_xys = np.array([curr_x, curr_y]).reshape(1,-1)
	actual_xys = np.array([most_curr_odom_pos.x, most_curr_odom_pos.y]).reshape(1,-1)
	cnt = 0 # solely used for counting how many estimates we have already made and debug
	fake_cnt = 0

	# lock that will be unlocked after we receive the first scan
	while first_scan and not rospy.is_shutdown():
		fake_cnt += 1

	while not rospy.is_shutdown():
		curr_scan = process_scan(most_curr_scan)
		curr_odom_pos = most_curr_odom_pos

		if not is_first_time:
			cnt += 1

			# given 2 lidar scans, get the q that minimizes the error function
			error_list = []
			error_2_list = []

			curr_odom_local = deepcopy(curr_odom)
			curr_odom_local_time = deepcopy(curr_odom_time)

			# delta_odom = curr_odom_local - prev_odom_local
			# delta_odom = pos_minus(prev_odom_local, curr_odom_local)
			# delta_odom = curr_odom_local + -1*prev_odom_local
			# delta_odom = curr_odom_local - q
			# delta_odom = pos_minus(curr_odom_local, q)
			delta_odom = np.array([0, 0, 0])

			q, mask = iterative_find_q(curr_scan, prev_scan, delta_odom)
			time2 = int(round(time.time() * 1000))
			# delta_odom = -delta_odom
			curr_transform = np.matmul(rot(q[2]),curr_scan.T).T + q[:2]
			first_transform = np.matmul(rot(delta_odom[2]),curr_scan.T).T + delta_odom[:2]
			curr_filtered_transform = np.matmul(rot(q[2]),curr_scan[mask].T).T + q[:2]
			# pdb.set_trace()

			## PLOT STUFF
			# plt.plot(prev_scan[:,0],prev_scan[:,1],'g')
			# plt.plot(curr_scan[:,0],curr_scan[:,1],'bo')
			# plt.plot(curr_transform[:,0],curr_transform[:,1],'ro')
			# plt.plot(first_transform[:,0],first_transform[:,1], 'co')
			# plt.axis('equal')
			# if len(mask) > 0:
			# 	if len(mask) != len(curr_transform):
			# 		pdb.set_trace()
			# 	# pdb.set_trace()
			# 	plt.plot(curr_filtered_transform[:,0], curr_filtered_transform[:,1], 'mo')
			# plt.legend(["prev_scan","curr_scan","curr_transform", "init_transform", "filtered_transform"])
			# plt.show()

			# plt.plot(error_list) # debug
			# plt.plot(error_2_list)
			# plt.legend(["error","error_2"])
			# plt.show()

			# pdb.set_trace()

			#print("found q: %0.2f %0.2f %0.2f" % (q[0], q[1], q[2]))

			# use the q to calculate current location
			#curr_x = curr_x + math.sqrt(q[0]**2 + q[1]**2) * math.cos(curr_direction - q[2])
			#curr_y = curr_y + math.sqrt(q[0]**2 + q[1]**2) * math.sin(curr_direction - q[2])
			prev_x = curr_x
			prev_y = curr_y
			curr_x = curr_x + math.sqrt(q[0]**2 + q[1]**2) * math.cos(curr_direction + q[2])
			curr_y = curr_y + math.sqrt(q[0]**2 + q[1]**2) * math.sin(curr_direction + q[2])

			# print out errors
			estimated_xys = np.append(estimated_xys, [[curr_x, curr_y]], axis=0)
			actual_xys = np.append(actual_xys, [[curr_odom_pos.x, curr_odom_pos.y]], axis=0)

			error_location = math.sqrt((curr_odom_pos.x - curr_x)**2 + (curr_odom_pos.y - curr_y)**2)
			max_error_location = max(max_error_location, error_location)
			mse_location = np.sum(np.sum((estimated_xys - actual_xys)**2, axis=1), axis=0) / (1.0 * cnt)
			tot_error_translation += np.sqrt(np.sum((delta_odom[:2] - q[:2])**2))
			avg_error_translation = tot_error_translation / (1.0 * cnt)
			tot_error_rot += (q[2] - delta_odom[2])
			avg_error_rot = tot_error_rot / (1.0 * cnt)

			print("mse_location: %0.2f" % mse_location)
			print("max_error_location: %0.2f" % max_error_location)
			print("avg_error_translation: %0.2f" % avg_error_translation)
			print("avg_error_rot: %0.2f" % avg_error_rot)

			#publish msg
			msg = Point()
			msg.x = curr_x
			msg.y = curr_y
			msg.z = 0
			pub.publish(msg)

			# update values
			#curr_direction = curr_direction - q[2]
			curr_direction = curr_direction + q[2]
			prev_scan = curr_scan

			prev_odom_local = curr_odom_local
			prev_odom_local_time = curr_odom_local_time

			#publish corresponding odom pos
			pub_odom.publish(curr_odom_pos)


		else: # first time
			cnt += 1
			is_first_time = False
			prev_scan = curr_scan

			prev_odom_local = deepcopy(curr_odom)
			prev_odom_local_time = deepcopy(curr_odom_time)

			msg = Point()
			msg.x = 0
			msg.y = 0
			msg.z = 0
			pub.publish(msg)

			#publish corresponding odom pos
			pub_odom.publish(curr_odom_pos)


# --------------------- HELPER FUNCTIONS RELATED TO SUBSCRIBER CALLBACK ------------------------ #

# most current odom & scan
most_curr_odom_pos = Point()
most_curr_scan = np.array(N)
first_scan = True
first_odom = False
curr_odom = np.array([0,0,0])
curr_odom_time = genpy.Time()

def scan_callback(data):
	global first_scan
	global most_curr_scan
	global N

	if first_scan:
		N = len(data.ranges)
		first_scan = False

	most_curr_scan = data

def odom_callback(data):
	global curr_odom
	global first_odom
	global curr_odom_time
	global most_curr_odom_pos

	most_curr_odom_pos = data.pose.pose.position

	# pdb.set_trace() # debug
	x = data.pose.pose.position.x
	y = data.pose.pose.position.y
	theta =  2 * np.arccos(data.pose.pose.orientation.w)

	curr_odom = np.array([x,y,theta])
	curr_odom_time = data.header.stamp
	first_odom = True

# --------------------- HELPER FUNCTIONS RELATED TO LIDAR SCAN PROCESSING ------------------------ #
# a get_correspondence_naive function that supports discarding inf points in scan
# pre-processing of scan input (in process_scan): if a scan range is larger than range_max,
# don't include that in the output curr_scan

def get_RT_mat(q1):
	t1 = np.matrix(q1[0:2].reshape(2,1))
	R1 = np.matrix(rot(q1[2]))

	RT1 = np.matrix(np.eye(3))
	RT1[0:2,0:2] = R1
	RT1[0:2,2] = t1

	return RT1

def pos_minus(q1,q2):
	# roto translate q1 by -q2
	RT1 = get_RT_mat(q1)
	RT2 = get_RT_mat(q2)

	RT = RT2.I*RT1

	q3 = np.array([RT[0,2],RT[1,2],np.arccos(RT[0,0])])

	return q3

def pos_plus(q1,q2):
	# roto translate q1 by q2
	RT1 = get_RT_mat(q1)
	RT2 = get_RT_mat(q2)
	RT = RT2*RT1

	q_out = np.array([RT[0,2],RT[1,2],np.arccos(RT[0,0])])

	return q_out

# Process laser scan and save as cartesian
def process_scan(data):
	# read input
	scans = np.array(data.ranges)
	theta_min = data.angle_min
	theta_max = data.angle_max
	theta_delta = data.angle_increment

	# pdb.set_trace()
	r_min = data.range_min
	r_max = data.range_max
	thetas = np.arange(theta_min,theta_max,theta_delta)
	theta_scans = np.hstack((thetas.reshape(-1,1), scans.reshape(-1,1)))
	print("theta_scans length: %d" % len(theta_scans))

	theta_scans = theta_scans[theta_scans[:,1] <= r_max]
	theta_scans = theta_scans[theta_scans[:,1] >= r_min]
	print("after discarding out-of-range vals: %d" % len(theta_scans))

	# converted to cartesian
	scan_x = theta_scans[:,1]*np.cos(theta_scans[:,0])
	scan_y = theta_scans[:,1]*np.sin(theta_scans[:,0])
	data_xy = np.hstack((scan_x.reshape(-1,1),scan_y.reshape(-1,1)))
	return data_xy

# --------------------- HELPER FUNCTIONS RELATED TO ITERATIVELY FINDING Q ------------------------ #
# Iteratively find the q that minimizes the error function
# input: curr_scan, prev_scan
# output: q = [t_x, t_y, theta]
epsilon_xy = 0.05
epsilon_theta = 0.05
max_iteration = 30
prev_q = np.array([0,0,0])
# debug!
error_list = []
error_2_list = []
def iterative_find_q(curr_scan, prev_scan, q0):
	global prev_q
	global error_list
	global error_2_list
	# define an initial guess for q_0
	q = prev_q.copy()
	best_q = q.copy()
	# initialize empty C & q
	C = np.zeros([N,3])
	prev_C = np.zeros([N,3])
	best_C = np.zeros([N,3])
	# k is the cnt of iteration
	k = 0
	# initialize error & diff_C to be something big
	error = N
	diff_C = sys.float_info.max
	diff_q_xy = sys.float_info.max
	diff_q_theta = sys.float_info.max
	diff_error = sys.float_info.max
	prev_error = 0;
	best_error = sys.float_info.max

	# initialize set of previously seen q
	seen_q = set()

	# while:
	# 1. test convergence: diff(C_(k-1),C_(k)) is larger than a threshold
	# 2. test cycle (previously seen C)
	while (diff_q_xy > epsilon_xy or diff_q_theta > epsilon_theta) or k >= 3:
		# global mask
		prev_C = C.copy()
		prev_q = q.copy()
		k += 1
		# print("iteration %d" % k)
		# C_(k+1) = search_correspondence(curr_scan, prev_scan, q_(k+1))
		# C = search_correspondence(curr_scan, prev_scan, prev_q)
		time1 = int(round(time.time() * 1000))
		# Cnaive = search_correspondence_naive(curr_scan, prev_scan, prev_q)
		time2 = int(round(time.time() * 1000))
		C = search_correspondence_brute(curr_scan, prev_scan, prev_q)
		time3 = int(round(time.time() * 1000))
		# pdb.set_trace()

		# debug
		error_2 = calculate_error(curr_scan, prev_scan, C, prev_q)
		error_2_list.append(error_2)
		error_vec = calculate_individual_error(curr_scan, prev_scan, C, prev_q)
		# pdb.set_trace()
		# print("iteration %d; error_2: %0.2f" % (k, error_2))
		# pdb.set_trace()
		# diff_C = np.sum((prev_C[:,1] - C[:,1])**2)
		# print("iteration %d; diff(prev_C[:,1] - C[:,1]): %0.2f" % (k, diff_C))
		# pdb.set_trace()
		# q_(k+2) = get_q(curr_scan, prev_scan, C_(k+2))
		time3 = int(round(time.time() * 1000))
		
		if error_2/len(error_vec) == 0 or k < 3:
			q = get_q(curr_scan, prev_scan, C)
		else:
			mask = error_vec < error_2/len(error_vec) + 2*np.std(error_vec)
			# pdb.set_trace()
			q = get_q(curr_scan[mask], prev_scan, C[mask])
		time4 = int(round(time.time() * 1000))

		diff_q_xy = np.sqrt(np.sum((prev_q[:2] - q[:2])**2))
		diff_q_theta = abs(q[2] - prev_q[2])
		print("iteration %d; diff_q_xy: %0.2f; diff_q_theta: %0.2f" % (k, diff_q_xy, diff_q_theta))

		# calculate error(q_(k+2), C_(k+1))
		prev_error = error
		error = calculate_error(curr_scan, prev_scan, C, q)
		diff_error = error - prev_error
		if (error < best_error):
			best_error = error
			best_C = C
			best_q = q

		# debug
		print("iteration %d; best_error: %0.2f; error: %0.2f; error diff: %0.2f" % (k, best_error, error, diff_error))
		print("iteration %d: search_correspondence_naive time: %d; get_q time: %d"%(k, time2-time1, time4-time3))
		error_list.append(error)

		# pdb.set_trace() # debug

		if (k > max_iteration):
			print("maximum iteration exceeded")
			break

		# detect loop
		q_str = np.array2string(q, precision=2)

		#print("iteration %d; q_str:%s" % (k, q_str))
		if q_str in seen_q:
			print("cycle detected")
			break
		else:
			seen_q.add(q_str)

	# return best_q
	if error_2/len(error_vec) == 0 or k < 3:
		return best_q, []
	else:
		return best_q, mask

def calculate_error(curr_scan, prev_scan, C, q):
	# pdb.set_trace()
	project_p2p = np.matmul(rot(q[2]),curr_scan.T).T + q[:2] - prev_scan[C[:,1],:]
	# pdb.set_trace()
	segments = prev_scan[C[:,1],:] - prev_scan[C[:,2],:]
	normals = np.array([-segments[:,1], segments[:,0]]).T
	normals_lengths = np.sqrt(np.sum(normals**2, axis = 1))
	normals = normals / normals_lengths.reshape(-1,1)
	project_p2l = np.sum(np.sum(np.multiply(normals,project_p2p), axis=1)**2)
	return project_p2l

def calculate_individual_error(curr_scan, prev_scan, C, q):
	project_p2p = np.matmul(rot(q[2]),curr_scan.T).T + q[:2] - prev_scan[C[:,1],:]
	segments = prev_scan[C[:,1],:] - prev_scan[C[:,2],:]
	normals = np.array([-segments[:,1], segments[:,0]]).T
	normals_lengths = np.sqrt(np.sum(normals**2, axis = 1))
	normals = normals / normals_lengths.reshape(-1,1)
	project_p2l = np.sum(np.multiply(normals,project_p2p), axis=1)**2
	return project_p2l

# --------------------- HELPER FUNCTIONS RELATED TO SEARCH CORRESPONDENCE ------------------------ #
from scipy.spatial.distance import cdist

def search_correspondence_brute(curr_scan, prev_scan, q):
	transformed_xy = np.matmul(rot(q[2]),curr_scan.T).T + q[:2]
	# pdb.set_trace()
	C = np.empty([len(transformed_xy), 3])
	# new_node = np.asarray(new_node).reshape(-1, 2)
	# old_node = old_node.reshape(-1, 2)
	C[:, 0] = np.arange(len(transformed_xy)).T
	# pdb.set_trace()
	# C[:, 1] = (np.argmin(cdist(prev_scan, transformed_xy), axis=0))
	# pdb.set_trace()
	C[:, 1:3] = cdist(transformed_xy, prev_scan).argsort(axis=1)[:, :2]
	# C = C.astype(int)
	# prev_scan[C[:, 1] == len(prev_scan) or prev_scan[C[:, 1] + 1]] > prev_scan[C[:, 1] - 1]
	# pdb.set_trace()
	# C[:, 2] = C[:, 1] + 1
	# pdb.set_trace()
	# C[C[:,2] == len(prev_scan), 2] = len(prev_scan) - 2
	C = C.astype(int)
	# pdb.set_trace()

	return C

def search_correspondence_naive(curr_scan, prev_scan, q):
	# transformed scan: curr_scan transformed onto prev_scan after transform q
  transformed_xy = np.matmul(rot(q[2]),curr_scan.T).T + q[:2]
  C = np.zeros([0, 3]).astype(int)
  N_curr = len(curr_scan)
  N_prev = len(prev_scan)

  for i in range(N_curr):
    ji1 = closest_node(transformed_xy[i,:],prev_scan)
    ji2 = -1
    if (ji1 == 0):
        ji2 = 1
    elif (ji1 == (N_prev-1)):
        ji2 = N_prev-2
    else:
      ji2 = (ji1 - 1) if (np.sum((prev_scan[(ji1-1),:] - transformed_xy[i,:])**2)
        < np.sum((prev_scan[ji1+1,:] - transformed_xy[i,:])**2)) else (ji1 + 1)

    C = np.append(C, [[i,ji1,ji2]], axis=0)

  return C

# input: node [1,2], nodes [N,2]
def closest_node(node, nodes):
    dist_2 = np.sum((nodes - node)**2, axis=1)
    return np.argmin(dist_2)

# Search the closest correspondence between curr_scan and prev_scan
# input: curr_scan, prev_scan: both lidar scans;
# q: roto-transformation guess from curr_scan to prev_scan [t_x, t_y, theta], where theta is in radian
# output: C[N,3]: [i,ji1,ji2] - i-th scan in current scan corresponds to ji1 and ji2 in previous scan
def search_correspondence(curr_scan, prev_scan, q):
	# values used for search correspondence (in angles)
	start_angle = -135
	end_angle = 135
	angle_span = end_angle - start_angle
	acceptable_distance = sys.float_info.max

	# old scan: prev_scan
	old_x = prev_scan[:,0]
	old_y = prev_scan[:,1]
	# world scan: curr_scan transformed onto prev_scan after transform q
	world_xy = np.matmul(rot(q[2]), curr_scan.T) + np.tile((q[:2].reshape(-1,1)),(1,N))
	world_x = world_xy[0,:]
	world_y = world_xy[1,:]

	last_best = -1

	C = np.zeros([N, 3]).astype(int)
	C[:,0] = np.arange(N)

	# ??? What does this do
	up_out, up_in = getUpArrays(old_x, old_y, N)
	down_out, down_in = getDownArrays(old_x, old_y, N)

	# create pairings
	for i in range(N):
	  	world_angle = i / (N - 1.0) * angle_span + start_angle
	  	world_norm = (world_x[i])**2 + (world_y[i])**2
	  	best = -1
	  	best_dist = sys.float_info.max

	  	start_index = last_best
	  	if (start_index == -1):
	  		start_index = i

	  	up = start_index + 1
	  	down = start_index

	  	last_dist_up = sys.float_info.max
	  	last_dist_down = sys.float_info.max

	  	up_stopped = False
	  	down_stopped = False

		# up stopped becomes true when no angle can become closer
		# down stopped becoems true when no smaller angle can become true
		while not up_stopped or not down_stopped:
			up = int(up)
			down = int(down)

			now_up = not up_stopped and (last_dist_up <= last_dist_down)
			if (now_up):
				if (up >= N):
					up_stopped = True
					continue

				last_dist_up = (old_x[up] - world_x[i])**2 + (old_y[up] - world_y[i])**2
				if (last_dist_up < best_dist and last_dist_up < acceptable_distance):
					best = up
					best_dist = last_dist_up

				if (isAngleBigger(world_x[i], world_y[i], old_x[up], old_y[up])):
					angle_offset = (up - i) / (N - 1.0) * angle_span + start_angle
					min_dist_up = np.sin(np.deg2rad(angle_offset)) * world_norm
					if (min_dist_up > best_dist):
						up_stopped = True
						continue

					if (old_x[up])**2 + old_y[up]**2 > world_norm:
						up = up_in[up][0]
					else:
						up = up_out[up][0]
				else:
					up += 1

				if (up < 0 or up >= N):
					up_stopped = True

			if (not now_up):
				if (down < 0):
					down_stopped = True
					continue

				last_dist_down = (old_x[down] - world_x[i])**2 + (old_y[down]- world_y[i])**2
				if (last_dist_down < best_dist and last_dist_down < acceptable_distance):
					best = down
					best_dist = last_dist_down

				if (isAngleBigger(old_x[down], old_y[down],world_x[i], world_y[i])):
					angle_offset = (i - down) / (N - 1.0) * angle_span + start_angle
					min_dist_down = np.sin(np.deg2rad(angle_offset)) * world_norm
					if (min_dist_down > best_dist):
						down_stopped = True
						continue

					if (old_x[down]**2 + old_y[down]**2 > world_norm):
						down = down_in[down][0]
					else:
						down = down_out[down][0]
				else:
					down -= 1

				if (down < 0 or down >= N): down_stopped = True

		#best + 1 is closer
		if (best == 0 or (best != (N-1) and ((old_x[best + 1] - world_x[i])**2 + (old_y[best + 1] - world_y[i]) > (old_x[best - 1] - world_x[i])**2 + (old_y[best - 1] - world_y[i])))):
			C[i,1] = best
			C[i,2] = best + 1
		else:
			C[i,1] = best - 1
			C[i,2] = best

		last_best = best

	return C

# use radian
def rot(rad):
	return np.array([[np.cos(rad), -np.sin(rad)], [np.sin(rad), np.cos(rad)]])

# use theta
def rot_deg(theta):
	rad = np.deg2rad(theta)
	return np.array([[np.cos(rad), -np.sin(rad)], [np.sin(rad), np.cos(rad)]])

def getDownArrays(x, y, N):

  downOut = np.empty([N, 1])
  downIn = np.empty([N, 1])

  outValueStack = []
  outIndexStack = []
  inValueStack = []
  inIndexStack = []
  for i in range(0, N, 1):

    r = x[i]**2 + y[i]**2

    lastOutIndex = -1
    lastOutValue = sys.float_info.max
    lastInIndex = -1
    lastInValue = 0

    while (len(outIndexStack) > 0):
      lastOutIndex = outIndexStack.pop()
      lastOutValue = outValueStack.pop()
      if (lastOutValue > r):
        break

    while (len(inIndexStack) > 0):
      lastInIndex = inIndexStack.pop()
      lastInValue = inValueStack.pop()
      if (lastInValue < r):
        break

    downOut[i] = lastOutIndex
    downIn[i] = lastInIndex

    if (lastOutValue > r):
      outIndexStack.append(lastOutIndex)
      outValueStack.append(lastOutValue)
    outIndexStack.append(i)
    outValueStack.append(r)

    if (lastInValue < r):
      inIndexStack.append(lastInIndex)
      inValueStack.append(lastInValue)
    inIndexStack.append(i)
    inValueStack.append(r)

  return downOut, downIn

def getUpArrays(x, y, N):
  upOut = np.empty([N, 1])
  upIn = np.empty([N, 1])

  outValueStack = []
  outIndexStack = []
  inValueStack = []
  inIndexStack = []
  for i in range(N-1, -1, -1):

    r = x[i]**2 + y[i]**2

    lastOutIndex = -1
    lastOutValue = sys.float_info.max
    lastInIndex = -1
    lastInValue = 0

    while (len(outIndexStack) > 0):
      lastOutIndex = outIndexStack.pop()
      lastOutValue = outValueStack.pop()
      if (lastOutValue > r):
        break

    while (len(inIndexStack) > 0):
      lastInIndex = inIndexStack.pop()
      lastInValue = inValueStack.pop()
      if (lastInValue < r):
        break

    upOut[i] = lastOutIndex
    upIn[i] = lastInIndex

    if (lastOutValue > r):
      outIndexStack.append(lastOutIndex)
      outValueStack.append(lastOutValue)
    outIndexStack.append(i)
    outValueStack.append(r)

    if (lastInValue < r):
      inIndexStack.append(lastInIndex)
      inValueStack.append(lastInValue)
    inIndexStack.append(i)
    inValueStack.append(r)

  return upOut, upIn

def dist(new_point):
  return np.sqrt(new_point[0]**2 + new_point[1]**2)

def isAngleBigger(x1, y1, x2, y2):
  # x1 = y1_in
  # x2 = y2_in
  # y1 = -x1_in
  # y2 = -x2_in
  # Returns whether angle 1 is to the right of (further up for indices) angle 2
  # if (x1 == 0): return (x1 > x2)
  # if (x1 > 0 and x2 < 0): return True
  # if (x1 < 0 and x2 > 0): return False
  # if (x1 > 0 and x2 > 0):
  #   if (y1 >= 0 and y2 <= 0): return False
  #   if (y1 <= 0 and y2 >= 0): return True
  #   else:
  #     return (y2/x2 > y1/x1)
  # else:
  #   # Xs negative
  #   if (y1 <= 0 and y2 >= 0): return False
  #   if (y1 >= 0 and y2 <= 0): return True
  #   else:
  #     return (y1/x1 > y2/x2)

  if (y1 * y2 < 0):
  	return (y1 > y2)
  else:
  	calc = (x1 - x2) * y2 - x2 * (y1 - y2)
  	return (calc < 0)


# --------------------- HELPER FUNCTIONS RELATED TO GET Q ------------------------ #
def get_q(p1,p2,C):

	M = np.zeros((4,4))
	g = np.zeros((4,1))
	x = np.zeros((4,1))
	W = np.zeros((4,4))
	# pdb.set_trace()
	for i in range(len(C)):

		M_k = np.array([[1 , 0, p1[i,0], -p1[i,1] ], \
			[ 0 , 1, p1[i,1], p1[i,0] ]])

		# M_k = np.array([1, 0 p1 rot()])

		n_k = np.matmul(normalize(p2[C[i,1],:] - p2[C[i,2],:]).reshape(1,2),rot(3.14159/2.)).reshape(2,1)

		C_k = np.matmul(n_k,n_k.T)

		M += np.matmul(np.matmul(M_k.T,C_k),M_k)

		Pi_k = p2[C[i,1],:].reshape(2,1)

		g += -2*np.matmul(Pi_k.T , np.matmul(C_k,M_k)).T

	W[[2,3],[2,3]] = 1
	W = np.matrix(W)
	A = np.matrix(2*M[0:2,0:2])
	B = np.matrix(2*M[0:2,2:4])
	D = np.matrix(2*M[2:4,2:4])
	g = np.matrix(g)
	M = np.matrix(M)

	S = D - (B.T*(A.I)*B)

	Sa = S.I * np.linalg.det(S)

	p_lambda = np.array([4., (2.*S[0,0]+2.*S[1,1]), np.linalg.det(S) ]);

	rhs = getRHS(A, B, Sa, g)

	roots = np.roots(rhs - np.convolve(p_lambda,p_lambda))

	lam = np.real(np.max(roots[np.isreal(roots)]))

	fx = lambda l: -((2*M + 2*l*W).I).T*g

	x = fx(lam)

	#theta = np.arctan(x[3,0]/x[2,0]) # theta is in radian
	theta = np.arctan2(x[3,0], x[2,0])

	# print "error: ",(g.T*((2*M + 2*lam*W).I)*W*((2*M + 2*lam*W).I).T*g)[0,0] - 1

	return np.array([x[0,0],x[1,0],theta]).T

# normalize vector
def normalize(v):
    norm = np.linalg.norm(v)
    if norm == 0:
       return v
    return v / norm

#TODO: what does this do???
def getRHS(A,B,Sa,g):

	g1 = g[0:2]; g2=g[2:4];

	p7 = np.array([0,0,( g1.T*((A.I)*B*  4    *B.T*(A.I))*g1 + 2*g1.T*(-(A.I)*B*  4   )*g2  + g2.T*( 4   )*g2)[0,0], \
		(g1.T*((A.I)*B*  4*Sa *B.T*(A.I))*g1 + 2*g1.T*(-(A.I)*B*  4*Sa)*g2  + g2.T*( 4*Sa)*g2)[0,0], \
		(g1.T*((A.I)*B* Sa*Sa *B.T*(A.I))*g1 + 2*g1.T*(-(A.I)*B* Sa*Sa)*g2 + g2.T*(Sa*Sa)*g2)])

   	return p7


# Boilerplate code to start this ROS node.
if __name__ == '__main__':
  rospy.init_node('scan_matcher', anonymous = True)
  rospy.Subscriber("scan", LaserScan, scan_callback)
  rospy.Subscriber("vesc/odom", Odometry, odom_callback)
  real_time_estimated_location()
  rospy.spin()
