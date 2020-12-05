#!python3

import irsdk
import time


class PitInfo:
    car_idx = 0
    pit_lane_time: 0
    pit_stop_time: 0
    
    lane_enter_time = 0,    
    pit_stop_start_time = 0;
    


class DataStore:
    """
    This holds data retrieved/computed on every step. 
    TODO: The data sent to the server is extracted from here
    """
    car_idx_position = []
    car_idx_lap_dist_pct = []
    car_idx_lap = []
    car_idx_on_pitroad = []
    session_time = 0
    work_pit_stop = {}

# this is our State class, with some helpful variables
class State:
    ir_connected = False
    last_car_setup_tick = -1
    last_data = DataStore() # this holds my required data of the previous tick
    last_publish = -1

# here we check if we are connected to iracing
# so we can retrieve some data
def check_iracing():
    if state.ir_connected and not (ir.is_initialized and ir.is_connected):
        state.ir_connected = False
        # don't forget to reset your State variables
        state.last_car_setup_tick = -1
        state.last_publish = -1
        # we are shutting down ir library (clearing all internal variables)
        ir.shutdown()
        print('irsdk disconnected')
    elif not state.ir_connected and ir.startup() and ir.is_initialized and ir.is_connected:
        state.ir_connected = True
        print('irsdk connected')
        

def save_step_data(data:DataStore):
    data.session_time = current_ir_session_time()
    data.car_idx_lap = ir['CarIdxLap'] 
    data.car_idx_lap_dist_pct = ir['CarIdxLapDistPct']
    data.car_idx_on_pitroad = ir['CarIdxOnPitRoad']

def log_current_info():
    print(ir['CarIdxLapDistPct'][0:6])
    

def handle_pitstops(data:DataStore):
    """
    Pit stops are measured like this:
    - CarIdxOnPitRoad changed 
    - from false to true: start pit lane timer
    - from true to false: end pit lane time
    - if true and "car did not move": start pit stop timer
    - if true and "car moved": end pit stop timer
      
    """
    
    pit = ir['CarIdxOnPitRoad']
    if (len(pit) != len(data.car_idx_on_pitroad)):
        return
    # this is useful for debugging sessions
    if (current_ir_session_time() == data.session_time):
        return
    for i in range(0, len(pit)):
        if (pit[i] and not data.car_idx_on_pitroad[i]):
            print(f"Car {i} entered pit")
            work = PitInfo()
            work.car_idx = i
            work.lane_enter_time = current_ir_session_time()
            data.work_pit_stop[i] = work

        if (pit[i] and data.car_idx_on_pitroad[i] and i in data.work_pit_stop.keys()):
            pit_info = data.work_pit_stop[i]
            track_length = 3900 # TODO: get this from weekend settings - this ist just ok for Watkins Glen Cup
            moveDistPct = abs(ir['CarIdxLapDistPct'][i]-data.car_idx_lap_dist_pct[i])            
            speed = moveDistPct*track_length/(current_ir_session_time() - data.session_time) * 3.6
            # print(f"moveDist: {moveDistPct} speed: {speed}")
            if (pit_info.pit_stop_start_time == 0 and  speed < 1):
                print(f"Car {i} stopped at pit")
                pit_info.pit_stop_start_time = current_ir_session_time()
            
            if (pit_info.pit_stop_start_time != 0 and speed > 5):
                print(f"Car {i} about to leave pit")            
                pit_info.pit_stop_time= current_ir_session_time() - pit_info.pit_stop_start_time
                print(f"Car {i} pit stop duration: {pit_info.pit_stop_time}")
                pit_info.pit_stop_start_time = 0 # reset the pit stop timer



        if (not pit[i] and data.car_idx_on_pitroad[i] and i in data.work_pit_stop.keys()):
            pit_info = data.work_pit_stop[i]
            pit_info.lane = current_ir_session_time() - pit_info.lane_enter_time 
            print(f"Car {i} left pit lane: duration: {pit_info.lane}")

def current_ir_session_time():
    return ir['SessionTime'];

def process_changes_to_last_run(data:DataStore):
    handle_pitstops(data)    

# our main loop, where we retrieve data
# and do something useful with it
def loop():
    # on each tick we freeze buffer with live telemetry
    # it is optional, but useful if you use vars like CarIdxXXX
    # this way you will have consistent data from those vars inside one tick
    # because sometimes while you retrieve one CarIdxXXX variable
    # another one in next line of code could change
    # to the next iracing internal tick_count
    # and you will get incosistent data
    ir.freeze_var_buffer_latest()

    # retrieve live telemetry data
    # check here for list of available variables
    # https://github.com/kutu/pyirsdk/blob/master/vars.txt
    # this is not full list, because some cars has additional
    # specific variables, like break bias, wings adjustment, etc

    t = ir['SessionTime']
    process_changes_to_last_run(state.last_data)
    if ((t - state.last_publish) > 1):
        # this is the point where we want to send the data to the server. 
        # By now we just log something....
        log_current_info()
        print('session time:', t)
        state.last_publish = t

    save_step_data(state.last_data)

    # and just as an example
    # you can send commands to iracing
    # like switch cameras, rewind in replay mode, send chat and pit commands, etc
    # check pyirsdk.py library to see what commands are available
    # https://github.com/kutu/pyirsdk/blob/master/irsdk.py#L134 (class BroadcastMsg)
    # when you run this script, camera will be switched to P1
    # and very first camera in list of cameras in iracing
    # while script is running, change camera by yourself in iracing
    # and notice how this code changes it back every 1 sec
    # ir.cam_switch_pos(0, 1)

if __name__ == '__main__':
    # initializing ir and state
    ir = irsdk.IRSDK()
    state = State()

    try:
        # infinite loop
        while True:
            # check if we are connected to iracing
            check_iracing()
            # if we are, then process data
            if state.ir_connected:
                loop()
            # sleep for 1 second
            # maximum you can use is 1/60
            # cause iracing updates data with 60 fps
            time.sleep(1/60)
    except KeyboardInterrupt:
        # press ctrl+c to exit
        pass
