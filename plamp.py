import sys
import s3g
import serial
import time
import commands


xLength = 227
yLength = 148
zLength = 150

xSPM = 94
ySPM = 94 
zSPM = 400
    
    
def home(s):


    
    feedrate = 500
    timeout = 2
    print "max xy"
    try:
        p = s.FindAxesMaximums(['x', 'y'], feedrate, timeout)
        print "packet", p
    except Exception as e:
        print "exception:", e
        
    
    print "min z"
    s.FindAxesMinimums(['z'], feedrate, timeout)
    print "set pos"
    s.SetPosition([xLength*xSPM/2, yLength*ySPM/2, 0])
    print "done!"

def goMiddle(s):
    print "go middle"
    feedrate = 500
    s.QueuePoint([0, 0, 0], feedrate)


def old_stuff(s):
    home(s)
    goMiddle(s)
    while not s.IsFinished():
        time.sleep(.5)
        print "moving"
    print "done moving"
    curPoint = s.GetPosition()[0]
    s.QueuePoint([curPoint[0], curPoint[1], 5*zSPM], 500)
    curPoint[2] = 5*zSPM
    s.SetToolheadTemperature(0, 220)
    s.SetPlatformTemperature(0, 100)
    while not s.IsToolReady(0) or not s.IsPlatformReady(0):
        time.sleep(10)
        print "heating up extruder: %i platform: %i"%(s.GetToolheadTemperature(0), s.GetPlatformTemperature(0))
    print "Done heating"    


def thisHasWorked():
    s = s3g.s3g()
    s.file = serial.Serial('/dev/tty.usbmodemfd121', '115200', timeout=1)
    
    old_stuff(s)
    
    s.SetPosition([0, 0, 0])
    feedrate = 300
    
    x = 100
    y = 100
    z = 100
     
    s.QueuePoint([x*xSPM, y*ySPM, z*zSPM], feedrate)
    while not s.IsFinished():
        time.sleep(.5)
        print "moving"
    print "done moving"
    
    s.ToggleAxes(['x','y','z'], False)             
                 
    s.file.close()    

class Robot(object):
    
    def __init__(self, portName, axes): 
        self.s3g = s3g.s3g()
        self.s3g.file = serial.Serial(portName, '115200', timeout=1)
        self.axes = axes
        print "Robot", portName, axes
        self.s3g.Init()
        
        tool_index = 0
        print "toolhead 0 temp:",  self.s3g.GetToolheadTemperature(tool_index)
        print "toolhead 0 ready:", self.s3g.IsToolReady(tool_index)
        print "platform 0 temp:",  self.s3g.GetPlatformTemperature(tool_index)
        #print "Comm", self.s3g.GetCommunicationStats()
        #print "Motherboard", self.s3g.GetMotherboardStatus()
    
    def goto(self, pos, feedrate, disableMotors = True):
        x_steps = pos[0]*self.axes[0]
        y_steps = pos[1]*self.axes[1]
        z_steps = pos[2]*self.axes[2] 
        print "GOTO: ", [x_steps, y_steps, z_steps]
        self.s3g.QueuePoint([x_steps, y_steps, z_steps], feedrate)
        if disableMotors:
            self.s3g.ToggleAxes(['x','y','z'], False) 
        
    def setPos(self, pos):
        x_steps = pos[0]*self.axes[0]
        y_steps = pos[1]*self.axes[1]
        z_steps = pos[2]*self.axes[2] 
        print "Set Position: " , [x_steps, y_steps, z_steps]
        self.s3g.SetPosition([x_steps, y_steps, z_steps])
    
    def getPos(self):
        pos = self.s3g.GetExtendedPosition()
        
        print "GET POS: ", pos[0]       
 
        x_steps = pos[0][0]
        x_steps_per_units =self.axes[0]
        
        x = (1.0 * x_steps) / x_steps_per_units
        y = (1.0 * pos[0][1])/self.axes[1]
        z = (1.0 * pos[0][2])/self.axes[2]
        stops = pos[1]
        stop0 = False
        if stops == 4 or stops == 36:
            stop0 = True
        stop1 = False
        if stops == 32 or stops == 36:
            stop1 = True
        
        r = [x, y, z, stop0, stop1 ]
        return r
        
    def close(self):
        self.s3g.file.close()  
    
    def wait(self):
        while not self.s3g.IsFinished():
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(.1)
        print "."

class ClickNSlide (Robot):
    
    def __init__(self, port):
        axes = [100, 1, 1]
        super(ClickNSlide,self).__init__(port, axes)
    

if __name__ == "__main__":
    
    axes = [94, 94, 400]
    robot = Robot('/dev/tty.usbmodemfa131', axes)
    robot.setPos([0, 0, 0])
    
    #old_stuff(robot.s3g)
    #robot = ClickNSlide('/dev/tty.usbmodemfd121')
    
    #robot.setPos([0,0,0])
    #robot.wait()
    #robot.goto([20, 0000, 00], 500, False)
    #robot.goto([0, 0000, 00], 500, False)
    #robot.wait()
    

    #robot.setPos([0,0,0])
    #robot.wait()
#    robot.wait()
    print(robot.getPos())
    
    pos = -50
    for i in range(0,10) :
        pos = -pos
        print("current pos",robot.getPos())
        print "going to", pos
        robot.wait()
        robot.goto([pos,  0000, 00], 100,  True)
        robot.wait()
        
    
    robot.close()
    
    # 36 = both 
    # 32 = single
    # 4 = x single
    
#    print "HO!"
#    s = s3g.s3g()
#    s.file = serial.Serial('/dev/tty.usbmodemfd121', '115200', timeout=1)
#    s.SetPosition([0, 0, 0])
#    feedrate = 300
#    
#    x = 100
#    y = 100
#    z = 100
#    
#    xSPM = 94
#    ySPM = 94
#    zSPM = 94 
#    
#    s.QueuePoint([x*xSPM, y*ySPM, z*zSPM], feedrate)
#    while not s.IsFinished():
#        time.sleep(.5)
#        print "moving"
#    print "done moving"
#    
#    s.ToggleAxes(['x','y','z'], False)             
#                 
#    s.file.close()

    

