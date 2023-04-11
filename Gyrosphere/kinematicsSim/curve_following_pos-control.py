from cProfile import label
import numpy as np
import pybullet as p
import controlpy
import scipy
import pybullet_data
import matplotlib.pyplot as plt
import time
import os


def Calc_components(desired_angVel):                    # takes the desired angle of steering and returns the
    R_matrix = np.array([[     2.,      0., 0.353627],  # driving torque of each wheel in form
                         [    -1.,  1.7319, 0.353521],  # np.array([[t1],[t2],[t3]]) (column matrix)
                         [    -1., -1.7319, 0.353521]])
    components = np.dot(R_matrix,desired_angVel)
    return components

M = 1.0
I = 0.6666666666667
R = 1.0

A = np.array([[    0.,   0.,   1.,  0.],
              [    0.,   0.,   0.,  1.],
              [    0.,   0.,   0.,  0.],
              [    0.,   0.,   0.,  0.]])   

B = R/I*np.array([[    0.,      0.,      0.],
                  [    0.,      0.,      0.],
                  [0.3333, -0.1667,  0.1667],
                  [    0.,  0.2887, -0.2887]])     

class LQR_control:

    def __init__(self):

        self.Q = np.array([[1000.,   0.,   0.,   0.],
                           [   0.,1000.,   0.,   0.],
                           [   0.,   0.,   0.,   0.],
                           [   0.,   0.,   0.,   0.]])
        self.R = 0.5*np.array([[1000.,    0.,   0.],
                               [   0., 1000.,   0.],
                               [   0.,    0.,1000.]])
        self.K,self.S,self.e = controlpy.synthesis.controller_lqr(A,B,self.Q,self.R)

    def callback(self,data,target):
        X = data-target

        u_t=-np.matmul(self.K,X)
        X_dot = (np.matmul(A,X)+np.matmul(B,u_t))
        
        return X_dot

    def callback_q(self,data):
        q = data.data
        self.Q = np.array([[ q,   0],[  0, 10*q]])
        self.K,self.S,self.e = controlpy.synthesis.controller_lqr(A,B,self.Q,self.R)
        
    def callback_r(self,data):
        r = data.data
        self.R = r
        self.K,self.S,self.e = controlpy.synthesis.controller_lqr(A,B,self.Q,self.R)

def synthesizeData(robot):

    pos = p.getBasePositionAndOrientation(robot)[0]
    vel = p.getBaseVelocity(robot)[0]

    data = np.array([[pos[0]],
                     [pos[1]],
                     [vel[0]],
                     [vel[1]]])

    return data         

if __name__ == "__main__":

    current_dir = os.path.dirname(__file__)   ##just to get the directory

    physics_client = p.connect(p.GUI)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0,0,-9.8)

    p.loadURDF("plane.urdf")
    bot = p.loadURDF(current_dir+"/urdfs/outershell.urdf",[0,0.0,2.5])

    my_controller = LQR_control()
    print(my_controller.K)
    print(my_controller.e)
    trq_min = 100
    trq_max = 0
    
    bot_positions_x = list()
    bot_positions_y = list()
    desired_pos_x = list()
    desired_pos_y = list()

    target_x,target_y = 0,0
    flag = False
    flag2 = False
    i = 0

    def target_function(x):      # Return the equation of desired curve, passing through origin
        return 2*np.sin(x)

    while True:
        
        keys = p.getKeyboardEvents()
        for k,v in keys.items():
            if(k == p.B3G_RETURN and (v & p.KEY_IS_DOWN)): flag = True
            if(k == ord('p') and (v & p.KEY_IS_DOWN)): flag2 = True
        if(flag): break    
        if(not flag2): continue
        data = synthesizeData(bot)
        desired_target = [[target_x],
                          [target_y],
                          [      0.],
                          [      0.]]        
        x_dot = my_controller.callback(
                data,
                target = desired_target
            ).ravel()

        disp = np.sqrt((data-desired_target).ravel()[0]**2+(data-desired_target).ravel()[1]**2) #keeping track of displacement from current desired position
        
        if(disp < 0.1):
            target_x += 0.5                         # updating the next state
            target_y = target_function(target_x)    # y as given function of x

        if(np.floor((10*time.time()))%5 == 0):  # For plotting in matplotlib
            bot_positions_x.append(data[0][0])
            bot_positions_y.append(data[1][0])    
            desired_pos_x.append(target_x)
            desired_pos_y.append(target_y)        
        
        trq_y = I/R*x_dot[2]
        trq_x = I/R*x_dot[3]
        trq = np.sqrt(trq_x**2+trq_y**2)

        desired_torque = np.array([[-trq_x],
                                   [ trq_y],
                                   [    0.]])

        t1,t2,t3 = Calc_components(desired_torque).ravel() #t1,t2,t3 are magnitudes of torques generated by motors
       
        T1 = np.array([ 0.3333*t1,      0*t1,0.9428*t1]) #Torque generated by motor 1 in vector form
        T2 = np.array([-0.1667*t2, 0.2887*t2,0.9428*t2]) #Torque generated by motor 2 in vector form
        T3 = np.array([-0.1667*t3,-0.2887*t3,0.9428*t3]) #Torque generated by motor 3 in vector form
        
        p.applyExternalTorque(bot,-1,T1,p.WORLD_FRAME) #Applying Torque generated by motor 1
        p.applyExternalTorque(bot,-1,T2,p.WORLD_FRAME) #Applying Torque generated by motor 2
        p.applyExternalTorque(bot,-1,T3,p.WORLD_FRAME) #Applying Torque generated by motor 3
        
        #print("data: {} trq: {}".format(data,trq))


        if(trq<trq_min): trq_min = trq
        if(trq>trq_max): trq_max = trq

        print("current torque: {} | max_torque: {} | min_torque: {}".format(trq,trq_max,trq_min))
        
        p.stepSimulation()
        time.sleep(0.001)
    
    plt.plot(bot_positions_x,bot_positions_y,label = 'Path followed by bot')
    plt.plot(desired_pos_x,desired_pos_y, label = 'desired path')
    plt.legend()
    plt.show()
    p.disconnect()